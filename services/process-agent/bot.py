"""VoiceBridge Process Agent entry point.

Local dev:  python bot.py -t daily --port 7861
Cloud:      pipecat cloud deploy

Listens to audio, runs STT, uses a fast LLM with tool calling to detect
processes from the catalog and track step progress.
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
from pipecat.services.openai.llm import OpenAILLMService
from pipecat.transports.daily.transport import DailyParams, DailyTransport

from src.frames import ProcessIllustrationFrame
from src.process_catalog import ProcessCatalog
from src.processors import (
    ProcessContextBuilder,
    ProcessOutputProcessor,
    ProcessRTVIObserver,
    TranscriptWriter,
)

load_dotenv()

logger = logging.getLogger("voicebridge-process")


def _build_process_illustration(catalog: ProcessCatalog, process_key: str, current_step: int):
    """Build a ProcessIllustrationFrame from catalog data."""
    defn = catalog.get_definition(process_key)
    if not defn:
        return None

    return ProcessIllustrationFrame(
        process_key=defn.process_key,
        process_name=defn.name,
        steps=[
            {
                "key": step.key,
                "label": step.label,
                "status": (
                    "completed"
                    if idx < current_step
                    else "in_progress" if idx == current_step else "pending"
                ),
            }
            for idx, step in enumerate(defn.steps)
        ],
        current_step=current_step,
        content=defn.full_content,
    )


async def bot(runner_args: RunnerArguments):
    """Main bot entry point compatible with Pipecat runner and Pipecat Cloud."""
    if not isinstance(runner_args, DailyRunnerArguments):
        raise ValueError("VoiceBridge only supports Daily transport")

    room_url = runner_args.room_url
    token = runner_args.token
    body = runner_args.body or {}
    session_id = body.get("session_id", "local")

    transport = DailyTransport(
        room_url,
        token,
        "VoiceBridge-Process",
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

    process_model = os.getenv("PROCESS_MODEL", "gpt-4.1-nano")
    llm = OpenAILLMService(
        api_key=os.getenv("OPENAI_API_KEY", ""),
        model=process_model,
    )

    catalog = ProcessCatalog(process_content_path="process_content/")
    catalog.load()

    transcript_writer = TranscriptWriter(session_id=session_id)
    process_context_builder = ProcessContextBuilder(session_id=session_id)
    process_output = ProcessOutputProcessor(session_id=session_id)

    # Register LLM tool handlers
    @llm.function("list_processes")
    async def handle_list_processes(llm_instance):
        return catalog.get_catalog_summary()

    @llm.function("get_process_details")
    async def handle_get_process_details(llm_instance, process_key: str):
        return catalog.get_process_definition(process_key)

    @llm.function("report_process_status")
    async def handle_report_process_status(
        llm_instance, process_key: str, current_step: int
    ):
        illustration = _build_process_illustration(catalog, process_key, current_step)
        if illustration:
            process_output.set_pending_illustration(illustration)
            return f"Process '{process_key}' at step {current_step} reported successfully."
        return f"Process '{process_key}' not found in catalog."

    rtvi_processor = RTVIProcessor()
    rtvi_observer = ProcessRTVIObserver(rtvi_processor)

    pipeline = Pipeline(
        [
            transport.input(),
            stt,
            transcript_writer,
            process_context_builder,
            llm,
            process_output,
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
        logger.info("[session=%s] RTVI client connected (process agent)", session_id)

    runner = PipelineRunner()
    await runner.run(task)


if __name__ == "__main__":
    from pipecat.runner.run import main

    main()
