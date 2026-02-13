"""Pipeline processors for VoiceBridge PCC service.

TranscriptWriter — converts STT transcriptions to TranscriptSegmentFrames.
ProcessDetectionProcessor — catalog-based process detection (no LLM).
SuggestionContextBuilder — builds LLM context from transcript + process.
SuggestionOutputProcessor — collects LLM output and emits SuggestionFrames.
VoiceBridgeRTVIObserver — sends custom frames via RTVI to the frontend.
"""

import json
import logging
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pipecat.frames.frames import (
    Frame,
    LLMContextFrame,
    LLMFullResponseEndFrame,
    LLMFullResponseStartFrame,
    LLMTextFrame,
    TranscriptionFrame,
)
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor

from src.frames import ProcessIllustrationFrame, SuggestionFrame, TranscriptSegmentFrame
from src.process_catalog import ProcessCatalogIndexService, ProcessDefinition

logger = logging.getLogger(__name__)

_JSON_BLOCK_PATTERN = re.compile(r"(\{.*\}|\[.*\])", re.DOTALL)
_SUGGESTION_TYPES = {"response", "question", "action", "escalation"}


class TranscriptWriter(FrameProcessor):
    """Convert finalized STT transcriptions to TranscriptSegmentFrames.

    With customer-only audio, all transcriptions are from the customer.
    Stateless — no DB persistence in PCC service.
    """

    def __init__(self, session_id: str, **kwargs):
        super().__init__(**kwargs)
        self.session_id = session_id

    async def process_frame(self, frame: Frame, direction: FrameDirection) -> None:
        await super().process_frame(frame, direction)

        if isinstance(frame, TranscriptionFrame):
            text = (frame.text or "").strip()
            if not text:
                await self.push_frame(frame, direction)
                return

            timestamp = frame.timestamp or datetime.now(UTC).isoformat()
            transcript_frame = TranscriptSegmentFrame(
                session_id=self.session_id,
                speaker="customer",
                text=text,
                timestamp=timestamp,
                is_final=True,
            )
            await self.push_frame(transcript_frame, FrameDirection.DOWNSTREAM)
            return

        await self.push_frame(frame, direction)


class ProcessDetectionProcessor(FrameProcessor):
    """Fast catalog-based process detection without LLM calls.

    Runs sequentially before the ParallelPipeline fork so that
    ProcessIllustrationFrame naturally flows into both branches.
    """

    def __init__(
        self,
        session_id: str,
        process_content_path: str,
        shortlist_k: int = 3,
        confidence_threshold: float = 0.50,
        margin_threshold: float = 0.15,
        cache_size: int = 32,
        min_utterances_before_detection: int = 3,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.session_id = session_id
        self._catalog = ProcessCatalogIndexService(shortlist_k=shortlist_k, cache_size=cache_size)
        self._process_path = Path(process_content_path)
        self._confidence_threshold = confidence_threshold
        self._margin_threshold = margin_threshold
        self._min_utterances_before_detection = max(1, min_utterances_before_detection)
        self._process_index: dict[str, Any] = {}
        self._index_loaded = False
        self._conversation_buffer: list[str] = []
        self._utterance_count = 0
        self._detected_process: ProcessDefinition | None = None
        self._current_step = 0

    async def process_frame(self, frame: Frame, direction: FrameDirection) -> None:
        await super().process_frame(frame, direction)

        if isinstance(frame, TranscriptSegmentFrame):
            line = f"[{frame.speaker}]: {frame.text}"
            self._conversation_buffer.append(line)

            if frame.speaker == "customer":
                self._utterance_count += 1
                await self._ensure_index_loaded()

                if (
                    not self._detected_process
                    and self._utterance_count >= self._min_utterances_before_detection
                ):
                    await self._select_process(direction)
                elif self._detected_process:
                    next_step = self._catalog.estimate_step_index(
                        process=self._detected_process,
                        conversation_buffer=self._conversation_buffer,
                        current_step=self._current_step,
                    )
                    if next_step != self._current_step:
                        self._current_step = next_step
                        await self.push_frame(
                            self._build_process_frame(self._detected_process, self._current_step),
                            direction,
                        )

        await self.push_frame(frame, direction)

    async def _ensure_index_loaded(self) -> None:
        if self._index_loaded:
            return
        self._process_index = await self._catalog.load_index(self._process_path)
        self._index_loaded = True
        logger.info(
            "[session=%s] Loaded process metadata index (%d processes)",
            self.session_id,
            len(self._process_index),
        )

    async def _select_process(self, direction: FrameDirection) -> None:
        matches = self._catalog.shortlist(self._conversation_buffer, self._process_index)
        if not matches:
            return

        top_match = matches[0]
        second_score = matches[1].score if len(matches) > 1 else 0.0
        margin = top_match.score - second_score
        query_text = " ".join(self._conversation_buffer[-6:])
        top_confidence = self._catalog.confidence_from_score(top_match.score, query_text)

        logger.info(
            "[session=%s] Process shortlist top=%s score=%.2f confidence=%.2f margin=%.2f",
            self.session_id,
            top_match.entry.process_key,
            top_match.score,
            top_confidence,
            margin,
        )

        if top_confidence >= self._confidence_threshold and margin >= self._margin_threshold:
            selected = self._catalog.load_process_definition(top_match.entry)
            if selected:
                self._detected_process = selected
                self._current_step = 0
                logger.info(
                    "[session=%s] Process selected: %s (%s)",
                    self.session_id,
                    selected.process_key,
                    selected.name,
                )
                await self.push_frame(self._build_process_frame(selected, 0), direction)

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
                        else "in_progress" if idx == step_index else "pending"
                    ),
                }
                for idx, step in enumerate(process.steps)
            ],
            current_step=step_index,
            content=process.full_content,
        )


