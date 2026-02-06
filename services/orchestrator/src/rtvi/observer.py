"""Custom RTVI observer for VoiceBridge."""

import logging
from typing import Any

from pipecat.frames.frames import Frame
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor

from src.config import settings
from src.frames import ProcessIllustrationFrame, SuggestionFrame, TranscriptSegmentFrame
from src.utils.retry import retry_async

logger = logging.getLogger(__name__)


class VoiceBridgeRTVIObserver(FrameProcessor):
    """Custom observer to publish suggestions and process events via RTVI.

    This processor intercepts custom VoiceBridge frames and sends them
    through RTVI for low-latency delivery to the frontend.
    """

    def __init__(self, rtvi_processor: Any, **kwargs):
        """Initialize the observer.

        Args:
            rtvi_processor: RTVIProcessor instance for sending messages
        """
        super().__init__(**kwargs)
        self._rtvi_processor = rtvi_processor

    async def process_frame(self, frame: Frame, direction: FrameDirection) -> None:
        """Process incoming frames and intercept custom frames.

        Args:
            frame: The frame to process
            direction: Frame direction (upstream/downstream)
        """
        await super().process_frame(frame, direction)

        # Intercept custom frames and send via RTVI
        if isinstance(frame, SuggestionFrame):
            await self._publish_suggestions(frame)
        elif isinstance(frame, ProcessIllustrationFrame):
            await self._publish_process_illustration(frame)
        elif isinstance(frame, TranscriptSegmentFrame):
            await self._publish_transcript(frame)

        # Always pass the frame through
        await self.push_frame(frame, direction)

    async def _publish_suggestions(self, frame: SuggestionFrame) -> None:
        """Send suggestions through RTVI channel with retry.

        Args:
            frame: The suggestion frame to publish
        """

        async def send_message():
            await self._rtvi_processor.send_server_message(
                {
                    "action": "agent_guidance",
                    "data": {
                        "suggestions": frame.suggestions,
                        "serviceType": frame.service_type,
                        "triggerTurn": frame.trigger_turn,
                        "latencyMs": frame.latency_ms,
                        "processKey": frame.process_key,
                        "toolsUsed": frame.tools_used,
                    },
                }
            )

        try:
            await retry_async(
                send_message,
                max_retries=settings.rtvi_max_retries,
                base_delay=0.2,
                exponential=False,
                on_retry=lambda attempt, exc: logger.warning(
                    "RTVI suggestion retry %d/%d: %s",
                    attempt,
                    settings.rtvi_max_retries,
                    exc,
                ),
            )
            logger.info(
                "Published suggestions via RTVI: service=%s, count=%d",
                frame.service_type,
                len(frame.suggestions),
            )
        except Exception as e:
            logger.error(
                "Failed to publish suggestions via RTVI after %d retries: %s",
                settings.rtvi_max_retries,
                e,
            )

    async def _publish_process_illustration(self, frame: ProcessIllustrationFrame) -> None:
        """Send process illustration through RTVI channel with retry.

        Args:
            frame: The process illustration frame to publish
        """

        async def send_message():
            await self._rtvi_processor.send_server_message(
                {
                    "action": "process_illustration",
                    "data": {
                        "processKey": frame.process_key,
                        "processName": frame.process_name,
                        "steps": frame.steps,
                        "currentStep": frame.current_step,
                        "content": frame.content,
                    },
                }
            )

        try:
            await retry_async(
                send_message,
                max_retries=settings.rtvi_max_retries,
                base_delay=0.2,
                exponential=False,
                on_retry=lambda attempt, exc: logger.warning(
                    "RTVI process illustration retry %d/%d: %s",
                    attempt,
                    settings.rtvi_max_retries,
                    exc,
                ),
            )
            logger.info(
                "Published process illustration via RTVI: process=%s",
                frame.process_key,
            )
        except Exception as e:
            logger.error(
                "Failed to publish process illustration via RTVI after %d retries: %s",
                settings.rtvi_max_retries,
                e,
            )

    async def _publish_transcript(self, frame: TranscriptSegmentFrame) -> None:
        """Send transcript segment through RTVI channel with retry.

        Args:
            frame: The transcript segment frame to publish
        """

        async def send_message():
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

        try:
            await retry_async(
                send_message,
                max_retries=settings.rtvi_max_retries,
                base_delay=0.2,
                exponential=False,
                on_retry=lambda attempt, exc: logger.warning(
                    "RTVI transcript retry %d/%d: %s",
                    attempt,
                    settings.rtvi_max_retries,
                    exc,
                ),
            )
            logger.debug(
                "Published transcript via RTVI: speaker=%s, text=%s",
                frame.speaker,
                frame.text[:50],
            )
        except Exception as e:
            logger.error(
                "Failed to publish transcript via RTVI after %d retries: %s",
                settings.rtvi_max_retries,
                e,
            )
