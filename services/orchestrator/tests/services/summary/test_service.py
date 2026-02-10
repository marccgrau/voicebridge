"""Tests for SessionSummaryService."""

from datetime import UTC, datetime

import pytest

from src.ports.repositories import TranscriptSegment
from src.services.summary.errors import (
    EmptySummaryError,
    EmptyTranscriptError,
    InvalidSessionStateError,
    SessionNotFoundError,
)
from src.services.summary.service import SessionSummaryService


class FakeClock:
    """Deterministic clock for tests."""

    def now_utc(self) -> datetime:
        return datetime(2026, 2, 9, 12, 0, 0, tzinfo=UTC)


class FakeSessionRepository:
    """In-memory session repository for tests."""

    def __init__(self, status_map: dict[str, str | None]):
        self.status_map = status_map
        self.updated_summaries: list[dict[str, str]] = []

    def get_status(self, session_id: str) -> str | None:
        return self.status_map.get(session_id)

    def update_summary(
        self,
        session_id: str,
        summary_text: str,
        updated_at: str,
        updated_by: str,
    ) -> None:
        self.updated_summaries.append(
            {
                "session_id": session_id,
                "summary_text": summary_text,
                "updated_at": updated_at,
                "updated_by": updated_by,
            }
        )

    def mark_error(self, session_id: str, error_message: str, occurred_at: str) -> None:
        raise NotImplementedError


class FakeTranscriptRepository:
    """In-memory transcript repository for tests."""

    def __init__(self, segments_by_session: dict[str, list[TranscriptSegment]]):
        self.segments_by_session = segments_by_session

    def insert_segment(self, session_id: str, speaker: str, text: str, timestamp: str) -> None:
        raise NotImplementedError

    def list_segments(self, session_id: str) -> list[TranscriptSegment]:
        return self.segments_by_session.get(session_id, [])


class FakeLlmSummary:
    """Stub LLM summary generator."""

    def __init__(self, output_text: str):
        self.output_text = output_text

    def generate_summary(self, segments: list[TranscriptSegment]) -> str:
        assert segments
        return self.output_text


class TestSessionSummaryService:
    """SessionSummaryService behavior tests."""

    def test_save_manual_summary_success(self):
        session_repo = FakeSessionRepository({"session-1": "completed"})
        transcript_repo = FakeTranscriptRepository({})
        service = SessionSummaryService(session_repo, transcript_repo, FakeClock())

        result = service.save_manual_summary("session-1", "  customer issue resolved  ")

        assert result.session_id == "session-1"
        assert result.summary_text == "customer issue resolved"
        assert result.updated_by == "agent"
        assert session_repo.updated_summaries[0]["summary_text"] == "customer issue resolved"

    def test_save_manual_summary_raises_on_empty_text(self):
        service = SessionSummaryService(
            FakeSessionRepository({"session-1": "completed"}),
            FakeTranscriptRepository({}),
            FakeClock(),
        )

        with pytest.raises(EmptySummaryError):
            service.save_manual_summary("session-1", "   ")

    def test_save_manual_summary_raises_on_non_terminal_status(self):
        service = SessionSummaryService(
            FakeSessionRepository({"session-1": "active"}),
            FakeTranscriptRepository({}),
            FakeClock(),
        )

        with pytest.raises(InvalidSessionStateError):
            service.save_manual_summary("session-1", "summary")

    def test_save_manual_summary_raises_when_session_missing(self):
        service = SessionSummaryService(
            FakeSessionRepository({}),
            FakeTranscriptRepository({}),
            FakeClock(),
        )

        with pytest.raises(SessionNotFoundError):
            service.save_manual_summary("missing", "summary")

    def test_generate_ai_summary_success(self):
        session_repo = FakeSessionRepository({"session-1": "completed"})
        transcript_repo = FakeTranscriptRepository(
            {
                "session-1": [
                    {"speaker": "customer", "text": "help", "ts": "2026-02-09T12:00:00+00:00"},
                    {"speaker": "agent", "text": "sure", "ts": "2026-02-09T12:00:05+00:00"},
                ]
            }
        )
        service = SessionSummaryService(
            session_repo,
            transcript_repo,
            FakeClock(),
            llm_summary_factory=lambda: FakeLlmSummary("AI summary text"),
        )

        result = service.generate_ai_summary("session-1")

        assert result.summary_text == "AI summary text"
        assert result.updated_by == "ai"
        assert session_repo.updated_summaries[0]["updated_by"] == "ai"

    def test_generate_ai_summary_raises_on_empty_transcript(self):
        service = SessionSummaryService(
            FakeSessionRepository({"session-1": "completed"}),
            FakeTranscriptRepository({"session-1": []}),
            FakeClock(),
            llm_summary_factory=lambda: FakeLlmSummary("unused"),
        )

        with pytest.raises(EmptyTranscriptError):
            service.generate_ai_summary("session-1")

    def test_generate_ai_summary_raises_on_non_terminal_status(self):
        service = SessionSummaryService(
            FakeSessionRepository({"session-1": "pending"}),
            FakeTranscriptRepository({}),
            FakeClock(),
        )

        with pytest.raises(InvalidSessionStateError):
            service.generate_ai_summary("session-1")
