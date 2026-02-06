"""Suggestion and process illustration frames."""

from dataclasses import dataclass
from typing import Any

from pipecat.frames.frames import Frame


@dataclass
class SuggestionFrame(Frame):
    """Frame containing generated suggestions."""

    suggestions: list[dict[str, Any]]
    service_type: str  # "simple_turn" | "tool_agent"
    trigger_turn: str | None = None
    latency_ms: float | None = None
    process_key: str | None = None
    tools_used: list[str] | None = None


@dataclass
class ProcessIllustrationFrame(Frame):
    """Frame containing process illustration data."""

    process_key: str
    process_name: str
    steps: list[dict[str, Any]]
    current_step: int
    content: str
