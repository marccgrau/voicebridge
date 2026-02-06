"""Configuration settings for the orchestrator."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Supabase
    supabase_url: str
    supabase_service_role_key: str

    # Speechmatics
    speechmatics_api_key: str
    speechmatics_url: str = "wss://neu.rt.speechmatics.com/v2"
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
    llm_model: str = "claude-sonnet-4-5-20250929"
    process_lookup_limit: int = 5

    # HTTP timeouts (seconds)
    daily_api_timeout: float = 10.0

    # Pipeline timeouts (seconds)
    pipeline_start_timeout: float = 3600.0  # 1 hour max session
    pipeline_stop_timeout: float = 30.0
    llm_timeout: float = 45.0

    # Retry config
    db_write_max_retries: int = 3
    db_write_retry_delay: float = 0.5
    rtvi_max_retries: int = 2

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


settings = Settings()
