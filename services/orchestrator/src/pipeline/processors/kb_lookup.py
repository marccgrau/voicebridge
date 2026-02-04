"""Knowledge base lookup processor."""

import logging
from typing import Any

from pipecat.frames.frames import Frame
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor

from src.db import get_supabase_client

from .process_selection import ProcessSelectionFrame
from .slot_extraction import SlotExtractionFrame

logger = logging.getLogger(__name__)


class KBSnippetFrame(Frame):
    """Frame containing KB snippets for suggestion generation."""

    def __init__(
        self,
        snippets: list[dict[str, Any]],
        process_key: str | None,
        step_key: str | None,
        intent_key: str | None,
    ):
        super().__init__()
        self.snippets = snippets
        self.process_key = process_key
        self.step_key = step_key
        self.intent_key = intent_key


class KBLookupProcessor(FrameProcessor):
    """Processor that retrieves KB snippets based on process and intent.

    Performs deterministic SQL queries against the kb_snippets table
    to find relevant templates for suggestion generation.
    """

    def __init__(
        self,
        session_id: str,
        **kwargs,
    ):
        """Initialize KB lookup processor.

        Args:
            session_id: The session ID for this pipeline
        """
        super().__init__(**kwargs)
        self.session_id = session_id
        self._client = None
        self._current_process: str | None = None
        self._current_step: str | None = None
        self._current_intent: str | None = None

    @property
    def client(self):
        """Get Supabase client lazily."""
        if self._client is None:
            self._client = get_supabase_client()
        return self._client

    async def process_frame(self, frame: Frame, direction: FrameDirection) -> None:
        """Process incoming frames for KB lookup."""
        await super().process_frame(frame, direction)

        # Track process selection
        if isinstance(frame, ProcessSelectionFrame) and frame.process_key != self._current_process:
            self._current_process = frame.process_key
            self._current_step = None  # Reset step on process change
            await self._lookup_and_push()

        # Track slot extraction for intent
        if isinstance(frame, SlotExtractionFrame) and frame.intent and frame.intent != self._current_intent:
            self._current_intent = frame.intent
            await self._lookup_and_push()

        await self.push_frame(frame, direction)

    async def _lookup_and_push(self) -> None:
        """Look up KB snippets and push frame."""
        if not self._current_process:
            return

        try:
            snippets = await self._lookup_snippets()
            if snippets:
                kb_frame = KBSnippetFrame(
                    snippets=snippets,
                    process_key=self._current_process,
                    step_key=self._current_step,
                    intent_key=self._current_intent,
                )
                await self.push_frame(kb_frame)

        except Exception as e:
            logger.error("KB lookup failed: %s", e)

    async def _lookup_snippets(self) -> list[dict[str, Any]]:
        """Query KB snippets from database.

        Returns:
            List of matching KB snippets
        """
        query = self.client.table("kb_snippets").select("*")

        # Filter by process
        query = query.eq("process_key", self._current_process)

        # Optionally filter by step
        if self._current_step:
            query = query.or_(f"step_key.eq.{self._current_step},step_key.is.null")

        # Optionally filter by intent
        if self._current_intent:
            query = query.or_(f"intent_key.eq.{self._current_intent},intent_key.is.null")

        # Order by priority (higher first) and limit
        query = query.order("priority", desc=True).limit(5)

        response = query.execute()

        return [
            {
                "id": row["id"],
                "template": row["template"],
                "step_key": row.get("step_key"),
                "intent_key": row.get("intent_key"),
                "constraints": row.get("constraints", {}),
                "priority": row.get("priority", 0),
            }
            for row in (response.data or [])
        ]

    def set_current_step(self, step_key: str) -> None:
        """Update the current step.

        Args:
            step_key: The new current step key
        """
        self._current_step = step_key
