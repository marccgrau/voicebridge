"""Tests for transcript branch processors."""

from unittest.mock import AsyncMock

import pytest
from pipecat.frames.frames import Frame, TranscriptionFrame
from pipecat.processors.frame_processor import FrameDirection
from pipecat.processors.frameworks.rtvi import RTVIServerMessageFrame

from src.transcript_processors import SpeakerLabelingProcessor, TranscriptWriter


def _get_frames_of_type(mock_push: AsyncMock, frame_type: type) -> list:
    return [
        call.args[0]
        for call in mock_push.await_args_list
        if call.args and isinstance(call.args[0], frame_type)
    ]


# --- SpeakerLabelingProcessor tests ---


@pytest.mark.asyncio
async def test_speaker_labeler_labels_customer():
    speaker_map = {"user1": "customer"}
    labeler = SpeakerLabelingProcessor(speaker_map=speaker_map)
    labeler.push_frame = AsyncMock()

    frame = TranscriptionFrame(text="Hallo, ich brauche Hilfe.", user_id="user1", timestamp="t1")
    await labeler.process_frame(frame, FrameDirection.DOWNSTREAM)

    pushed = labeler.push_frame.await_args_list
    assert len(pushed) == 1
    pushed_frame = pushed[0].args[0]
    assert isinstance(pushed_frame, TranscriptionFrame)
    assert pushed_frame.text == "[Kunde] Hallo, ich brauche Hilfe."


@pytest.mark.asyncio
async def test_speaker_labeler_labels_agent():
    speaker_map = {"agent1": "agent"}
    labeler = SpeakerLabelingProcessor(speaker_map=speaker_map)
    labeler.push_frame = AsyncMock()

    frame = TranscriptionFrame(text="Wie kann ich helfen?", user_id="agent1", timestamp="t1")
    await labeler.process_frame(frame, FrameDirection.DOWNSTREAM)

    pushed_frame = labeler.push_frame.await_args_list[0].args[0]
    assert pushed_frame.text == "[Berater] Wie kann ich helfen?"


@pytest.mark.asyncio
async def test_speaker_labeler_defaults_to_customer_for_unknown():
    speaker_map = {}
    labeler = SpeakerLabelingProcessor(speaker_map=speaker_map)
    labeler.push_frame = AsyncMock()

    frame = TranscriptionFrame(text="Unknown speaker.", user_id="unknown_id", timestamp="t1")
    await labeler.process_frame(frame, FrameDirection.DOWNSTREAM)

    pushed_frame = labeler.push_frame.await_args_list[0].args[0]
    assert pushed_frame.text == "[Kunde] Unknown speaker."


@pytest.mark.asyncio
async def test_speaker_labeler_passes_non_transcription_frames():
    labeler = SpeakerLabelingProcessor(speaker_map={})
    labeler.push_frame = AsyncMock()

    frame = Frame()
    await labeler.process_frame(frame, FrameDirection.DOWNSTREAM)

    pushed_frame = labeler.push_frame.await_args_list[0].args[0]
    assert isinstance(pushed_frame, Frame)
    assert not isinstance(pushed_frame, TranscriptionFrame)


# --- TranscriptWriter tests ---


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
async def test_transcript_writer_uses_speaker_map_for_agent():
    speaker_map = {"agent1": "agent"}
    writer = TranscriptWriter(session_id="test-session", speaker_map=speaker_map)
    writer.push_frame = AsyncMock()

    frame = TranscriptionFrame(
        text="[Berater] Ich helfe Ihnen gerne.",
        user_id="agent1",
        timestamp="2026-02-10T10:00:00Z",
    )
    await writer.process_frame(frame, FrameDirection.DOWNSTREAM)

    rtvi_frames = _get_frames_of_type(writer.push_frame, RTVIServerMessageFrame)
    assert len(rtvi_frames) == 1
    msg = rtvi_frames[0].data
    assert msg["data"]["speaker"] == "agent"
    assert msg["data"]["text"] == "Ich helfe Ihnen gerne."


@pytest.mark.asyncio
async def test_transcript_writer_strips_kunde_prefix():
    speaker_map = {"cust1": "customer"}
    writer = TranscriptWriter(session_id="test-session", speaker_map=speaker_map)
    writer.push_frame = AsyncMock()

    frame = TranscriptionFrame(
        text="[Kunde] Mein Konto wurde belastet.",
        user_id="cust1",
        timestamp="2026-02-10T10:00:00Z",
    )
    await writer.process_frame(frame, FrameDirection.DOWNSTREAM)

    rtvi_frames = _get_frames_of_type(writer.push_frame, RTVIServerMessageFrame)
    msg = rtvi_frames[0].data
    assert msg["data"]["text"] == "Mein Konto wurde belastet."
    assert msg["data"]["speaker"] == "customer"


@pytest.mark.asyncio
async def test_transcript_writer_defaults_to_customer_without_speaker_map():
    writer = TranscriptWriter(session_id="test-session")
    writer.push_frame = AsyncMock()

    frame = TranscriptionFrame(
        text="Some text.",
        user_id="unknown",
        timestamp="2026-02-10T10:00:00Z",
    )
    await writer.process_frame(frame, FrameDirection.DOWNSTREAM)

    rtvi_frames = _get_frames_of_type(writer.push_frame, RTVIServerMessageFrame)
    msg = rtvi_frames[0].data
    assert msg["data"]["speaker"] == "customer"
