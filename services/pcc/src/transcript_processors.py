"""Transcript branch processors for unified PCC service."""

import logging
from datetime import UTC, datetime

from pipecat.frames.frames import Frame, TranscriptionFrame
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor
from pipecat.processors.frameworks.rtvi import RTVIServerMessageFrame

logger = logging.getLogger(__name__)

_SPEAKER_PREFIXES = ("[Kunde] ", "[Berater] ")


class SpeakerLabelingProcessor(FrameProcessor):
    """Prefix TranscriptionFrame.text with [Kunde]/[Berater] based on speaker map.

    Sits between STT and ParallelPipeline so both LLM context aggregators
    see speaker-labeled text.
    """

    def __init__(self, speaker_map: dict[str, str], **kwargs):
        super().__init__(**kwargs)
        self._speaker_map = speaker_map

    async def process_frame(self, frame: Frame, direction: FrameDirection) -> None:
        await super().process_frame(frame, direction)

        if isinstance(frame, TranscriptionFrame):
            role = self._speaker_map.get(frame.user_id, "customer")
            label = "Kunde" if role == "customer" else "Berater"
            frame.text = f"[{label}] {frame.text}"

        await self.push_frame(frame, direction)


class TranscriptWriter(FrameProcessor):
    """Convert finalized STT transcriptions to transcript RTVI messages."""

    def __init__(self, session_id: str, speaker_map: dict[str, str] | None = None, **kwargs):
        super().__init__(**kwargs)
        self.session_id = session_id
        self._speaker_map = speaker_map or {}

    async def process_frame(self, frame: Frame, direction: FrameDirection) -> None:
        await super().process_frame(frame, direction)

        if isinstance(frame, TranscriptionFrame):
            text = (frame.text or "").strip()
            if not text:
                await self.push_frame(frame, direction)
                return

            # Strip speaker label prefix (added by SpeakerLabelingProcessor)
            for prefix in _SPEAKER_PREFIXES:
                if text.startswith(prefix):
                    text = text[len(prefix):]
                    break

            speaker = self._speaker_map.get(frame.user_id, "customer")
            timestamp = frame.timestamp or datetime.now(UTC).isoformat()
            rtvi_msg = RTVIServerMessageFrame(
                data={
                    "action": "transcript_segment",
                    "data": {
                        "sessionId": self.session_id,
                        "speaker": speaker,
                        "text": text,
                        "timestamp": timestamp,
                        "isFinal": True,
                    },
                }
            )
            await self.push_frame(rtvi_msg, FrameDirection.DOWNSTREAM)
            return

        await self.push_frame(frame, direction)
