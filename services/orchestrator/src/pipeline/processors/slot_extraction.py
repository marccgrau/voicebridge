"""Slot extraction processor using LLM structured output."""

import logging
from typing import Any

from pipecat.frames.frames import Frame, TranscriptionFrame
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor

from src.db import get_supabase_client
from src.events import get_event_publisher

from .process_selection import ProcessSelectionFrame

logger = logging.getLogger(__name__)


class SlotExtractionFrame(Frame):
    """Frame containing extracted slots."""

    def __init__(
        self,
        intent: str | None,
        slots: list[dict[str, Any]],
        process_key: str | None,
    ):
        super().__init__()
        self.intent = intent
        self.slots = slots
        self.process_key = process_key


class SlotExtractionProcessor(FrameProcessor):
    """Processor that extracts structured data from conversation.

    Uses Claude to extract:
    1. Customer intent
    2. Named entities and values (slots)
    3. Process-specific data points
    """

    def __init__(
        self,
        session_id: str,
        anthropic_client: Any,
        model: str = "claude-sonnet-4-20250514",
        **kwargs,
    ):
        """Initialize slot extraction processor.

        Args:
            session_id: The session ID for this pipeline
            anthropic_client: Anthropic client for LLM calls
            model: Model to use for extraction
        """
        super().__init__(**kwargs)
        self.session_id = session_id
        self.anthropic = anthropic_client
        self.model = model
        self._client = None
        self._publisher = None
        self._current_process: str | None = None
        self._extracted_slots: dict[str, str] = {}
        self._conversation_buffer: list[str] = []
        self._buffer_size = 3

    @property
    def client(self):
        """Get Supabase client lazily."""
        if self._client is None:
            self._client = get_supabase_client()
        return self._client

    @property
    def publisher(self):
        """Get event publisher lazily."""
        if self._publisher is None:
            self._publisher = get_event_publisher()
        return self._publisher

    async def process_frame(self, frame: Frame, direction: FrameDirection) -> None:
        """Process incoming frames for slot extraction."""
        await super().process_frame(frame, direction)

        # Track process selection
        if isinstance(frame, ProcessSelectionFrame):
            self._current_process = frame.process_key

        # Extract slots from transcriptions
        if isinstance(frame, TranscriptionFrame):
            text = frame.text.strip()
            if text and getattr(frame, "is_final", True):
                self._conversation_buffer.append(text)
                if len(self._conversation_buffer) > self._buffer_size:
                    self._conversation_buffer.pop(0)

                await self._extract_slots()

        await self.push_frame(frame, direction)

    async def _extract_slots(self) -> None:
        """Extract slots from recent conversation."""
        if not self._conversation_buffer:
            return

        context = "\n".join(self._conversation_buffer)

        try:
            result = await self._extract_with_llm(context)
            if result:
                # Merge new slots with existing
                for slot in result["slots"]:
                    self._extracted_slots[slot["key"]] = slot["value"]

                # Publish event
                await self._publish_extraction(result)

                # Push frame downstream
                extraction_frame = SlotExtractionFrame(
                    intent=result.get("intent"),
                    slots=result["slots"],
                    process_key=self._current_process,
                )
                await self.push_frame(extraction_frame)

        except Exception as e:
            logger.error("Slot extraction failed: %s", e)

    async def _extract_with_llm(self, context: str) -> dict[str, Any] | None:
        """Use Claude to extract slots from text.

        Args:
            context: Recent conversation context

        Returns:
            Extraction result with intent and slots
        """
        system_prompt = """You are a slot extraction system for customer service.
Extract structured information from the conversation.

Return a JSON object with:
- intent: The customer's primary intent (e.g., "dispute_charge", "reset_password", "check_order")
- slots: Array of extracted values, each with:
  - key: Slot name (e.g., "order_number", "email", "amount")
  - value: Extracted value
  - confidence: 0-1 confidence score
  - source: "customer" or "agent" or "inferred"

Only extract information that is explicitly stated or clearly implied.
Return empty slots array if nothing can be extracted."""

        process_context = ""
        if self._current_process:
            process_context = f"\nCurrent process: {self._current_process}"

        try:
            response = self.anthropic.messages.create(
                model=self.model,
                max_tokens=1024,
                system=system_prompt,
                messages=[
                    {
                        "role": "user",
                        "content": f"Conversation:{process_context}\n{context}\n\nExtract slots as JSON:",
                    }
                ],
            )

            # Parse JSON from response
            text = ""
            for content in response.content:
                if hasattr(content, "text"):
                    text = content.text
                    break

            # Simple JSON extraction
            import json

            # Look for JSON in the response
            start = text.find("{")
            end = text.rfind("}") + 1
            if start >= 0 and end > start:
                json_str = text[start:end]
                return json.loads(json_str)

        except Exception as e:
            logger.error("LLM slot extraction error: %s", e)

        return None

    async def _publish_extraction(self, result: dict[str, Any]) -> None:
        """Publish slot extraction event.

        Args:
            result: The extraction result
        """
        try:
            await self.publisher.publish_slot_extraction(
                session_id=self.session_id,
                intent=result.get("intent"),
                slots=result.get("slots", []),
                process_key=self._current_process,
            )
        except Exception as e:
            logger.error("Failed to publish slot extraction: %s", e)
