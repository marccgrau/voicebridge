"""Typed internal events for orchestrator services."""

from dataclasses import dataclass


@dataclass(frozen=True)
class TranscriptSegmentEvent:
    """Normalized transcript segment consumed by services."""

    session_id: str
    speaker: str
    text: str
    timestamp: str
    is_final: bool = True


@dataclass(frozen=True)
class ProcessStepState:
    """Status snapshot for one process step."""

    key: str
    label: str
    status: str


@dataclass(frozen=True)
class ProcessContextUpdatedEvent:
    """Published when process detection or step tracking changes."""

    session_id: str
    process_key: str
    process_name: str
    current_step: int
    steps: list[ProcessStepState]
    content: str


@dataclass(frozen=True)
class SuggestionItem:
    """One suggestion item for the agent UI."""

    text: str
    type: str


@dataclass(frozen=True)
class SuggestionGeneratedEvent:
    """Published when suggestion service returns a new suggestion set."""

    session_id: str
    suggestions: list[SuggestionItem]
    service_type: str = "direct_call"
    latency_ms: float | None = None
    process_key: str | None = None
    tools_used: list[str] | None = None
