"""VoiceBridge Pipecat pipeline."""

import asyncio

from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.audio.vad.vad_analyzer import VADParams
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.frameworks.rtvi import RTVIProcessor
from pipecat.services.anthropic.llm import AnthropicLLMService
from pipecat.services.speechmatics.stt import Language, SpeechmaticsSTTService, TurnDetectionMode
from pipecat.transports.daily.transport import DailyParams, DailyTransport
from pipecat_flows import FlowManager
from pipecat_flows.adapters import LLMContextAggregatorPair

from src.config import settings
from src.flows import ProcessFlow, SuggestionFlow
from src.rtvi import VoiceBridgeRTVIObserver
from src.utils.logging import get_session_logger

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
        process_flow_model: str = "claude-haiku-4-5-20251001",
        suggestion_flow_model: str = "claude-sonnet-4-5-20250929",
        process_content_path: str = "process_content/",
    ):
        """Initialize the pipeline.

        Args:
            session_id: Unique session identifier
            room_url: Daily.co room URL
            room_token: Daily.co room token
            enable_process_flow: Enable process detection and step tracking
            enable_suggestion_flow: Enable agent suggestion generation
            process_flow_model: Model for process flow (default: Haiku for speed)
            suggestion_flow_model: Model for suggestions (default: Sonnet for quality)
            process_content_path: Path to process markdown files
        """
        self.session_id = session_id
        self.room_url = room_url
        self.room_token = room_token
        self.enable_process_flow = enable_process_flow
        self.enable_suggestion_flow = enable_suggestion_flow
        self.process_flow_model = process_flow_model
        self.suggestion_flow_model = suggestion_flow_model
        self.process_content_path = process_content_path
        self._pipeline: Pipeline | None = None
        self._task: PipelineTask | None = None
        self._runner: PipelineRunner | None = None
        self._process_flow: ProcessFlow | None = None
        self._suggestion_flow: SuggestionFlow | None = None
        self._process_flow_manager: FlowManager | None = None
        self._suggestion_flow_manager: FlowManager | None = None

        # Session-scoped logger
        self.logger = get_session_logger(__name__, session_id)

    async def start(self) -> None:
        """Start the pipeline."""
        self.logger.info(
            "Starting VoiceBridge pipeline (process_flow=%s, suggestion_flow=%s)",
            self.enable_process_flow,
            self.enable_suggestion_flow,
        )

        # Configure VAD with responsive settings
        vad_params = VADParams(
            start_secs=0.2,  # Quick to detect speech start
            stop_secs=0.8,  # Wait before considering speech ended
        )

        # Initialize transport
        transport = DailyTransport(
            room_url=self.room_url,
            token=self.room_token,
            bot_name="VoiceBridge",
            params=DailyParams(
                audio_in_enabled=True,
                audio_out_enabled=False,  # Listen only
                vad_analyzer=SileroVADAnalyzer(params=vad_params),
                audio_in_filter=None,  # Accept audio from all participants
            ),
        )

        # Initialize STT with speaker diarization
        stt = SpeechmaticsSTTService(
            api_key=settings.speechmatics_api_key,
            url=settings.speechmatics_url,
            turn_detection_mode=TurnDetectionMode.EXTERNAL,
            params=SpeechmaticsSTTService.InputParams(
                language=Language.EN,
            ),
        )

        # Initialize transcript writer with speaker mapping
        transcript_writer = TranscriptWriter(
            session_id=self.session_id,
            first_speaker_role=settings.first_speaker_role,
        )

        # Create RTVI components
        rtvi_processor = RTVIProcessor()
        rtvi_observer = VoiceBridgeRTVIObserver(rtvi_processor)

        # Base processors (always needed)
        processors = [
            transport.input(),
            stt,
            transcript_writer,
        ]

        # Initialize ProcessFlow (optional)
        if self.enable_process_flow:
            self.logger.info("Initializing ProcessFlow (model: %s)", self.process_flow_model)

            # Create LLM service for ProcessFlow
            process_llm = AnthropicLLMService(
                api_key=settings.anthropic_api_key,
                model=self.process_flow_model,
            )

            # Create context aggregator pair for ProcessFlow FlowManager
            process_context = LLMContext()
            process_agg_pair = LLMContextAggregatorPair(process_context)

            # Create task for ProcessFlow FlowManager
            process_flow_pipeline = Pipeline(
                [process_agg_pair.user(), process_llm, process_agg_pair.assistant()]
            )
            process_task = PipelineTask(
                process_flow_pipeline,
                params=PipelineParams(
                    allow_interruptions=False,
                    enable_metrics=True,
                ),
                enable_rtvi=False,
            )

            # Initialize ProcessFlow FlowManager
            self._process_flow_manager = FlowManager(
                task=process_task,
                llm=process_llm,
                context_aggregator=process_agg_pair,
            )

            # Initialize ProcessFlow
            self._process_flow = ProcessFlow(
                session_id=self.session_id,
                flow_manager=self._process_flow_manager,
                process_content_path=self.process_content_path,
            )
            await self._process_flow.start()

            # Add ProcessFlow to main pipeline (no aggregators needed -
            # ProcessFlow handles TranscriptionFrames directly and uses
            # FlowManager's own pipeline for LLM calls)
            processors.append(self._process_flow)

        # Initialize SuggestionFlow (optional)
        if self.enable_suggestion_flow:
            self.logger.info("Initializing SuggestionFlow (model: %s)", self.suggestion_flow_model)

            # Create LLM service for SuggestionFlow
            suggestion_llm = AnthropicLLMService(
                api_key=settings.anthropic_api_key,
                model=self.suggestion_flow_model,
            )

            # Create context aggregator pair for SuggestionFlow FlowManager
            suggestion_context = LLMContext()
            suggestion_agg_pair = LLMContextAggregatorPair(suggestion_context)

            # Create task for SuggestionFlow FlowManager
            suggestion_flow_pipeline = Pipeline(
                [suggestion_agg_pair.user(), suggestion_llm, suggestion_agg_pair.assistant()]
            )
            suggestion_task = PipelineTask(
                suggestion_flow_pipeline,
                params=PipelineParams(
                    allow_interruptions=False,
                    enable_metrics=True,
                ),
                enable_rtvi=False,
            )

            # Initialize SuggestionFlow FlowManager
            self._suggestion_flow_manager = FlowManager(
                task=suggestion_task,
                llm=suggestion_llm,
                context_aggregator=suggestion_agg_pair,
            )

            # Initialize SuggestionFlow
            self._suggestion_flow = SuggestionFlow(
                session_id=self.session_id,
                flow_manager=self._suggestion_flow_manager,
            )
            await self._suggestion_flow.start()

            # Add SuggestionFlow to main pipeline (no aggregators needed -
            # SuggestionFlow handles frames directly and uses
            # FlowManager's own pipeline for LLM calls)
            processors.append(self._suggestion_flow)

        # Add RTVI observer and transport output at the end.
        # transport.output() is needed even though audio_out is disabled —
        # it handles the WebRTC data channel for RTVI messages.
        processors.append(rtvi_observer)
        processors.append(transport.output())

        # Build final pipeline
        self._pipeline = Pipeline(processors)

        # Create main task — pass rtvi_processor so PipelineTask uses our
        # instance (the same one the observer sends messages through)
        self._task = PipelineTask(
            self._pipeline,
            params=PipelineParams(
                allow_interruptions=False,
                enable_metrics=True,
            ),
            rtvi_processor=rtvi_processor,
        )

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
