"""Tests for transcript agent processors."""

from unittest.mock import AsyncMock

import pytest
from pipecat.frames.frames import TranscriptionFrame
from pipecat.processors.frame_processor import FrameDirection

from src.frames import TranscriptSegmentFrame
from src.processors import TranscriptRTVIObserver, TranscriptWriter


def _get_frames_of_type(mock_push: AsyncMock, frame_type: type) -> list:
    return [
        call.args[0]
        for call in mock_push.await_args_list
        if call.args and isinstance(call.args[0], frame_type)
    ]


# --- TranscriptWriter Tests ---


@pytest.mark.asyncio
async def test_transcript_writer_emits_transcript_segment():
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
    assert transcript_frames[0].session_id == "test-session"
    assert transcript_frames[0].is_final is True


@pytest.mark.asyncio
async def test_transcript_writer_skips_empty_text():
    writer = TranscriptWriter(session_id="test-session")
    writer.push_frame = AsyncMock()

    frame = TranscriptionFrame(text="   ", user_id="user1", timestamp="2026-02-10T10:00:00Z")
    await writer.process_frame(frame, FrameDirection.DOWNSTREAM)

    transcript_frames = _get_frames_of_type(writer.push_frame, TranscriptSegmentFrame)
    assert len(transcript_frames) == 0


# --- TranscriptRTVIObserver Tests ---


@pytest.mark.asyncio
async def test_rtvi_observer_publishes_transcript():
    rtvi_processor = AsyncMock()
    observer = TranscriptRTVIObserver(rtvi_processor)
    observer.push_frame = AsyncMock()

    frame = TranscriptSegmentFrame(
        session_id="test-session",
        speaker="customer",
        text="Hello, I need help.",
        timestamp="2026-02-10T10:00:00Z",
        is_final=True,
    )
    await observer.process_frame(frame, FrameDirection.DOWNSTREAM)

    rtvi_processor.send_server_message.assert_awaited_once()
    msg = rtvi_processor.send_server_message.call_args[0][0]
    assert msg["action"] == "transcript_segment"
    assert msg["data"]["speaker"] == "customer"
    assert msg["data"]["text"] == "Hello, I need help."

    # Frame should still pass through
    pushed = _get_frames_of_type(observer.push_frame, TranscriptSegmentFrame)
    assert len(pushed) == 1


@pytest.mark.asyncio
async def test_rtvi_observer_handles_send_failure():
    rtvi_processor = AsyncMock()
    rtvi_processor.send_server_message.side_effect = RuntimeError("RTVI not connected")
    observer = TranscriptRTVIObserver(rtvi_processor)
    observer.push_frame = AsyncMock()

    frame = TranscriptSegmentFrame(
        session_id="test-session",
        speaker="customer",
        text="Hello.",
        timestamp="2026-02-10T10:00:00Z",
        is_final=True,
    )
    # Should not raise — best-effort delivery
    await observer.process_frame(frame, FrameDirection.DOWNSTREAM)

    # Frame should still pass through even on RTVI failure
    pushed = _get_frames_of_type(observer.push_frame, TranscriptSegmentFrame)
    assert len(pushed) == 1
