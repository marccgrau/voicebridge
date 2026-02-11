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

    # LLM Providers
    anthropic_api_key: str | None = None
    google_api_key: str | None = None
    openai_api_key: str | None = None

    # Daily
    daily_api_key: str

    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False

    # Pipeline
    stt_language: str = "en"
    stt_include_partials: bool = False
    stt_enable_diarization: bool = True
    stt_max_speakers: int = 2
    stt_prefer_current_speaker: bool = True
    process_lookup_limit: int = 5
    conversation_window_size: int = 8
    process_match_confidence_threshold: float = 0.50
    process_match_margin_threshold: float = 0.15
    process_shortlist_k: int = 3
    process_content_cache_size: int = 32
    suggestion_debounce_ms: int = 250
    default_llm_provider: str = "openai"
    default_llm_model: str = "gpt-4.1"

    # HTTP timeouts (seconds)
    daily_api_timeout: float = 10.0

    # Pipeline timeouts (seconds)
    pipeline_start_timeout: float = 3600.0  # 1 hour max session
    pipeline_stop_timeout: float = 30.0
    process_detection_llm_timeout: float = 8.0
    suggestion_llm_timeout: float = 15.0

    # Retry config
    db_write_max_retries: int = 3
    db_write_retry_delay: float = 0.5
    transcript_write_queue_size: int = 256
    rtvi_max_retries: int = 2

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


settings = Settings()
