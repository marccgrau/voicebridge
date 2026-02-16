"""Pipeline processors for VoiceBridge transcript agent.

TranscriptWriter — converts STT transcriptions to TranscriptSegmentFrames.
TranscriptRTVIObserver — sends transcript frames via RTVI to the frontend.
"""

import logging
from datetime import UTC, datetime
from typing import Any

from pipecat.frames.frames import Frame, TranscriptionFrame
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor

from src.frames import TranscriptSegmentFrame

logger = logging.getLogger(__name__)


class TranscriptWriter(FrameProcessor):
    """Convert finalized STT transcriptions to TranscriptSegmentFrames.

    With customer-only audio, all transcriptions are from the customer.
    """

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
            transcript_frame = TranscriptSegmentFrame(
                session_id=self.session_id,
                speaker="customer",
                text=text,
                timestamp=timestamp,
                is_final=True,
            )
            await self.push_frame(transcript_frame, FrameDirection.DOWNSTREAM)
            return

        await self.push_frame(frame, direction)


class TranscriptRTVIObserver(FrameProcessor):
    """Publishes TranscriptSegmentFrames via RTVI to the frontend."""

    def __init__(self, rtvi_processor: Any, **kwargs):
        super().__init__(**kwargs)
        self._rtvi_processor = rtvi_processor

    async def process_frame(self, frame: Frame, direction: FrameDirection) -> None:
        await super().process_frame(frame, direction)

        if isinstance(frame, TranscriptSegmentFrame):
            await self._publish_transcript(frame)

        await self.push_frame(frame, direction)

    async def _publish_transcript(self, frame: TranscriptSegmentFrame) -> None:
        try:
            await self._rtvi_processor.send_server_message(
                {
                    "action": "transcript_segment",
                    "data": {
                        "sessionId": frame.session_id,
                        "speaker": frame.speaker,
                        "text": frame.text,
                        "timestamp": frame.timestamp,
                        "isFinal": frame.is_final,
                    },
                }
            )
            logger.debug(
                "Published transcript via RTVI: speaker=%s, text=%s",
                frame.speaker,
                frame.text[:50],
            )
        except Exception as e:
            logger.error("Failed to publish transcript via RTVI, dropping message: %s", e)
