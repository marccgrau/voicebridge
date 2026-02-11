"""Tests for configuration settings."""

import pytest
from pydantic import ValidationError

from src.config import Settings


class TestSettings:
    """Tests for the Settings class."""

    def test_loads_all_required_fields(self, monkeypatch):
        """Test that all required environment variables can be loaded."""
        # Set all required env vars
        monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
        monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "test-key")
        monkeypatch.setenv("SPEECHMATICS_API_KEY", "sm-key")
        monkeypatch.setenv("GOOGLE_API_KEY", "google-key")
        monkeypatch.setenv("ANTHROPIC_API_KEY", "an-key")
        monkeypatch.setenv("OPENAI_API_KEY", "openai-key")
        monkeypatch.setenv("DAILY_API_KEY", "daily-key")

        settings = Settings()

        assert settings.supabase_url == "https://test.supabase.co"
        assert settings.supabase_service_role_key == "test-key"
        assert settings.speechmatics_api_key == "sm-key"
        assert settings.speechmatics_url == "wss://neu.rt.speechmatics.com/v2"
        assert settings.first_speaker_role == "customer"
        assert settings.google_api_key == "google-key"
        assert settings.anthropic_api_key == "an-key"
        assert settings.openai_api_key == "openai-key"
        assert settings.daily_api_key == "daily-key"

    def test_default_values_applied(self, monkeypatch):
        """Test that default values are applied for optional fields."""
        # Set only required env vars
        monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
        monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "test-key")
        monkeypatch.setenv("DAILY_API_KEY", "daily-key")

        settings = Settings()

        # Check default values
        assert settings.host == "0.0.0.0"
        assert settings.port == 8000
        assert settings.debug is False
        assert settings.stt_language == "en"
        assert settings.stt_include_partials is False
        assert settings.stt_enable_diarization is True
        assert settings.stt_max_speakers == 2
        assert settings.stt_prefer_current_speaker is True
        assert settings.default_stt_provider == "deepgram"
        assert settings.deepgram_model == "nova-3-general"
        assert settings.process_lookup_limit == 5
        assert settings.transcript_write_queue_size == 256

    def test_optional_fields_can_be_overridden(self, monkeypatch):
        """Test that optional fields can be overridden via env vars."""
        # Set required + optional env vars
        monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
        monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "test-key")
        monkeypatch.setenv("SPEECHMATICS_API_KEY", "sm-key")
        monkeypatch.setenv("ANTHROPIC_API_KEY", "an-key")
        monkeypatch.setenv("DAILY_API_KEY", "daily-key")
        monkeypatch.setenv("HOST", "127.0.0.1")
        monkeypatch.setenv("PORT", "9000")
        monkeypatch.setenv("DEBUG", "true")
        monkeypatch.setenv("STT_LANGUAGE", "es")
        monkeypatch.setenv("STT_INCLUDE_PARTIALS", "true")
        monkeypatch.setenv("STT_ENABLE_DIARIZATION", "false")
        monkeypatch.setenv("STT_MAX_SPEAKERS", "3")
        monkeypatch.setenv("STT_PREFER_CURRENT_SPEAKER", "false")
        monkeypatch.setenv("PROCESS_LOOKUP_LIMIT", "10")

        settings = Settings()

        assert settings.host == "127.0.0.1"
        assert settings.port == 9000
        assert settings.debug is True
        assert settings.stt_language == "es"
        assert settings.stt_include_partials is True
        assert settings.stt_enable_diarization is False
        assert settings.stt_max_speakers == 3
        assert settings.stt_prefer_current_speaker is False
        assert settings.process_lookup_limit == 10

    def test_missing_supabase_url_raises_validation_error(self, monkeypatch):
        """Test that missing required field raises validation error."""
        # Disable .env file loading for this test
        monkeypatch.delenv("SUPABASE_URL", raising=False)
        monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "test-key")
        monkeypatch.setenv("SPEECHMATICS_API_KEY", "sm-key")
        monkeypatch.setenv("ANTHROPIC_API_KEY", "an-key")
        monkeypatch.setenv("DAILY_API_KEY", "daily-key")

        # Create Settings with _env_file=None to prevent loading from .env
        with pytest.raises(ValidationError) as exc_info:
            Settings(_env_file=None)

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("supabase_url",) for error in errors)

    def test_missing_supabase_service_role_key_raises_error(self, monkeypatch):
        """Test that missing service role key raises validation error."""
        monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
        monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
        monkeypatch.setenv("SPEECHMATICS_API_KEY", "sm-key")
        monkeypatch.setenv("ANTHROPIC_API_KEY", "an-key")
        monkeypatch.setenv("DAILY_API_KEY", "daily-key")

        with pytest.raises(ValidationError) as exc_info:
            Settings(_env_file=None)

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("supabase_service_role_key",) for error in errors)

    def test_stt_api_keys_are_optional(self, monkeypatch):
        """Test that STT API keys are optional in config and validated at runtime."""
        monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
        monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "test-key")
        monkeypatch.delenv("SPEECHMATICS_API_KEY", raising=False)
        monkeypatch.delenv("DEEPGRAM_API_KEY", raising=False)
        monkeypatch.setenv("DAILY_API_KEY", "daily-key")

        settings = Settings(_env_file=None)
        assert settings.speechmatics_api_key is None
        assert settings.deepgram_api_key is None

    def test_llm_api_keys_are_optional(self, monkeypatch):
        """Test that LLM API keys are optional (at least one provider must be configured at runtime)."""
        monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
        monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "test-key")
        monkeypatch.setenv("SPEECHMATICS_API_KEY", "sm-key")
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.setenv("DAILY_API_KEY", "daily-key")

        # Should not raise - LLM keys are optional in config
        settings = Settings(_env_file=None)
        assert settings.anthropic_api_key is None
        assert settings.google_api_key is None
        assert settings.openai_api_key is None

    def test_missing_daily_api_key_raises_error(self, monkeypatch):
        """Test that missing Daily API key raises validation error."""
        monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
        monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "test-key")
        monkeypatch.setenv("SPEECHMATICS_API_KEY", "sm-key")
        monkeypatch.setenv("ANTHROPIC_API_KEY", "an-key")
        monkeypatch.delenv("DAILY_API_KEY", raising=False)

        with pytest.raises(ValidationError) as exc_info:
            Settings(_env_file=None)

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("daily_api_key",) for error in errors)

    def test_port_type_validation(self, monkeypatch):
        """Test that port must be an integer."""
        monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
        monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "test-key")
        monkeypatch.setenv("SPEECHMATICS_API_KEY", "sm-key")
        monkeypatch.setenv("ANTHROPIC_API_KEY", "an-key")
        monkeypatch.setenv("DAILY_API_KEY", "daily-key")
        monkeypatch.setenv("PORT", "not-a-number")

        with pytest.raises(ValidationError) as exc_info:
            Settings()

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("port",) for error in errors)

    def test_debug_boolean_conversion(self, monkeypatch):
        """Test that debug accepts various boolean representations."""
        monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
        monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "test-key")
        monkeypatch.setenv("SPEECHMATICS_API_KEY", "sm-key")
        monkeypatch.setenv("ANTHROPIC_API_KEY", "an-key")
        monkeypatch.setenv("DAILY_API_KEY", "daily-key")

        # Test various truthy values
        for value in ["1", "true", "True", "TRUE", "yes", "Yes"]:
            monkeypatch.setenv("DEBUG", value)
            settings = Settings()
            assert settings.debug is True, f"Failed for value: {value}"

        # Test various falsy values
        for value in ["0", "false", "False", "FALSE", "no", "No"]:
            monkeypatch.setenv("DEBUG", value)
            settings = Settings()
            assert settings.debug is False, f"Failed for value: {value}"

    def test_process_lookup_limit_type_validation(self, monkeypatch):
        """Test that process_lookup_limit must be an integer."""
        monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
        monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "test-key")
        monkeypatch.setenv("SPEECHMATICS_API_KEY", "sm-key")
        monkeypatch.setenv("ANTHROPIC_API_KEY", "an-key")
        monkeypatch.setenv("DAILY_API_KEY", "daily-key")
        monkeypatch.setenv("PROCESS_LOOKUP_LIMIT", "invalid")

        with pytest.raises(ValidationError) as exc_info:
            Settings()

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("process_lookup_limit",) for error in errors)

    def test_extra_fields_ignored(self, monkeypatch):
        """Test that extra environment variables are ignored."""
        monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
        monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "test-key")
        monkeypatch.setenv("SPEECHMATICS_API_KEY", "sm-key")
        monkeypatch.setenv("ANTHROPIC_API_KEY", "an-key")
        monkeypatch.setenv("DAILY_API_KEY", "daily-key")
        monkeypatch.setenv("UNKNOWN_FIELD", "some-value")
        monkeypatch.setenv("ANOTHER_RANDOM_VAR", "another-value")

        # Should not raise error due to model_config with extra="ignore"
        settings = Settings()

        # Unknown fields should not be set
        assert not hasattr(settings, "unknown_field")
        assert not hasattr(settings, "another_random_var")


