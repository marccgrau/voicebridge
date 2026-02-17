"""Tests for process branch processors."""

from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from pipecat.frames.frames import LLMFullResponseEndFrame, LLMFullResponseStartFrame, LLMTextFrame
from pipecat.processors.frame_processor import FrameDirection
from pipecat.processors.frameworks.rtvi import RTVIServerMessageFrame

from src.process_catalog import ProcessCatalog
from src.process_processors import ProcessOutputProcessor


def _get_frames_of_type(mock_push: AsyncMock, frame_type: type) -> list:
    return [
        call.args[0]
        for call in mock_push.await_args_list
        if call.args and isinstance(call.args[0], frame_type)
    ]


def _write_process_file(
    path: Path,
    process_key: str,
    name: str,
    intents: list[str],
    *,
    include_third_step: bool = False,
) -> None:
    intents_yaml = "\n".join(f"  - {intent}" for intent in intents)
    third_step = (
        "\n## Step 3: Confirm Resolution\n\n"
        "Confirm the customer has everything needed.\n"
        if include_third_step
        else ""
    )

    path.write_text(
        f"""---
process_key: {process_key}
name: {name}
domain: card_services
intents:
{intents_yaml}
---

# {name}

## Step 1: Verify Identity

Verify identity.

## Step 2: Block Card

Block the card.
{third_step}"""
    )


@pytest.mark.asyncio
async def test_process_output_emits_rtvi_server_message(tmp_path: Path):
    _write_process_file(
        tmp_path / "lost_stolen_card.md",
        "lost_stolen_card",
        "Lost or Stolen Card",
        ["lost card", "stolen card"],
    )
    catalog = ProcessCatalog(process_content_path=str(tmp_path))
    processor = ProcessOutputProcessor(catalog=catalog)
    processor.push_frame = AsyncMock()

    await processor.process_frame(LLMFullResponseStartFrame(), FrameDirection.DOWNSTREAM)
    await processor.process_frame(
        LLMTextFrame(text='{"processKey":"lost_stolen_card","currentStep":0}'),
        FrameDirection.DOWNSTREAM,
    )
    await processor.process_frame(LLMFullResponseEndFrame(), FrameDirection.DOWNSTREAM)

    rtvi_frames = _get_frames_of_type(processor.push_frame, RTVIServerMessageFrame)
    assert len(rtvi_frames) == 1

    msg = rtvi_frames[0].data
    assert msg["action"] == "process_illustration"
    assert msg["data"]["processKey"] == "lost_stolen_card"
    assert msg["data"]["processName"] == "Lost or Stolen Card"
    assert msg["data"]["currentStep"] == 0
    assert msg["data"]["steps"][0]["label"] == "Verify Identity"
    assert msg["data"]["steps"][0]["status"] == "in_progress"


@pytest.mark.asyncio
async def test_process_output_skips_when_process_key_is_null(tmp_path: Path):
    _write_process_file(
        tmp_path / "lost_stolen_card.md",
        "lost_stolen_card",
        "Lost or Stolen Card",
        ["lost card", "stolen card"],
    )
    catalog = ProcessCatalog(process_content_path=str(tmp_path))
    processor = ProcessOutputProcessor(catalog=catalog)
    processor.push_frame = AsyncMock()

    await processor.process_frame(LLMFullResponseStartFrame(), FrameDirection.DOWNSTREAM)
    await processor.process_frame(
        LLMTextFrame(text='{"processKey": null, "currentStep": 0}'),
        FrameDirection.DOWNSTREAM,
    )
    await processor.process_frame(LLMFullResponseEndFrame(), FrameDirection.DOWNSTREAM)

    rtvi_frames = _get_frames_of_type(processor.push_frame, RTVIServerMessageFrame)
    assert len(rtvi_frames) == 0


@pytest.mark.asyncio
async def test_process_output_skips_on_invalid_json(tmp_path: Path):
    _write_process_file(
        tmp_path / "lost_stolen_card.md",
        "lost_stolen_card",
        "Lost or Stolen Card",
        ["lost card", "stolen card"],
    )
    catalog = ProcessCatalog(process_content_path=str(tmp_path))
    processor = ProcessOutputProcessor(catalog=catalog)
    processor.push_frame = AsyncMock()

    await processor.process_frame(LLMFullResponseStartFrame(), FrameDirection.DOWNSTREAM)
    await processor.process_frame(
        LLMTextFrame(text="this is not valid json"),
        FrameDirection.DOWNSTREAM,
    )
    await processor.process_frame(LLMFullResponseEndFrame(), FrameDirection.DOWNSTREAM)

    rtvi_frames = _get_frames_of_type(processor.push_frame, RTVIServerMessageFrame)
    assert len(rtvi_frames) == 0


@pytest.mark.asyncio
async def test_process_output_builds_completed_in_progress_pending_steps(tmp_path: Path):
    _write_process_file(
        tmp_path / "lost_stolen_card.md",
        "lost_stolen_card",
        "Lost or Stolen Card",
        ["lost card", "stolen card"],
        include_third_step=True,
    )
    catalog = ProcessCatalog(process_content_path=str(tmp_path))
    processor = ProcessOutputProcessor(catalog=catalog)
    processor.push_frame = AsyncMock()

    await processor.process_frame(LLMFullResponseStartFrame(), FrameDirection.DOWNSTREAM)
    await processor.process_frame(
        LLMTextFrame(text='{"processKey":"lost_stolen_card","currentStep":1}'),
        FrameDirection.DOWNSTREAM,
    )
    await processor.process_frame(LLMFullResponseEndFrame(), FrameDirection.DOWNSTREAM)

    rtvi_frames = _get_frames_of_type(processor.push_frame, RTVIServerMessageFrame)
    assert len(rtvi_frames) == 1

    steps = rtvi_frames[0].data["data"]["steps"]
    assert [step["status"] for step in steps] == ["completed", "in_progress", "pending"]
    assert rtvi_frames[0].data["data"]["currentStep"] == 1
