"""Custom frames for VoiceBridge suggestion agent."""

from dataclasses import dataclass
from typing import Any

from pipecat.frames.frames import Frame


@dataclass
class TranscriptSegmentFrame(Frame):
    """Frame containing transcript segment (internal use for context building)."""

    session_id: str
    speaker: str  # "agent" | "customer"
    text: str
    timestamp: str
    is_final: bool = True


@dataclass
class SuggestionFrame(Frame):
    """Frame containing generated suggestions."""

    suggestions: list[dict[str, Any]]
    service_type: str  # "suggestion_agent"
    trigger_turn: str | None = None
    latency_ms: float | None = None
    process_key: str | None = None
    tools_used: list[str] | None = None
