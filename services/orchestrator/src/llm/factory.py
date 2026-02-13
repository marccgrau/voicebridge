"""Factory for creating LLM service instances based on provider."""

import logging
from typing import Literal

from pipecat.services.anthropic.llm import AnthropicLLMService
from pipecat.services.google.llm import GoogleLLMService
from pipecat.services.openai.llm import OpenAILLMService

from ..config import settings

logger = logging.getLogger(__name__)

LLMProvider = Literal["gemini", "anthropic", "openai"]


class LLMServiceFactory:
    """Factory for creating LLM service instances."""

    @staticmethod
    def create_llm_service(
        provider: LLMProvider,
        model: str,
    ) -> AnthropicLLMService | GoogleLLMService | OpenAILLMService:
        """
        Create an LLM service instance for the specified provider.

        Args:
            provider: The LLM provider ("gemini", "anthropic", or "openai")
            model: The model identifier to use

        Returns:
            Configured LLM service instance

        Raises:
            ValueError: If provider is unsupported or API key is missing
        """
        logger.info("Creating LLM service: provider=%s, model=%s", provider, model)

        if provider == "gemini":
            if not settings.google_api_key:
                raise ValueError(
                    "GOOGLE_API_KEY environment variable is required for Gemini provider"
                )
            return GoogleLLMService(
                api_key=settings.google_api_key,
                model=model,
            )
        elif provider == "anthropic":
            if not settings.anthropic_api_key:
                raise ValueError(
                    "ANTHROPIC_API_KEY environment variable is required for Anthropic provider"
                )
            return AnthropicLLMService(
                api_key=settings.anthropic_api_key,
                model=model,
            )
        elif provider == "openai":
            if not settings.openai_api_key:
                raise ValueError(
                    "OPENAI_API_KEY environment variable is required for OpenAI provider"
                )
            return OpenAILLMService(
                api_key=settings.openai_api_key,
                model=model,
            )
        else:
            raise ValueError(
                f"Unsupported LLM provider: {provider}. Must be one of: gemini, anthropic, openai"
            )

    @staticmethod
    def validate_provider_config(provider: LLMProvider) -> None:
        """
        Validate that the required API key is configured for the provider.

        Args:
            provider: The LLM provider to validate

        Raises:
            ValueError: If the required API key is missing
        """
        if provider == "gemini" and not settings.google_api_key:
            raise ValueError("GOOGLE_API_KEY environment variable is required for Gemini provider")
        elif provider == "anthropic" and not settings.anthropic_api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY environment variable is required for Anthropic provider"
            )
        elif provider == "openai" and not settings.openai_api_key:
            raise ValueError("OPENAI_API_KEY environment variable is required for OpenAI provider")
