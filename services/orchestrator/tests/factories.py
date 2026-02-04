"""Test data factories for creating sample data in tests."""

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4


class SessionFactory:
    """Factory for creating session test data."""

    @staticmethod
    def create_session_data(
        session_id: str | None = None,
        process_key: str | None = None,
        status: str = "active",
        slots: dict[str, str] | None = None,
        steps: list[dict[str, Any]] | None = None,
        **kwargs,
    ) -> dict[str, Any]:
        """Create a session data dictionary for testing.

        Args:
            session_id: Optional session ID, generates UUID if not provided
            process_key: Optional process key
            status: Session status (default: "active")
            slots: Optional slots dictionary
            steps: Optional steps list
            **kwargs: Additional fields to override

        Returns:
            Dictionary with session data
        """
        now = datetime.now(UTC).isoformat()
        data = {
            "id": session_id or str(uuid4()),
            "process_key": process_key,
            "state": {
                "slots": slots or {},
                "steps": steps or [],
            },
            "status": status,
            "created_at": kwargs.get("created_at", now),
            "updated_at": kwargs.get("updated_at", now),
        }
        # Merge any additional kwargs
        data.update({k: v for k, v in kwargs.items() if k not in data})
        return data

    @staticmethod
    def create_session_row(
        session_id: str | None = None,
        process_key: str | None = None,
        status: str = "active",
        state: dict[str, Any] | None = None,
        **kwargs,
    ) -> dict[str, Any]:
        """Create a session row as returned from database.

        This matches the structure of rows from the sessions table.

        Args:
            session_id: Optional session ID
            process_key: Optional process key
            status: Session status
            state: Optional state JSONB field
            **kwargs: Additional fields

        Returns:
            Dictionary matching database row structure
        """
        now = datetime.now(UTC).isoformat()
        return {
            "id": session_id or str(uuid4()),
            "process_key": process_key,
            "state": state or {"slots": {}, "steps": []},
            "status": status,
            "created_at": kwargs.get("created_at", now),
            "updated_at": kwargs.get("updated_at", now),
        }


class ProcessFactory:
    """Factory for creating process catalog test data."""

    @staticmethod
    def create_process_data(
        process_key: str = "test-process",
        name: str = "Test Process",
        domain: str = "test",
        version: str = "1.0.0",
        locale: str = "en",
        queue_tags: list[str] | None = None,
        description: str | None = None,
        steps: list[dict[str, Any]] | None = None,
        slots: list[dict[str, Any]] | None = None,
        **kwargs,
    ) -> dict[str, Any]:
        """Create a process catalog entry for testing.

        Args:
            process_key: Unique process identifier
            name: Human-readable process name
            domain: Process domain (e.g., "billing", "account")
            version: Semantic version
            locale: Language/locale code
            queue_tags: Optional list of queue tags
            description: Optional process description
            steps: Optional list of process steps
            slots: Optional list of process slots
            **kwargs: Additional fields

        Returns:
            Dictionary with process data
        """
        now = datetime.now(UTC).isoformat()
        return {
            "process_key": process_key,
            "name": name,
            "domain": domain,
            "version": version,
            "locale": locale,
            "queue_tags": queue_tags or [],
            "description": description or f"Description for {name}",
            "steps_json": steps
            or [
                {"key": "step1", "label": "First Step"},
                {"key": "step2", "label": "Second Step"},
            ],
            "slots_json": slots
            or [
                {
                    "key": "customer_name",
                    "label": "Customer Name",
                    "type": "string",
                    "required": True,
                }
            ],
            "process_text": kwargs.get(
                "process_text",
                f"{name} process with steps and slots",
            ),
            "embedding": kwargs.get("embedding"),
            "created_at": kwargs.get("created_at", now),
            "updated_at": kwargs.get("updated_at", now),
        }

    @staticmethod
    def create_process_result(
        process_key: str = "test-process",
        name: str = "Test Process",
        domain: str = "test",
        score: float = 0.85,
        **kwargs,
    ) -> dict[str, Any]:
        """Create a process search result for testing.

        This matches the structure returned by the process_lookup RPC.

        Args:
            process_key: Process identifier
            name: Process name
            domain: Process domain
            score: Relevance score (0-1)
            **kwargs: Additional fields

        Returns:
            Dictionary matching process search result structure
        """
        return {
            "process_key": process_key,
            "name": name,
            "domain": domain,
            "version": kwargs.get("version", "1.0.0"),
            "rank": score,
            "process_text": kwargs.get(
                "process_text",
                f"{name} process description",
            ),
            "steps_json": kwargs.get(
                "steps_json",
                [{"key": "step1", "label": "Step 1"}],
            ),
        }


