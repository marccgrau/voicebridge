"""Process selection processor using LLM with tool use."""

import logging
from datetime import UTC, datetime
from typing import Any

from pipecat.frames.frames import Frame, TranscriptionFrame
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor

from src.db import get_supabase_client
from src.events import get_event_publisher
from src.skills import ProcessLookupSkill

logger = logging.getLogger(__name__)


class ProcessSelectionFrame(Frame):
    """Frame containing process selection result."""

    def __init__(
        self,
        process_key: str,
        process_name: str,
        confidence: float,
        rationale: str,
        candidates: list[dict[str, Any]],
    ):
        super().__init__()
        self.process_key = process_key
        self.process_name = process_name
        self.confidence = confidence
        self.rationale = rationale
        self.candidates = candidates


class ProcessSelectionProcessor(FrameProcessor):
    """Processor that selects the appropriate process based on conversation.

    Uses Claude with the process_lookup tool to:
    1. Search the process catalog for relevant processes
    2. Select the most appropriate process
    3. Provide rationale for the selection
    """

    def __init__(
        self,
        session_id: str,
        anthropic_client: Any,
        model: str = "claude-sonnet-4-20250514",
        confidence_threshold: float = 0.6,
        **kwargs,
    ):
        """Initialize process selection processor.

        Args:
            session_id: The session ID for this pipeline
            anthropic_client: Anthropic client for LLM calls
            model: Model to use for selection
            confidence_threshold: Minimum confidence to accept selection
        """
        super().__init__(**kwargs)
        self.session_id = session_id
        self.anthropic = anthropic_client
        self.model = model
        self.confidence_threshold = confidence_threshold
        self._client = None
        self._publisher = None
        self._lookup_skill = ProcessLookupSkill()
        self._current_process: str | None = None
        self._conversation_buffer: list[str] = []
        self._buffer_size = 5  # Number of turns to consider

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
        """Process incoming frames for process selection."""
        await super().process_frame(frame, direction)

        if isinstance(frame, TranscriptionFrame):
            # Add to conversation buffer
            text = frame.text.strip()
            if text and getattr(frame, "is_final", True):
                self._conversation_buffer.append(text)
                if len(self._conversation_buffer) > self._buffer_size:
                    self._conversation_buffer.pop(0)

                # Trigger process selection on customer turns
                await self._maybe_select_process()

        await self.push_frame(frame, direction)

    async def _maybe_select_process(self) -> None:
        """Determine if we should (re)select a process."""
        if not self._conversation_buffer:
            return

        # Get recent conversation context
        context = "\n".join(self._conversation_buffer)

        try:
            result = await self._select_process_with_llm(context)
            if (
                result
                and result["confidence"] >= self.confidence_threshold
                and result["process_key"] != self._current_process
            ):
                # Only update if different from current or higher confidence
                self._current_process = result["process_key"]
                await self._persist_and_publish(result, context)

                # Push a ProcessSelectionFrame downstream
                selection_frame = ProcessSelectionFrame(
                    process_key=result["process_key"],
                    process_name=result["process_name"],
                    confidence=result["confidence"],
                    rationale=result["rationale"],
                    candidates=result["candidates"],
                )
                await self.push_frame(selection_frame)

        except Exception as e:
            logger.error("Process selection failed: %s", e)

    async def _select_process_with_llm(self, context: str) -> dict[str, Any] | None:
        """Use Claude with tool use to select a process.

        Args:
            context: Recent conversation context

        Returns:
            Process selection result or None
        """
        tool_definition = self._lookup_skill.get_tool_definition()

        system_prompt = """You are a customer service process selector. Based on the conversation,
determine which customer service process is most relevant. Use the process_lookup tool to search
for matching processes, then select the best one.

Always provide:
1. The selected process_key
2. A confidence score (0-1)
3. A brief rationale for your selection

If no process clearly matches, set confidence below 0.5."""

        messages = [
            {
                "role": "user",
                "content": f"Recent conversation:\n{context}\n\nIdentify the most relevant customer service process.",
            }
        ]

        # First call - let LLM use the tool
        response = self.anthropic.messages.create(
            model=self.model,
            max_tokens=1024,
            system=system_prompt,
            tools=[tool_definition],
            messages=messages,
        )

        # Handle tool use
        candidates = []
        for content in response.content:
            if content.type == "tool_use" and content.name == "process_lookup":
                # Execute the tool
                tool_input = content.input
                lookup_result = self._lookup_skill.search(
                    query=tool_input.get("query", ""),
                    domain=tool_input.get("domain"),
                )
                candidates = [
                    {
                        "processKey": r.process_key,
                        "name": r.name,
                        "domain": r.domain,
                        "score": r.score,
                    }
                    for r in lookup_result.results
                ]

                # Send tool result back
                messages.append({"role": "assistant", "content": response.content})
                messages.append(
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": content.id,
                                "content": self._lookup_skill.format_for_llm(lookup_result),
                            }
                        ],
                    }
                )

                # Get final response
                final_response = self.anthropic.messages.create(
                    model=self.model,
                    max_tokens=1024,
                    system=system_prompt,
                    messages=messages,
                )

                # Parse the selection from the response
                return self._parse_selection_response(final_response, candidates)

        return None

    def _parse_selection_response(
        self,
        response: Any,
        candidates: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        """Parse the LLM response to extract process selection.

        Args:
            response: The LLM response
            candidates: List of candidate processes from lookup

        Returns:
            Parsed selection result or None
        """
        # Extract text content
        text = ""
        for content in response.content:
            if hasattr(content, "text"):
                text = content.text
                break

        if not text or not candidates:
            return None

        # Simple parsing - look for process key in response
        # In production, use structured output
        selected = candidates[0] if candidates else None
        if not selected:
            return None

        # Look for confidence mention
        confidence = 0.7  # Default
        if "high confidence" in text.lower():
            confidence = 0.9
        elif "low confidence" in text.lower():
            confidence = 0.4
        elif "uncertain" in text.lower():
            confidence = 0.3

        return {
            "process_key": selected["processKey"],
            "process_name": selected["name"],
            "confidence": confidence,
            "rationale": text[:500],
            "candidates": candidates,
        }

    async def _persist_and_publish(
        self,
        result: dict[str, Any],
        trigger_text: str,
    ) -> None:
        """Persist selection to DB and publish event.

        Args:
            result: The selection result
            trigger_text: The text that triggered selection
        """
        # Persist to database
        try:
            self.client.table("process_selection_events").insert(
                {
                    "session_id": self.session_id,
                    "process_key": result["process_key"],
                    "confidence": result["confidence"],
                    "rationale": result["rationale"],
                    "candidates": result["candidates"],
                    "trigger_text": trigger_text,
                    "ts": datetime.now(UTC).isoformat(),
                }
            ).execute()
        except Exception as e:
            logger.error("Failed to persist process selection: %s", e)

        # Update session
        try:
            self.client.table("sessions").update(
                {
                    "process_key": result["process_key"],
                    "updated_at": datetime.now(UTC).isoformat(),
                }
            ).eq("id", self.session_id).execute()
        except Exception as e:
            logger.error("Failed to update session: %s", e)

        # Publish event
        try:
            await self.publisher.publish_process_selection(
                session_id=self.session_id,
                process_key=result["process_key"],
                process_name=result["process_name"],
                confidence=result["confidence"],
                rationale=result["rationale"],
                candidates=result["candidates"],
            )
        except Exception as e:
            logger.error("Failed to publish process selection: %s", e)
