"""VoiceBridge unified PCC bot entry point.

Local dev:  python bot.py -t daily --port 7860
Cloud:      pipecat cloud deploy

The pipeline creates one STT stream, then fans out to three parallel branches:
- transcript branch
- process branch
- suggestion branch
"""

import logging
import os
from pathlib import Path

from deepgram import LiveOptions
from dotenv import load_dotenv
from pipecat.audio.turn.smart_turn.base_smart_turn import SmartTurnParams
from pipecat.audio.turn.smart_turn.local_smart_turn_v3 import LocalSmartTurnAnalyzerV3
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.audio.vad.vad_analyzer import VADParams
from pipecat.pipeline.parallel_pipeline import ParallelPipeline
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import (
    LLMContextAggregatorPair,
    LLMUserAggregatorParams,
)
from pipecat.runner.types import DailyRunnerArguments, RunnerArguments
from pipecat.services.deepgram.stt import DeepgramSTTService
from pipecat.services.openai.llm import OpenAILLMService
from pipecat.transports.daily.transport import DailyParams, DailyTransport
from pipecat.turns.user_stop import TurnAnalyzerUserTurnStopStrategy
from pipecat.turns.user_turn_strategies import UserTurnStrategies

from src.process_catalog import ProcessCatalog
from src.process_processors import PROCESS_SYSTEM_PROMPT, ProcessOutputProcessor
from src.suggestion_processors import SUGGESTION_SYSTEM_PROMPT, SuggestionOutputProcessor
from src.transcript_processors import TranscriptWriter

load_dotenv()

logger = logging.getLogger("voicebridge-pcc")


def _resolve_process_content_path() -> Path:
    configured_path = os.getenv("PROCESS_CONTENT_PATH")
    if configured_path:
        return Path(configured_path)

    return Path(__file__).resolve().parent / "process_content"


def build_process_system_prompt(catalog: ProcessCatalog) -> str:
    """Build process system prompt with the catalog embedded."""
    definitions = sorted(catalog.get_definitions(), key=lambda definition: definition.process_key)
    if not definitions:
        catalog_summary = "- No processes available"
    else:
        lines = []
        for definition in definitions:
            step_labels = ", ".join(
                f"{idx}:{step.label}" for idx, step in enumerate(definition.steps)
            )
            intents = ", ".join(definition.intents) if definition.intents else "(none)"
            lines.append(
                f"- {definition.process_key}: {definition.name} | "
                f"domain: {definition.domain or '(none)'} | "
                f"intents: {intents} | "
                f"steps: {step_labels or '(no steps)'}"
            )
        catalog_summary = "\n".join(lines)

    return PROCESS_SYSTEM_PROMPT.replace("{catalog_summary}", catalog_summary)


async def bot(runner_args: RunnerArguments):
    """Main bot entry point compatible with Pipecat runner and Pipecat Cloud."""
    body = runner_args.body or {}
    session_id = body.get("session_id", "local")

    if isinstance(runner_args, DailyRunnerArguments):
        room_url = runner_args.room_url
        token = runner_args.token
    elif body.get("dailyRoom"):
        room_url = body["dailyRoom"]
        token = body.get("dailyToken") or ""
    else:
        raise ValueError(
            "No Daily room URL provided (need DailyRunnerArguments or dailyRoom in body)"
        )

    transport = DailyTransport(
        room_url,
        token,
        "VoiceBridge",
        params=DailyParams(
            camera_in_enabled=False,
            camera_out_enabled=False,
            audio_in_enabled=True,
            audio_in_user_tracks=True,
            audio_out_enabled=False,
            microphone_out_enabled=False,
            transcription_enabled=False,
            vad_analyzer=SileroVADAnalyzer(params=VADParams(stop_secs=0.2)),
            turn_analyzer=LocalSmartTurnAnalyzerV3(params=SmartTurnParams()),
        ),
    )

    stt = DeepgramSTTService(
        api_key=os.getenv("DEEPGRAM_API_KEY", ""),
        live_options=LiveOptions(
            model="nova-3-general",
            language="en-US",
            smart_format=True,
            endpointing=True,
            profanity_filter=False,
            interim_results=True,
        ),
    )

    @stt.event_handler("on_connection_error")
    async def on_stt_connection_error(_stt, error):
        logger.warning("[session=%s] Deepgram connection error: %s", session_id, error)

    transcript_writer = TranscriptWriter(session_id=session_id)

    process_catalog = ProcessCatalog(process_content_path=str(_resolve_process_content_path()))
    process_catalog.load()
    process_system_prompt = build_process_system_prompt(process_catalog)
    process_context = LLMContext(messages=[{"role": "system", "content": process_system_prompt}])
    process_context_agg = LLMContextAggregatorPair(
        process_context,
        user_params=LLMUserAggregatorParams(
            user_turn_strategies=UserTurnStrategies(
                stop=[TurnAnalyzerUserTurnStopStrategy(turn_analyzer=LocalSmartTurnAnalyzerV3())]
            ),
            vad_analyzer=SileroVADAnalyzer(),
        ),
    )
    process_model = os.getenv("PROCESS_MODEL", "gpt-4.1-nano")
    process_llm = OpenAILLMService(
        api_key=os.getenv("OPENAI_API_KEY", ""),
        model=process_model,
    )
    process_output = ProcessOutputProcessor(catalog=process_catalog)

    suggestion_context = LLMContext(
        messages=[{"role": "system", "content": SUGGESTION_SYSTEM_PROMPT}]
    )
    suggestion_context_agg = LLMContextAggregatorPair(
        suggestion_context,
        user_params=LLMUserAggregatorParams(
            user_turn_strategies=UserTurnStrategies(
                stop=[TurnAnalyzerUserTurnStopStrategy(turn_analyzer=LocalSmartTurnAnalyzerV3())]
            ),
            vad_analyzer=SileroVADAnalyzer(),
        ),
    )
    suggestion_model = os.getenv("SUGGESTION_MODEL", "gpt-4.1")
    suggestion_llm = OpenAILLMService(
        api_key=os.getenv("OPENAI_API_KEY", ""),
        model=suggestion_model,
    )
    suggestion_output = SuggestionOutputProcessor(session_id=session_id)

    pipeline = Pipeline(
        [
            transport.input(),
            stt,
            ParallelPipeline(
                [
                    transcript_writer,
                ],
                [
                    process_context_agg.user(),
                    process_llm,
                    process_output,
                ],
                [
                    suggestion_context_agg.user(),
                    suggestion_llm,
                    suggestion_output,
                ],
            ),
            transport.output(),
        ]
    )

    task = PipelineTask(
        pipeline,
        params=PipelineParams(allow_interruptions=False, enable_metrics=True),
    )

    @task.rtvi.event_handler("on_client_ready")
    async def on_client_ready(_rtvi):
        logger.info("[session=%s] RTVI client connected", session_id)

    runner = PipelineRunner()
    await runner.run(task)


if __name__ == "__main__":
    from pipecat.runner.run import main

    main()
