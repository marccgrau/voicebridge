"""Contracts for session lifecycle service."""

from dataclasses import dataclass
from typing import Any, Literal

LLMProvider = Literal["gemini", "anthropic", "openai"]


@dataclass(frozen=True)
class SessionStartParams:
    """Input params for agent-initiated session start."""

    session_id: str
    locale: str
    domain: str | None
    queue_tag: str | None
    metadata: dict[str, Any] | None
    enable_process_flow: bool
    enable_suggestion_flow: bool
    process_flow_provider: LLMProvider
    process_flow_model: str
    suggestion_flow_provider: LLMProvider
    suggestion_flow_model: str
    process_content_path: str | None


@dataclass(frozen=True)
class SessionCreateParams:
    """Input params for customer-initiated session create."""

    locale: str
    domain: str | None
    metadata: dict[str, Any] | None
    customer_id: str | None


@dataclass(frozen=True)
class SessionAcceptParams:
    """Input params for agent accept."""

    session_id: str
    enable_process_flow: bool
    enable_suggestion_flow: bool
    process_flow_provider: LLMProvider
    process_flow_model: str
    suggestion_flow_provider: LLMProvider
    suggestion_flow_model: str


@dataclass(frozen=True)
class SessionStartResult:
    """Result payload for session start."""

    session_id: str
    room_url: str
    room_token: str
    created_at: str
    rtvi_url: str
    services: dict[str, Any]


@dataclass(frozen=True)
class SessionCreateResult:
    """Result payload for session create."""

    session_id: str
    room_url: str
    customer_token: str


@dataclass(frozen=True)
class SessionAcceptResult:
    """Result payload for session accept."""

    session_id: str
    room_url: str
    agent_token: str
    rtvi_url: str
    services: dict[str, Any]


@dataclass(frozen=True)
class SessionStopResult:
    """Result payload for session stop."""

    session_id: str
    stopped_at: str
    status: str
