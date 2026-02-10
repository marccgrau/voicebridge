"""Pipecat adapter for process detection and step tracking service."""

import asyncio
import logging
from pathlib import Path

from pipecat.frames.frames import Frame, TranscriptionFrame
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor
from pipecat_flows import FlowArgs, FlowManager, FlowResult, FlowsFunctionSchema, NodeConfig

from src.config import settings
from src.services.process import ProcessService
from src.utils.logging import get_session_logger


async def load_process_catalog(
    process_path: Path,
    logger: logging.Logger | logging.LoggerAdapter,
):
    """Compatibility shim for legacy import paths."""
    return await ProcessService().load_process_catalog(process_path, logger)


class ProcessFlow(FrameProcessor):
    """Process detection and step tracking flow adapter."""

    def __init__(
        self,
        session_id: str,
        flow_manager: FlowManager,
        process_content_path: str,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.session_id = session_id
        self.flow_manager = flow_manager
        self.process_path = Path(process_content_path)
        self.service = ProcessService(conversation_window_size=settings.conversation_window_size)

        self.logger = get_session_logger(__name__, session_id)

        self.select_process_schema = FlowsFunctionSchema(
            name="select_process",
            description="Select the matching process based on customer intent",
            properties={
                "process_key": {
                    "type": "string",
                    "description": "Key of the selected process",
                },
                "confidence": {
                    "type": "number",
                    "description": "Confidence score (0-1)",
                },
                "rationale": {
                    "type": "string",
                    "description": "Why this process was selected",
                },
            },
            required=["process_key", "confidence"],
            handler=self._handle_select_process,
        )
        self.need_more_context_schema = FlowsFunctionSchema(
            name="need_more_context",
            description="Return to listening if no confident process match found",
            properties={
                "reason": {
                    "type": "string",
                    "description": "Why more context is needed",
                },
            },
            required=["reason"],
            handler=self._handle_need_more_context,
        )
        self.update_step_schema = FlowsFunctionSchema(
            name="update_step",
            description="Update current step based on conversation progress",
            properties={
                "step_number": {
                    "type": "number",
                    "description": "New step number (1-indexed)",
                },
                "rationale": {
                    "type": "string",
                    "description": "Why this step was selected",
                },
            },
            required=["step_number"],
            handler=self._handle_update_step,
        )

    async def start(self) -> None:
        """Start the flow."""
        self.logger.info("Starting ProcessFlow")

        processes = await self.service.load_process_catalog(self.process_path, self.logger)
        self.flow_manager.state.update(self.service.initial_state(processes))
        await self.flow_manager.initialize(self.service.create_idle_node())

        self.logger.info("ProcessFlow loaded %d processes", len(processes))

    async def stop(self) -> None:
        """Stop the flow."""
        self.logger.info("Stopping ProcessFlow")

    async def process_frame(self, frame: Frame, direction: FrameDirection) -> None:
        """Process transcription frames and drive process nodes."""
        await super().process_frame(frame, direction)

        if isinstance(frame, TranscriptionFrame) and frame.finalized:
            self.logger.debug("ProcessFlow processing: %s", frame.text)

            try:
                speaker = getattr(frame, "user_id", "unknown")
                phase, next_node = self.service.handle_transcription(
                    state=self.flow_manager.state,
                    speaker=speaker,
                    text=frame.text,
                    current_node=self.flow_manager.current_node,
                    select_process_schema=self.select_process_schema,
                    need_more_context_schema=self.need_more_context_schema,
                    update_step_schema=self.update_step_schema,
                )

                if next_node:
                    try:
                        await asyncio.wait_for(
                            self.flow_manager.set_node_from_config(next_node),
                            timeout=settings.llm_timeout,
                        )
                    except TimeoutError:
                        timeout_phase = phase or "unknown"
                        self.logger.error("ProcessFlow LLM timeout (%s)", timeout_phase)

            except Exception as e:
                self.logger.error("Error in ProcessFlow: %s", e)

        await self.push_frame(frame, direction)

    async def _handle_select_process(self, args: FlowArgs) -> tuple[FlowResult, NodeConfig]:
        """Handle process selection callback."""
        result, next_node, illustration_frame = self.service.handle_select_process(
            args=args,
            state=self.flow_manager.state,
            update_step_schema=self.update_step_schema,
            logger=self.logger,
        )

        if illustration_frame:
            await self.push_frame(illustration_frame)

        return result, next_node

    async def _handle_need_more_context(self, args: FlowArgs) -> tuple[FlowResult, NodeConfig]:
        """Handle need-more-context callback."""
        return self.service.handle_need_more_context(args=args, logger=self.logger)

    async def _handle_update_step(self, args: FlowArgs) -> tuple[FlowResult, NodeConfig]:
        """Handle step update callback."""
        result, next_node, illustration_frame = self.service.handle_update_step(
            args=args,
            state=self.flow_manager.state,
            update_step_schema=self.update_step_schema,
            logger=self.logger,
        )

        if illustration_frame:
            await self.push_frame(illustration_frame)

        return result, next_node
