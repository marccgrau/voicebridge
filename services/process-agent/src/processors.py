"""Pipeline processors for VoiceBridge process agent.

TranscriptWriter — converts STT transcriptions to TranscriptSegmentFrames.
ProcessContextBuilder — accumulates transcript, pushes LLMContextFrame on customer utterances.
ProcessOutputProcessor — consumes LLM frames, emits ProcessIllustrationFrame from tool calls.
ProcessRTVIObserver — sends ProcessIllustrationFrame via RTVI to the frontend.
"""

import logging
from datetime import UTC, datetime
from typing import Any

from pipecat.frames.frames import (
    Frame,
    LLMContextFrame,
    LLMFullResponseEndFrame,
    LLMFullResponseStartFrame,
    LLMTextFrame,
    TranscriptionFrame,
)
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor

from src.frames import ProcessIllustrationFrame, TranscriptSegmentFrame

logger = logging.getLogger(__name__)

PROCESS_SYSTEM_PROMPT = (
    "You are a process identification agent for a customer service call center. "
    "Analyze the customer conversation and identify which business process is being discussed. "
    "Use the list_processes tool to see available processes, "
    "get_process_details to inspect a specific process, "
    "and report_process_status to report your finding with the current step. "
    "Be fast and decisive. Always call report_process_status when you identify a process."
)


class TranscriptWriter(FrameProcessor):
    """Convert finalized STT transcriptions to TranscriptSegmentFrames."""

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


class ProcessContextBuilder(FrameProcessor):
    """Accumulates conversation from TranscriptSegmentFrames and pushes LLMContextFrame.

    On each customer utterance, pushes an LLMContextFrame with the system prompt
    and current conversation transcript. Consumes TranscriptSegmentFrame (does not
    pass downstream).
    """

    def __init__(self, session_id: str, **kwargs):
        super().__init__(**kwargs)
        self.session_id = session_id
        self._conversation_lines: list[str] = []

    async def process_frame(self, frame: Frame, direction: FrameDirection) -> None:
        await super().process_frame(frame, direction)

        if isinstance(frame, TranscriptSegmentFrame):
            self._conversation_lines.append(f"[{frame.speaker}]: {frame.text}")
            if frame.speaker == "customer":
                context = self._build_llm_context()
                await self.push_frame(LLMContextFrame(context=context), direction)
            # Consumed — not passed downstream
            return

        await self.push_frame(frame, direction)

    def _build_llm_context(self) -> LLMContext:
        conversation_text = "\n".join(self._conversation_lines) or "(waiting)"
        return LLMContext(
            messages=[
                {"role": "system", "content": PROCESS_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": (
                        f"Current conversation:\n{conversation_text}\n\n"
                        "Identify the business process and current step."
                    ),
                },
            ]
        )


class ProcessOutputProcessor(FrameProcessor):
    """Listens for tool call results and emits ProcessIllustrationFrame.

    The report_process_status tool handler stores detected process state on this
    processor. When the LLM response ends, if a process was reported, emit a
    ProcessIllustrationFrame. Consumes all LLM text frames (only tool calls matter).
    """

    def __init__(self, session_id: str, **kwargs):
        super().__init__(**kwargs)
        self.session_id = session_id
        self._pending_illustration: ProcessIllustrationFrame | None = None
        self._in_response = False

    def set_pending_illustration(self, frame: ProcessIllustrationFrame) -> None:
        """Called by the report_process_status tool handler."""
        self._pending_illustration = frame

    async def process_frame(self, frame: Frame, direction: FrameDirection) -> None:
        await super().process_frame(frame, direction)

        if isinstance(frame, LLMFullResponseStartFrame):
            self._in_response = True
            return

        if isinstance(frame, LLMTextFrame) and self._in_response:
            # Consume LLM text — only tool calls matter
            return

        if isinstance(frame, LLMFullResponseEndFrame):
            self._in_response = False
            if self._pending_illustration:
                await self.push_frame(self._pending_illustration, direction)
                self._pending_illustration = None
            return

        await self.push_frame(frame, direction)


class ProcessRTVIObserver(FrameProcessor):
    """Publishes ProcessIllustrationFrames via RTVI to the frontend.

    Only handles process_illustration — does NOT publish transcript segments.
    """

    def __init__(self, rtvi_processor: Any, **kwargs):
        super().__init__(**kwargs)
        self._rtvi_processor = rtvi_processor

    async def process_frame(self, frame: Frame, direction: FrameDirection) -> None:
        await super().process_frame(frame, direction)

        if isinstance(frame, ProcessIllustrationFrame):
            await self._publish_process_illustration(frame)

        await self.push_frame(frame, direction)

    async def _publish_process_illustration(self, frame: ProcessIllustrationFrame) -> None:
        try:
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
            logger.info("Published process illustration via RTVI: process=%s", frame.process_key)
        except Exception as e:
            logger.error(
                "Failed to publish process illustration via RTVI, dropping message: %s", e
            )
