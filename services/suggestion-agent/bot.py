"""VoiceBridge Suggestion Agent entry point.

Local dev:  python bot.py -t daily --port 7862
Cloud:      pipecat cloud deploy

Listens to audio, runs STT, and generates one actionable agent suggestion.
"""

import logging
import os

from deepgram import LiveOptions
from dotenv import load_dotenv
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import LLMContextAggregatorPair
from pipecat.processors.frameworks.rtvi import RTVIConfig, RTVIObserver, RTVIProcessor
from pipecat.runner.types import DailyRunnerArguments, RunnerArguments
from pipecat.services.deepgram.stt import DeepgramSTTService
from pipecat.services.openai.llm import OpenAILLMService
from pipecat.transports.daily.transport import DailyParams, DailyTransport

from src.processors import SUGGESTION_SYSTEM_PROMPT, SuggestionOutputProcessor

load_dotenv()

logger = logging.getLogger("voicebridge-suggestion")


async def bot(runner_args: RunnerArguments):
    """Main bot entry point compatible with Pipecat runner and Pipecat Cloud."""
    body = runner_args.body or {}
    session_id = body.get("session_id", "local")

    # When joining an existing room via dailyRoom, the runner passes base
    # RunnerArguments (not DailyRunnerArguments). Extract room URL from body.
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
        "VoiceBridge-Suggestion",
        params=DailyParams(
            camera_in_enabled=False,
            camera_out_enabled=False,
            audio_in_enabled=True,
            audio_in_user_tracks=False,
            audio_out_enabled=False,
            microphone_out_enabled=False,
            transcription_enabled=False,
            # vad_analyzer=SileroVADAnalyzer(params=VADParams(stop_secs=0.2)),
            # turn_analyzer=LocalSmartTurnAnalyzerV3(params=SmartTurnParams()),
        ),
    )

    stt = DeepgramSTTService(
        api_key=os.getenv("DEEPGRAM_API_KEY", ""),
        live_options=LiveOptions(
            model="nova-3-general",
            language="en-US",
            # smart_format=True,
            # endpointing=True,
            # profanity_filter=False,
            # interim_results=True,
        ),
    )

    @stt.event_handler("on_connection_error")
    async def on_stt_connection_error(_stt, error):
        logger.warning("[session=%s] Deepgram connection error: %s", session_id, error)

    suggestion_model = os.getenv("SUGGESTION_MODEL", "gpt-4.1")
    llm = OpenAILLMService(
        api_key=os.getenv("OPENAI_API_KEY", ""),
        model=suggestion_model,
    )

    context = LLMContext(messages=[{"role": "system", "content": SUGGESTION_SYSTEM_PROMPT}])
    context_agg = LLMContextAggregatorPair(context)
    suggestion_output = SuggestionOutputProcessor(session_id=session_id)

    rtvi_processor = RTVIProcessor(config=RTVIConfig(config=[]))

    pipeline = Pipeline(
        [
            transport.input(),
            stt,
            context_agg.user(),
            llm,
            suggestion_output,
            rtvi_processor,
            transport.output(),
        ]
    )

    task = PipelineTask(
        pipeline,
        params=PipelineParams(allow_interruptions=False, enable_metrics=True),
        observers=[RTVIObserver(rtvi=rtvi_processor)],
    )

    @rtvi_processor.event_handler("on_client_ready")
    async def on_client_ready(rtvi):
        await rtvi.set_bot_ready()
        logger.info("[session=%s] RTVI client connected (suggestion agent)", session_id)

    runner = PipelineRunner()
    await runner.run(task)


if __name__ == "__main__":
    from pipecat.runner.run import main

    main()
