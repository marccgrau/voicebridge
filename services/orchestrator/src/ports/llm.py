"""LLM provider abstraction ports."""

from typing import Any, Literal, Protocol

LLMProvider = Literal["gemini", "anthropic", "openai"]


class LLMFactoryPort(Protocol):
    """Factory abstraction for creating Pipecat LLM services."""

    def create(self, provider: LLMProvider, model: str) -> Any:
        """Create provider-specific Pipecat LLM service instance."""

    def validate_provider_config(self, provider: LLMProvider) -> None:
        """Validate required credentials for a provider."""
