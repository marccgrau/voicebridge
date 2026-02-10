"""Internal events and mapping helpers."""

from .contracts import (
    ProcessContextUpdatedEvent,
    ProcessStepState,
    SuggestionGeneratedEvent,
    SuggestionItem,
    TranscriptSegmentEvent,
)
from .frame_mapper import (
    process_event_to_frame,
    process_frame_to_event,
    suggestion_event_to_frame,
    suggestion_frame_to_event,
    transcript_frame_to_event,
)

__all__ = [
    "TranscriptSegmentEvent",
    "ProcessStepState",
    "ProcessContextUpdatedEvent",
    "SuggestionItem",
    "SuggestionGeneratedEvent",
    "transcript_frame_to_event",
    "process_event_to_frame",
    "process_frame_to_event",
    "suggestion_event_to_frame",
    "suggestion_frame_to_event",
]
