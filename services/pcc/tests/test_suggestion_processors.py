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
        LLMTextFrame(text='{"advice": ["Fragen Sie nach der Transaktionsnummer.", "Bestätigen Sie das Anliegen."]}'),
        FrameDirection.DOWNSTREAM,
    )
    await processor.process_frame(LLMFullResponseEndFrame(), FrameDirection.DOWNSTREAM)

    msg = _get_single_rtvi_message(processor)
    assert msg["action"] == "agent_guidance"
    assert len(msg["data"]["advice"]) == 2
    assert msg["data"]["advice"][0]["text"] == "Fragen Sie nach der Transaktionsnummer."
    assert msg["data"]["advice"][1]["text"] == "Bestätigen Sie das Anliegen."


@pytest.mark.asyncio
async def test_output_processor_advice_items_have_uuid_ids():
    processor = SuggestionOutputProcessor(session_id="test-session")
    processor.push_frame = AsyncMock()

    await processor.process_frame(LLMFullResponseStartFrame(), FrameDirection.DOWNSTREAM)
    await processor.process_frame(
        LLMTextFrame(text='{"advice": ["Hinweis eins", "Hinweis zwei"]}'),
        FrameDirection.DOWNSTREAM,
    )
    await processor.process_frame(LLMFullResponseEndFrame(), FrameDirection.DOWNSTREAM)

    msg = _get_single_rtvi_message(processor)
    for item in msg["data"]["advice"]:
        assert "id" in item
        assert "text" in item
        # UUID format check (8-4-4-4-12)
        assert len(item["id"].split("-")) == 5


@pytest.mark.asyncio
async def test_output_processor_pushes_rtvi_server_message_metadata():
    processor = SuggestionOutputProcessor(session_id="test-session")
    processor.push_frame = AsyncMock()

    await processor.process_frame(LLMFullResponseStartFrame(), FrameDirection.DOWNSTREAM)
    await processor.process_frame(
        LLMTextFrame(text='{"advice": ["Bestätigen Sie das Anliegen."]}'),
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
        LLMTextFrame(text='{"advice": ["Bestätigen Sie das Anl'),
        FrameDirection.DOWNSTREAM,
    )
    await processor.process_frame(
        LLMTextFrame(text='iegen des Kunden."]}'),
        FrameDirection.DOWNSTREAM,
    )
    await processor.process_frame(LLMFullResponseEndFrame(), FrameDirection.DOWNSTREAM)

    msg = _get_single_rtvi_message(processor)
    assert msg["data"]["advice"][0]["text"] == "Bestätigen Sie das Anliegen des Kunden."


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
    assert len(msg["data"]["advice"]) == 1
    assert "id" in msg["data"]["advice"][0]
    assert msg["data"]["advice"][0]["text"] == "Anliegen bestätigen und offene Fragen klären"


@pytest.mark.asyncio
async def test_output_processor_passes_all_advice_items():
    processor = SuggestionOutputProcessor(session_id="test-session")
    processor.push_frame = AsyncMock()

    json_response = '{"advice": ["Eins", "Zwei", "Drei", "Vier"]}'

    await processor.process_frame(LLMFullResponseStartFrame(), FrameDirection.DOWNSTREAM)
    await processor.process_frame(LLMTextFrame(text=json_response), FrameDirection.DOWNSTREAM)
    await processor.process_frame(LLMFullResponseEndFrame(), FrameDirection.DOWNSTREAM)

    msg = _get_single_rtvi_message(processor)
    assert len(msg["data"]["advice"]) == 4
    assert msg["data"]["advice"][0]["text"] == "Eins"
    assert msg["data"]["advice"][3]["text"] == "Vier"


@pytest.mark.asyncio
async def test_output_processor_skips_empty_strings():
    processor = SuggestionOutputProcessor(session_id="test-session")
    processor.push_frame = AsyncMock()

    json_response = '{"advice": ["Valid", "", "  ", "Also valid"]}'

    await processor.process_frame(LLMFullResponseStartFrame(), FrameDirection.DOWNSTREAM)
    await processor.process_frame(LLMTextFrame(text=json_response), FrameDirection.DOWNSTREAM)
    await processor.process_frame(LLMFullResponseEndFrame(), FrameDirection.DOWNSTREAM)

    msg = _get_single_rtvi_message(processor)
    assert len(msg["data"]["advice"]) == 2
    assert msg["data"]["advice"][0]["text"] == "Valid"
    assert msg["data"]["advice"][1]["text"] == "Also valid"


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


def test_suggestion_prompt_has_customer_only_transcript_rule():
    prompt = build_suggestion_system_prompt()
    assert "Kundenäusserungen" in prompt
    assert "nur Kundenaudio wird transkribiert" in prompt


def test_suggestion_prompt_has_process_pilot_identity():
    prompt = build_suggestion_system_prompt()
    assert "Process-Pilot" in prompt
    assert '"advice"' in prompt