class EventFactory:
    """Factory for creating event test data."""

    @staticmethod
    def create_base_event(
        event_id: str | None = None,
        session_id: str | None = None,
        event_type: str = "test",
        **data,
    ) -> dict[str, Any]:
        """Create a base event structure.

        Args:
            event_id: Optional event ID
            session_id: Optional session ID
            event_type: Event type
            **data: Additional event data fields

        Returns:
            Dictionary with base event structure
        """
        return {
            "eventId": event_id or str(uuid4()),
            "sessionId": session_id or str(uuid4()),
            "timestamp": datetime.now(UTC).isoformat(),
            "type": event_type,
            **data,
        }

    @staticmethod
    def create_transcript_segment_event(
        session_id: str | None = None,
        speaker: str = "customer",
        text: str = "Hello, I need help",
        is_final: bool = True,
        confidence: float | None = 0.95,
        **kwargs,
    ) -> dict[str, Any]:
        """Create a transcript segment event."""
        return EventFactory.create_base_event(
            session_id=session_id,
            event_type="transcript_segment",
            speaker=speaker,
            text=text,
            isFinal=is_final,
            confidence=confidence,
            **kwargs,
        )

    @staticmethod
    def create_process_selection_event(
        session_id: str | None = None,
        process_key: str = "test-process",
        process_name: str = "Test Process",
        confidence: float = 0.85,
        rationale: str = "Test rationale",
        candidates: list[dict[str, Any]] | None = None,
        **kwargs,
    ) -> dict[str, Any]:
        """Create a process selection event."""
        return EventFactory.create_base_event(
            session_id=session_id,
            event_type="process_selection",
            processKey=process_key,
            processName=process_name,
            confidence=confidence,
            rationale=rationale,
            candidates=candidates
            or [
                {
                    "process_key": process_key,
                    "name": process_name,
                    "score": confidence,
                }
            ],
            **kwargs,
        )

    @staticmethod
    def create_slot_extraction_event(
        session_id: str | None = None,
        intent: str | None = "test_intent",
        slots: list[dict[str, Any]] | None = None,
        process_key: str | None = "test-process",
        **kwargs,
    ) -> dict[str, Any]:
        """Create a slot extraction event."""
        return EventFactory.create_base_event(
            session_id=session_id,
            event_type="slot_extraction",
            intent=intent,
            slots=slots
            or [
                {
                    "key": "customer_name",
                    "value": "John Doe",
                    "confidence": 0.9,
                }
            ],
            processKey=process_key,
            **kwargs,
        )

    @staticmethod
    def create_suggestion_event(
        session_id: str | None = None,
        suggestions: list[dict[str, Any]] | None = None,
        process_key: str | None = "test-process",
        step_key: str | None = "step1",
        **kwargs,
    ) -> dict[str, Any]:
        """Create a suggestion event."""
        return EventFactory.create_base_event(
            session_id=session_id,
            event_type="suggestion",
            suggestions=suggestions
            or [
                {
                    "type": "response",
                    "text": "Test suggestion",
                    "priority": 1,
                }
            ],
            processKey=process_key,
            stepKey=step_key,
            **kwargs,
        )

    @staticmethod
    def create_session_state_event(
        session_id: str | None = None,
        process_key: str | None = "test-process",
        process_name: str | None = "Test Process",
        current_step: str | None = "step1",
        steps: list[dict[str, Any]] | None = None,
        slots: dict[str, str] | None = None,
        status: str = "active",
        **kwargs,
    ) -> dict[str, Any]:
        """Create a session state event."""
        return EventFactory.create_base_event(
            session_id=session_id,
            event_type="session_state",
            processKey=process_key,
            processName=process_name,
            currentStep=current_step,
            steps=steps or [{"key": "step1", "label": "Step 1", "completed": False}],
            slots=slots or {},
            status=status,
            **kwargs,
        )


