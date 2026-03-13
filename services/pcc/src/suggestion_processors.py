"""Suggestion branch processors for unified PCC service."""

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

_SUGGESTION_SYSTEM_PROMPT_TEMPLATE = (
    "Du bist ein Beratungsassistent für ein Kundenservice-Callcenter.\n"
    "Basierend auf dem Gesprächsverlauf, gib genau einen konkreten Vorschlag.\n"
    "Antworte ausschliesslich in striktem JSON:\n"
    '{"suggestions":[{"text":"...","type":"response|question|action|escalation"}]}\n'
    "Kein Prosa, kein Markdown, keine Code-Blöcke.\n"
    "Der Vorschlag muss prägnant und die hilfreichste nächste Aktion sein.\n"
    "\n"
    "{kb_section}"
)


def build_suggestion_system_prompt(kb_content: str = "") -> str:
    """Build suggestion system prompt, optionally injecting KB content."""
    kb_section = f"Wissensbasis für dieses Szenario:\n{kb_content}" if kb_content else ""
    return _SUGGESTION_SYSTEM_PROMPT_TEMPLATE.replace("{kb_section}", kb_section)


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
            await self.push_frame(rtvi_msg, FrameDirection.DOWNSTREAM)
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
                "text": "Bestätigen Sie das Anliegen des Kunden und fragen Sie, wie Sie helfen können.",
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
