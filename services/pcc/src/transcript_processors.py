"""Transcript branch processors for unified PCC service."""

import logging
from datetime import UTC, datetime

from pipecat.frames.frames import Frame, TranscriptionFrame
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor
from pipecat.processors.frameworks.rtvi import RTVIServerMessageFrame

logger = logging.getLogger(__name__)


class TranscriptWriter(FrameProcessor):
    """Convert finalized STT transcriptions to transcript RTVI messages."""

    def __init__(self, session_id: str, **kwargs):
        super().__init__(**kwargs)
        self.session_id = session_id

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
            return

        await self.push_frame(frame, direction)
