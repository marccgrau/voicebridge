"""Custom frames for VoiceBridge process agent."""

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
class ProcessIllustrationFrame(Frame):
    """Frame containing process illustration data."""

    process_key: str
    process_name: str
    steps: list[dict[str, Any]]
    current_step: int
    content: str
