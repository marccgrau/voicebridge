"""Supabase-backed repository adapter implementations."""

from collections.abc import Sequence
from typing import Any

from src.db import get_supabase_client
from src.ports.repositories import (
    SessionRepositoryPort,
    TranscriptRepositoryPort,
    TranscriptSegment,
)


class SupabaseSessionRepository(SessionRepositoryPort):
    """Session repository implemented with Supabase table operations."""

    def __init__(self, client: Any | None = None):
        self._client = client or get_supabase_client()

    def get_status(self, session_id: str) -> str | None:
        """Return session status or None when not found."""
        result = (
            self._client.table("sessions").select("status").eq("id", session_id).single().execute()
        )
        if not result.data:
            return None
        return result.data.get("status")

    def update_summary(
        self,
        session_id: str,
        summary_text: str,
        updated_at: str,
        updated_by: str,
    ) -> None:
        """Persist summary fields for one session."""
        self._client.table("sessions").update(
            {
                "summary_text": summary_text,
                "summary_updated_at": updated_at,
                "summary_updated_by": updated_by,
                "updated_at": updated_at,
            }
        ).eq("id", session_id).execute()

    def mark_error(self, session_id: str, error_message: str, occurred_at: str) -> None:
        """Mark session with error details."""
        self._client.table("sessions").update(
            {
                "status": "error",
                "error_message": error_message,
                "error_occurred_at": occurred_at,
                "updated_at": occurred_at,
            }
        ).eq("id", session_id).execute()


class SupabaseTranscriptRepository(TranscriptRepositoryPort):
    """Transcript repository implemented with Supabase table operations."""

    def __init__(self, client: Any | None = None):
        self._client = client or get_supabase_client()

    def insert_segment(self, session_id: str, speaker: str, text: str, timestamp: str) -> None:
        """Insert transcript segment row."""
        self._client.table("transcript_segments").insert(
            {
                "session_id": session_id,
                "speaker": speaker,
                "text": text,
                "ts": timestamp,
            }
        ).execute()

    def list_segments(self, session_id: str) -> Sequence[TranscriptSegment]:
        """Return transcript segments ordered by timestamp ascending."""
        result = (
            self._client.table("transcript_segments")
            .select("speaker, text, ts")
            .eq("session_id", session_id)
            .order("ts", desc=False)
            .execute()
        )
        return result.data or []
