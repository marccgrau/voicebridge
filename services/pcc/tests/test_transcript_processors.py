"""Tests for transcript branch processors."""

from unittest.mock import AsyncMock

import pytest
from pipecat.frames.frames import Frame, TranscriptionFrame
from pipecat.processors.frame_processor import FrameDirection
from pipecat.processors.frameworks.rtvi import RTVIServerMessageFrame

from src.transcript_processors import TranscriptWriter


def _get_frames_of_type(mock_push: AsyncMock, frame_type: type) -> list:
    return [
        call.args[0]
        for call in mock_push.await_args_list
        if call.args and isinstance(call.args[0], frame_type)
    ]


@pytest.mark.asyncio
async def test_transcript_writer_pushes_rtvi_server_message():
    writer = TranscriptWriter(session_id="test-session")
    writer.push_frame = AsyncMock()

    frame = TranscriptionFrame(
        text="Hello, I need help.",
        user_id="user1",
        timestamp="2026-02-10T10:00:00Z",
    )
    await writer.process_frame(frame, FrameDirection.DOWNSTREAM)

    rtvi_frames = _get_frames_of_type(writer.push_frame, RTVIServerMessageFrame)
    assert len(rtvi_frames) == 1
    msg = rtvi_frames[0].data
    assert msg["action"] == "transcript_segment"
    assert msg["data"]["speaker"] == "customer"
    assert msg["data"]["text"] == "Hello, I need help."
    assert msg["data"]["sessionId"] == "test-session"
    assert msg["data"]["isFinal"] is True


@pytest.mark.asyncio
async def test_transcript_writer_no_rtvi_for_empty_text():
    writer = TranscriptWriter(session_id="test-session")
    writer.push_frame = AsyncMock()

    frame = TranscriptionFrame(text="  ", user_id="user1", timestamp="2026-02-10T10:00:00Z")
    await writer.process_frame(frame, FrameDirection.DOWNSTREAM)

    rtvi_frames = _get_frames_of_type(writer.push_frame, RTVIServerMessageFrame)
    assert len(rtvi_frames) == 0


@pytest.mark.asyncio
async def test_transcript_writer_always_emits_customer_speaker():
    writer = TranscriptWriter(session_id="test-session")
    writer.push_frame = AsyncMock()

    frame = TranscriptionFrame(
        text="Mein Konto wurde belastet.",
        user_id="any-user-id",
        timestamp="2026-02-10T10:00:00Z",
    )
    await writer.process_frame(frame, FrameDirection.DOWNSTREAM)

    rtvi_frames = _get_frames_of_type(writer.push_frame, RTVIServerMessageFrame)
    msg = rtvi_frames[0].data
    assert msg["data"]["speaker"] == "customer"
    assert msg["data"]["text"] == "Mein Konto wurde belastet."


@pytest.mark.asyncio
async def test_transcript_writer_passes_non_transcription_frames():
    writer = TranscriptWriter(session_id="test-session")
    writer.push_frame = AsyncMock()

    frame = Frame()
    await writer.process_frame(frame, FrameDirection.DOWNSTREAM)

    pushed = writer.push_frame.await_args_list
    assert len(pushed) == 1
    pushed_frame = pushed[0].args[0]
    assert isinstance(pushed_frame, Frame)
    assert not isinstance(pushed_frame, TranscriptionFrame)
