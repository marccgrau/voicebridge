"""Pipeline processors for VoiceBridge suggestion agent.

TranscriptWriter — converts STT transcriptions to TranscriptSegmentFrames.
SuggestionContextBuilder — builds LLM context from transcript only (no process context).
SuggestionOutputProcessor — collects LLM output and emits SuggestionFrame (1 suggestion).
SuggestionRTVIObserver — sends SuggestionFrame via RTVI to the frontend.
"""

import json
import logging
import re
from datetime import UTC, datetime
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

from src.frames import SuggestionFrame, TranscriptSegmentFrame

logger = logging.getLogger(__name__)

_JSON_BLOCK_PATTERN = re.compile(r"(\{.*\}|\[.*\])", re.DOTALL)
_SUGGESTION_TYPES = {"response", "question", "action", "escalation"}


class TranscriptWriter(FrameProcessor):
    """Convert finalized STT transcriptions to TranscriptSegmentFrames."""

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


class SuggestionContextBuilder(FrameProcessor):
    """Builds LLM context from transcript only (no process context).

    Consumes TranscriptSegmentFrame. On each customer utterance, pushes
    an LLMContextFrame to trigger LLM inference downstream.
    """

    def __init__(self, session_id: str, **kwargs):
        super().__init__(**kwargs)
        self.session_id = session_id
        self._conversation_lines: list[str] = []

    async def process_frame(self, frame: Frame, direction: FrameDirection) -> None:
        await super().process_frame(frame, direction)

        if isinstance(frame, TranscriptSegmentFrame):
            self._conversation_lines.append(f"[{frame.speaker}]: {frame.text}")
            if frame.speaker == "customer":
                context = self._build_llm_context()
                await self.push_frame(LLMContextFrame(context=context), direction)
            # Consumed — not passed downstream
            return

        # Pass control frames through
        await self.push_frame(frame, direction)

    def _build_llm_context(self) -> LLMContext:
        conversation_text = "\n".join(self._conversation_lines) or "(waiting)"

        return LLMContext(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an agent guidance assistant for a customer service call center. "
                        "Return strict JSON only in the format "
                        '{"suggestions":[{"text":"...","type":"response|question|action|escalation"}]} '
                        "with exactly 1 suggestion. The suggestion should be the single most "
                        "helpful action the agent can take right now."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Conversation:\n{conversation_text}\n\n"
                        "Generate 1 concise, actionable suggestion for the agent."
                    ),
                },
            ]
        )


class SuggestionOutputProcessor(FrameProcessor):
    """Collects streamed LLM text and emits SuggestionFrame on completion.

    Limits output to 1 suggestion.
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
                        "[session=%s] LLM response parse failed, using fallback suggestion",
                        self.session_id,
                    )
                    suggestions = self._fallback_suggestions()
                else:
                    suggestions = suggestions[:1]

                await self.push_frame(
                    SuggestionFrame(
                        suggestions=suggestions,
                        service_type="suggestion_agent",
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
            if len(normalized) == 1:
                break
        return normalized

    @staticmethod
    def _fallback_suggestions() -> list[dict[str, str]]:
        return [
            {"text": "Acknowledge the customer concern and ask how you can help.", "type": "response"},
        ]


class SuggestionRTVIObserver(FrameProcessor):
    """Publishes SuggestionFrames via RTVI to the frontend.

    Only handles agent_guidance — does NOT publish transcript or process frames.
    """

    def __init__(self, rtvi_processor: Any, **kwargs):
        super().__init__(**kwargs)
        self._rtvi_processor = rtvi_processor

    async def process_frame(self, frame: Frame, direction: FrameDirection) -> None:
        await super().process_frame(frame, direction)

        if isinstance(frame, SuggestionFrame):
            await self._publish_suggestions(frame)

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
                "Published suggestions via RTVI: count=%d",
                len(frame.suggestions),
            )
        except Exception as e:
            logger.error("Failed to publish suggestions via RTVI, dropping message: %s", e)


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
