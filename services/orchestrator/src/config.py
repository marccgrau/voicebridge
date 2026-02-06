"""Configuration settings for the orchestrator."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Supabase
    supabase_url: str
    supabase_service_role_key: str

    # Speechmatics
    speechmatics_api_key: str
    speechmatics_url: str = "wss://eu2.rt.speechmatics.com/v2"
    first_speaker_role: str = "customer"

    # Anthropic
    anthropic_api_key: str

    # Daily
    daily_api_key: str

    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False

    # Pipeline
    stt_language: str = "en"
    llm_model: str = "claude-sonnet-4-20250514"
    process_lookup_limit: int = 5

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


settings = Settings()
