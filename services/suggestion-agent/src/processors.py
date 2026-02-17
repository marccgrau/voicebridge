"""Pipeline processors for VoiceBridge suggestion agent."""

import json
import logging
import re
from typing import Any

from pipecat.frames.frames import (
    Frame,
    LLMFullResponseEndFrame,
    LLMFullResponseStartFrame,
    LLMTextFrame,
)
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor
from pipecat.processors.frameworks.rtvi import RTVIServerMessageFrame

logger = logging.getLogger(__name__)

_JSON_BLOCK_PATTERN = re.compile(r"(\{.*\}|\[.*\])", re.DOTALL)
_SUGGESTION_TYPES = {"response", "question", "action", "escalation"}

SUGGESTION_SYSTEM_PROMPT = (
    "You are an agent guidance assistant for a customer service call center. "
    "Return strict JSON only with exactly one suggestion in this format: "
    '{"suggestions":[{"text":"...","type":"response|question|action|escalation"}]}. '
    "No prose, no markdown, no code fences. "
    "The suggestion must be concise and the single most helpful next action."
)


class SuggestionOutputProcessor(FrameProcessor):
    """Collects streamed LLM output and emits RTVI agent_guidance messages."""

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
            if not self._in_response:
                await self.push_frame(frame, direction)
                return

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

            rtvi_msg = RTVIServerMessageFrame(
                data={
                    "action": "agent_guidance",
                    "data": {
                        "suggestions": suggestions,
                        "serviceType": "suggestion_agent",
                        "toolsUsed": ["llm_inference"],
                    },
                }
            )
            await self.push_frame(rtvi_msg, direction)
            return

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
            {
                "text": "Acknowledge the customer concern and ask how you can help.",
                "type": "response",
            },
        ]


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