class TestSettingsModuleLevel:
    """Tests for module-level settings instance."""

    def test_module_settings_is_settings_instance(self):
        """Test that module-level settings is a Settings instance."""
        from src.config import settings

        assert isinstance(settings, Settings)

    def test_module_settings_has_all_fields(self):
        """Test that module-level settings has all required fields."""
        from src.config import settings

        # Should have all fields (may be loaded from actual .env)
        assert hasattr(settings, "supabase_url")
        assert hasattr(settings, "supabase_service_role_key")
        assert hasattr(settings, "speechmatics_api_key")
        assert hasattr(settings, "deepgram_api_key")
        assert hasattr(settings, "default_stt_provider")
        assert hasattr(settings, "deepgram_model")
        assert hasattr(settings, "speechmatics_url")
        assert hasattr(settings, "first_speaker_role")
        assert hasattr(settings, "anthropic_api_key")
        assert hasattr(settings, "daily_api_key")
        assert hasattr(settings, "host")
        assert hasattr(settings, "port")
        assert hasattr(settings, "debug")
        assert hasattr(settings, "stt_language")
        assert hasattr(settings, "stt_include_partials")
        assert hasattr(settings, "stt_enable_diarization")
        assert hasattr(settings, "stt_max_speakers")
        assert hasattr(settings, "stt_prefer_current_speaker")
        assert hasattr(settings, "process_lookup_limit")
