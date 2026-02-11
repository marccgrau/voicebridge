"""Direct-call guidance processors without LLM tool-callback loops."""

import asyncio
import json
import re
import time
from contextlib import suppress
from pathlib import Path
from typing import Any

from pipecat.frames.frames import Frame, TranscriptionFrame
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor

from src.frames import ProcessIllustrationFrame, SuggestionFrame
from src.services.process import ProcessCatalogIndexService, ProcessMatch
from src.services.process.service import ProcessDefinition
from src.utils.logging import get_session_logger

_SUGGESTION_TYPES = {"response", "question", "action", "escalation"}
_JSON_BLOCK_PATTERN = re.compile(r"(\{.*\}|\[.*\])", re.DOTALL)


def _preview_text(text: str, limit: int = 180) -> str:
    """Compact and truncate text for structured logs."""
    compact = " ".join(text.split())
    if len(compact) <= limit:
        return compact
    return f"{compact[: limit - 3]}..."


def _parse_json_payload(raw_text: str) -> dict[str, Any] | list[Any] | None:
    """Parse a JSON object/list from an LLM response string."""
    text = raw_text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:].strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = _JSON_BLOCK_PATTERN.search(raw_text)
        if not match:
            return None
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            return None


class ProcessContextResolverProcessor(FrameProcessor):
    """Resolves process context directly from transcript turns."""

    def __init__(
        self,
        session_id: str,
        llm: Any,
        process_content_path: str,
        llm_timeout: float,
        shortlist_k: int,
        confidence_threshold: float,
        margin_threshold: float,
        cache_size: int,
        history_limit: int = 24,
        min_utterances_before_detection: int = 3,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.session_id = session_id
        self._llm = llm
        self._llm_timeout = llm_timeout
        self._catalog = ProcessCatalogIndexService(shortlist_k=shortlist_k, cache_size=cache_size)
        self._process_path = Path(process_content_path)
        self._confidence_threshold = confidence_threshold
        self._margin_threshold = margin_threshold
        self._history_limit = max(6, history_limit)
        self._min_utterances_before_detection = max(1, min_utterances_before_detection)
        self._process_index: dict[str, Any] = {}
        self._index_loaded = False
        self._conversation_buffer: list[str] = []
        self._utterance_count = 0
        self._detected_process: ProcessDefinition | None = None
        self._current_step = 0
        self._llm_call_count = 0
        self._disambiguation_task: asyncio.Task | None = None
        self._detection_attempt_id = 0
        self.logger = get_session_logger(__name__, session_id)

    async def stop(self) -> None:
        """Cancel in-flight disambiguation task."""
        if self._disambiguation_task and not self._disambiguation_task.done():
            self._disambiguation_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._disambiguation_task

    async def process_frame(self, frame: Frame, direction: FrameDirection) -> None:
        await super().process_frame(frame, direction)

        if isinstance(frame, TranscriptionFrame):
            speaker = getattr(frame, "user_id", "unknown")
            line = f"[{speaker}]: {frame.text}"
            self._conversation_buffer.append(line)
            if len(self._conversation_buffer) > self._history_limit:
                self._conversation_buffer = self._conversation_buffer[-self._history_limit :]
            self._utterance_count += 1

            if speaker == "customer":
                await self._ensure_index_loaded()

                if (
                    not self._detected_process
                    and self._utterance_count >= self._min_utterances_before_detection
                ):
                    self.logger.debug(
                        "Process detection check (utterances=%d, history_lines=%d)",
                        self._utterance_count,
                        len(self._conversation_buffer),
                    )
                    await self._select_process(direction)

                elif self._detected_process:
                    next_step = self._catalog.estimate_step_index(
                        process=self._detected_process,
                        conversation_buffer=self._conversation_buffer,
                        current_step=self._current_step,
                    )
                    if next_step != self._current_step:
                        previous_step = self._current_step
                        self._current_step = next_step
                        step_label = self._detected_process.steps[self._current_step].label
                        self.logger.info(
                            "Process step advanced: %s step %d -> %d (%s)",
                            self._detected_process.process_key,
                            previous_step + 1,
                            self._current_step + 1,
                            step_label,
                        )
                        await self.push_frame(
                            self._build_process_frame(self._detected_process, self._current_step),
                            direction,
                        )

        await self.push_frame(frame, direction)

    async def _ensure_index_loaded(self) -> None:
        if self._index_loaded:
            return
        self._process_index = await self._catalog.load_index(self._process_path, self.logger)
        self._index_loaded = True
        self.logger.info("Loaded process metadata index (%d processes)", len(self._process_index))

    async def _select_process(self, direction: FrameDirection) -> None:
        matches = self._catalog.shortlist(self._conversation_buffer, self._process_index)
        if not matches:
            self.logger.debug("Process shortlist empty")
            return

        top_match = matches[0]
        second_score = matches[1].score if len(matches) > 1 else 0.0
        margin = top_match.score - second_score
        query_text = " ".join(self._conversation_buffer[-6:])
        top_confidence = self._catalog.confidence_from_score(top_match.score, query_text)
        self.logger.info(
            "Process shortlist top=%s score=%.2f confidence=%.2f margin=%.2f candidates=%d",
            top_match.entry.process_key,
            top_match.score,
            top_confidence,
            margin,
            len(matches),
        )

        # Fast path: metadata confidence is high enough, no LLM needed
        if top_confidence >= self._confidence_threshold and margin >= self._margin_threshold:
            self.logger.info(
                "Process selected from metadata without LLM (threshold=%.2f, margin=%.2f)",
                self._confidence_threshold,
                self._margin_threshold,
            )
            selected = self._catalog.load_process_definition(top_match.entry, self.logger)
            if selected:
                self._detected_process = selected
                self._current_step = 0
                self.logger.info("Process selected: %s (%s)", selected.process_key, selected.name)
                await self.push_frame(self._build_process_frame(selected, 0), direction)
            return

        # Slow path: schedule LLM disambiguation as background task
        await self._schedule_disambiguation(matches, top_confidence, top_match, direction)

    async def _schedule_disambiguation(
        self,
        matches: list[ProcessMatch],
        top_confidence: float,
        top_match: ProcessMatch,
        direction: FrameDirection,
    ) -> None:
        """Cancel any stale disambiguation and schedule a new background task."""
        if self._disambiguation_task and not self._disambiguation_task.done():
            self.logger.info("Cancelling stale disambiguation task")
            self._disambiguation_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._disambiguation_task

        self._detection_attempt_id += 1
        attempt_id = self._detection_attempt_id
        task = asyncio.create_task(
            self._run_disambiguation_task(attempt_id, matches, top_confidence, top_match, direction)
        )
        self._disambiguation_task = task
        self.logger.debug("Disambiguation task scheduled (attempt_id=%d)", attempt_id)

    async def _run_disambiguation_task(
        self,
        attempt_id: int,
        matches: list[ProcessMatch],
        top_confidence: float,
        top_match: ProcessMatch,
        direction: FrameDirection,
    ) -> None:
        """Background coroutine that runs LLM disambiguation and pushes result."""
        if not self._llm or len(matches) < 2:
            return

        candidates = "\n".join(
            f"- {match.entry.process_key}: {match.entry.name} (intents: {', '.join(match.entry.intents)})"
            for match in matches
        )
        conversation_window = "\n".join(self._conversation_buffer[-6:])
        context = LLMContext(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Select the best matching process from the candidate list. "
                        "Return strict JSON with keys process_key and confidence (0-1)."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Conversation:\n{conversation_window}\n\nCandidates:\n{candidates}\n\n"
                        "Return only JSON."
                    ),
                },
            ]
        )
        self._llm_call_count += 1
        call_id = self._llm_call_count
        call_started = time.perf_counter()
        self.logger.info(
            "Process disambiguation LLM call started (call_id=%d, attempt_id=%d, candidates=%d, window_preview=%s)",
            call_id,
            attempt_id,
            len(matches),
            _preview_text(conversation_window),
        )

        selected: ProcessDefinition | None = None
        try:
            raw = await asyncio.wait_for(
                self._llm.run_inference(context),
                timeout=self._llm_timeout,
            )
            call_latency_ms = (time.perf_counter() - call_started) * 1000
            self.logger.info(
                "Process disambiguation LLM call completed (call_id=%d, latency_ms=%.1f)",
                call_id,
                call_latency_ms,
            )
            selected = self._parse_disambiguation_result(raw, call_id)
        except TimeoutError:
            call_latency_ms = (time.perf_counter() - call_started) * 1000
            self.logger.warning(
                "Process disambiguation timed out (call_id=%d, latency_ms=%.1f)",
                call_id,
                call_latency_ms,
            )
        except asyncio.CancelledError:
            self.logger.info(
                "Disambiguation task cancelled (call_id=%d, attempt_id=%d)", call_id, attempt_id
            )
            raise
        except Exception as e:
            call_latency_ms = (time.perf_counter() - call_started) * 1000
            self.logger.warning(
                "Process disambiguation failed (call_id=%d, latency_ms=%.1f): %s",
                call_id,
                call_latency_ms,
                e,
            )

        # Fallback to top metadata candidate if LLM didn't resolve
        if not selected and top_confidence >= self._confidence_threshold:
            self.logger.info(
                "Process fallback to top metadata candidate after LLM: %s",
                top_match.entry.process_key,
            )
            selected = self._catalog.load_process_definition(top_match.entry, self.logger)

        if not selected:
            self.logger.info("Process remains unresolved after shortlist + LLM")
            return

        # Stale check: another attempt may have started while we were waiting
        if attempt_id != self._detection_attempt_id:
            self.logger.info(
                "Dropping stale disambiguation result (attempt_id=%d, current=%d)",
                attempt_id,
                self._detection_attempt_id,
            )
            return

        # Another path may have already resolved the process
        if self._detected_process:
            self.logger.info(
                "Process already detected, ignoring disambiguation result (attempt_id=%d)",
                attempt_id,
            )
            return

        self._detected_process = selected
        self._current_step = 0
        self.logger.info("Process selected: %s (%s)", selected.process_key, selected.name)
        await self.push_frame(self._build_process_frame(selected, 0), direction)

    def _parse_disambiguation_result(self, raw: Any, call_id: int) -> ProcessDefinition | None:
        """Parse LLM disambiguation response into a ProcessDefinition."""
        payload = _parse_json_payload(raw if isinstance(raw, str) else str(raw))
        if not isinstance(payload, dict):
            self.logger.warning(
                "Process disambiguation returned non-dict JSON (call_id=%d)", call_id
            )
            return None

        process_key = payload.get("process_key")
        confidence = payload.get("confidence")
        if not isinstance(process_key, str):
            self.logger.warning("Process disambiguation missing process_key (call_id=%d)", call_id)
            return None
        if not isinstance(confidence, int | float):
            self.logger.warning("Process disambiguation missing confidence (call_id=%d)", call_id)
            return None
        if float(confidence) < self._confidence_threshold:
            self.logger.info(
                "Process disambiguation below confidence threshold (call_id=%d, process_key=%s, confidence=%.2f, threshold=%.2f)",
                call_id,
                process_key,
                float(confidence),
                self._confidence_threshold,
            )
            return None

        entry = self._process_index.get(process_key)
        if not entry:
            self.logger.warning(
                "Process disambiguation returned unknown process_key (call_id=%d, process_key=%s)",
                call_id,
                process_key,
            )
            return None
        self.logger.info(
            "Process disambiguation accepted (call_id=%d, process_key=%s, confidence=%.2f)",
            call_id,
            process_key,
            float(confidence),
        )
        return self._catalog.load_process_definition(entry, self.logger)

    @staticmethod
    def _build_process_frame(
        process: ProcessDefinition, step_index: int
    ) -> ProcessIllustrationFrame:
        return ProcessIllustrationFrame(
            process_key=process.process_key,
            process_name=process.name,
            steps=[
                {
                    "key": step.key,
                    "label": step.label,
                    "status": (
                        "completed"
                        if idx < step_index
                        else "in_progress"
                        if idx == step_index
                        else "pending"
                    ),
                }
                for idx, step in enumerate(process.steps)
            ],
            current_step=step_index,
            content=process.full_content,
        )


