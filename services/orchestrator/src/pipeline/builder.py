"""Pipeline builder for VoiceBridge Pipecat runtime assembly."""

from dataclasses import dataclass

from pipecat.audio.turn.smart_turn.local_smart_turn_v3 import LocalSmartTurnAnalyzerV3
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.audio.vad.vad_analyzer import VADParams
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import LLMUserAggregatorParams
from pipecat.processors.frameworks.rtvi import RTVIProcessor
from pipecat.services.speechmatics.stt import Language, SpeechmaticsSTTService, TurnDetectionMode
from pipecat.transports.daily.transport import DailyParams, DailyTransport
from pipecat.turns.user_stop import TurnAnalyzerUserTurnStopStrategy
from pipecat.turns.user_turn_strategies import UserTurnStrategies
from pipecat_flows import FlowManager
from pipecat_flows.adapters import LLMContextAggregatorPair

from src.config import settings
from src.flows import ProcessFlow, SuggestionFlow
from src.llm import LLMServiceFactory
from src.rtvi import VoiceBridgeRTVIObserver

from .processors import TranscriptWriter


@dataclass
class BuiltPipelineComponents:
    """Built components required to run one VoiceBridge pipeline."""

    pipeline: Pipeline
    task: PipelineTask
    transcript_writer: TranscriptWriter
    process_flow: ProcessFlow | None
    suggestion_flow: SuggestionFlow | None
    process_flow_manager: FlowManager | None
    suggestion_flow_manager: FlowManager | None


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
        process_content_path: str,
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
        """Build pipeline processors and task with optional flows."""
        vad_params = VADParams(
            start_secs=settings.vad_start_secs,
            stop_secs=settings.vad_stop_secs,
        )
        stt_language = self._resolve_stt_language(settings.stt_language)

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

        speechmatics_params = SpeechmaticsSTTService.InputParams(
            language=stt_language,
            turn_detection_mode=TurnDetectionMode.EXTERNAL,
            include_partials=settings.stt_include_partials,
            enable_diarization=settings.stt_enable_diarization,
            max_speakers=settings.stt_max_speakers,
            prefer_current_speaker=settings.stt_prefer_current_speaker,
        )
        stt = SpeechmaticsSTTService(
            api_key=settings.speechmatics_api_key,
            base_url=settings.speechmatics_url,
            params=speechmatics_params,
        )

        smart_turn_analyzer = LocalSmartTurnAnalyzerV3(
            smart_turn_model_path=settings.smart_turn_model_path,
            cpu_count=settings.smart_turn_cpu_count,
        )
        smart_turn_agg_pair = LLMContextAggregatorPair(
            LLMContext(),
            user_params=LLMUserAggregatorParams(
                vad_analyzer=SileroVADAnalyzer(params=vad_params),
                user_turn_strategies=UserTurnStrategies(
                    stop=[
                        TurnAnalyzerUserTurnStopStrategy(
                            turn_analyzer=smart_turn_analyzer,
                        )
                    ]
                ),
            ),
        )

        transcript_writer = TranscriptWriter(
            session_id=self.session_id,
            first_speaker_role=settings.first_speaker_role,
        )

        rtvi_processor = RTVIProcessor()
        rtvi_observer = VoiceBridgeRTVIObserver(rtvi_processor)

        processors = [transport.input(), smart_turn_agg_pair.user(), stt, transcript_writer]

        process_flow, process_flow_manager = await self._build_process_flow()
        if process_flow:
            processors.append(process_flow)

        suggestion_flow, suggestion_flow_manager = await self._build_suggestion_flow()
        if suggestion_flow:
            processors.append(suggestion_flow)

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
            process_flow=process_flow,
            suggestion_flow=suggestion_flow,
            process_flow_manager=process_flow_manager,
            suggestion_flow_manager=suggestion_flow_manager,
        )

    @staticmethod
    def _resolve_stt_language(language: str) -> Language:
        """Resolve configured language string to Pipecat Language enum."""
        normalized = language.strip()
        candidates = [normalized]
        if normalized.lower() != normalized:
            candidates.append(normalized.lower())

        for candidate in candidates:
            try:
                return Language(candidate)
            except ValueError:
                continue

        raise ValueError(
            f"Unsupported STT_LANGUAGE '{language}'. "
            "Provide a valid Pipecat Language value (for example: en, en-US, es)."
        )

    async def _build_process_flow(self) -> tuple[ProcessFlow | None, FlowManager | None]:
        """Build optional process flow + FlowManager."""
        if not self.enable_process_flow:
            return None, None

        process_llm = LLMServiceFactory.create_llm_service(
            provider=self.process_flow_provider,
            model=self.process_flow_model,
        )

        process_context = LLMContext()
        process_agg_pair = LLMContextAggregatorPair(process_context)

        process_flow_pipeline = Pipeline(
            [
                process_agg_pair.user(),
                process_llm,
                process_agg_pair.assistant(),
            ]
        )
        process_task = PipelineTask(
            process_flow_pipeline,
            params=PipelineParams(
                allow_interruptions=False,
                enable_metrics=True,
            ),
            enable_rtvi=False,
        )

        process_flow_manager = FlowManager(
            task=process_task,
            llm=process_llm,
            context_aggregator=process_agg_pair,
        )

        process_flow = ProcessFlow(
            session_id=self.session_id,
            flow_manager=process_flow_manager,
            process_content_path=self.process_content_path,
        )
        await process_flow.start()

        return process_flow, process_flow_manager

    async def _build_suggestion_flow(self) -> tuple[SuggestionFlow | None, FlowManager | None]:
        """Build optional suggestion flow + FlowManager."""
        if not self.enable_suggestion_flow:
            return None, None

        suggestion_llm = LLMServiceFactory.create_llm_service(
            provider=self.suggestion_flow_provider,
            model=self.suggestion_flow_model,
        )

        suggestion_context = LLMContext()
        suggestion_agg_pair = LLMContextAggregatorPair(suggestion_context)

        suggestion_flow_pipeline = Pipeline(
            [
                suggestion_agg_pair.user(),
                suggestion_llm,
                suggestion_agg_pair.assistant(),
            ]
        )
        suggestion_task = PipelineTask(
            suggestion_flow_pipeline,
            params=PipelineParams(
                allow_interruptions=False,
                enable_metrics=True,
            ),
            enable_rtvi=False,
        )

        suggestion_flow_manager = FlowManager(
            task=suggestion_task,
            llm=suggestion_llm,
            context_aggregator=suggestion_agg_pair,
        )

        suggestion_flow = SuggestionFlow(
            session_id=self.session_id,
            flow_manager=suggestion_flow_manager,
        )
        await suggestion_flow.start()

        return suggestion_flow, suggestion_flow_manager
