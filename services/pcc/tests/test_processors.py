"""Tests for PCC pipeline processors."""

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

from src.frames import ProcessIllustrationFrame, SuggestionFrame, TranscriptSegmentFrame
from src.processors import (
    ProcessDetectionProcessor,
    SuggestionContextBuilder,
    SuggestionOutputProcessor,
    TranscriptWriter,
    VoiceBridgeRTVIObserver,
)

# --- Helpers ---


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


def _make_customer_frame(text: str, ts_suffix: str = "00") -> TranscriptSegmentFrame:
    return TranscriptSegmentFrame(
        session_id="test-session",
        speaker="customer",
        text=text,
        timestamp=f"2026-02-10T10:00:{ts_suffix}Z",
        is_final=True,
    )


def _setup_process_files(tmp_path: Path) -> None:
    _write_process_file(
        tmp_path / "lost_stolen_card.md",
        "lost_stolen_card",
        "Lost or Stolen Card",
        ["lost card", "stolen card", "block card"],
    )
    _write_process_file(
        tmp_path / "small_estates.md",
        "small_estates",
        "Small Estates",
        ["estate", "deceased"],
    )


def _get_frames_of_type(mock_push: AsyncMock, frame_type: type) -> list:
    return [
        call.args[0]
        for call in mock_push.await_args_list
        if call.args and isinstance(call.args[0], frame_type)
    ]


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
    assert transcript_frames[0].session_id == "test-session"
    assert transcript_frames[0].is_final is True


@pytest.mark.asyncio
async def test_transcript_writer_skips_empty_text():
    from pipecat.frames.frames import TranscriptionFrame

    writer = TranscriptWriter(session_id="test-session")
    writer.push_frame = AsyncMock()

    frame = TranscriptionFrame(text="   ", user_id="user1", timestamp="2026-02-10T10:00:00Z")
    await writer.process_frame(frame, FrameDirection.DOWNSTREAM)

    transcript_frames = _get_frames_of_type(writer.push_frame, TranscriptSegmentFrame)
    assert len(transcript_frames) == 0


# --- ProcessDetectionProcessor Tests ---


@pytest.mark.asyncio
async def test_process_detection_emits_process_illustration(tmp_path: Path):
    _setup_process_files(tmp_path)
    processor = ProcessDetectionProcessor(
        session_id="test-session",
        process_content_path=str(tmp_path),
        confidence_threshold=0.20,
        margin_threshold=0.10,
        min_utterances_before_detection=3,
    )
    processor.push_frame = AsyncMock()

    frames = [
        _make_customer_frame("Hello", "00"),
        _make_customer_frame("My debit card is gone", "01"),
        _make_customer_frame("I think it was stolen and I need to block it", "02"),
    ]
    for frame in frames:
        await processor.process_frame(frame, FrameDirection.DOWNSTREAM)

    process_frames = _get_frames_of_type(processor.push_frame, ProcessIllustrationFrame)
    assert process_frames
    assert process_frames[0].process_key == "lost_stolen_card"


@pytest.mark.asyncio
async def test_process_detection_passes_all_frames_through(tmp_path: Path):
    _setup_process_files(tmp_path)
    processor = ProcessDetectionProcessor(
        session_id="test-session",
        process_content_path=str(tmp_path),
        confidence_threshold=0.20,
        margin_threshold=0.10,
        min_utterances_before_detection=3,
    )
    processor.push_frame = AsyncMock()

    frames = [
        _make_customer_frame("Hello", "00"),
        _make_customer_frame("My debit card is gone", "01"),
        _make_customer_frame("I think it was stolen and I need to block it", "02"),
    ]
    for frame in frames:
        await processor.process_frame(frame, FrameDirection.DOWNSTREAM)

    transcript_frames = _get_frames_of_type(processor.push_frame, TranscriptSegmentFrame)
    assert len(transcript_frames) == 3


