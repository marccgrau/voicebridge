"""Factory for creating STT service instances based on provider."""

import logging
from typing import Literal

from pipecat.services.deepgram.stt import DeepgramSTTService, LiveOptions
from pipecat.services.speechmatics.stt import Language, SpeechmaticsSTTService, TurnDetectionMode

from src.config import settings

logger = logging.getLogger(__name__)

STTProvider = Literal["speechmatics", "deepgram"]


class STTServiceFactory:
    """Factory for creating STT service instances."""

    @staticmethod
    def create_stt_service(
        provider: STTProvider,
        language: str = "en",
    ) -> SpeechmaticsSTTService | DeepgramSTTService:
        """Create an STT service instance for the specified provider."""
        logger.info("Creating STT service: provider=%s, language=%s", provider, language)
        STTServiceFactory.validate_provider_config(provider)

        if provider == "speechmatics":
            speechmatics_api_key = settings.speechmatics_api_key
            assert speechmatics_api_key is not None
            params = SpeechmaticsSTTService.InputParams(
                language=STTServiceFactory._resolve_stt_language(language),
                turn_detection_mode=TurnDetectionMode.SMART_TURN,
                include_partials=settings.stt_include_partials,
                enable_diarization=settings.stt_enable_diarization,
                max_speakers=settings.stt_max_speakers,
                prefer_current_speaker=settings.stt_prefer_current_speaker,
            )
            return SpeechmaticsSTTService(
                api_key=speechmatics_api_key,
                base_url=settings.speechmatics_url,
                params=params,
                should_interrupt=False,
            )

        if provider == "deepgram":
            deepgram_api_key = settings.deepgram_api_key
            assert deepgram_api_key is not None
            live_options = LiveOptions(
                language="en-US",
                model=settings.deepgram_model,
                smart_format=True,
                endpointing=True,
                profanity_filter=False,
                interim_results=True,
            )
            return DeepgramSTTService(
                api_key=deepgram_api_key,
                live_options=live_options,
                should_interrupt=False,
            )

        raise ValueError(
            f"Unsupported STT provider: {provider}. Must be one of: speechmatics, deepgram"
        )

    @staticmethod
    def validate_provider_config(provider: STTProvider) -> None:
        """Validate that the required API key is configured for the provider."""
        if provider == "speechmatics" and not settings.speechmatics_api_key:
            raise ValueError(
                "SPEECHMATICS_API_KEY environment variable is required for Speechmatics provider"
            )
        if provider == "deepgram" and not settings.deepgram_api_key:
            raise ValueError(
                "DEEPGRAM_API_KEY environment variable is required for Deepgram provider"
            )
        if provider not in ("speechmatics", "deepgram"):
            raise ValueError(
                f"Unsupported STT provider: {provider}. Must be one of: speechmatics, deepgram"
            )

    @staticmethod
    def _resolve_stt_language(language: str) -> Language:
        """Resolve configured language string to Pipecat Language enum."""
        normalized = language.strip()
        candidates = [normalized]
        if normalized.lower() != normalized:
            candidates.append(normalized.lower())

        for candidate in candidates:
            try:
                return Language(candidate)
            except ValueError:
                continue

        raise ValueError(
            f"Unsupported STT_LANGUAGE '{language}'. "
            "Provide a valid Pipecat Language value (for example: en, en-US, es)."
        )
