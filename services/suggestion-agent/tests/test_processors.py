"""Tests for suggestion agent processors."""

from unittest.mock import AsyncMock

import pytest
from pipecat.frames.frames import LLMFullResponseEndFrame, LLMFullResponseStartFrame, LLMTextFrame
from pipecat.processors.frame_processor import FrameDirection
from pipecat.processors.frameworks.rtvi import RTVIServerMessageFrame

from src.processors import SuggestionOutputProcessor


def _get_frames_of_type(mock_push: AsyncMock, frame_type: type) -> list:
    return [
        call.args[0]
        for call in mock_push.await_args_list
        if call.args and isinstance(call.args[0], frame_type)
    ]


def _get_single_rtvi_message(processor: SuggestionOutputProcessor) -> dict:
    rtvi_frames = _get_frames_of_type(processor.push_frame, RTVIServerMessageFrame)
    assert len(rtvi_frames) == 1
    return rtvi_frames[0].data


@pytest.mark.asyncio
async def test_output_processor_collects_llm_text_emits_rtvi_message():
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

    msg = _get_single_rtvi_message(processor)
    assert msg["action"] == "agent_guidance"
    assert msg["data"]["suggestions"][0]["text"] == "Ask about the issue."
    assert msg["data"]["suggestions"][0]["type"] == "question"


@pytest.mark.asyncio
async def test_output_processor_pushes_rtvi_server_message_metadata():
    processor = SuggestionOutputProcessor(session_id="test-session")
    processor.push_frame = AsyncMock()

    await processor.process_frame(LLMFullResponseStartFrame(), FrameDirection.DOWNSTREAM)
    await processor.process_frame(
        LLMTextFrame(
            text='{"suggestions": [{"text": "Help the customer.", "type": "response"}]}'
        ),
        FrameDirection.DOWNSTREAM,
    )
    await processor.process_frame(LLMFullResponseEndFrame(), FrameDirection.DOWNSTREAM)

    msg = _get_single_rtvi_message(processor)
    assert msg["action"] == "agent_guidance"
    assert msg["data"]["serviceType"] == "suggestion_agent"
    assert msg["data"]["toolsUsed"] == ["llm_inference"]


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

    msg = _get_single_rtvi_message(processor)
    assert msg["data"]["suggestions"][0]["text"] == "Acknowledge the issue."


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

    msg = _get_single_rtvi_message(processor)
    assert len(msg["data"]["suggestions"]) == 1
    assert msg["data"]["suggestions"][0]["type"] == "response"


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

    msg = _get_single_rtvi_message(processor)
    assert len(msg["data"]["suggestions"]) == 1
    assert msg["data"]["suggestions"][0]["text"] == "One"


class _FakeLLMProcessor:
    """Mock LLM that streams one response into a downstream processor."""

    def __init__(self, response_text: str):
        self._response_text = response_text

    async def emit(self, downstream: SuggestionOutputProcessor):
        await downstream.process_frame(LLMFullResponseStartFrame(), FrameDirection.DOWNSTREAM)
        await downstream.process_frame(
            LLMTextFrame(text=self._response_text),
            FrameDirection.DOWNSTREAM,
        )
        await downstream.process_frame(LLMFullResponseEndFrame(), FrameDirection.DOWNSTREAM)


@pytest.mark.asyncio
async def test_integration_fake_llm_to_output_processor():
    """Test fake LLM -> output processor integration with one emitted suggestion."""
    output_processor = SuggestionOutputProcessor(session_id="test-session")
    output_processor.push_frame = AsyncMock()

    llm_response = (
        '{"suggestions": ['
        '{"text": "Acknowledge the customer concern.", "type": "response"},'
        '{"text": "Ask when the card was last used.", "type": "question"}'
        "]}"
    )
    fake_llm = _FakeLLMProcessor(llm_response)

    await fake_llm.emit(output_processor)

    msg = _get_single_rtvi_message(output_processor)
    assert msg["action"] == "agent_guidance"
    assert len(msg["data"]["suggestions"]) == 1
    assert msg["data"]["suggestions"][0]["type"] == "response"