class SuggestionContextBuilder(FrameProcessor):
    """Builds LLM context from transcript and process frames.

    Consumes TranscriptSegmentFrame and ProcessIllustrationFrame (the passthrough
    branch handles delivering those to RTVI). On each customer utterance, pushes
    an LLMContextFrame to trigger LLM inference downstream.
    """

    def __init__(self, session_id: str, **kwargs):
        super().__init__(**kwargs)
        self.session_id = session_id
        self._conversation_lines: list[str] = []
        self._process_context: dict[str, Any] | None = None

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
            # Consumed — passthrough branch delivers to RTVI
            return

        if isinstance(frame, TranscriptSegmentFrame):
            self._conversation_lines.append(f"[{frame.speaker}]: {frame.text}")
            if frame.speaker == "customer":
                context = self._build_llm_context()
                await self.push_frame(LLMContextFrame(context=context), direction)
            # Consumed — passthrough branch delivers to RTVI
            return

        # Pass control frames through
        await self.push_frame(frame, direction)

    def _build_llm_context(self) -> LLMContext:
        conversation_text = "\n".join(self._conversation_lines) or "(waiting)"

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
            full_content = str(self._process_context.get("content", ""))
            process_block = (
                f"Process: {self._process_context.get('process_name', 'Unknown')}\n"
                f"Current Step: {current_step + 1} ({current_label})\n"
                f"Steps:\n{step_lines}\n\n"
                f"Full Process Content:\n{full_content}"
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
                        f"Conversation:\n{conversation_text}\n\n"
                        f"Process Context:\n{process_block}\n\n"
                        "Generate up to 3 concise suggestions."
                    ),
                },
            ]
        )


