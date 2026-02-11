"""Simple processors for the pipeline."""

import asyncio
import logging
from contextlib import suppress
from datetime import UTC, datetime
from typing import Any

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
        self._write_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(
            maxsize=settings.transcript_write_queue_size
        )
        self._write_task: asyncio.Task | None = None

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

    def _ensure_writer_task(self) -> None:
        """Start background writer task lazily."""
        if self._write_task is None or self._write_task.done():
            self._write_task = asyncio.create_task(self._write_worker())

    def _enqueue_write(self, payload: dict[str, Any]) -> None:
        """Enqueue transcript write without blocking frame propagation."""
        self._ensure_writer_task()
        if self._write_queue.full():
            try:
                # Drop oldest pending write to keep hot path non-blocking.
                self._write_queue.get_nowait()
                self._write_queue.task_done()
                logger.warning(
                    "Transcript write queue full for session %s, dropped oldest pending write",
                    self.session_id,
                )
            except asyncio.QueueEmpty:
                pass
        try:
            self._write_queue.put_nowait(payload)
        except asyncio.QueueFull:
            logger.warning(
                "Transcript write queue still full for session %s, dropped newest write",
                self.session_id,
            )

    async def _write_worker(self) -> None:
        """Background worker that persists transcript writes with retries."""
        while True:
            payload = await self._write_queue.get()
            try:

                async def write_transcript(current_payload: dict[str, Any] = payload) -> None:
                    self.client.table("transcript_segments").insert(current_payload).execute()

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
                    payload["speaker"],
                    str(payload["text"])[:50],
                )
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.error(
                    "Failed to write transcript after %d retries for session %s: %s",
                    settings.db_write_max_retries,
                    self.session_id,
                    e,
                )
            finally:
                self._write_queue.task_done()

    async def flush_writes(self) -> None:
        """Wait until all queued transcript writes are processed."""
        await self._write_queue.join()

    async def stop(self) -> None:
        """Flush and stop background writer task."""
        await self.flush_writes()
        if self._write_task and not self._write_task.done():
            self._write_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._write_task

    async def process_frame(self, frame: Frame, direction: FrameDirection) -> None:
        """Process transcription frames.

        Args:
            frame: The frame to process
            direction: Frame direction
        """
        await super().process_frame(frame, direction)

        if isinstance(frame, TranscriptionFrame):
            # Resolve speaker from Speechmatics user_id
            speaker = self._resolve_speaker(getattr(frame, "user_id", None))

            # Stamp resolved role back onto frame for downstream processors
            frame.user_id = speaker

            # Emit transcript frame immediately (low-latency path).
            transcript_frame = TranscriptSegmentFrame(
                session_id=self.session_id,
                speaker=speaker,
                text=frame.text,
                timestamp=frame.timestamp or datetime.now(UTC).isoformat(),
                is_final=True,
            )
            await self.push_frame(transcript_frame, direction)

            # Persist transcript asynchronously in the background.
            self._enqueue_write(
                {
                    "session_id": self.session_id,
                    "speaker": speaker,
                    "text": frame.text,
                    "ts": frame.timestamp,
                }
            )

        # Always push frame downstream
        await self.push_frame(frame, direction)
