"""Adapter exposing existing LLMServiceFactory through port interface."""

from typing import Any

from src.llm import LLMServiceFactory
from src.ports.llm import LLMFactoryPort, LLMProvider


class PipecatLLMFactoryAdapter(LLMFactoryPort):
    """LLMFactoryPort implementation backed by existing LLMServiceFactory."""

    def create(self, provider: LLMProvider, model: str) -> Any:
        """Create provider-specific Pipecat LLM service."""
        return LLMServiceFactory.create_llm_service(provider=provider, model=model)

    def validate_provider_config(self, provider: LLMProvider) -> None:
        """Validate provider credentials are configured."""
        LLMServiceFactory.validate_provider_config(provider)
