"""Application service for session summary operations."""

from collections.abc import Callable

from src.llm.summary_service import SummaryService as LlmSummaryService
from src.ports.clock import ClockPort
from src.ports.repositories import SessionRepositoryPort, TranscriptRepositoryPort
from src.services.summary.contracts import SummaryResult
from src.services.summary.errors import (
    EmptySummaryError,
    EmptyTranscriptError,
    InvalidSessionStateError,
    SessionNotFoundError,
)

TERMINAL_STATUSES = {"completed", "abandoned", "escalated"}


class SessionSummaryService:
    """Coordinates summary business rules and persistence."""

    def __init__(
        self,
        session_repository: SessionRepositoryPort,
        transcript_repository: TranscriptRepositoryPort,
        clock: ClockPort,
        llm_summary_factory: Callable[[], LlmSummaryService] | None = None,
    ):
        self._session_repository = session_repository
        self._transcript_repository = transcript_repository
        self._clock = clock
        self._llm_summary_factory = llm_summary_factory or LlmSummaryService

    def save_manual_summary(
        self,
        session_id: str,
        summary_text: str,
        updated_by: str = "agent",
    ) -> SummaryResult:
        """Save/overwrite a manual summary for a terminal session."""
        cleaned_summary = summary_text.strip()
        if not cleaned_summary:
            raise EmptySummaryError("Summary text cannot be empty")

        session_status = self._session_repository.get_status(session_id)
        if session_status is None:
            raise SessionNotFoundError(f"Session {session_id} not found")
        if session_status not in TERMINAL_STATUSES:
            raise InvalidSessionStateError(
                "Summary can only be saved for terminal sessions "
                f"(completed/abandoned/escalated), current status: {session_status}"
            )

        now = self._clock.now_utc().isoformat()
        self._session_repository.update_summary(
            session_id=session_id,
            summary_text=cleaned_summary,
            updated_at=now,
            updated_by=updated_by,
        )

        return SummaryResult(
            session_id=session_id,
            summary_text=cleaned_summary,
            updated_at=now,
            updated_by=updated_by,
        )

    def generate_ai_summary(self, session_id: str) -> SummaryResult:
        """Generate and persist AI summary for a terminal session."""
        session_status = self._session_repository.get_status(session_id)
        if session_status is None:
            raise SessionNotFoundError(f"Session {session_id} not found")
        if session_status not in TERMINAL_STATUSES:
            raise InvalidSessionStateError(
                "Summary can only be generated for terminal sessions, "
                f"current status: {session_status}"
            )

        segments = list(self._transcript_repository.list_segments(session_id))
        if not segments:
            raise EmptyTranscriptError("No transcript segments found for this session")

        summary_generator = self._llm_summary_factory()
        summary_text = summary_generator.generate_summary(segments)

        now = self._clock.now_utc().isoformat()
        self._session_repository.update_summary(
            session_id=session_id,
            summary_text=summary_text,
            updated_at=now,
            updated_by="ai",
        )

        return SummaryResult(
            session_id=session_id,
            summary_text=summary_text,
            updated_at=now,
            updated_by="ai",
        )
