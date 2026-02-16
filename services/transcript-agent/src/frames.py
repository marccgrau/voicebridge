"""Custom frames for VoiceBridge transcript agent."""

from dataclasses import dataclass

from pipecat.frames.frames import Frame


@dataclass
class TranscriptSegmentFrame(Frame):
    """Frame containing transcript segment for RTVI delivery."""

    session_id: str
    speaker: str  # "agent" | "customer"
    text: str
    timestamp: str
    is_final: bool = True
