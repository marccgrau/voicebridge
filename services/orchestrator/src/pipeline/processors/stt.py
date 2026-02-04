"""Speech-to-text transcript writer processor."""

import logging
from datetime import UTC, datetime

from pipecat.frames.frames import Frame, TranscriptionFrame
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor

from src.db import get_supabase_client
from src.events import get_event_publisher

logger = logging.getLogger(__name__)


class TranscriptWriter(FrameProcessor):
    """Processor that writes transcript segments to Supabase and publishes events.

    Receives TranscriptionFrame from Deepgram STT and:
    1. Persists to transcript_segments table
    2. Publishes real-time event to UI
    """

    def __init__(
        self,
        session_id: str,
        speaker: str = "customer",
        **kwargs,
    ):
        """Initialize transcript writer.

        Args:
            session_id: The session ID for this pipeline
            speaker: Default speaker label ('customer' or 'agent')
        """
        super().__init__(**kwargs)
        self.session_id = session_id
        self.speaker = speaker
        self._client = None
        self._publisher = None

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
        """Process incoming frames for transcription."""
        await super().process_frame(frame, direction)

        if isinstance(frame, TranscriptionFrame):
            await self._handle_transcription(frame)

        await self.push_frame(frame, direction)

    async def _handle_transcription(self, frame: TranscriptionFrame) -> None:
        """Handle a transcription frame.

        Args:
            frame: The transcription frame from STT
        """
        text = frame.text.strip()
        if not text:
            return

        # Deepgram provides is_final in the frame
        is_final = getattr(frame, "is_final", True)

        logger.debug(
            "Transcript: speaker=%s, is_final=%s, text=%r",
            self.speaker,
            is_final,
            text[:100],
        )

        # Persist to database (only final transcripts)
        if is_final:
            try:
                self.client.table("transcript_segments").insert(
                    {
                        "session_id": self.session_id,
                        "speaker": self.speaker,
                        "text": text,
                        "is_final": is_final,
                        "ts": datetime.now(UTC).isoformat(),
                    }
                ).execute()
            except Exception as e:
                logger.error("Failed to persist transcript: %s", e)

        # Publish real-time event
        try:
            await self.publisher.publish_transcript_segment(
                session_id=self.session_id,
                speaker=self.speaker,
                text=text,
                is_final=is_final,
            )
        except Exception as e:
            logger.error("Failed to publish transcript event: %s", e)
