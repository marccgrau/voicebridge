"""Tests for process agent processors."""

from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from pipecat.frames.frames import (
    LLMContextFrame,
    LLMFullResponseEndFrame,
    LLMFullResponseStartFrame,
    LLMTextFrame,
)
from pipecat.processors.frame_processor import FrameDirection

from src.frames import ProcessIllustrationFrame, TranscriptSegmentFrame
from src.process_catalog import ProcessCatalog
from src.processors import (
    ProcessContextBuilder,
    ProcessOutputProcessor,
    ProcessRTVIObserver,
    TranscriptWriter,
)


def _get_frames_of_type(mock_push: AsyncMock, frame_type: type) -> list:
    return [
        call.args[0]
        for call in mock_push.await_args_list
        if call.args and isinstance(call.args[0], frame_type)
    ]


def _make_customer_frame(text: str, ts_suffix: str = "00") -> TranscriptSegmentFrame:
    return TranscriptSegmentFrame(
        session_id="test-session",
        speaker="customer",
        text=text,
        timestamp=f"2026-02-10T10:00:{ts_suffix}Z",
        is_final=True,
    )


def _write_process_file(path: Path, process_key: str, name: str, intents: list[str]) -> None:
    intents_yaml = "\n".join(f"  - {intent}" for intent in intents)
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
"""
    )


# --- TranscriptWriter Tests ---


@pytest.mark.asyncio
async def test_transcript_writer_emits_transcript_segment():
    from pipecat.frames.frames import TranscriptionFrame

    writer = TranscriptWriter(session_id="test-session")
    writer.push_frame = AsyncMock()

    frame = TranscriptionFrame(
        text="Hello, I need help with my card.",
        user_id="user1",
        timestamp="2026-02-10T10:00:00Z",
    )
    await writer.process_frame(frame, FrameDirection.DOWNSTREAM)

    transcript_frames = _get_frames_of_type(writer.push_frame, TranscriptSegmentFrame)
    assert len(transcript_frames) == 1
    assert transcript_frames[0].speaker == "customer"
    assert transcript_frames[0].text == "Hello, I need help with my card."


# --- ProcessContextBuilder Tests ---


@pytest.mark.asyncio
async def test_process_context_builder_pushes_llm_context():
    builder = ProcessContextBuilder(session_id="test-session")
    builder.push_frame = AsyncMock()

    await builder.process_frame(
        _make_customer_frame("My card is lost"),
        FrameDirection.DOWNSTREAM,
    )

    context_frames = _get_frames_of_type(builder.push_frame, LLMContextFrame)
    assert len(context_frames) == 1
    messages = context_frames[0].context.messages
    assert len(messages) == 2
    assert "process identification" in messages[0]["content"].lower()
    assert "My card is lost" in messages[1]["content"]


@pytest.mark.asyncio
async def test_process_context_builder_consumes_transcript_frames():
    builder = ProcessContextBuilder(session_id="test-session")
    builder.push_frame = AsyncMock()

    await builder.process_frame(
        _make_customer_frame("Hello"),
        FrameDirection.DOWNSTREAM,
    )

    transcript_frames = _get_frames_of_type(builder.push_frame, TranscriptSegmentFrame)
    assert len(transcript_frames) == 0

    context_frames = _get_frames_of_type(builder.push_frame, LLMContextFrame)
    assert len(context_frames) == 1


# --- ProcessOutputProcessor Tests ---


@pytest.mark.asyncio
async def test_process_output_emits_illustration_frame():
    processor = ProcessOutputProcessor(session_id="test-session")
    processor.push_frame = AsyncMock()

    illustration = ProcessIllustrationFrame(
        process_key="lost_stolen_card",
        process_name="Lost or Stolen Card",
        steps=[
            {"key": "step_1", "label": "Verify Identity", "status": "in_progress"},
            {"key": "step_2", "label": "Block Card", "status": "pending"},
        ],
        current_step=0,
        content="## Step 1: Verify Identity",
    )
    processor.set_pending_illustration(illustration)

    await processor.process_frame(LLMFullResponseStartFrame(), FrameDirection.DOWNSTREAM)
    await processor.process_frame(
        LLMTextFrame(text="I found the process."),
        FrameDirection.DOWNSTREAM,
    )
    await processor.process_frame(LLMFullResponseEndFrame(), FrameDirection.DOWNSTREAM)

    process_frames = _get_frames_of_type(processor.push_frame, ProcessIllustrationFrame)
    assert len(process_frames) == 1
    assert process_frames[0].process_key == "lost_stolen_card"
    assert process_frames[0].current_step == 0

    # LLM text frames should be consumed
    text_frames = _get_frames_of_type(processor.push_frame, LLMTextFrame)
    assert len(text_frames) == 0


@pytest.mark.asyncio
async def test_process_output_no_emission_without_pending():
    processor = ProcessOutputProcessor(session_id="test-session")
    processor.push_frame = AsyncMock()

    await processor.process_frame(LLMFullResponseStartFrame(), FrameDirection.DOWNSTREAM)
    await processor.process_frame(
        LLMTextFrame(text="No process found."),
        FrameDirection.DOWNSTREAM,
    )
    await processor.process_frame(LLMFullResponseEndFrame(), FrameDirection.DOWNSTREAM)

    process_frames = _get_frames_of_type(processor.push_frame, ProcessIllustrationFrame)
    assert len(process_frames) == 0


# --- ProcessCatalog Tests ---


def test_tool_handler_list_processes(tmp_path: Path):
    _write_process_file(
        tmp_path / "lost_stolen_card.md",
        "lost_stolen_card",
        "Lost or Stolen Card",
        ["lost card", "stolen card"],
    )
    catalog = ProcessCatalog(process_content_path=str(tmp_path))
    result = catalog.get_catalog_summary()
    assert "lost_stolen_card" in result
    assert "Lost or Stolen Card" in result


def test_tool_handler_get_process_details(tmp_path: Path):
    _write_process_file(
        tmp_path / "lost_stolen_card.md",
        "lost_stolen_card",
        "Lost or Stolen Card",
        ["lost card", "stolen card"],
    )
    catalog = ProcessCatalog(process_content_path=str(tmp_path))
    result = catalog.get_process_definition("lost_stolen_card")
    assert "Lost or Stolen Card" in result
    assert "Step 1: Verify Identity" in result
    assert "Step 2: Block Card" in result


def test_tool_handler_get_process_details_not_found(tmp_path: Path):
    catalog = ProcessCatalog(process_content_path=str(tmp_path))
    result = catalog.get_process_definition("nonexistent")
    assert "not found" in result.lower()


def test_tool_handler_report_process_status(tmp_path: Path):
    """Test that the catalog provides data to build a ProcessIllustrationFrame."""
    _write_process_file(
        tmp_path / "lost_stolen_card.md",
        "lost_stolen_card",
        "Lost or Stolen Card",
        ["lost card", "stolen card"],
    )
    catalog = ProcessCatalog(process_content_path=str(tmp_path))
    defn = catalog.get_definition("lost_stolen_card")
    assert defn is not None
    assert defn.process_key == "lost_stolen_card"
    assert len(defn.steps) == 2
    assert defn.steps[0].label == "Verify Identity"


# --- ProcessRTVIObserver Tests ---


@pytest.mark.asyncio
async def test_rtvi_observer_publishes_process_illustration():
    rtvi_processor = AsyncMock()
    observer = ProcessRTVIObserver(rtvi_processor)
    observer.push_frame = AsyncMock()

    frame = ProcessIllustrationFrame(
        process_key="lost_stolen_card",
        process_name="Lost or Stolen Card",
        steps=[{"key": "step_1", "label": "Verify", "status": "in_progress"}],
        current_step=0,
        content="## Step 1: Verify",
    )
    await observer.process_frame(frame, FrameDirection.DOWNSTREAM)

    rtvi_processor.send_server_message.assert_awaited_once()
    msg = rtvi_processor.send_server_message.call_args[0][0]
    assert msg["action"] == "process_illustration"
    assert msg["data"]["processKey"] == "lost_stolen_card"

    # Frame should still pass through
    pushed = _get_frames_of_type(observer.push_frame, ProcessIllustrationFrame)
    assert len(pushed) == 1


@pytest.mark.asyncio
async def test_rtvi_observer_does_not_publish_transcript():
    rtvi_processor = AsyncMock()
    observer = ProcessRTVIObserver(rtvi_processor)
    observer.push_frame = AsyncMock()

    frame = TranscriptSegmentFrame(
        session_id="test-session",
        speaker="customer",
        text="Hello",
        timestamp="2026-02-10T10:00:00Z",
        is_final=True,
    )
    await observer.process_frame(frame, FrameDirection.DOWNSTREAM)

    # Should NOT call send_server_message for transcript frames
    rtvi_processor.send_server_message.assert_not_awaited()

    # Frame should still pass through
    pushed = _get_frames_of_type(observer.push_frame, TranscriptSegmentFrame)
    assert len(pushed) == 1
