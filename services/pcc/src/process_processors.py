"""Process branch processors for unified PCC service."""

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

from src.process_catalog import ProcessCatalog, ProcessDefinition

logger = logging.getLogger(__name__)

_JSON_BLOCK_PATTERN = re.compile(r"(\{.*\})", re.DOTALL)

PROCESS_SYSTEM_PROMPT = (
    "Du bist ein Prozesserkennungs-Assistent für ein Kundenservice-Callcenter.\n"
    "Nutze den Transkriptkontext, um den wahrscheinlichsten Prozess und aktuellen Schritt zu identifizieren.\n"
    "\n"
    "Prozesskatalog:\n"
    "{catalog_summary}\n"
    "\n"
    "Antworte ausschliesslich in striktem JSON. Kein Prosa, kein Markdown, keine Code-Blöcke.\n"
    "Ausgabeformat:\n"
    '{"processKey":"<process_key_oder_null>","currentStep":<nullbasierter_integer>}\n'
    "\n"
    "Regeln:\n"
    "- processKey muss ein Katalogschlüssel oder null sein\n"
    "- currentStep muss nullbasiert sein\n"
    "- wähle nur einen Prozess"
)


class ProcessOutputProcessor(FrameProcessor):
    """Buffers streamed LLM JSON and emits process_illustration RTVI messages."""

    def __init__(self, catalog: ProcessCatalog, **kwargs):
        super().__init__(**kwargs)
        self._catalog = catalog
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
            raw = "".join(self._buffer).strip()
            self._buffer.clear()

            rtvi_data = self._parse_and_build(raw)
            if rtvi_data:
                await self.push_frame(
                    RTVIServerMessageFrame(data=rtvi_data), FrameDirection.DOWNSTREAM
                )
            return

        await self.push_frame(frame, direction)

    def _parse_and_build(self, raw: str) -> dict[str, Any] | None:
        payload = _parse_json_payload(raw)
        if not isinstance(payload, dict):
            logger.warning("ProcessOutputProcessor: failed to parse JSON payload")
            return None

        process_key = payload.get("processKey")
        if process_key is None:
            logger.warning("ProcessOutputProcessor: processKey is null, skipping emission")
            return None
        if not isinstance(process_key, str) or not process_key.strip():
            logger.warning("ProcessOutputProcessor: processKey is invalid: %r", process_key)
            return None

        current_step = payload.get("currentStep")
        if not isinstance(current_step, int):
            logger.warning("ProcessOutputProcessor: currentStep is invalid: %r", current_step)
            return None

        definition = self._catalog.get_definition(process_key.strip())
        if not definition:
            logger.warning("ProcessOutputProcessor: unknown processKey: %s", process_key)
            return None

        steps, bounded_step = self._build_steps(definition, current_step)

        return {
            "action": "process_illustration",
            "data": {
                "processKey": definition.process_key,
                "processName": definition.name,
                "steps": steps,
                "currentStep": bounded_step,
                "content": definition.full_content,
            },
        }

    @staticmethod
    def _build_steps(
        definition: ProcessDefinition, current_step: int
    ) -> tuple[list[dict[str, str]], int]:
        if not definition.steps:
            return [], 0

        bounded_step = min(max(current_step, 0), len(definition.steps) - 1)
        steps = []
        for idx, step in enumerate(definition.steps):
            if idx < bounded_step:
                status = "completed"
            elif idx == bounded_step:
                status = "in_progress"
            else:
                status = "pending"
            steps.append({"key": step.key, "label": step.label, "status": status})

        return steps, bounded_step


def _parse_json_payload(raw_text: str) -> dict[str, Any] | None:
    text = raw_text.strip()
    if not text:
        return None

    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:].strip()

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        match = _JSON_BLOCK_PATTERN.search(raw_text)
        if not match:
            return None
        try:
            parsed = json.loads(match.group(1))
        except json.JSONDecodeError:
            return None

    return parsed if isinstance(parsed, dict) else None
