"""FastAPI request/response schemas for orchestrator endpoints."""

from typing import Any, Literal

from pydantic import BaseModel, Field

LLMProvider = Literal["gemini", "anthropic", "openai"]


class SessionStartRequest(BaseModel):
    """Request to start a new session."""

    session_id: str | None = Field(default=None, description="Optional session ID")
    locale: str = Field(default="en", description="Session locale")
    domain: str | None = Field(default=None, description="Optional domain filter")
    queue_tag: str | None = Field(default=None, description="Optional queue tag filter")
    metadata: dict[str, Any] | None = Field(default=None, description="Optional metadata")
    enable_process_flow: bool = Field(
        default=True,
        description="Enable process detection and step tracking",
    )
    enable_suggestion_flow: bool = Field(
        default=True,
        description="Enable agent suggestion generation",
    )
    process_flow_provider: LLMProvider = Field(
        default="openai",
        description="LLM provider for process flow",
    )
    process_flow_model: str = Field(
        default="gpt-5-nano",
        description="Model for process flow (fast/cheap for infrequent calls)",
    )
    suggestion_flow_provider: LLMProvider = Field(
        default="openai",
        description="LLM provider for suggestion flow",
    )
    suggestion_flow_model: str = Field(
        default="gpt-5-nano",
        description="Model for suggestion flow (quality for frequent calls)",
    )
    process_content_path: str | None = Field(
        default=None,
        description="Path to process markdown files",
    )


class SessionStartResponse(BaseModel):
    """Response after starting a session."""

    session_id: str
    room_url: str
    room_token: str
    created_at: str
    rtvi_url: str
    services: dict[str, Any]


class SessionStopRequest(BaseModel):
    """Request to stop a session."""

    session_id: str


class SessionStopResponse(BaseModel):
    """Response after stopping a session."""

    session_id: str
    stopped_at: str
    status: str


class SessionCreateRequest(BaseModel):
    """Customer-initiated session creation request."""

    locale: str = Field(default="en", description="Session locale")
    domain: str | None = Field(default=None, description="Optional domain filter")
    metadata: dict[str, Any] | None = Field(default=None, description="Optional metadata")
    customer_id: str | None = Field(default=None, description="Optional customer UUID")


class SessionCreateResponse(BaseModel):
    """Customer-initiated session creation response."""

    session_id: str
    room_url: str
    customer_token: str


class SessionAcceptRequest(BaseModel):
    """Agent accepts a pending session."""

    session_id: str
    enable_process_flow: bool = Field(default=True)
    enable_suggestion_flow: bool = Field(default=True)
    process_flow_provider: LLMProvider = Field(default="openai")
    process_flow_model: str = Field(default="gpt-5-nano")
    suggestion_flow_provider: LLMProvider = Field(default="openai")
    suggestion_flow_model: str = Field(default="gpt-5-nano")
    process_content_path: str | None = Field(default=None)


class SessionAcceptResponse(BaseModel):
    """Agent accept session response."""

    session_id: str
    room_url: str
    agent_token: str
    rtvi_url: str
    services: dict[str, Any]


class SessionSummaryRequest(BaseModel):
    """Request to save a session summary."""

    session_id: str
    summary_text: str
    updated_by: str = Field(default="agent")


class SessionSummaryResponse(BaseModel):
    """Response after saving a session summary."""

    session_id: str
    summary_text: str
    updated_at: str
    updated_by: str


class GenerateSummaryResponse(BaseModel):
    """Response after generating a session summary."""

    session_id: str
    summary_text: str
    updated_at: str
    updated_by: str


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    version: str
    services: dict[str, str]