class SuggestionOutputProcessor(FrameProcessor):
    """Collects streamed LLM text and emits SuggestionFrame on completion.

    Collects LLMTextFrame chunks between LLMFullResponseStartFrame and
    LLMFullResponseEndFrame, parses JSON, emits domain frame.
    """

    def __init__(self, session_id: str, **kwargs):
        super().__init__(**kwargs)
        self.session_id = session_id
        self._buffer: list[str] = []
        self._in_response = False

    async def process_frame(self, frame: Frame, direction: FrameDirection) -> None:
        await super().process_frame(frame, direction)

        if isinstance(frame, LLMFullResponseStartFrame):
            self._buffer.clear()
            self._in_response = True
            return

        if isinstance(frame, LLMTextFrame) and self._in_response:
            self._buffer.append(frame.text)
            return

        if isinstance(frame, LLMFullResponseEndFrame):
            if self._in_response:
                self._in_response = False
                raw_text = "".join(self._buffer)
                self._buffer.clear()
                suggestions = self._parse_suggestions(raw_text)
                if not suggestions:
                    logger.warning(
                        "[session=%s] LLM response parse failed, using fallback suggestions",
                        self.session_id,
                    )
                    suggestions = self._fallback_suggestions()
                else:
                    suggestions = suggestions[:3]

                await self.push_frame(
                    SuggestionFrame(
                        suggestions=suggestions,
                        service_type="parallel_pipeline",
                        tools_used=["llm_inference"],
                    ),
                    direction,
                )
            return

        # Pass control frames through
        await self.push_frame(frame, direction)

    def _parse_suggestions(self, raw_text: str) -> list[dict[str, str]]:
        payload = _parse_json_payload(raw_text)
        if payload is None:
            return []

        if isinstance(payload, dict):
            suggestions_list = payload.get("suggestions")
        elif isinstance(payload, list):
            suggestions_list = payload
        else:
            return []

        if not isinstance(suggestions_list, list):
            return []

        normalized: list[dict[str, str]] = []
        for item in suggestions_list:
            if not isinstance(item, dict):
                continue
            text = item.get("text")
            suggestion_type = item.get("type")
            if not isinstance(text, str) or not text.strip():
                continue
            if suggestion_type not in _SUGGESTION_TYPES:
                suggestion_type = "action"
            normalized.append({"text": text.strip(), "type": suggestion_type})
            if len(normalized) == 3:
                break
        return normalized

    @staticmethod
    def _fallback_suggestions() -> list[dict[str, str]]:
        return [
            {"text": "Acknowledge the customer concern in one clear sentence.", "type": "response"},
            {
                "text": "Ask a clarifying question to narrow down the customer intent.",
                "type": "question",
            },
            {
                "text": "Summarize the understood issue and propose the immediate next step.",
                "type": "action",
            },
        ]


class VoiceBridgeRTVIObserver(FrameProcessor):
    """Intercepts custom frames and publishes them via RTVI.

    Sends SuggestionFrame, ProcessIllustrationFrame, and TranscriptSegmentFrame
    as bot-action messages through the RTVI data channel.
    """

    def __init__(self, rtvi_processor: Any, **kwargs):
        super().__init__(**kwargs)
        self._rtvi_processor = rtvi_processor

    async def process_frame(self, frame: Frame, direction: FrameDirection) -> None:
        await super().process_frame(frame, direction)

        if isinstance(frame, SuggestionFrame):
            await self._publish_suggestions(frame)
        elif isinstance(frame, ProcessIllustrationFrame):
            await self._publish_process_illustration(frame)
        elif isinstance(frame, TranscriptSegmentFrame):
            await self._publish_transcript(frame)

        await self.push_frame(frame, direction)

    async def _publish_suggestions(self, frame: SuggestionFrame) -> None:
        try:
            await self._rtvi_processor.send_server_message(
                {
                    "action": "agent_guidance",
                    "data": {
                        "suggestions": frame.suggestions,
                        "serviceType": frame.service_type,
                        "triggerTurn": frame.trigger_turn,
                        "latencyMs": frame.latency_ms,
                        "processKey": frame.process_key,
                        "toolsUsed": frame.tools_used,
                    },
                }
            )
            logger.info(
                "Published suggestions via RTVI: service=%s, count=%d",
                frame.service_type,
                len(frame.suggestions),
            )
        except Exception as e:
            logger.error("Failed to publish suggestions via RTVI, dropping message: %s", e)

    async def _publish_process_illustration(self, frame: ProcessIllustrationFrame) -> None:
        try:
            await self._rtvi_processor.send_server_message(
                {
                    "action": "process_illustration",
                    "data": {
                        "processKey": frame.process_key,
                        "processName": frame.process_name,
                        "steps": frame.steps,
                        "currentStep": frame.current_step,
                        "content": frame.content,
                    },
                }
            )
            logger.info("Published process illustration via RTVI: process=%s", frame.process_key)
        except Exception as e:
            logger.error(
                "Failed to publish process illustration via RTVI, dropping message: %s", e
            )

    async def _publish_transcript(self, frame: TranscriptSegmentFrame) -> None:
        try:
            await self._rtvi_processor.send_server_message(
                {
                    "action": "transcript_segment",
                    "data": {
                        "sessionId": frame.session_id,
                        "speaker": frame.speaker,
                        "text": frame.text,
                        "timestamp": frame.timestamp,
                        "isFinal": frame.is_final,
                    },
                }
            )
            logger.debug(
                "Published transcript via RTVI: speaker=%s, text=%s",
                frame.speaker,
                frame.text[:50],
            )
        except Exception as e:
            logger.error("Failed to publish transcript via RTVI, dropping message: %s", e)


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
