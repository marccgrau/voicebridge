"""VoiceBridge Pipecat bot entry point.

Local dev:  python bot.py -t daily --port 7860
Cloud:      pipecat cloud deploy

The bot uses the Pipecat runner pattern with RunnerArguments.
The runner automatically creates a FastAPI server with /start endpoint.
"""

import logging
import os

from deepgram import LiveOptions
from dotenv import load_dotenv
from pipecat.pipeline.parallel_pipeline import ParallelPipeline
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.processors.frameworks.rtvi import RTVIProcessor
from pipecat.runner.types import DailyRunnerArguments, RunnerArguments
from pipecat.services.deepgram.stt import DeepgramSTTService
from pipecat.services.openai.llm import OpenAILLMService
from pipecat.transports.daily.transport import DailyParams, DailyTransport

from src.processors import (
    ProcessDetectionProcessor,
    SuggestionContextBuilder,
    SuggestionOutputProcessor,
    TranscriptWriter,
    VoiceBridgeRTVIObserver,
)

load_dotenv()

logger = logging.getLogger("voicebridge-pcc")


async def bot(runner_args: RunnerArguments):
    """Main bot entry point compatible with Pipecat runner and Pipecat Cloud.

    Args:
        runner_args: RunnerArguments containing transport-specific info
    """
    # Only support Daily transport for VoiceBridge
    if not isinstance(runner_args, DailyRunnerArguments):
        raise ValueError("VoiceBridge only supports Daily transport")

    room_url = runner_args.room_url
    token = runner_args.token
    body = runner_args.body or {}
    session_id = body.get("session_id", "local")

    transport = DailyTransport(
        room_url,
        token,
        "VoiceBridge",
        params=DailyParams(
            audio_in_enabled=True,
            audio_out_enabled=False,
        ),
    )

    stt = DeepgramSTTService(
        api_key=os.getenv("DEEPGRAM_API_KEY", ""),
        live_options=LiveOptions(
            model="nova-3-general",
            smart_format=True,
            endpointing=True,
            interim_results=False,
        ),
    )

    suggestion_llm = OpenAILLMService(
        api_key=os.getenv("OPENAI_API_KEY", ""),
        model=os.getenv("SUGGESTION_MODEL", "gpt-4.1"),
    )

    transcript_writer = TranscriptWriter(session_id=session_id)
    process_detector = ProcessDetectionProcessor(
        session_id=session_id,
        process_content_path="process_content/",
    )
    suggestion_context_builder = SuggestionContextBuilder(session_id=session_id)
    suggestion_output = SuggestionOutputProcessor(session_id=session_id)

    rtvi_processor = RTVIProcessor()
    rtvi_observer = VoiceBridgeRTVIObserver(rtvi_processor)

    pipeline = Pipeline(
        [
            transport.input(),
            stt,
            transcript_writer,
            process_detector,
            ParallelPipeline(
                [],  # passthrough — frames reach RTVI immediately
                [suggestion_context_builder, suggestion_llm, suggestion_output],
            ),
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
    async def on_client_ready(_rtvi):
        logger.info("[session=%s] RTVI client connected", session_id)

    runner = PipelineRunner()
    await runner.run(task)


if __name__ == "__main__":
    from pipecat.runner.run import main

    main()
