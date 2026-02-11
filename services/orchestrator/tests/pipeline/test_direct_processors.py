"""Tests for direct_call guidance processors."""

import asyncio
from contextlib import suppress
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from pipecat.frames.frames import TranscriptionFrame
from pipecat.processors.frame_processor import FrameDirection

from src.frames import ProcessIllustrationFrame, SuggestionFrame
from src.pipeline.direct_processors import (
    DirectSuggestionProcessor,
    ProcessContextResolverProcessor,
)


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


class _FakeLLM:
    def __init__(self, response: str | None):
        self._response = response

    async def run_inference(self, _context):
        return self._response


class _SlowFakeLLM:
    """LLM that takes a configurable delay before returning."""

    def __init__(self, response: str, delay: float = 0.5):
        self._response = response
        self._delay = delay
        self.call_count = 0

    async def run_inference(self, _context):
        self.call_count += 1
        await asyncio.sleep(self._delay)
        return self._response


def _make_customer_frame(text: str, ts_suffix: str = "00") -> TranscriptionFrame:
    return TranscriptionFrame(
        text=text,
        user_id="customer",
        timestamp=f"2026-02-10T10:00:{ts_suffix}Z",
        finalized=True,
    )


def _make_resolver(tmp_path: Path, llm, **overrides) -> ProcessContextResolverProcessor:
    defaults = {
        "session_id": "test-session",
        "llm": llm,
        "process_content_path": str(tmp_path),
        "llm_timeout": 2.0,
        "shortlist_k": 3,
        "confidence_threshold": 0.65,
        "margin_threshold": 0.15,
        "cache_size": 8,
        "min_utterances_before_detection": 3,
    }
    defaults.update(overrides)
    return ProcessContextResolverProcessor(**defaults)


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


def _setup_ambiguous_process_files(tmp_path: Path) -> None:
    """Create two similar processes that require LLM disambiguation."""
    _write_process_file(
        tmp_path / "lost_stolen_card.md",
        "lost_stolen_card",
        "Lost or Stolen Card",
        ["lost card", "stolen card", "block card", "card problem"],
    )
    _write_process_file(
        tmp_path / "card_replacement.md",
        "card_replacement",
        "Card Replacement",
        ["replace card", "new card", "reissue card", "card problem"],
    )


def _get_process_frames(mock_push: AsyncMock) -> list[ProcessIllustrationFrame]:
    emitted = [call.args[0] for call in mock_push.await_args_list if call.args]
    return [f for f in emitted if isinstance(f, ProcessIllustrationFrame)]


@pytest.mark.asyncio
async def test_process_context_resolver_emits_process_illustration(tmp_path: Path):
    _setup_process_files(tmp_path)

    processor = _make_resolver(
        tmp_path,
        _FakeLLM('{"process_key":"lost_stolen_card","confidence":0.95}'),
    )
    processor.push_frame = AsyncMock()

    frames = [
        _make_customer_frame("Hello", "00"),
        _make_customer_frame("My debit card is gone", "01"),
        _make_customer_frame("I think it was stolen and I need to block it", "02"),
    ]

    for frame in frames:
        await processor.process_frame(frame, FrameDirection.DOWNSTREAM)

    # Wait for background disambiguation task if one was scheduled
    if processor._disambiguation_task:
        await processor._disambiguation_task

    process_frames = _get_process_frames(processor.push_frame)
    assert process_frames
    assert process_frames[0].process_key == "lost_stolen_card"


@pytest.mark.asyncio
async def test_process_resolver_does_not_block_frame_passthrough(tmp_path: Path):
    """process_frame() returns immediately even when LLM disambiguation is needed."""
    _setup_process_files(tmp_path)

    slow_llm = _SlowFakeLLM('{"process_key":"lost_stolen_card","confidence":0.95}', delay=0.3)
    processor = _make_resolver(tmp_path, slow_llm)
    processor.push_frame = AsyncMock()

    frames = [
        _make_customer_frame("Hello", "00"),
        _make_customer_frame("My debit card is gone", "01"),
        _make_customer_frame("I think it was stolen and I need to block it", "02"),
    ]

    # process_frame should return quickly, not block on the LLM
    for frame in frames:
        await asyncio.wait_for(
            processor.process_frame(frame, FrameDirection.DOWNSTREAM),
            timeout=0.1,  # Must return well under the LLM delay
        )

    # Transcript frames should have been passed through immediately
    passthrough_frames = [
        call.args[0]
        for call in processor.push_frame.await_args_list
        if call.args and isinstance(call.args[0], TranscriptionFrame)
    ]
    assert len(passthrough_frames) == 3

    # Now wait for background task to complete and verify result
    if processor._disambiguation_task:
        await processor._disambiguation_task
    process_frames = _get_process_frames(processor.push_frame)
    assert process_frames
    assert process_frames[0].process_key == "lost_stolen_card"


