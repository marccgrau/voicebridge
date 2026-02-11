"""Pipeline builder for VoiceBridge Pipecat runtime assembly."""

import logging
from dataclasses import dataclass

from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.processors.frameworks.rtvi import RTVIProcessor
from pipecat.transports.daily.transport import DailyParams, DailyTransport

from src.config import settings
from src.llm import LLMServiceFactory
from src.rtvi import VoiceBridgeRTVIObserver
from src.stt import STTServiceFactory

from .direct_processors import DirectSuggestionProcessor, ProcessContextResolverProcessor
from .processors import TranscriptWriter

logger = logging.getLogger(__name__)


@dataclass
class BuiltPipelineComponents:
    """Built components required to run one VoiceBridge pipeline."""

    pipeline: Pipeline
    task: PipelineTask
    transcript_writer: TranscriptWriter
    process_context_resolver: ProcessContextResolverProcessor | None
    direct_suggestion_processor: DirectSuggestionProcessor | None


class VoiceBridgePipelineBuilder:
    """Builds fully-wired Pipecat pipeline components for a session."""

    def __init__(
        self,
        session_id: str,
        room_url: str,
        room_token: str,
        enable_process_flow: bool,
        enable_suggestion_flow: bool,
        process_flow_provider: str,
        process_flow_model: str,
        suggestion_flow_provider: str,
        suggestion_flow_model: str,
        process_content_path: str = "process_content/",
    ):
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

    async def build(self) -> BuiltPipelineComponents:
        """Build pipeline processors and task with optional direct processors."""
        transport = DailyTransport(
            room_url=self.room_url,
            token=self.room_token,
            bot_name="VoiceBridge",
            params=DailyParams(
                audio_in_enabled=True,
                audio_out_enabled=False,
                audio_in_filter=None,
            ),
        )

        stt = STTServiceFactory.create_stt_service(
            provider=settings.default_stt_provider,
            language=settings.stt_language,
        )

        transcript_writer = TranscriptWriter(
            session_id=self.session_id,
            first_speaker_role=settings.first_speaker_role,
        )

        rtvi_processor = RTVIProcessor()
        rtvi_observer = VoiceBridgeRTVIObserver(rtvi_processor)

        processors = [transport.input(), stt, transcript_writer]

        process_context_resolver = await self._build_process_context_resolver()
        if process_context_resolver:
            processors.append(process_context_resolver)
        logger.info(
            "Process context resolver: %s (enable_process_flow=%s)",
            "built" if process_context_resolver else "skipped",
            self.enable_process_flow,
        )

        direct_suggestion_processor = await self._build_direct_suggestion_processor()
        if direct_suggestion_processor:
            processors.append(direct_suggestion_processor)
        logger.info(
            "Direct suggestion processor: %s (enable_suggestion_flow=%s)",
            "built" if direct_suggestion_processor else "skipped",
            self.enable_suggestion_flow,
        )

        processors.append(rtvi_observer)
        processors.append(transport.output())

        pipeline = Pipeline(processors)
        task = PipelineTask(
            pipeline,
            params=PipelineParams(
                allow_interruptions=False,
                enable_metrics=True,
            ),
            rtvi_processor=rtvi_processor,
        )

        return BuiltPipelineComponents(
            pipeline=pipeline,
            task=task,
            transcript_writer=transcript_writer,
            process_context_resolver=process_context_resolver,
            direct_suggestion_processor=direct_suggestion_processor,
        )

    async def _build_process_context_resolver(self) -> ProcessContextResolverProcessor | None:
        """Build direct process resolver processor."""
        if not self.enable_process_flow:
            return None

        process_llm = LLMServiceFactory.create_llm_service(
            provider=self.process_flow_provider,
            model=self.process_flow_model,
            extra_params={"response_format": {"type": "json_object"}},
        )
        return ProcessContextResolverProcessor(
            session_id=self.session_id,
            llm=process_llm,
            process_content_path=self.process_content_path,
            llm_timeout=settings.process_detection_llm_timeout,
            shortlist_k=settings.process_shortlist_k,
            confidence_threshold=settings.process_match_confidence_threshold,
            margin_threshold=settings.process_match_margin_threshold,
            cache_size=settings.process_content_cache_size,
        )

    async def _build_direct_suggestion_processor(self) -> DirectSuggestionProcessor | None:
        """Build direct suggestion processor."""
        if not self.enable_suggestion_flow:
            logger.info("Suggestion flow disabled, skipping processor build")
            return None

        try:
            suggestion_llm = LLMServiceFactory.create_llm_service(
                provider=self.suggestion_flow_provider,
                model=self.suggestion_flow_model,
                extra_params={"response_format": {"type": "json_object"}},
            )
            return DirectSuggestionProcessor(
                session_id=self.session_id,
                llm=suggestion_llm,
                llm_timeout=settings.suggestion_llm_timeout,
                conversation_window_size=settings.conversation_window_size,
                debounce_ms=settings.suggestion_debounce_ms,
            )
        except Exception:
            logger.exception("Failed to build DirectSuggestionProcessor")
            return None
