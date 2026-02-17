"""Transcript branch processors for unified PCC service."""

import logging
from datetime import UTC, datetime

from pipecat.frames.frames import CancelFrame, EndFrame, Frame, TranscriptionFrame
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor, FrameProcessorSetup
from pipecat.processors.frameworks.rtvi import RTVIServerMessageFrame

from src.transcript_persistence import TranscriptPersistenceWorker

logger = logging.getLogger(__name__)


class TranscriptWriter(FrameProcessor):
    """Convert finalized STT transcriptions to transcript RTVI messages."""

    def __init__(
        self,
        session_id: str,
        persistence: TranscriptPersistenceWorker | None = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.session_id = session_id
        self._persistence = persistence

    async def setup(self, setup: FrameProcessorSetup) -> None:
        await super().setup(setup)
        if self._persistence:
            await self._persistence.start()

    async def cleanup(self) -> None:
        if self._persistence:
            await self._persistence.shutdown()
        await super().cleanup()

    async def process_frame(self, frame: Frame, direction: FrameDirection) -> None:
        await super().process_frame(frame, direction)

        if isinstance(frame, TranscriptionFrame):
            text = (frame.text or "").strip()
            if not text:
                await self.push_frame(frame, direction)
                return

            timestamp = frame.timestamp or datetime.now(UTC).isoformat()
            rtvi_msg = RTVIServerMessageFrame(
                data={
                    "action": "transcript_segment",
                    "data": {
                        "sessionId": self.session_id,
                        "speaker": "customer",
                        "text": text,
                        "timestamp": timestamp,
                        "isFinal": True,
                    },
                }
            )
            await self.push_frame(rtvi_msg, FrameDirection.DOWNSTREAM)

            if self._persistence:
                self._persistence.enqueue(
                    {
                        "session_id": self.session_id,
                        "speaker": "customer",
                        "text": text,
                        "is_final": True,
                        "ts": timestamp,
                    }
                )
            return

        if isinstance(frame, (EndFrame, CancelFrame)) and self._persistence:
            await self._persistence.flush(timeout_seconds=2.0)

        await self.push_frame(frame, direction)