@pytest.mark.asyncio
async def test_process_resolver_cancels_stale_disambiguation(tmp_path: Path):
    """A new disambiguation cancels any in-flight stale one."""
    _setup_ambiguous_process_files(tmp_path)

    slow_llm = _SlowFakeLLM('{"process_key":"lost_stolen_card","confidence":0.95}', delay=0.5)
    # High margin forces LLM path; high confidence prevents metadata fallback
    processor = _make_resolver(tmp_path, slow_llm, margin_threshold=0.99, confidence_threshold=0.99)
    processor.push_frame = AsyncMock()

    # Ambiguous text that matches both processes
    for i in range(3):
        await processor.process_frame(
            _make_customer_frame("I have a problem with my card", f"{i:02d}"),
            FrameDirection.DOWNSTREAM,
        )

    first_task = processor._disambiguation_task
    assert first_task is not None

    # Send another customer frame to trigger a new disambiguation
    await processor.process_frame(
        _make_customer_frame("I have a card problem", "03"),
        FrameDirection.DOWNSTREAM,
    )

    # The first task should have been cancelled
    assert first_task.cancelled() or first_task.done()
    second_task = processor._disambiguation_task
    assert second_task is not first_task

    # Clean up
    if second_task and not second_task.done():
        second_task.cancel()
        with suppress(asyncio.CancelledError):
            await second_task


@pytest.mark.asyncio
async def test_process_resolver_stop_cancels_disambiguation(tmp_path: Path):
    """stop() cancels any in-flight disambiguation task."""
    _setup_ambiguous_process_files(tmp_path)

    slow_llm = _SlowFakeLLM('{"process_key":"lost_stolen_card","confidence":0.95}', delay=5.0)
    processor = _make_resolver(tmp_path, slow_llm, margin_threshold=0.99, confidence_threshold=0.99)
    processor.push_frame = AsyncMock()

    for i in range(3):
        await processor.process_frame(
            _make_customer_frame("I have a problem with my card", f"{i:02d}"),
            FrameDirection.DOWNSTREAM,
        )

    assert processor._disambiguation_task is not None
    assert not processor._disambiguation_task.done()

    await processor.stop()
    assert processor._disambiguation_task.done()


@pytest.mark.asyncio
async def test_process_resolver_llm_timeout(tmp_path: Path):
    """LLM timeout does not crash and process remains unresolved."""
    _setup_ambiguous_process_files(tmp_path)

    slow_llm = _SlowFakeLLM('{"process_key":"lost_stolen_card","confidence":0.95}', delay=5.0)
    # Very short timeout + high confidence threshold to prevent metadata fallback
    processor = _make_resolver(
        tmp_path, slow_llm, llm_timeout=0.05, margin_threshold=0.99, confidence_threshold=0.99
    )
    processor.push_frame = AsyncMock()

    for i in range(3):
        await processor.process_frame(
            _make_customer_frame("I have a problem with my card", f"{i:02d}"),
            FrameDirection.DOWNSTREAM,
        )

    if processor._disambiguation_task:
        await processor._disambiguation_task

    # Process should not be detected (LLM timed out, no metadata fallback with high thresholds)
    assert processor._detected_process is None


