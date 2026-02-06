"""Simple processors for the pipeline."""

import logging
from datetime import UTC, datetime

from pipecat.frames.frames import Frame, TranscriptionFrame
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor

from src.config import settings
from src.db import get_supabase_client
from src.frames import TranscriptSegmentFrame
from src.utils.retry import retry_async

logger = logging.getLogger(__name__)


class TranscriptWriter(FrameProcessor):
    """Write transcription frames to database with speaker diarization."""

    def __init__(self, session_id: str, first_speaker_role: str = "customer", **kwargs):
        """Initialize transcript writer.

        Args:
            session_id: Session ID
            first_speaker_role: Role to assign to first speaker (default: "customer")
        """
        super().__init__(**kwargs)
        self.session_id = session_id
        self.first_speaker_role = first_speaker_role
        self._speaker_map: dict[str, str] = {}
        self._client = None

    @property
    def client(self):
        """Get Supabase client lazily."""
        if self._client is None:
            self._client = get_supabase_client()
        return self._client

    def _resolve_speaker(self, raw_id: str | None) -> str:
        """Map raw Speechmatics speaker ID to agent/customer role.

        Args:
            raw_id: Raw speaker ID from Speechmatics (e.g., "S1", "S2")

        Returns:
            Resolved role ("agent" or "customer")
        """
        speaker_id = raw_id or "unknown"
        if speaker_id not in self._speaker_map:
            if not self._speaker_map:
                # First speaker seen - assign configured role
                self._speaker_map[speaker_id] = self.first_speaker_role
            else:
                # Subsequent speaker - assign opposite role
                self._speaker_map[speaker_id] = (
                    "agent" if self.first_speaker_role == "customer" else "customer"
                )
        return self._speaker_map[speaker_id]

    async def process_frame(self, frame: Frame, direction: FrameDirection) -> None:
        """Process transcription frames.

        Args:
            frame: The frame to process
            direction: Frame direction
        """
        await super().process_frame(frame, direction)

        if isinstance(frame, TranscriptionFrame) and frame.finalized:
            # Resolve speaker from Speechmatics user_id
            speaker = self._resolve_speaker(getattr(frame, "user_id", None))

            # Stamp resolved role back onto frame for downstream processors
            frame.user_id = speaker

            # Write to database with retry
            async def write_transcript():
                self.client.table("transcript_segments").insert(
                    {
                        "session_id": self.session_id,
                        "speaker": speaker,
                        "text": frame.text,
                        "ts": frame.timestamp,
                    }
                ).execute()

            try:
                await retry_async(
                    write_transcript,
                    max_retries=settings.db_write_max_retries,
                    base_delay=settings.db_write_retry_delay,
                    exponential=True,
                    on_retry=lambda attempt, exc: logger.warning(
                        "DB write retry %d/%d for session %s: %s",
                        attempt,
                        settings.db_write_max_retries,
                        self.session_id,
                        exc,
                    ),
                )

                logger.debug(
                    "Wrote transcript for session %s [%s]: %s",
                    self.session_id,
                    speaker,
                    frame.text[:50],
                )

                # Emit TranscriptSegmentFrame for RTVI delivery to frontend
                transcript_frame = TranscriptSegmentFrame(
                    session_id=self.session_id,
                    speaker=speaker,
                    text=frame.text,
                    timestamp=frame.timestamp or datetime.now(UTC).isoformat(),
                    is_final=True,
                )
                await self.push_frame(transcript_frame, direction)

            except Exception as e:
                # Log error but never raise - always push frame downstream
                logger.error(
                    "Failed to write transcript after %d retries for session %s: %s",
                    settings.db_write_max_retries,
                    self.session_id,
                    e,
                )

        # Always push frame downstream
        await self.push_frame(frame, direction)
