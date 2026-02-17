"""Tests for transcript branch processors."""

from unittest.mock import AsyncMock

import pytest
from pipecat.frames.frames import EndFrame, TranscriptionFrame
from pipecat.processors.frame_processor import FrameDirection
from pipecat.processors.frameworks.rtvi import RTVIServerMessageFrame

from src.transcript_processors import TranscriptWriter


def _get_frames_of_type(mock_push: AsyncMock, frame_type: type) -> list:
    return [
        call.args[0]
        for call in mock_push.await_args_list
        if call.args and isinstance(call.args[0], frame_type)
    ]


class _PersistenceStub:
    def __init__(self):
        self.rows: list[dict] = []
        self.flush = AsyncMock()
        self.shutdown = AsyncMock()
        self.start = AsyncMock()

    def enqueue(self, row: dict) -> None:
        self.rows.append(row)


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
async def test_transcript_writer_enqueues_background_persistence_row():
    persistence = _PersistenceStub()
    writer = TranscriptWriter(session_id="test-session", persistence=persistence)
    writer.push_frame = AsyncMock()

    frame = TranscriptionFrame(
        text="Please help me with a transfer",
        user_id="user1",
        timestamp="2026-02-10T10:00:00Z",
    )
    await writer.process_frame(frame, FrameDirection.DOWNSTREAM)

    assert len(persistence.rows) == 1
    assert persistence.rows[0] == {
        "session_id": "test-session",
        "speaker": "customer",
        "text": "Please help me with a transfer",
        "is_final": True,
        "ts": "2026-02-10T10:00:00Z",
    }


@pytest.mark.asyncio
async def test_transcript_writer_flushes_on_end_frame():
    persistence = _PersistenceStub()
    writer = TranscriptWriter(session_id="test-session", persistence=persistence)
    writer.push_frame = AsyncMock()

    await writer.process_frame(EndFrame(), FrameDirection.DOWNSTREAM)

    persistence.flush.assert_awaited_once_with(timeout_seconds=2.0)
    end_frames = _get_frames_of_type(writer.push_frame, EndFrame)
    assert len(end_frames) == 1
