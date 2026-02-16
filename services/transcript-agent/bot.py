"""VoiceBridge Transcript Agent entry point.

Local dev:  python bot.py -t daily --port 7860
Cloud:      pipecat cloud deploy

Listens to audio, runs STT, and delivers transcript segments via RTVI.
No LLM — simplest of the three agents.
"""

import logging
import os

from deepgram import LiveOptions
from dotenv import load_dotenv
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.processors.frameworks.rtvi import RTVIProcessor
from pipecat.runner.types import DailyRunnerArguments, RunnerArguments
from pipecat.services.deepgram.stt import DeepgramSTTService
from pipecat.transports.daily.transport import DailyParams, DailyTransport

from src.processors import TranscriptRTVIObserver, TranscriptWriter

load_dotenv()

logger = logging.getLogger("voicebridge-transcript")


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
        token = ""
    else:
        raise ValueError("No Daily room URL provided (need DailyRunnerArguments or dailyRoom in body)")

    transport = DailyTransport(
        room_url,
        token,
        "VoiceBridge-Transcript",
        params=DailyParams(
            camera_in_enabled=False,
            camera_out_enabled=False,
            audio_in_enabled=True,
            audio_out_enabled=False,
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

    transcript_writer = TranscriptWriter(session_id=session_id)

    rtvi_processor = RTVIProcessor()
    rtvi_observer = TranscriptRTVIObserver(rtvi_processor)

    pipeline = Pipeline(
        [
            transport.input(),
            stt,
            # transcript_writer,
            rtvi_observer,
            transport.output(),
        ]
    )

    task = PipelineTask(
        pipeline,
        params=PipelineParams(allow_interruptions=False, enable_metrics=True),
        rtvi_processor=rtvi_processor,
    )

    @task.rtvi.event_handler("on_client_ready")
    async def on_client_ready(rtvi):
        await rtvi.set_bot_ready()
        logger.info("[session=%s] RTVI client connected (transcript agent)", session_id)

    runner = PipelineRunner()
    await runner.run(task)


if __name__ == "__main__":
    from pipecat.runner.run import main

    main()