@pytest.mark.asyncio
async def test_direct_suggestion_processor_emits_llm_suggestions():
    llm = _FakeLLM(
        """{
            "suggestions": [
                {"text": "Acknowledge the issue clearly.", "type": "response"},
                {"text": "Ask when the card was last used.", "type": "question"},
                {"text": "Offer to block the card immediately.", "type": "action"}
            ]
        }"""
    )
    processor = DirectSuggestionProcessor(
        session_id="test-session",
        llm=llm,
        llm_timeout=2.0,
        conversation_window_size=8,
        debounce_ms=0,
    )
    processor.push_frame = AsyncMock()

    await processor.process_frame(
        ProcessIllustrationFrame(
            process_key="lost_stolen_card",
            process_name="Lost or Stolen Card",
            steps=[{"key": "step_1", "label": "Verify Identity", "status": "in_progress"}],
            current_step=0,
            content="## Step 1: Verify Identity",
        ),
        FrameDirection.DOWNSTREAM,
    )
    await processor.process_frame(
        TranscriptionFrame(
            text="My card got stolen",
            user_id="customer",
            timestamp="2026-02-10T10:00:00Z",
            finalized=True,
        ),
        FrameDirection.DOWNSTREAM,
    )
    if processor._suggestion_task:
        await processor._suggestion_task

    emitted_frames = [call.args[0] for call in processor.push_frame.await_args_list if call.args]
    suggestion_frames = [frame for frame in emitted_frames if isinstance(frame, SuggestionFrame)]
    assert suggestion_frames
    assert suggestion_frames[0].service_type == "direct_call"
    assert len(suggestion_frames[0].suggestions) == 3


@pytest.mark.asyncio
async def test_direct_suggestion_processor_falls_back_on_invalid_json():
    processor = DirectSuggestionProcessor(
        session_id="test-session",
        llm=_FakeLLM("not-json"),
        llm_timeout=2.0,
        conversation_window_size=8,
        debounce_ms=0,
    )
    processor.push_frame = AsyncMock()

    await processor.process_frame(
        TranscriptionFrame(
            text="I need help",
            user_id="customer",
            timestamp="2026-02-10T10:00:00Z",
            finalized=True,
        ),
        FrameDirection.DOWNSTREAM,
    )
    if processor._suggestion_task:
        await processor._suggestion_task

    emitted_frames = [call.args[0] for call in processor.push_frame.await_args_list if call.args]
    suggestion_frames = [frame for frame in emitted_frames if isinstance(frame, SuggestionFrame)]
    assert suggestion_frames
    assert len(suggestion_frames[0].suggestions) == 3


@pytest.mark.asyncio
async def test_direct_suggestion_processor_falls_back_on_none_response():
    """LLM returning None should produce fallback suggestions."""
    processor = DirectSuggestionProcessor(
        session_id="test-session",
        llm=_FakeLLM(None),
        llm_timeout=2.0,
        conversation_window_size=8,
        debounce_ms=0,
    )
    processor.push_frame = AsyncMock()

    await processor.process_frame(
        TranscriptionFrame(
            text="I need help",
            user_id="customer",
            timestamp="2026-02-10T10:00:00Z",
            finalized=True,
        ),
        FrameDirection.DOWNSTREAM,
    )
    if processor._suggestion_task:
        await processor._suggestion_task

    emitted_frames = [call.args[0] for call in processor.push_frame.await_args_list if call.args]
    suggestion_frames = [frame for frame in emitted_frames if isinstance(frame, SuggestionFrame)]
    assert suggestion_frames
    assert len(suggestion_frames[0].suggestions) == 3


@pytest.mark.asyncio
async def test_direct_suggestion_processor_accepts_partial_list():
    """1-2 valid suggestions should be accepted without fallback."""
    llm = _FakeLLM(
        '{"suggestions": [{"text": "Ask about the issue.", "type": "question"}, '
        '{"text": "Offer to help.", "type": "response"}]}'
    )
    processor = DirectSuggestionProcessor(
        session_id="test-session",
        llm=llm,
        llm_timeout=2.0,
        conversation_window_size=8,
        debounce_ms=0,
    )
    processor.push_frame = AsyncMock()

    await processor.process_frame(
        TranscriptionFrame(
            text="I need help",
            user_id="customer",
            timestamp="2026-02-10T10:00:00Z",
            finalized=True,
        ),
        FrameDirection.DOWNSTREAM,
    )
    if processor._suggestion_task:
        await processor._suggestion_task

    emitted_frames = [call.args[0] for call in processor.push_frame.await_args_list if call.args]
    suggestion_frames = [frame for frame in emitted_frames if isinstance(frame, SuggestionFrame)]
    assert suggestion_frames
    assert len(suggestion_frames[0].suggestions) == 2
    assert suggestion_frames[0].suggestions[0]["type"] == "question"