@pytest.mark.asyncio
async def test_process_detection_step_advancement(tmp_path: Path):
    _setup_process_files(tmp_path)
    processor = ProcessDetectionProcessor(
        session_id="test-session",
        process_content_path=str(tmp_path),
        confidence_threshold=0.20,
        margin_threshold=0.10,
        min_utterances_before_detection=3,
    )
    processor.push_frame = AsyncMock()

    frames = [
        _make_customer_frame("Hello", "00"),
        _make_customer_frame("My card is gone", "01"),
        _make_customer_frame("I need to block my stolen card", "02"),
    ]
    for frame in frames:
        await processor.process_frame(frame, FrameDirection.DOWNSTREAM)

    await processor.process_frame(
        _make_customer_frame("Please block the card now", "03"),
        FrameDirection.DOWNSTREAM,
    )

    process_frames = _get_frames_of_type(processor.push_frame, ProcessIllustrationFrame)
    assert len(process_frames) >= 1
    assert process_frames[0].process_key == "lost_stolen_card"


@pytest.mark.asyncio
async def test_process_detection_no_match_below_threshold(tmp_path: Path):
    _setup_process_files(tmp_path)
    processor = ProcessDetectionProcessor(
        session_id="test-session",
        process_content_path=str(tmp_path),
        confidence_threshold=0.99,
        margin_threshold=0.99,
        min_utterances_before_detection=3,
    )
    processor.push_frame = AsyncMock()

    frames = [
        _make_customer_frame("Hello", "00"),
        _make_customer_frame("How are you", "01"),
        _make_customer_frame("Just chatting", "02"),
    ]
    for frame in frames:
        await processor.process_frame(frame, FrameDirection.DOWNSTREAM)

    process_frames = _get_frames_of_type(processor.push_frame, ProcessIllustrationFrame)
    assert len(process_frames) == 0


# --- SuggestionContextBuilder Tests ---


@pytest.mark.asyncio
async def test_context_builder_pushes_llm_context_on_customer_utterance():
    builder = SuggestionContextBuilder(session_id="test-session")
    builder.push_frame = AsyncMock()

    await builder.process_frame(
        _make_customer_frame("My card is lost"),
        FrameDirection.DOWNSTREAM,
    )

    context_frames = _get_frames_of_type(builder.push_frame, LLMContextFrame)
    assert len(context_frames) == 1
    messages = context_frames[0].context.messages
    assert len(messages) == 2
    assert "suggestions" in messages[0]["content"].lower()


@pytest.mark.asyncio
async def test_context_builder_includes_process_context():
    builder = SuggestionContextBuilder(session_id="test-session")
    builder.push_frame = AsyncMock()

    await builder.process_frame(
        ProcessIllustrationFrame(
            process_key="lost_stolen_card",
            process_name="Lost or Stolen Card",
            steps=[{"key": "step_1", "label": "Verify Identity", "status": "in_progress"}],
            current_step=0,
            content="## Step 1: Verify Identity",
        ),
        FrameDirection.DOWNSTREAM,
    )

    await builder.process_frame(
        _make_customer_frame("My card got stolen"),
        FrameDirection.DOWNSTREAM,
    )

    context_frames = _get_frames_of_type(builder.push_frame, LLMContextFrame)
    assert len(context_frames) == 1
    user_content = context_frames[0].context.messages[1]["content"]
    assert "Lost or Stolen Card" in user_content
    assert "Verify Identity" in user_content


@pytest.mark.asyncio
async def test_context_builder_consumes_transcript_and_process_frames():
    builder = SuggestionContextBuilder(session_id="test-session")
    builder.push_frame = AsyncMock()

    await builder.process_frame(
        ProcessIllustrationFrame(
            process_key="lost_stolen_card",
            process_name="Lost or Stolen Card",
            steps=[],
            current_step=0,
            content="",
        ),
        FrameDirection.DOWNSTREAM,
    )
    await builder.process_frame(
        _make_customer_frame("Hello"),
        FrameDirection.DOWNSTREAM,
    )

    transcript_frames = _get_frames_of_type(builder.push_frame, TranscriptSegmentFrame)
    process_frames = _get_frames_of_type(builder.push_frame, ProcessIllustrationFrame)
    assert len(transcript_frames) == 0
    assert len(process_frames) == 0

    context_frames = _get_frames_of_type(builder.push_frame, LLMContextFrame)
    assert len(context_frames) == 1


# --- SuggestionOutputProcessor Tests ---


