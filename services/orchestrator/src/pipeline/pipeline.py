"""VoiceBridge Pipecat pipeline."""

import logging
from typing import Any

from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.audio.vad.vad_analyzer import VADParams
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response import (
    LLMAssistantContextAggregator,
    LLMUserContextAggregator,
)
from pipecat.processors.frameworks.rtvi import RTVIProcessor
from pipecat.services.anthropic.llm import AnthropicLLMService
from pipecat.services.speechmatics.stt import Language, SpeechmaticsSTTService, TurnDetectionMode
from pipecat.transports.daily.transport import DailyParams, DailyTransport
from pipecat_flows import FlowManager

from src.config import settings
from src.flows import ProcessFlow, SuggestionFlow
from src.rtvi import VoiceBridgeRTVIObserver

from .processors import TranscriptWriter

logger = logging.getLogger(__name__)


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
        anthropic_client: Any,
        enable_process_flow: bool = True,
        enable_suggestion_flow: bool = True,
        process_flow_model: str = "claude-3-5-haiku-20241022",
        suggestion_flow_model: str = "claude-sonnet-4-20250514",
        process_content_path: str = "process_content/",
    ):
        """Initialize the pipeline.

        Args:
            session_id: Unique session identifier
            room_url: Daily.co room URL
            room_token: Daily.co room token
            anthropic_client: Anthropic client for LLM operations
            enable_process_flow: Enable process detection and step tracking
            enable_suggestion_flow: Enable agent suggestion generation
            process_flow_model: Model for process flow (default: Haiku for speed)
            suggestion_flow_model: Model for suggestions (default: Sonnet for quality)
            process_content_path: Path to process markdown files
        """
        self.session_id = session_id
        self.room_url = room_url
        self.room_token = room_token
        self.anthropic = anthropic_client
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

    async def start(self) -> None:
        """Start the pipeline."""
        logger.info(
            "Starting VoiceBridge pipeline for session %s (process_flow=%s, suggestion_flow=%s)",
            self.session_id,
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
                vad_enabled=True,
                vad_analyzer=SileroVADAnalyzer(params=vad_params),
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
            logger.info("Initializing ProcessFlow (model: %s)", self.process_flow_model)

            # Create LLM service for ProcessFlow
            process_llm = AnthropicLLMService(
                api_key=settings.anthropic_api_key,
                model=self.process_flow_model,
            )

            # Create context aggregators for ProcessFlow
            process_context = LLMContext()
            process_user_agg = LLMUserContextAggregator(process_context)
            process_asst_agg = LLMAssistantContextAggregator(process_context)

            # Create task for ProcessFlow FlowManager
            temp_pipeline = Pipeline([])
            process_task = PipelineTask(
                temp_pipeline,
                params=PipelineParams(
                    allow_interruptions=False,
                    enable_metrics=True,
                ),
            )

            # Initialize ProcessFlow FlowManager
            self._process_flow_manager = FlowManager(
                task=process_task,
                llm=process_llm,
                context_aggregator=process_user_agg,
            )

            # Initialize ProcessFlow
            self._process_flow = ProcessFlow(
                session_id=self.session_id,
                flow_manager=self._process_flow_manager,
                process_content_path=self.process_content_path,
            )
            await self._process_flow.start()

            # Add to processor chain
            processors.extend(
                [
                    process_user_agg,
                    self._process_flow,
                    process_asst_agg,
                ]
            )

        # Initialize SuggestionFlow (optional)
        if self.enable_suggestion_flow:
            logger.info("Initializing SuggestionFlow (model: %s)", self.suggestion_flow_model)

            # Create LLM service for SuggestionFlow
            suggestion_llm = AnthropicLLMService(
                api_key=settings.anthropic_api_key,
                model=self.suggestion_flow_model,
            )

            # Create context aggregators for SuggestionFlow
            suggestion_context = LLMContext()
            suggestion_user_agg = LLMUserContextAggregator(suggestion_context)
            suggestion_asst_agg = LLMAssistantContextAggregator(suggestion_context)

            # Create task for SuggestionFlow FlowManager
            temp_pipeline = Pipeline([])
            suggestion_task = PipelineTask(
                temp_pipeline,
                params=PipelineParams(
                    allow_interruptions=False,
                    enable_metrics=True,
                ),
            )

            # Initialize SuggestionFlow FlowManager
            self._suggestion_flow_manager = FlowManager(
                task=suggestion_task,
                llm=suggestion_llm,
                context_aggregator=suggestion_user_agg,
            )

            # Initialize SuggestionFlow
            self._suggestion_flow = SuggestionFlow(
                session_id=self.session_id,
                flow_manager=self._suggestion_flow_manager,
            )
            await self._suggestion_flow.start()

            # Add to processor chain
            processors.extend(
                [
                    suggestion_user_agg,
                    rtvi_processor,
                    self._suggestion_flow,
                    suggestion_asst_agg,
                ]
            )

        # Add RTVI observer at the end
        processors.append(rtvi_observer)

        # Build final pipeline
        self._pipeline = Pipeline(processors)

        # Create main task if not created by flows
        if not self._task:
            self._task = PipelineTask(
                self._pipeline,
                params=PipelineParams(
                    allow_interruptions=False,
                    enable_metrics=True,
                ),
            )
        else:
            # Update task pipeline if flows created it
            self._task._pipeline = self._pipeline

        # RTVI event handlers
        @self._task.rtvi.event_handler("on_client_ready")
        async def on_client_ready(_rtvi):
            logger.info("RTVI client connected for session %s", self.session_id)

        # Create runner
        self._runner = PipelineRunner()

        # Run pipeline
        await self._runner.run(self._task)

    async def stop(self) -> None:
        """Stop the pipeline."""
        logger.info("Stopping VoiceBridge pipeline for session %s", self.session_id)

        # Stop flows
        if self._process_flow:
            await self._process_flow.stop()

        if self._suggestion_flow:
            await self._suggestion_flow.stop()

        # Stop pipeline
        if self._task:
            await self._task.cancel()

        if self._runner:
            await self._runner.stop()

    @property
    def is_running(self) -> bool:
        """Check if pipeline is running."""
        return self._task is not None and not self._task.cancelled()
