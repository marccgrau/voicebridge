"""Tests for transcript branch processors."""

from unittest.mock import AsyncMock

import pytest
from pipecat.frames.frames import TranscriptionFrame
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
