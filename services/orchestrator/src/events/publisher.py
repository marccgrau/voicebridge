"""Event publisher for Supabase Realtime channels."""

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from supabase import Client

from src.db import get_supabase_client

logger = logging.getLogger(__name__)


@dataclass
class Event:
    """Base event structure."""

    event_id: str
    session_id: str
    timestamp: str
    type: str
    data: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "eventId": self.event_id,
            "sessionId": self.session_id,
            "timestamp": self.timestamp,
            "type": self.type,
            **self.data,
        }


class EventPublisher:
    """Publishes events to Supabase Realtime channels.

    Events are broadcast on session-specific channels that the UI subscribes to.
    Channel pattern: session:{session_id}:events
    """

    def __init__(self, client: Client | None = None):
        """Initialize the publisher.

        Args:
            client: Optional Supabase client. Uses default if not provided.
        """
        self._client = client

    @property
    def client(self) -> Client:
        """Get the Supabase client."""
        if self._client is None:
            self._client = get_supabase_client()
        return self._client

    def _get_channel_name(self, session_id: str) -> str:
        """Get the channel name for a session."""
        return f"session:{session_id}:events"

    def _create_event(
        self,
        session_id: str,
        event_type: str,
        data: dict[str, Any],
    ) -> Event:
        """Create an event with metadata."""
        return Event(
            event_id=str(uuid4()),
            session_id=session_id,
            timestamp=datetime.now(UTC).isoformat(),
            type=event_type,
            data=data,
        )

    async def publish(
        self,
        session_id: str,
        event_type: str,
        data: dict[str, Any],
    ) -> Event:
        """Publish an event to the session channel.

        Args:
            session_id: The session ID to publish to
            event_type: Type of event (e.g., 'transcript_segment')
            data: Event data payload

        Returns:
            The created Event
        """
        event = self._create_event(session_id, event_type, data)
        channel_name = self._get_channel_name(session_id)

        logger.debug(
            "Publishing event: type=%s, session=%s",
            event_type,
            session_id,
        )

        # Broadcast via Supabase Realtime
        # Note: This uses the broadcast feature for real-time delivery
        channel = self.client.channel(channel_name)
        await channel.subscribe()
        await channel.send_broadcast(
            event="event",
            payload=event.to_dict(),
        )
        await channel.unsubscribe()

        return event

    async def publish_transcript_segment(
        self,
        session_id: str,
        speaker: str,
        text: str,
        is_final: bool,
        confidence: float | None = None,
    ) -> Event:
        """Publish a transcript segment event."""
        return await self.publish(
            session_id,
            "transcript_segment",
            {
                "speaker": speaker,
                "text": text,
                "isFinal": is_final,
                "confidence": confidence,
            },
        )

    async def publish_process_selection(
        self,
        session_id: str,
        process_key: str,
        process_name: str,
        confidence: float,
        rationale: str,
        candidates: list[dict[str, Any]],
    ) -> Event:
        """Publish a process selection event."""
        return await self.publish(
            session_id,
            "process_selection",
            {
                "processKey": process_key,
                "processName": process_name,
                "confidence": confidence,
                "rationale": rationale,
                "candidates": candidates,
            },
        )

    async def publish_slot_extraction(
        self,
        session_id: str,
        intent: str | None,
        slots: list[dict[str, Any]],
        process_key: str | None = None,
    ) -> Event:
        """Publish a slot extraction event."""
        return await self.publish(
            session_id,
            "slot_extraction",
            {
                "intent": intent,
                "slots": slots,
                "processKey": process_key,
            },
        )

    async def publish_suggestions(
        self,
        session_id: str,
        suggestions: list[dict[str, Any]],
        process_key: str | None = None,
        step_key: str | None = None,
    ) -> Event:
        """Publish a suggestions event."""
        return await self.publish(
            session_id,
            "suggestion",
            {
                "suggestions": suggestions,
                "processKey": process_key,
                "stepKey": step_key,
            },
        )

    async def publish_session_state(
        self,
        session_id: str,
        process_key: str | None,
        process_name: str | None,
        current_step: str | None,
        steps: list[dict[str, Any]],
        slots: dict[str, str],
        status: str,
    ) -> Event:
        """Publish a session state event."""
        return await self.publish(
            session_id,
            "session_state",
            {
                "processKey": process_key,
                "processName": process_name,
                "currentStep": current_step,
                "steps": steps,
                "slots": slots,
                "status": status,
            },
        )


# Module-level singleton
_publisher: EventPublisher | None = None


def get_event_publisher() -> EventPublisher:
    """Get the global event publisher instance."""
    global _publisher
    if _publisher is None:
        _publisher = EventPublisher()
    return _publisher
