"""Suggestion composer processor."""

import logging
import re
from typing import Any
from uuid import uuid4

from pipecat.frames.frames import Frame
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor

from src.db import get_supabase_client
from src.events import get_event_publisher

from .kb_lookup import KBSnippetFrame
from .slot_extraction import SlotExtractionFrame

logger = logging.getLogger(__name__)


class SuggestionFrame(Frame):
    """Frame containing generated suggestions."""

    def __init__(
        self,
        suggestions: list[dict[str, Any]],
        process_key: str | None,
        step_key: str | None,
    ):
        super().__init__()
        self.suggestions = suggestions
        self.process_key = process_key
        self.step_key = step_key


class SuggestionComposer(FrameProcessor):
    """Processor that composes agent response suggestions.

    Takes KB snippets and extracted slots to:
    1. Fill in template placeholders
    2. Optionally rewrite with LLM for natural language
    3. Generate 3-6 candidate suggestions
    """

    def __init__(
        self,
        session_id: str,
        anthropic_client: Any | None = None,
        model: str = "claude-sonnet-4-20250514",
        enable_rewrite: bool = True,
        min_suggestions: int = 3,
        max_suggestions: int = 6,
        **kwargs,
    ):
        """Initialize suggestion composer.

        Args:
            session_id: The session ID for this pipeline
            anthropic_client: Optional Anthropic client for rewrites
            model: Model for rewriting
            enable_rewrite: Whether to use LLM to polish suggestions
            min_suggestions: Minimum suggestions to generate
            max_suggestions: Maximum suggestions to generate
        """
        super().__init__(**kwargs)
        self.session_id = session_id
        self.anthropic = anthropic_client
        self.model = model
        self.enable_rewrite = enable_rewrite
        self.min_suggestions = min_suggestions
        self.max_suggestions = max_suggestions
        self._client = None
        self._publisher = None
        self._kb_snippets: list[dict[str, Any]] = []
        self._slots: dict[str, str] = {}
        self._current_process: str | None = None
        self._current_step: str | None = None

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
        """Process incoming frames for suggestion generation."""
        await super().process_frame(frame, direction)

        # Collect KB snippets
        if isinstance(frame, KBSnippetFrame):
            self._kb_snippets = frame.snippets
            self._current_process = frame.process_key
            self._current_step = frame.step_key
            await self._generate_suggestions()

        # Collect extracted slots
        if isinstance(frame, SlotExtractionFrame):
            for slot in frame.slots:
                self._slots[slot["key"]] = slot["value"]
            # Regenerate suggestions when slots change
            if self._kb_snippets:
                await self._generate_suggestions()

        await self.push_frame(frame, direction)

    async def _generate_suggestions(self) -> None:
        """Generate suggestions from templates and slots."""
        if not self._kb_snippets:
            return

        suggestions = []

        for snippet in self._kb_snippets[: self.max_suggestions]:
            suggestion = await self._compose_suggestion(snippet)
            if suggestion:
                suggestions.append(suggestion)

        # Ensure minimum suggestions
        if len(suggestions) < self.min_suggestions:
            # Add generic fallback suggestions
            suggestions.extend(self._get_fallback_suggestions())

        suggestions = suggestions[: self.max_suggestions]

        if suggestions:
            # Persist and publish
            await self._persist_suggestions(suggestions)

            # Push frame
            suggestion_frame = SuggestionFrame(
                suggestions=suggestions,
                process_key=self._current_process,
                step_key=self._current_step,
            )
            await self.push_frame(suggestion_frame)

    async def _compose_suggestion(self, snippet: dict[str, Any]) -> dict[str, Any] | None:
        """Compose a single suggestion from a template.

        Args:
            snippet: KB snippet with template

        Returns:
            Composed suggestion dict or None
        """
        template = snippet.get("template", "")
        if not template:
            return None

        # Fill in placeholders with slots
        text = self._fill_template(template)

        # Check if all required placeholders are filled
        if "{{" in text:
            # Still has unfilled placeholders - skip or use as-is
            # In production, might skip or show with placeholders highlighted
            pass

        # Optionally rewrite with LLM
        if self.enable_rewrite and self.anthropic:
            text = await self._rewrite_suggestion(text)

        # Determine suggestion type based on content
        suggestion_type = self._classify_suggestion(text)

        return {
            "id": str(uuid4()),
            "text": text,
            "type": suggestion_type,
            "confidence": 0.8 if "{{" not in text else 0.5,
            "source": "hybrid" if self.enable_rewrite else "template",
            "metadata": {
                "snippet_id": snippet.get("id"),
                "step_key": snippet.get("step_key"),
            },
        }

    def _fill_template(self, template: str) -> str:
        """Fill template placeholders with slot values.

        Args:
            template: Template string with {{placeholder}} syntax

        Returns:
            Filled template
        """
        result = template
        for key, value in self._slots.items():
            # Handle both {{key}} and {{key_name}} patterns
            result = re.sub(
                rf"\{{\{{\s*{re.escape(key)}\s*\}}\}}",
                value,
                result,
            )
        return result

    async def _rewrite_suggestion(self, text: str) -> str:
        """Use LLM to polish the suggestion.

        Args:
            text: Raw suggestion text

        Returns:
            Polished suggestion
        """
        if not self.anthropic:
            return text

        try:
            response = self.anthropic.messages.create(
                model=self.model,
                max_tokens=256,
                system="You are a customer service writing assistant. Polish the following response to sound natural and professional while keeping the same meaning. Only output the polished text, nothing else.",
                messages=[{"role": "user", "content": text}],
            )

            for content in response.content:
                if hasattr(content, "text"):
                    return content.text.strip()

        except Exception as e:
            logger.warning("Failed to rewrite suggestion: %s", e)

        return text

    def _classify_suggestion(self, text: str) -> str:
        """Classify the suggestion type.

        Args:
            text: Suggestion text

        Returns:
            Type: 'response', 'question', 'action', or 'escalation'
        """
        text_lower = text.lower()

        if "?" in text:
            return "question"
        if any(word in text_lower for word in ["escalate", "transfer", "supervisor"]):
            return "escalation"
        if any(word in text_lower for word in ["processed", "completed", "done", "refund"]):
            return "action"
        return "response"

    def _get_fallback_suggestions(self) -> list[dict[str, Any]]:
        """Get generic fallback suggestions.

        Returns:
            List of fallback suggestions
        """
        return [
            {
                "id": str(uuid4()),
                "text": "I understand. Could you tell me more about the issue?",
                "type": "question",
                "confidence": 0.5,
                "source": "template",
            },
            {
                "id": str(uuid4()),
                "text": "Let me look into that for you right away.",
                "type": "response",
                "confidence": 0.5,
                "source": "template",
            },
        ]

    async def _persist_suggestions(self, suggestions: list[dict[str, Any]]) -> None:
        """Persist suggestions to database and publish event.

        Args:
            suggestions: List of suggestions to persist
        """
        # Persist to database
        try:
            self.client.table("suggestions").insert(
                {
                    "session_id": self.session_id,
                    "suggestions_json": suggestions,
                    "process_key": self._current_process,
                    "step_key": self._current_step,
                }
            ).execute()
        except Exception as e:
            logger.error("Failed to persist suggestions: %s", e)

        # Publish event
        try:
            await self.publisher.publish_suggestions(
                session_id=self.session_id,
                suggestions=suggestions,
                process_key=self._current_process,
                step_key=self._current_step,
            )
        except Exception as e:
            logger.error("Failed to publish suggestions: %s", e)
