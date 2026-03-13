"""Tests for suggestion branch processors."""

from typing import Any
from unittest.mock import AsyncMock

import pytest
from pipecat.frames.frames import LLMFullResponseEndFrame, LLMFullResponseStartFrame, LLMTextFrame
from pipecat.processors.frame_processor import FrameDirection
from pipecat.processors.frameworks.rtvi import RTVIServerMessageFrame

from src.suggestion_processors import SuggestionOutputProcessor, build_suggestion_system_prompt


def _get_frames_of_type(mock_push: Any, frame_type: type) -> list:
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
        LLMTextFrame(text='{"suggestions": [{"text": "Ask about the issue.", "type": "question"}]}'),
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
        LLMTextFrame(text='{"suggestions": [{"text": "Help the customer.", "type": "response"}]}'),
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
        ']}'
    )

    await processor.process_frame(LLMFullResponseStartFrame(), FrameDirection.DOWNSTREAM)
    await processor.process_frame(LLMTextFrame(text=json_response), FrameDirection.DOWNSTREAM)
    await processor.process_frame(LLMFullResponseEndFrame(), FrameDirection.DOWNSTREAM)

    msg = _get_single_rtvi_message(processor)
    assert len(msg["data"]["suggestions"]) == 1
    assert msg["data"]["suggestions"][0]["text"] == "One"


# --- build_suggestion_system_prompt tests ---


def test_build_suggestion_system_prompt_with_kb_only():
    prompt = build_suggestion_system_prompt(kb_content="Some KB info")
    assert "Wissensbasis für dieses Szenario:" in prompt
    assert "Some KB info" in prompt
    assert "Prozessdefinition:" not in prompt


def test_build_suggestion_system_prompt_with_process_content():
    prompt = build_suggestion_system_prompt(
        process_content="Prozess: Kreditablehnung\n  Step 0 – Begrüssung: Kunden begrüssen"
    )
    assert "Prozessdefinition:" in prompt
    assert "Kreditablehnung" in prompt
    assert "Begrüssung" in prompt


def test_build_suggestion_system_prompt_with_both():
    prompt = build_suggestion_system_prompt(
        kb_content="KB info here",
        process_content="Process info here",
    )
    assert "Wissensbasis für dieses Szenario:" in prompt
    assert "KB info here" in prompt
    assert "Prozessdefinition:" in prompt
    assert "Process info here" in prompt


def test_build_suggestion_system_prompt_empty():
    prompt = build_suggestion_system_prompt()
    assert "Prozessdefinition:" not in prompt
    assert "Wissensbasis für dieses Szenario:" not in prompt


def test_suggestion_prompt_has_speaker_awareness():
    prompt = build_suggestion_system_prompt()
    assert "[Kunde]" in prompt
    assert "[Berater]" in prompt
    assert "redundanten Vorschläge" in prompt
