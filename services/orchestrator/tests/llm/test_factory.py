"""Tests for LLM service factory."""

import pytest
from pipecat.services.anthropic.llm import AnthropicLLMService
from pipecat.services.google.llm import GoogleLLMService
from pipecat.services.openai.llm import OpenAILLMService

from src.llm import LLMServiceFactory


class TestLLMServiceFactory:
    """Test LLM service factory."""

    def test_create_gemini_service(self, mocker):
        """Test creating Gemini LLM service."""
        mocker.patch("src.llm.factory.settings.google_api_key", "test-key")

        service = LLMServiceFactory.create_llm_service(
            provider="gemini",
            model="gemini-3-flash-preview",
        )

        assert isinstance(service, GoogleLLMService)

    def test_create_anthropic_service(self, mocker):
        """Test creating Anthropic LLM service."""
        mocker.patch("src.llm.factory.settings.anthropic_api_key", "test-key")

        service = LLMServiceFactory.create_llm_service(
            provider="anthropic",
            model="claude-sonnet-4-5-20250929",
        )

        assert isinstance(service, AnthropicLLMService)

    def test_create_openai_service(self, mocker):
        """Test creating OpenAI LLM service."""
        mocker.patch("src.llm.factory.settings.openai_api_key", "test-key")

        service = LLMServiceFactory.create_llm_service(
            provider="openai",
            model="gpt-4",
        )

        assert isinstance(service, OpenAILLMService)

    def test_missing_gemini_api_key(self, mocker):
        """Test error when Gemini API key is missing."""
        mocker.patch("src.llm.factory.settings.google_api_key", None)

        with pytest.raises(ValueError, match="GOOGLE_API_KEY.*required"):
            LLMServiceFactory.create_llm_service(
                provider="gemini",
                model="gemini-3-flash-preview",
            )

    def test_missing_anthropic_api_key(self, mocker):
        """Test error when Anthropic API key is missing."""
        mocker.patch("src.llm.factory.settings.anthropic_api_key", None)

        with pytest.raises(ValueError, match="ANTHROPIC_API_KEY.*required"):
            LLMServiceFactory.create_llm_service(
                provider="anthropic",
                model="claude-sonnet-4-5-20250929",
            )

    def test_missing_openai_api_key(self, mocker):
        """Test error when OpenAI API key is missing."""
        mocker.patch("src.llm.factory.settings.openai_api_key", None)

        with pytest.raises(ValueError, match="OPENAI_API_KEY.*required"):
            LLMServiceFactory.create_llm_service(
                provider="openai",
                model="gpt-4",
            )

    def test_invalid_provider(self, mocker):
        """Test error for invalid provider."""
        mocker.patch("src.llm.factory.settings.google_api_key", "test-key")

        with pytest.raises(ValueError, match="Unsupported LLM provider"):
            LLMServiceFactory.create_llm_service(
                provider="invalid",  # type: ignore
                model="some-model",
            )

    def test_validate_provider_config_gemini(self, mocker):
        """Test validating Gemini provider config."""
        mocker.patch("src.llm.factory.settings.google_api_key", "test-key")

        # Should not raise
        LLMServiceFactory.validate_provider_config("gemini")

    def test_validate_provider_config_missing_key(self, mocker):
        """Test validating provider config with missing key."""
        mocker.patch("src.llm.factory.settings.google_api_key", None)

        with pytest.raises(ValueError, match="GOOGLE_API_KEY.*required"):
            LLMServiceFactory.validate_provider_config("gemini")
