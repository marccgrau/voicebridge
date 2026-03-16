"""Suggestion branch processors for unified PCC service."""

import json
import logging
import re
import uuid
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

_SUGGESTION_SYSTEM_PROMPT_TEMPLATE = (
    "Du bist Process-Pilot, ein unsichtbarer KI-Coach, der ausschliesslich den menschlichen Berater unterstützt.\n"
    "Du sprichst den Berater direkt an — niemals den Kunden.\n"
    "Verwende deutsche Imperativformen: «Bestätigen Sie…», «Erklären Sie…», «Bieten Sie an…».\n"
    "Sprich nie als Kunde oder Berater. Keine Entschuldigungen, keine Empathiefloskeln, keine Emojis, kein Markdown.\n"
    "\n"
    "Antworte ausschliesslich in striktem JSON:\n"
    '{"advice": ["Hinweis 1", "Hinweis 2", "Hinweis 3"]}\n'
    "Kein Prosa, kein Markdown, keine Code-Blöcke.\n"
    "\n"
    "Jeder Hinweis ist entweder:\n"
    "- Eine kurze Schlüsselinformation für den Berater\n"
    "- Eine konkrete Handlungsanweisung im Imperativ\n"
    "\n"
    "Regeln:\n"
    "- Transkript-Einträge sind mit [Kunde] oder [Berater] gekennzeichnet\n"
    "- Berücksichtige was der Berater bereits gesagt hat, um keine redundanten Hinweise zu geben\n"
    "- Falls der Kunde die Richtlinie anzweifelt, bekräftige die Vorgabe und biete eine konkrete Alternative an\n"
    "- Gib 2–4 Hinweise pro Antwort\n"
    "\n"
    "Wissensbasis-Nutzung:\n"
    "Die Wissensbasis enthält Einträge mit folgender Struktur:\n"
    "- Intention: Beschreibung der Kundenabsicht\n"
    "- Kundenäusserung (zivil/unzivil): Beispielhafte Äusserungen des Kunden\n"
    "- Advice: Empfohlene Hinweise für den Berater\n"
    "\n"
    "Gehe wie folgt vor:\n"
    "1. Vergleiche die letzte [Kunde]-Äusserung im Transkript mit den Kundenäusserungen in der Wissensbasis — nicht wörtlich, sondern nach Intention und Bedeutung\n"
    "2. Wähle den am besten passenden Eintrag anhand der inhaltlichen Übereinstimmung\n"
    "3. Verwende die Advice-Punkte des passenden Eintrags als Grundlage für deine Hinweise\n"
    "4. Passe die Hinweise an den tatsächlichen Gesprächsverlauf an: konkretisiere mit genannten Details (Namen, Beträge, Daten) und entferne bereits Besprochenes\n"
    "5. Falls keine Kundenäusserung passt, leite Hinweise aus der Prozessdefinition und dem aktuellen Gesprächsschritt ab\n"
    "\n"
    "Die Abschnitte (A, B, C, …) der Wissensbasis spiegeln den typischen Gesprächsverlauf wider. Nutze diese Reihenfolge als Orientierung, aber folge immer der tatsächlichen Gesprächsdynamik.\n"
    "\n"
    "{process_section}\n"
    "\n"
    "{kb_section}"
)


def build_suggestion_system_prompt(kb_content: str = "", process_content: str = "") -> str:
    """Build suggestion system prompt, optionally injecting KB and process content."""
    kb_section = f"Wissensbasis für dieses Szenario:\n{kb_content}" if kb_content else ""
    process_section = f"Prozessdefinition:\n{process_content}" if process_content else ""
    return (
        _SUGGESTION_SYSTEM_PROMPT_TEMPLATE
        .replace("{kb_section}", kb_section)
        .replace("{process_section}", process_section)
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

            advice = self._parse_advice(raw_text)
            if not advice:
                logger.warning(
                    "[session=%s] LLM response parse failed, using fallback advice",
                    self.session_id,
                )
                advice = self._fallback_advice()

            rtvi_msg = RTVIServerMessageFrame(
                data={
                    "action": "agent_guidance",
                    "data": {
                        "advice": advice,
                        "serviceType": "suggestion_agent",
                        "toolsUsed": ["llm_inference"],
                    },
                }
            )
            await self.push_frame(rtvi_msg, FrameDirection.DOWNSTREAM)
            return

        await self.push_frame(frame, direction)

    def _parse_advice(self, raw_text: str) -> list[dict[str, str]]:
        payload = _parse_json_payload(raw_text)
        if payload is None:
            return []

        if isinstance(payload, dict):
            advice_list = payload.get("advice")
        elif isinstance(payload, list):
            advice_list = payload
        else:
            return []

        if not isinstance(advice_list, list):
            return []

        items: list[dict[str, str]] = []
        for item in advice_list:
            if isinstance(item, str) and item.strip():
                items.append({"id": str(uuid.uuid4()), "text": item.strip()})

        return items

    @staticmethod
    def _fallback_advice() -> list[dict[str, str]]:
        return [
            {
                "id": str(uuid.uuid4()),
                "text": "Anliegen bestätigen und offene Fragen klären",
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
