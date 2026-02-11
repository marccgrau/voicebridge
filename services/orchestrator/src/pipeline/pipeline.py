"""VoiceBridge Pipecat pipeline."""

import asyncio

from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineTask

from src.config import settings
from src.utils.logging import get_session_logger

from .builder import VoiceBridgePipelineBuilder
from .direct_processors import DirectSuggestionProcessor, ProcessContextResolverProcessor
from .processors import TranscriptWriter


class VoiceBridgePipeline:
    """Main pipeline for VoiceBridge voice processing."""

    def __init__(
        self,
        session_id: str,
        room_url: str,
        room_token: str,
        enable_process_flow: bool = True,
        enable_suggestion_flow: bool = True,
        process_flow_provider: str | None = None,
        process_flow_model: str | None = None,
        suggestion_flow_provider: str | None = None,
        suggestion_flow_model: str | None = None,
        process_content_path: str = "process_content/",
    ):
        """Initialize the pipeline."""
        self.session_id = session_id
        self.room_url = room_url
        self.room_token = room_token
        self.enable_process_flow = enable_process_flow
        self.enable_suggestion_flow = enable_suggestion_flow
        self.process_flow_provider = process_flow_provider or settings.default_llm_provider
        self.process_flow_model = process_flow_model or settings.default_llm_model
        self.suggestion_flow_provider = suggestion_flow_provider or settings.default_llm_provider
        self.suggestion_flow_model = suggestion_flow_model or settings.default_llm_model
        self.process_content_path = process_content_path
        self._pipeline: Pipeline | None = None
        self._task: PipelineTask | None = None
        self._runner: PipelineRunner | None = None
        self._process_context_resolver: ProcessContextResolverProcessor | None = None
        self._direct_suggestion_processor: DirectSuggestionProcessor | None = None
        self._transcript_writer: TranscriptWriter | None = None

        self.logger = get_session_logger(__name__, session_id)

    async def start(self) -> None:
        """Start the pipeline."""
        self.logger.info(
            "Starting VoiceBridge pipeline (process_flow=%s, suggestion_flow=%s)",
            self.enable_process_flow,
            self.enable_suggestion_flow,
        )

        builder = VoiceBridgePipelineBuilder(
            session_id=self.session_id,
            room_url=self.room_url,
            room_token=self.room_token,
            enable_process_flow=self.enable_process_flow,
            enable_suggestion_flow=self.enable_suggestion_flow,
            process_flow_provider=self.process_flow_provider,
            process_flow_model=self.process_flow_model,
            suggestion_flow_provider=self.suggestion_flow_provider,
            suggestion_flow_model=self.suggestion_flow_model,
            process_content_path=self.process_content_path,
        )
        components = await builder.build()

        self._pipeline = components.pipeline
        self._task = components.task
        self._transcript_writer = components.transcript_writer
        self._process_context_resolver = components.process_context_resolver
        self._direct_suggestion_processor = components.direct_suggestion_processor

        @self._task.rtvi.event_handler("on_client_ready")
        async def on_client_ready(_rtvi):
            self.logger.info("RTVI client connected")

        self._runner = PipelineRunner()
        await self._runner.run(self._task)

    async def stop(self) -> None:
        """Stop the pipeline gracefully."""
        self.logger.info("Stopping VoiceBridge pipeline")

        errors = []

        if self._transcript_writer:
            try:
                await asyncio.wait_for(self._transcript_writer.stop(), timeout=5.0)
                self.logger.debug("TranscriptWriter stopped successfully")
            except TimeoutError:
                msg = "TranscriptWriter stop timed out"
                self.logger.warning(msg)
                errors.append(msg)
            except Exception as e:
                msg = f"TranscriptWriter stop failed: {e}"
                self.logger.warning(msg)
                errors.append(msg)

        for name, processor in [
            ("ProcessContextResolver", self._process_context_resolver),
            ("DirectSuggestionProcessor", self._direct_suggestion_processor),
        ]:
            if not processor:
                continue
            try:
                await asyncio.wait_for(processor.stop(), timeout=5.0)
                self.logger.debug("%s stopped successfully", name)
            except TimeoutError:
                msg = f"{name} stop timed out"
                self.logger.warning(msg)
                errors.append(msg)
            except Exception as e:
                msg = f"{name} stop failed: {e}"
                self.logger.warning(msg)
                errors.append(msg)

        if self._task:
            try:
                await asyncio.wait_for(self._task.cancel(), timeout=5.0)
                self.logger.debug("Pipeline task cancelled successfully")
            except TimeoutError:
                msg = "Pipeline task cancel timed out"
                self.logger.warning(msg)
                errors.append(msg)
            except Exception as e:
                msg = f"Pipeline task cancel failed: {e}"
                self.logger.warning(msg)
                errors.append(msg)

        if errors:
            self.logger.warning(
                "Pipeline stop completed with %d errors: %s",
                len(errors),
                "; ".join(errors),
            )
        else:
            self.logger.info("Pipeline stopped successfully")

    @property
    def is_running(self) -> bool:
        """Check if pipeline is running."""
        return self._task is not None and not self._task.cancelled()