class TranscriptFactory:
    """Factory for creating transcript segment test data."""

    @staticmethod
    def create_transcript_segment(
        segment_id: str | None = None,
        session_id: str | None = None,
        speaker: str = "customer",
        text: str = "Hello, I need help",
        is_final: bool = True,
        confidence: float | None = 0.95,
        **kwargs,
    ) -> dict[str, Any]:
        """Create a transcript segment row.

        Args:
            segment_id: Optional segment ID
            session_id: Optional session ID
            speaker: Speaker identifier
            text: Transcript text
            is_final: Whether this is a final transcript
            confidence: Optional confidence score
            **kwargs: Additional fields

        Returns:
            Dictionary matching transcript_segments table structure
        """
        return {
            "id": segment_id or str(uuid4()),
            "session_id": session_id or str(uuid4()),
            "speaker": speaker,
            "text": text,
            "is_final": is_final,
            "confidence": confidence,
            "timestamp": kwargs.get(
                "timestamp",
                datetime.now(UTC).isoformat(),
            ),
        }


class SuggestionFactory:
    """Factory for creating suggestion test data."""

    @staticmethod
    def create_suggestion(
        suggestion_id: str | None = None,
        session_id: str | None = None,
        process_key: str = "test-process",
        step_key: str | None = "step1",
        suggestion_type: str = "response",
        suggestion_text: str = "Test suggestion",
        priority: int = 1,
        source: str = "kb_template",
        metadata: dict[str, Any] | None = None,
        **kwargs,
    ) -> dict[str, Any]:
        """Create a suggestion row.

        Args:
            suggestion_id: Optional suggestion ID
            session_id: Optional session ID
            process_key: Process identifier
            step_key: Optional step identifier
            suggestion_type: Type of suggestion
            suggestion_text: Suggestion content
            priority: Priority level
            source: Source of suggestion
            metadata: Optional metadata dict
            **kwargs: Additional fields

        Returns:
            Dictionary matching suggestions table structure
        """
        return {
            "id": suggestion_id or str(uuid4()),
            "session_id": session_id or str(uuid4()),
            "process_key": process_key,
            "step_key": step_key,
            "suggestion_type": suggestion_type,
            "suggestion_text": suggestion_text,
            "priority": priority,
            "source": source,
            "metadata": metadata or {},
            "created_at": kwargs.get(
                "created_at",
                datetime.now(UTC).isoformat(),
            ),
        }


class KBSnippetFactory:
    """Factory for creating KB snippet test data."""

    @staticmethod
    def create_kb_snippet(
        snippet_id: str | None = None,
        process_key: str = "test-process",
        step_key: str | None = "step1",
        template: str = "Hello {customer_name}, how can I help you?",
        snippet_type: str = "response",
        priority: int = 1,
        metadata: dict[str, Any] | None = None,
        **kwargs,
    ) -> dict[str, Any]:
        """Create a KB snippet row.

        Args:
            snippet_id: Optional snippet ID
            process_key: Process identifier
            step_key: Optional step identifier
            template: Template text with slot placeholders
            snippet_type: Type of snippet
            priority: Priority level
            metadata: Optional metadata dict
            **kwargs: Additional fields

        Returns:
            Dictionary matching kb_snippets table structure
        """
        return {
            "id": snippet_id or str(uuid4()),
            "process_key": process_key,
            "step_key": step_key,
            "template": template,
            "snippet_type": snippet_type,
            "priority": priority,
            "metadata": metadata or {},
            "created_at": kwargs.get(
                "created_at",
                datetime.now(UTC).isoformat(),
            ),
            "updated_at": kwargs.get(
                "updated_at",
                datetime.now(UTC).isoformat(),
            ),
        }