@pytest.mark.asyncio
async def test_output_processor_collects_llm_text_emits_suggestion():
    processor = SuggestionOutputProcessor(session_id="test-session")
    processor.push_frame = AsyncMock()

    await processor.process_frame(LLMFullResponseStartFrame(), FrameDirection.DOWNSTREAM)
    await processor.process_frame(
        LLMTextFrame(
            text='{"suggestions": [{"text": "Ask about the issue.", "type": "question"}]}'
        ),
        FrameDirection.DOWNSTREAM,
    )
    await processor.process_frame(LLMFullResponseEndFrame(), FrameDirection.DOWNSTREAM)

    suggestion_frames = _get_frames_of_type(processor.push_frame, SuggestionFrame)
    assert len(suggestion_frames) == 1
    assert suggestion_frames[0].suggestions[0]["text"] == "Ask about the issue."
    assert suggestion_frames[0].suggestions[0]["type"] == "question"
    assert suggestion_frames[0].service_type == "parallel_pipeline"


@pytest.mark.asyncio
async def test_output_processor_collects_chunked_response():
    processor = SuggestionOutputProcessor(session_id="test-session")
    processor.push_frame = AsyncMock()

    await processor.process_frame(LLMFullResponseStartFrame(), FrameDirection.DOWNSTREAM)
    await processor.process_frame(
        LLMTextFrame(text='{"suggestions": [{"text": "Ack'),
        FrameDirection.DOWNSTREAM,
    )
    await processor.process_frame(
        LLMTextFrame(text='nowledge the issue.", "type": "response"}]}'),
        FrameDirection.DOWNSTREAM,
    )
    await processor.process_frame(LLMFullResponseEndFrame(), FrameDirection.DOWNSTREAM)

    suggestion_frames = _get_frames_of_type(processor.push_frame, SuggestionFrame)
    assert len(suggestion_frames) == 1
    assert suggestion_frames[0].suggestions[0]["text"] == "Acknowledge the issue."


@pytest.mark.asyncio
async def test_output_processor_fallback_on_invalid_json():
    processor = SuggestionOutputProcessor(session_id="test-session")
    processor.push_frame = AsyncMock()

    await processor.process_frame(LLMFullResponseStartFrame(), FrameDirection.DOWNSTREAM)
    await processor.process_frame(
        LLMTextFrame(text="this is not valid json at all"),
        FrameDirection.DOWNSTREAM,
    )
    await processor.process_frame(LLMFullResponseEndFrame(), FrameDirection.DOWNSTREAM)

    suggestion_frames = _get_frames_of_type(processor.push_frame, SuggestionFrame)
    assert len(suggestion_frames) == 1
    assert len(suggestion_frames[0].suggestions) == 3  # fallback


@pytest.mark.asyncio
async def test_output_processor_consumes_llm_frames():
    processor = SuggestionOutputProcessor(session_id="test-session")
    processor.push_frame = AsyncMock()

    await processor.process_frame(LLMFullResponseStartFrame(), FrameDirection.DOWNSTREAM)
    await processor.process_frame(
        LLMTextFrame(text='{"suggestions": []}'),
        FrameDirection.DOWNSTREAM,
    )
    await processor.process_frame(LLMFullResponseEndFrame(), FrameDirection.DOWNSTREAM)

    start_frames = _get_frames_of_type(processor.push_frame, LLMFullResponseStartFrame)
    text_frames = _get_frames_of_type(processor.push_frame, LLMTextFrame)
    end_frames = _get_frames_of_type(processor.push_frame, LLMFullResponseEndFrame)
    assert len(start_frames) == 0
    assert len(text_frames) == 0
    assert len(end_frames) == 0


@pytest.mark.asyncio
async def test_output_processor_limits_to_3_suggestions():
    processor = SuggestionOutputProcessor(session_id="test-session")
    processor.push_frame = AsyncMock()

    json_response = (
        '{"suggestions": ['
        '{"text": "One", "type": "response"},'
        '{"text": "Two", "type": "question"},'
        '{"text": "Three", "type": "action"},'
        '{"text": "Four", "type": "escalation"}'
        "]}"
    )

    await processor.process_frame(LLMFullResponseStartFrame(), FrameDirection.DOWNSTREAM)
    await processor.process_frame(LLMTextFrame(text=json_response), FrameDirection.DOWNSTREAM)
    await processor.process_frame(LLMFullResponseEndFrame(), FrameDirection.DOWNSTREAM)

    suggestion_frames = _get_frames_of_type(processor.push_frame, SuggestionFrame)
    assert len(suggestion_frames) == 1
    assert len(suggestion_frames[0].suggestions) == 3


# --- VoiceBridgeRTVIObserver Tests ---


