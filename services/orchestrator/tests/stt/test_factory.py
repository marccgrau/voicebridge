"""Tests for STT service factory."""

import pytest
from pipecat.services.deepgram.stt import DeepgramSTTService
from pipecat.services.speechmatics.stt import Language, SpeechmaticsSTTService

from src.stt import STTServiceFactory


class TestSTTServiceFactory:
    """Test STT service factory."""

    def test_create_speechmatics_service(self, mocker):
        """Test creating Speechmatics STT service."""
        mocker.patch("src.stt.factory.settings.speechmatics_api_key", "test-key")

        service = STTServiceFactory.create_stt_service(provider="speechmatics", language="en")

        assert isinstance(service, SpeechmaticsSTTService)

    def test_create_deepgram_service(self, mocker):
        """Test creating Deepgram STT service."""
        mocker.patch("src.stt.factory.settings.deepgram_api_key", "test-key")

        service = STTServiceFactory.create_stt_service(provider="deepgram", language="en")

        assert isinstance(service, DeepgramSTTService)

    def test_missing_speechmatics_api_key(self, mocker):
        """Test error when Speechmatics API key is missing."""
        mocker.patch("src.stt.factory.settings.speechmatics_api_key", None)

        with pytest.raises(ValueError, match="SPEECHMATICS_API_KEY"):
            STTServiceFactory.create_stt_service(provider="speechmatics", language="en")

    def test_missing_deepgram_api_key(self, mocker):
        """Test error when Deepgram API key is missing."""
        mocker.patch("src.stt.factory.settings.deepgram_api_key", None)

        with pytest.raises(ValueError, match="DEEPGRAM_API_KEY"):
            STTServiceFactory.create_stt_service(provider="deepgram", language="en")

    def test_invalid_provider(self, mocker):
        """Test error for invalid provider."""
        mocker.patch("src.stt.factory.settings.speechmatics_api_key", "test-key")

        with pytest.raises(ValueError, match="Unsupported STT provider"):
            STTServiceFactory.create_stt_service(provider="invalid", language="en")  # type: ignore[arg-type]

    def test_validate_provider_config_speechmatics(self, mocker):
        """Test validating Speechmatics provider config."""
        mocker.patch("src.stt.factory.settings.speechmatics_api_key", "test-key")

        STTServiceFactory.validate_provider_config("speechmatics")

    def test_validate_provider_config_missing_key(self, mocker):
        """Test validating provider config with missing key."""
        mocker.patch("src.stt.factory.settings.speechmatics_api_key", None)

        with pytest.raises(ValueError, match="SPEECHMATICS_API_KEY"):
            STTServiceFactory.validate_provider_config("speechmatics")

    def test_speechmatics_uses_smart_turn(self, mocker):
        """Test that Speechmatics STT is configured with SMART_TURN mode."""
        mocker.patch("src.stt.factory.settings.speechmatics_api_key", "test-key")

        service = STTServiceFactory.create_stt_service(provider="speechmatics", language="en")

        assert service._config.end_of_utterance_mode.value == "adaptive"

    def test_speechmatics_maps_config_params(self, mocker):
        """Test Speechmatics InputParams are mapped from app settings."""
        mocker.patch("src.stt.factory.settings.speechmatics_api_key", "test-key")
        mocker.patch(
            "src.stt.factory.settings.speechmatics_url", "wss://neu.rt.speechmatics.com/v2"
        )
        mocker.patch("src.stt.factory.settings.stt_include_partials", True)
        mocker.patch("src.stt.factory.settings.stt_enable_diarization", False)
        mocker.patch("src.stt.factory.settings.stt_max_speakers", 3)
        mocker.patch("src.stt.factory.settings.stt_prefer_current_speaker", False)

        service = STTServiceFactory.create_stt_service(provider="speechmatics", language="es")

        assert service._base_url == "wss://neu.rt.speechmatics.com/v2"
        assert service._config.language == "es"
        assert service._config.include_partials is True
        assert service._config.enable_diarization is False
        assert service._config.max_speakers == 3
        assert service._config.prefer_current_speaker is False

    def test_deepgram_maps_config_params(self, mocker):
        """Test Deepgram LiveOptions are mapped from app settings."""
        mocker.patch("src.stt.factory.settings.deepgram_api_key", "test-key")
        mocker.patch("src.stt.factory.settings.deepgram_model", "nova-3-general")

        service = STTServiceFactory.create_stt_service(provider="deepgram", language="en")

        assert service._settings["language"] == "en-US"
        assert service._settings["model"] == "nova-3-general"
        assert service._settings["smart_format"] is True
        assert service._settings["endpointing"] is True
        assert service._settings["profanity_filter"] is False
        assert service._settings["interim_results"] is True

    def test_language_resolution(self):
        """Test language resolution accepts known values and rejects invalid ones."""
        assert STTServiceFactory._resolve_stt_language("en") == Language.EN
        assert STTServiceFactory._resolve_stt_language("EN") == Language.EN

        with pytest.raises(ValueError, match="Unsupported STT_LANGUAGE"):
            STTServiceFactory._resolve_stt_language("not-a-language")
