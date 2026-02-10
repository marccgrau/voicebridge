"""Repository port definitions for orchestrator services."""

from collections.abc import Sequence
from typing import Protocol, TypedDict


class TranscriptSegment(TypedDict):
    """Transcript segment shape used by summary generation."""

    speaker: str
    text: str
    ts: str


class SessionRepositoryPort(Protocol):
    """Session persistence interface."""

    def get_status(self, session_id: str) -> str | None:
        """Return session status or None when not found."""

    def update_summary(
        self,
        session_id: str,
        summary_text: str,
        updated_at: str,
        updated_by: str,
    ) -> None:
        """Persist session summary fields."""

    def mark_error(self, session_id: str, error_message: str, occurred_at: str) -> None:
        """Mark session as errored."""


class TranscriptRepositoryPort(Protocol):
    """Transcript persistence interface."""

    def insert_segment(self, session_id: str, speaker: str, text: str, timestamp: str) -> None:
        """Insert one transcript segment."""

    def list_segments(self, session_id: str) -> Sequence[TranscriptSegment]:
        """Return transcript segments in chronological order."""