@pytest.mark.asyncio
async def test_rtvi_observer_publishes_suggestions():
    rtvi_processor = AsyncMock()
    observer = VoiceBridgeRTVIObserver(rtvi_processor)
    observer.push_frame = AsyncMock()

    frame = SuggestionFrame(
        suggestions=[{"text": "Help the customer.", "type": "response"}],
        service_type="parallel_pipeline",
        tools_used=["llm_inference"],
    )
    await observer.process_frame(frame, FrameDirection.DOWNSTREAM)

    rtvi_processor.send_server_message.assert_awaited_once()
    msg = rtvi_processor.send_server_message.call_args[0][0]
    assert msg["action"] == "agent_guidance"
    assert msg["data"]["suggestions"][0]["text"] == "Help the customer."

    # Frame should still pass through
    pushed = _get_frames_of_type(observer.push_frame, SuggestionFrame)
    assert len(pushed) == 1


@pytest.mark.asyncio
async def test_rtvi_observer_publishes_process_illustration():
    rtvi_processor = AsyncMock()
    observer = VoiceBridgeRTVIObserver(rtvi_processor)
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


@pytest.mark.asyncio
async def test_rtvi_observer_publishes_transcript():
    rtvi_processor = AsyncMock()
    observer = VoiceBridgeRTVIObserver(rtvi_processor)
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


@pytest.mark.asyncio
async def test_rtvi_observer_handles_send_failure():
    rtvi_processor = AsyncMock()
    rtvi_processor.send_server_message.side_effect = RuntimeError("RTVI not connected")
    observer = VoiceBridgeRTVIObserver(rtvi_processor)
    observer.push_frame = AsyncMock()

    frame = SuggestionFrame(
        suggestions=[{"text": "Help.", "type": "response"}],
        service_type="parallel_pipeline",
    )
    # Should not raise — best-effort delivery
    await observer.process_frame(frame, FrameDirection.DOWNSTREAM)

    # Frame should still pass through even on RTVI failure
    pushed = _get_frames_of_type(observer.push_frame, SuggestionFrame)
    assert len(pushed) == 1


# --- Integration: Full suggestion branch ---


class _FakeLLMProcessor:
    """Mock FrameProcessor that responds to LLMContextFrame with configurable response."""

    def __init__(self, response_text: str):
        self._response_text = response_text
        self._downstream: SuggestionOutputProcessor | None = None

    async def process_frame(self, frame, direction):
        if isinstance(frame, LLMContextFrame) and self._downstream:
            await self._downstream.process_frame(LLMFullResponseStartFrame(), direction)
            await self._downstream.process_frame(
                LLMTextFrame(text=self._response_text), direction
            )
            await self._downstream.process_frame(LLMFullResponseEndFrame(), direction)


@pytest.mark.asyncio
async def test_integration_suggestion_branch():
    """Test full suggestion branch: context builder -> fake LLM -> output processor."""
    context_builder = SuggestionContextBuilder(session_id="test-session")
    output_processor = SuggestionOutputProcessor(session_id="test-session")

    llm_response = (
        '{"suggestions": ['
        '{"text": "Acknowledge the customer concern.", "type": "response"},'
        '{"text": "Ask when the card was last used.", "type": "question"}'
        "]}"
    )
    fake_llm = _FakeLLMProcessor(llm_response)
    fake_llm._downstream = output_processor

    output_processor.push_frame = AsyncMock()

    async def forward_to_llm(frame, direction=FrameDirection.DOWNSTREAM):
        await fake_llm.process_frame(frame, direction)

    context_builder.push_frame = AsyncMock(side_effect=forward_to_llm)

    await context_builder.process_frame(
        ProcessIllustrationFrame(
            process_key="lost_stolen_card",
            process_name="Lost or Stolen Card",
            steps=[{"key": "step_1", "label": "Verify Identity", "status": "in_progress"}],
            current_step=0,
            content="## Step 1: Verify Identity",
        ),
        FrameDirection.DOWNSTREAM,
    )
    await context_builder.process_frame(
        _make_customer_frame("My card got stolen"),
        FrameDirection.DOWNSTREAM,
    )

    suggestion_frames = _get_frames_of_type(output_processor.push_frame, SuggestionFrame)
    assert len(suggestion_frames) == 1
    assert len(suggestion_frames[0].suggestions) == 2
    assert suggestion_frames[0].suggestions[0]["type"] == "response"
    assert suggestion_frames[0].service_type == "parallel_pipeline"
