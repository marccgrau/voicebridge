"""Tests for suggestion agent processors."""

from unittest.mock import AsyncMock

import pytest
from pipecat.frames.frames import (
    LLMContextFrame,
    LLMFullResponseEndFrame,
    LLMFullResponseStartFrame,
    LLMTextFrame,
)
from pipecat.processors.frame_processor import FrameDirection

from src.frames import SuggestionFrame, TranscriptSegmentFrame
from src.processors import (
    SuggestionContextBuilder,
    SuggestionOutputProcessor,
    SuggestionRTVIObserver,
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
    assert "suggestion" in messages[0]["content"].lower()


@pytest.mark.asyncio
async def test_context_builder_no_process_context():
    """Verify no process block in LLM prompt — transcript only."""
    builder = SuggestionContextBuilder(session_id="test-session")
    builder.push_frame = AsyncMock()

    await builder.process_frame(
        _make_customer_frame("My card got stolen"),
        FrameDirection.DOWNSTREAM,
    )

    context_frames = _get_frames_of_type(builder.push_frame, LLMContextFrame)
    assert len(context_frames) == 1
    user_content = context_frames[0].context.messages[1]["content"]
    # Should NOT contain process context
    assert "Process:" not in user_content
    assert "Process Context:" not in user_content
    # Should contain conversation
    assert "My card got stolen" in user_content


@pytest.mark.asyncio
async def test_context_builder_consumes_transcript_frames():
    builder = SuggestionContextBuilder(session_id="test-session")
    builder.push_frame = AsyncMock()

    await builder.process_frame(
        _make_customer_frame("Hello"),
        FrameDirection.DOWNSTREAM,
    )

    transcript_frames = _get_frames_of_type(builder.push_frame, TranscriptSegmentFrame)
    assert len(transcript_frames) == 0

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
    assert suggestion_frames[0].service_type == "suggestion_agent"


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
    assert len(suggestion_frames[0].suggestions) == 1  # 1 fallback suggestion


@pytest.mark.asyncio
async def test_output_processor_limits_to_1_suggestion():
    processor = SuggestionOutputProcessor(session_id="test-session")
    processor.push_frame = AsyncMock()

    json_response = (
        '{"suggestions": ['
        '{"text": "One", "type": "response"},'
        '{"text": "Two", "type": "question"},'
        '{"text": "Three", "type": "action"}'
        "]}"
    )

    await processor.process_frame(LLMFullResponseStartFrame(), FrameDirection.DOWNSTREAM)
    await processor.process_frame(LLMTextFrame(text=json_response), FrameDirection.DOWNSTREAM)
    await processor.process_frame(LLMFullResponseEndFrame(), FrameDirection.DOWNSTREAM)

    suggestion_frames = _get_frames_of_type(processor.push_frame, SuggestionFrame)
    assert len(suggestion_frames) == 1
    assert len(suggestion_frames[0].suggestions) == 1
    assert suggestion_frames[0].suggestions[0]["text"] == "One"


# --- SuggestionRTVIObserver Tests ---


@pytest.mark.asyncio
async def test_rtvi_observer_publishes_suggestions():
    rtvi_processor = AsyncMock()
    observer = SuggestionRTVIObserver(rtvi_processor)
    observer.push_frame = AsyncMock()

    frame = SuggestionFrame(
        suggestions=[{"text": "Help the customer.", "type": "response"}],
        service_type="suggestion_agent",
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


# --- Integration: Full suggestion branch ---


class _FakeLLMProcessor:
    """Mock FrameProcessor that responds to LLMContextFrame."""

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
    """Test full suggestion branch: context builder -> fake LLM -> output processor.
    Verifies no process context and 1 suggestion output.
    """
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
        _make_customer_frame("My card got stolen"),
        FrameDirection.DOWNSTREAM,
    )

    suggestion_frames = _get_frames_of_type(output_processor.push_frame, SuggestionFrame)
    assert len(suggestion_frames) == 1
    # Should be limited to 1 suggestion
    assert len(suggestion_frames[0].suggestions) == 1
    assert suggestion_frames[0].suggestions[0]["type"] == "response"
    assert suggestion_frames[0].service_type == "suggestion_agent"