class DirectSuggestionProcessor(FrameProcessor):
    """Generates suggestions with one direct LLM call per customer turn."""

    def __init__(
        self,
        session_id: str,
        llm: Any,
        llm_timeout: float,
        conversation_window_size: int = 8,
        history_limit: int | None = None,
        debounce_ms: int = 250,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.session_id = session_id
        self._llm = llm
        self._llm_timeout = llm_timeout
        self._conversation_window_size = max(1, conversation_window_size)
        self._history_limit = max(
            self._conversation_window_size,
            history_limit or (self._conversation_window_size * 4),
        )
        self._debounce_ms = max(0, debounce_ms)
        self._process_context: dict[str, Any] | None = None
        self._conversation_buffer: list[str] = []
        self._latest_turn_id = 0
        self._suggestion_task: asyncio.Task | None = None
        self._task_turn_map: dict[asyncio.Task, int] = {}
        self._turn_start_times: dict[int, float] = {}
        self._llm_call_count = 0
        self.logger = get_session_logger(__name__, session_id)

    async def stop(self) -> None:
        """Cancel in-flight suggestion generation task."""
        if self._suggestion_task and not self._suggestion_task.done():
            self._suggestion_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._suggestion_task

    async def process_frame(self, frame: Frame, direction: FrameDirection) -> None:
        await super().process_frame(frame, direction)

        if isinstance(frame, ProcessIllustrationFrame):
            self._process_context = {
                "process_key": frame.process_key,
                "process_name": frame.process_name,
                "current_step": frame.current_step,
                "steps": frame.steps,
                "content": frame.content,
            }
            self.logger.debug(
                "Updated suggestion process context (process=%s, step=%d)",
                frame.process_key,
                frame.current_step + 1,
            )
        elif isinstance(frame, TranscriptionFrame):
            speaker = getattr(frame, "user_id", "unknown")
            self._conversation_buffer.append(f"[{speaker}]: {frame.text}")
            if len(self._conversation_buffer) > self._history_limit:
                self._conversation_buffer = self._conversation_buffer[-self._history_limit :]
            if speaker == "customer":
                self._latest_turn_id += 1
                self._turn_start_times[self._latest_turn_id] = time.time()
                self.logger.info(
                    "Scheduling suggestion generation for customer turn %d (utterance=%s)",
                    self._latest_turn_id,
                    _preview_text(frame.text),
                )
                await self._schedule_suggestion_task(self._latest_turn_id)

        await self.push_frame(frame, direction)

    async def _schedule_suggestion_task(self, turn_id: int) -> None:
        if self._suggestion_task and not self._suggestion_task.done():
            stale_turn = self._task_turn_map.get(self._suggestion_task)
            self.logger.info(
                "Cancelling in-flight suggestion task (stale_turn=%s, new_turn=%d)",
                stale_turn,
                turn_id,
            )
            self._suggestion_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._suggestion_task

        task = asyncio.create_task(self._run_suggestion_turn(turn_id))
        self._task_turn_map[task] = turn_id
        task.add_done_callback(lambda t: self._task_turn_map.pop(t, None))
        self._suggestion_task = task
        self.logger.debug("Suggestion task scheduled (turn_id=%d)", turn_id)

    async def _run_suggestion_turn(self, turn_id: int) -> None:
        if self._debounce_ms:
            await asyncio.sleep(self._debounce_ms / 1000.0)

        self._llm_call_count += 1
        call_id = self._llm_call_count
        call_started = time.perf_counter()
        process_key = self._process_context.get("process_key") if self._process_context else None
        prompt_context = self._build_prompt_context()
        self.logger.info(
            "Suggestion LLM call started (call_id=%d, turn_id=%d, process_key=%s, window_size=%d)",
            call_id,
            turn_id,
            process_key,
            min(len(self._conversation_buffer), self._conversation_window_size),
        )

        try:
            raw = await asyncio.wait_for(
                self._llm.run_inference(prompt_context),
                timeout=self._llm_timeout,
            )
            call_latency_ms = (time.perf_counter() - call_started) * 1000
            if raw is None:
                self.logger.warning(
                    "Suggestion LLM returned None (call_id=%d, turn_id=%d, latency_ms=%.1f)",
                    call_id,
                    turn_id,
                    call_latency_ms,
                )
                suggestions = []
            else:
                raw_str = raw if isinstance(raw, str) else str(raw)
                self.logger.debug(
                    "Suggestion LLM raw response (call_id=%d): %s",
                    call_id,
                    raw_str[:500],
                )
                suggestions = self._parse_suggestions(raw_str)
            self.logger.info(
                "Suggestion LLM call completed (call_id=%d, turn_id=%d, latency_ms=%.1f, parsed_suggestions=%d)",
                call_id,
                turn_id,
                call_latency_ms,
                len(suggestions),
            )
        except TimeoutError:
            call_latency_ms = (time.perf_counter() - call_started) * 1000
            self.logger.warning(
                "Suggestion generation timed out (call_id=%d, turn_id=%d, latency_ms=%.1f)",
                call_id,
                turn_id,
                call_latency_ms,
            )
            suggestions = []
        except asyncio.CancelledError:
            self.logger.info(
                "Suggestion task cancelled (call_id=%d, turn_id=%d)",
                call_id,
                turn_id,
            )
            raise
        except Exception as e:
            call_latency_ms = (time.perf_counter() - call_started) * 1000
            self.logger.warning(
                "Suggestion generation failed (call_id=%d, turn_id=%d, latency_ms=%.1f): %s",
                call_id,
                turn_id,
                call_latency_ms,
                e,
                exc_info=True,
            )
            suggestions = []

        if turn_id < self._latest_turn_id:
            self.logger.info(
                "Dropping stale suggestions for turn %d (latest=%d)",
                turn_id,
                self._latest_turn_id,
            )
            return

        if not suggestions:
            self.logger.warning(
                "Using fallback suggestions (call_id=%d, turn_id=%d, parsed_suggestions=%d)",
                call_id,
                turn_id,
                len(suggestions),
            )
            suggestions = self._fallback_suggestions()
        else:
            suggestions = suggestions[:3]

        started_at = self._turn_start_times.pop(turn_id, None)
        latency_ms = (time.time() - started_at) * 1000 if started_at else None
        process_key = self._process_context.get("process_key") if self._process_context else None
        tools_used = ["metadata_retrieval", "llm_inference"] if process_key else ["llm_inference"]
        await self.push_frame(
            SuggestionFrame(
                suggestions=suggestions,
                service_type="direct_call",
                latency_ms=latency_ms,
                process_key=process_key,
                tools_used=tools_used,
            )
        )
        self.logger.info(
            "Published suggestions (call_id=%d, turn_id=%d, process_key=%s, latency_ms=%.1f, tools=%s)",
            call_id,
            turn_id,
            process_key,
            latency_ms or 0.0,
            tools_used,
        )

    def _build_prompt_context(self) -> LLMContext:
        conversation_window = "\n".join(
            self._conversation_buffer[-self._conversation_window_size :]
        )
        if not conversation_window:
            conversation_window = "(waiting)"

        process_block = "No process selected yet."
        if self._process_context:
            steps = self._process_context.get("steps", [])
            step_lines = "\n".join(
                f"{idx + 1}. {step.get('label', 'Unknown')} [{step.get('status', 'pending')}]"
                for idx, step in enumerate(steps)
            )
            current_step = int(self._process_context.get("current_step", 0))
            current_label = (
                steps[current_step].get("label", "Unknown")
                if current_step < len(steps)
                else "Unknown"
            )
            content_snippet = str(self._process_context.get("content", ""))[:1200]
            process_block = (
                f"Process: {self._process_context.get('process_name', 'Unknown')}\n"
                f"Current Step: {current_step + 1} ({current_label})\n"
                f"Steps:\n{step_lines}\n\n"
                f"Process Content Snippet:\n{content_snippet}"
            )

        return LLMContext(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an agent guidance assistant. "
                        "Return strict JSON only in the format "
                        '{"suggestions":[{"text":"...","type":"response|question|action|escalation"}, ...]} '
                        "with up to 3 suggestions."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Conversation:\n{conversation_window}\n\n"
                        f"Process Context:\n{process_block}\n\n"
                        "Generate up to 3 concise suggestions."
                    ),
                },
            ]
        )

    def _parse_suggestions(self, raw_text: str) -> list[dict[str, str]]:
        payload = _parse_json_payload(raw_text)
        if payload is None:
            return []

        if isinstance(payload, dict):
            suggestions_payload = payload.get("suggestions")
        elif isinstance(payload, list):
            suggestions_payload = payload
        else:
            return []

        if not isinstance(suggestions_payload, list):
            return []

        normalized: list[dict[str, str]] = []
        for item in suggestions_payload:
            if not isinstance(item, dict):
                continue
            text = item.get("text")
            suggestion_type = item.get("type")
            if not isinstance(text, str) or not text.strip():
                continue
            if suggestion_type not in _SUGGESTION_TYPES:
                suggestion_type = "action"
            normalized.append(
                {
                    "text": text.strip(),
                    "type": suggestion_type,
                }
            )
            if len(normalized) == 3:
                break
        return normalized

    def _fallback_suggestions(self) -> list[dict[str, str]]:
        if self._process_context:
            steps = self._process_context.get("steps", [])
            current_step = int(self._process_context.get("current_step", 0))
            step_label = (
                steps[current_step].get("label", "the current step")
                if current_step < len(steps)
                else "the current step"
            )
            return [
                {
                    "text": f"Acknowledge the concern and align on {step_label}.",
                    "type": "response",
                },
                {
                    "text": f"Ask one targeted question to complete {step_label}.",
                    "type": "question",
                },
                {
                    "text": "Confirm the next action and timeline before closing the turn.",
                    "type": "action",
                },
            ]

        return [
            {
                "text": "Acknowledge the customer concern in one clear sentence.",
                "type": "response",
            },
            {
                "text": "Ask a clarifying question to narrow down the customer intent.",
                "type": "question",
            },
            {
                "text": "Summarize the understood issue and propose the immediate next step.",
                "type": "action",
            },
        ]
