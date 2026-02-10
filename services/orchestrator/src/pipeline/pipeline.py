"""VoiceBridge Pipecat pipeline."""

import asyncio

from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineTask
from pipecat_flows import FlowManager

from src.flows import ProcessFlow, SuggestionFlow
from src.utils.logging import get_session_logger

from .builder import VoiceBridgePipelineBuilder
from .processors import TranscriptWriter


class VoiceBridgePipeline:
    """Main pipeline for VoiceBridge voice processing.

    Orchestrates:
    - Daily.co WebRTC transport
    - Silero VAD with smart turn detection
    - Speechmatics STT with speaker diarization
    - Custom processors for process selection, slot extraction, suggestions
    """

    def __init__(
        self,
        session_id: str,
        room_url: str,
        room_token: str,
        enable_process_flow: bool = True,
        enable_suggestion_flow: bool = True,
        process_flow_provider: str = "openai",
        process_flow_model: str = "gpt-5-nano",
        suggestion_flow_provider: str = "openai",
        suggestion_flow_model: str = "gpt-5-nano",
        process_content_path: str = "process_content/",
    ):
        """Initialize the pipeline.

        Args:
            session_id: Unique session identifier
            room_url: Daily.co room URL
            room_token: Daily.co room token
            enable_process_flow: Enable process detection and step tracking
            enable_suggestion_flow: Enable agent suggestion generation
            process_flow_provider: LLM provider for process flow
            process_flow_model: Model for process flow
            suggestion_flow_provider: LLM provider for suggestion flow
            suggestion_flow_model: Model for suggestion flow
            process_content_path: Path to process markdown files
        """
        self.session_id = session_id
        self.room_url = room_url
        self.room_token = room_token
        self.enable_process_flow = enable_process_flow
        self.enable_suggestion_flow = enable_suggestion_flow
        self.process_flow_provider = process_flow_provider
        self.process_flow_model = process_flow_model
        self.suggestion_flow_provider = suggestion_flow_provider
        self.suggestion_flow_model = suggestion_flow_model
        self.process_content_path = process_content_path
        self._pipeline: Pipeline | None = None
        self._task: PipelineTask | None = None
        self._runner: PipelineRunner | None = None
        self._process_flow: ProcessFlow | None = None
        self._suggestion_flow: SuggestionFlow | None = None
        self._process_flow_manager: FlowManager | None = None
        self._suggestion_flow_manager: FlowManager | None = None
        self._transcript_writer: TranscriptWriter | None = None

        # Session-scoped logger
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
        self._process_flow = components.process_flow
        self._suggestion_flow = components.suggestion_flow
        self._process_flow_manager = components.process_flow_manager
        self._suggestion_flow_manager = components.suggestion_flow_manager

        # RTVI event handlers
        @self._task.rtvi.event_handler("on_client_ready")
        async def on_client_ready(_rtvi):
            self.logger.info("RTVI client connected")

        # Start FlowManager pipeline tasks in background
        # These tasks run the LLM pipelines that FlowManager queues frames into
        self._flow_tasks: list[asyncio.Task] = []
        if self._process_flow_manager:
            process_runner = PipelineRunner(handle_sigint=False)
            self._flow_tasks.append(
                asyncio.create_task(process_runner.run(self._process_flow_manager.task))
            )
        if self._suggestion_flow_manager:
            suggestion_runner = PipelineRunner(handle_sigint=False)
            self._flow_tasks.append(
                asyncio.create_task(suggestion_runner.run(self._suggestion_flow_manager.task))
            )

        # Create runner for main pipeline
        self._runner = PipelineRunner()

        # Run main pipeline (blocks until pipeline completes)
        await self._runner.run(self._task)

    async def stop(self) -> None:
        """Stop the pipeline gracefully.

        Each stop step is attempted independently with timeout.
        All steps are always attempted regardless of earlier failures.
        """
        self.logger.info("Stopping VoiceBridge pipeline")

        errors = []

        # Flush/cancel transcript writer background writes first
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

        # Stop ProcessFlow
        if self._process_flow:
            try:
                await asyncio.wait_for(self._process_flow.stop(), timeout=5.0)
                self.logger.debug("ProcessFlow stopped successfully")
            except TimeoutError:
                msg = "ProcessFlow stop timed out"
                self.logger.warning(msg)
                errors.append(msg)
            except Exception as e:
                msg = f"ProcessFlow stop failed: {e}"
                self.logger.warning(msg)
                errors.append(msg)

        # Stop SuggestionFlow
        if self._suggestion_flow:
            try:
                await asyncio.wait_for(self._suggestion_flow.stop(), timeout=5.0)
                self.logger.debug("SuggestionFlow stopped successfully")
            except TimeoutError:
                msg = "SuggestionFlow stop timed out"
                self.logger.warning(msg)
                errors.append(msg)
            except Exception as e:
                msg = f"SuggestionFlow stop failed: {e}"
                self.logger.warning(msg)
                errors.append(msg)

        # Cancel pipeline task
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

        # Stop flow manager pipeline tasks
        for name, fm in [
            ("ProcessFlow", self._process_flow_manager),
            ("SuggestionFlow", self._suggestion_flow_manager),
        ]:
            if fm and fm.task:
                try:
                    await asyncio.wait_for(fm.task.cancel(), timeout=5.0)
                    self.logger.debug("%s FlowManager task cancelled successfully", name)
                except TimeoutError:
                    msg = f"{name} FlowManager task cancel timed out"
                    self.logger.warning(msg)
                    errors.append(msg)
                except Exception as e:
                    msg = f"{name} FlowManager task cancel failed: {e}"
                    self.logger.warning(msg)
                    errors.append(msg)

        # Cancel background asyncio tasks for flow runners
        for task in getattr(self, "_flow_tasks", []):
            if not task.done():
                task.cancel()

        # Log summary
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
