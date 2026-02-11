"""Tests for pipeline builder wiring and STT configuration."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pipecat.services.speechmatics.stt import Language

import src.pipeline.builder as builder_module
from src.pipeline.builder import VoiceBridgePipelineBuilder


@pytest.fixture
def configure_builder_settings(monkeypatch):
    """Configure deterministic settings for builder tests."""
    monkeypatch.setattr(builder_module.settings, "speechmatics_api_key", "sm-key")
    monkeypatch.setattr(
        builder_module.settings,
        "speechmatics_url",
        "wss://neu.rt.speechmatics.com/v2",
    )
    monkeypatch.setattr(builder_module.settings, "stt_language", "es")
    monkeypatch.setattr(builder_module.settings, "stt_include_partials", False)
    monkeypatch.setattr(builder_module.settings, "stt_enable_diarization", True)
    monkeypatch.setattr(builder_module.settings, "stt_max_speakers", 2)
    monkeypatch.setattr(builder_module.settings, "stt_prefer_current_speaker", True)
    monkeypatch.setattr(builder_module.settings, "first_speaker_role", "customer")


def _build_test_builder() -> VoiceBridgePipelineBuilder:
    return VoiceBridgePipelineBuilder(
        session_id="test-session",
        room_url="https://example.daily.co/test-room",
        room_token="test-token",
        enable_process_flow=False,
        enable_suggestion_flow=False,
        process_flow_provider="openai",
        process_flow_model="gpt-5-nano",
        suggestion_flow_provider="openai",
        suggestion_flow_model="gpt-5-nano",
        process_content_path="process_content/",
    )


def _build_flow_enabled_builder() -> VoiceBridgePipelineBuilder:
    return VoiceBridgePipelineBuilder(
        session_id="test-session",
        room_url="https://example.daily.co/test-room",
        room_token="test-token",
        enable_process_flow=True,
        enable_suggestion_flow=True,
        process_flow_provider="openai",
        process_flow_model="gpt-5-nano",
        suggestion_flow_provider="openai",
        suggestion_flow_model="gpt-5-nano",
        process_content_path="process_content/",
    )


@pytest.mark.usefixtures("configure_builder_settings")
@pytest.mark.asyncio
async def test_build_wires_stt_before_transcript_writer():
    """Test STT is placed before TranscriptWriter in the pipeline (no user aggregator)."""
    builder = _build_test_builder()
    components = await builder.build()

    processors = components.pipeline.processors
    names = [type(processor).__name__ for processor in processors]

    input_idx = names.index("DailyInputTransport")
    stt_idx = names.index("SpeechmaticsSTTService")
    transcript_idx = names.index("TranscriptWriter")

    assert input_idx < stt_idx < transcript_idx
    assert "LLMUserAggregator" not in names


@pytest.mark.usefixtures("configure_builder_settings")
@pytest.mark.asyncio
async def test_build_sets_explicit_speechmatics_input_params(monkeypatch):
    """Test Speechmatics InputParams are explicitly set from config."""
    monkeypatch.setattr(builder_module.settings, "stt_include_partials", True)
    monkeypatch.setattr(builder_module.settings, "stt_enable_diarization", False)
    monkeypatch.setattr(builder_module.settings, "stt_max_speakers", 3)
    monkeypatch.setattr(builder_module.settings, "stt_prefer_current_speaker", False)

    builder = _build_test_builder()
    components = await builder.build()

    stt = next(
        processor
        for processor in components.pipeline.processors
        if type(processor).__name__ == "SpeechmaticsSTTService"
    )

    assert stt._base_url == "wss://neu.rt.speechmatics.com/v2"
    assert stt._config.language == "es"
    assert stt._config.end_of_utterance_mode.value == "adaptive"
    assert stt._config.include_partials is True
    assert stt._config.speech_segment_config.emit_sentences is False
    assert stt._config.enable_diarization is False
    assert stt._config.max_speakers == 3
    assert stt._config.prefer_current_speaker is False


def test_resolve_stt_language_accepts_enum_values():
    """Test language resolution accepts canonical language values."""
    assert VoiceBridgePipelineBuilder._resolve_stt_language("en") == Language.EN
    assert VoiceBridgePipelineBuilder._resolve_stt_language("EN") == Language.EN


def test_resolve_stt_language_raises_on_invalid_value():
    """Test invalid language strings raise a clear error."""
    with pytest.raises(ValueError, match="Unsupported STT_LANGUAGE"):
        VoiceBridgePipelineBuilder._resolve_stt_language("not-a-language")


@pytest.mark.usefixtures("configure_builder_settings")
@pytest.mark.asyncio
async def test_build_uses_direct_processors_only():
    """Test builder wires direct processors and never calls legacy flow builders."""
    builder = _build_flow_enabled_builder()
    fake_process_resolver = MagicMock()
    fake_suggestion_processor = MagicMock()

    builder._build_process_context_resolver = AsyncMock(return_value=fake_process_resolver)
    builder._build_direct_suggestion_processor = AsyncMock(return_value=fake_suggestion_processor)

    components = await builder.build()

    builder._build_process_context_resolver.assert_awaited_once()
    builder._build_direct_suggestion_processor.assert_awaited_once()
    assert components.process_context_resolver is fake_process_resolver
    assert components.direct_suggestion_processor is fake_suggestion_processor


@pytest.mark.usefixtures("configure_builder_settings")
@pytest.mark.asyncio
async def test_build_wires_separate_llm_timeouts(monkeypatch):
    """Test process and suggestion processors get separate timeout values."""
    monkeypatch.setattr(builder_module.settings, "process_detection_llm_timeout", 8.0)
    monkeypatch.setattr(builder_module.settings, "suggestion_llm_timeout", 15.0)

    builder = _build_flow_enabled_builder()

    with patch("src.pipeline.builder.LLMServiceFactory") as mock_factory:
        mock_factory.create_llm_service.return_value = MagicMock()
        components = await builder.build()

    assert components.process_context_resolver._llm_timeout == 8.0
    assert components.direct_suggestion_processor._llm_timeout == 15.0


@pytest.mark.usefixtures("configure_builder_settings")
@pytest.mark.asyncio
async def test_build_uses_smart_turn_mode():
    """Test that STT is configured with SMART_TURN mode."""
    builder = _build_test_builder()
    components = await builder.build()

    stt = next(
        processor
        for processor in components.pipeline.processors
        if type(processor).__name__ == "SpeechmaticsSTTService"
    )

    assert stt._config.end_of_utterance_mode.value == "adaptive"
