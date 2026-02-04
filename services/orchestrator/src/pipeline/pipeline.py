"""VoiceBridge Pipecat pipeline."""

import logging
from typing import Any

from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.audio.vad.vad_analyzer import VADParams
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.services.deepgram.stt import DeepgramSTTService
from pipecat.transports.daily.transport import DailyParams, DailyTransport

from src.config import settings

from .processors import (
    KBLookupProcessor,
    ProcessSelectionProcessor,
    SlotExtractionProcessor,
    SuggestionComposer,
    TranscriptWriter,
)

logger = logging.getLogger(__name__)


class VoiceBridgePipeline:
    """Main pipeline for VoiceBridge voice processing.

    Orchestrates:
    - Daily.co WebRTC transport
    - Silero VAD with smart turn detection
    - Deepgram STT
    - Custom processors for process selection, slot extraction, suggestions
    """

    def __init__(
        self,
        session_id: str,
        room_url: str,
        room_token: str,
        anthropic_client: Any,
    ):
        """Initialize the pipeline.

        Args:
            session_id: Unique session identifier
            room_url: Daily.co room URL
            room_token: Daily.co room token
            anthropic_client: Anthropic client for LLM operations
        """
        self.session_id = session_id
        self.room_url = room_url
        self.room_token = room_token
        self.anthropic = anthropic_client
        self._pipeline: Pipeline | None = None
        self._task: PipelineTask | None = None
        self._runner: PipelineRunner | None = None

    async def start(self) -> None:
        """Start the pipeline."""
        logger.info("Starting VoiceBridge pipeline for session %s", self.session_id)

        # Configure VAD with responsive settings
        vad_params = VADParams(
            start_secs=0.2,  # Quick to detect speech start
            stop_secs=0.8,   # Wait before considering speech ended
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

        # Initialize STT
        stt = DeepgramSTTService(
            api_key=settings.deepgram_api_key,
            language=settings.stt_language,
        )

        # Initialize custom processors
        transcript_writer = TranscriptWriter(
            session_id=self.session_id,
            speaker="customer",
        )

        process_selection = ProcessSelectionProcessor(
            session_id=self.session_id,
            anthropic_client=self.anthropic,
            model=settings.llm_model,
        )

        slot_extraction = SlotExtractionProcessor(
            session_id=self.session_id,
            anthropic_client=self.anthropic,
            model=settings.llm_model,
        )

        kb_lookup = KBLookupProcessor(session_id=self.session_id)

        suggestion_composer = SuggestionComposer(
            session_id=self.session_id,
            anthropic_client=self.anthropic,
            model=settings.llm_model,
        )

        # Build pipeline
        # For a listen-only bot (no LLM assistant response), we use a simpler pipeline
        self._pipeline = Pipeline(
            [
                transport.input(),
                stt,
                transcript_writer,
                process_selection,
                slot_extraction,
                kb_lookup,
                suggestion_composer,
            ]
        )

        # Create task
        self._task = PipelineTask(
            self._pipeline,
            params=PipelineParams(
                allow_interruptions=False,  # We're listen-only
                enable_metrics=True,
            ),
        )

        # Create runner
        self._runner = PipelineRunner()

        # Run pipeline
        await self._runner.run(self._task)

    async def stop(self) -> None:
        """Stop the pipeline."""
        logger.info("Stopping VoiceBridge pipeline for session %s", self.session_id)

        if self._task:
            await self._task.cancel()

        if self._runner:
            await self._runner.stop()

    @property
    def is_running(self) -> bool:
        """Check if pipeline is running."""
        return self._task is not None and not self._task.cancelled()
