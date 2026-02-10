"""Mapping helpers between internal events and Pipecat frames."""

from src.events.contracts import (
    ProcessContextUpdatedEvent,
    ProcessStepState,
    SuggestionGeneratedEvent,
    SuggestionItem,
    TranscriptSegmentEvent,
)
from src.frames import ProcessIllustrationFrame, SuggestionFrame, TranscriptSegmentFrame


def transcript_frame_to_event(frame: TranscriptSegmentFrame) -> TranscriptSegmentEvent:
    """Convert Pipecat transcript frame to internal transcript event."""
    return TranscriptSegmentEvent(
        session_id=frame.session_id,
        speaker=frame.speaker,
        text=frame.text,
        timestamp=frame.timestamp,
        is_final=frame.is_final,
    )


def process_event_to_frame(event: ProcessContextUpdatedEvent) -> ProcessIllustrationFrame:
    """Convert internal process context event to Pipecat frame."""
    return ProcessIllustrationFrame(
        process_key=event.process_key,
        process_name=event.process_name,
        current_step=event.current_step,
        content=event.content,
        steps=[
            {
                "key": step.key,
                "label": step.label,
                "status": step.status,
            }
            for step in event.steps
        ],
    )


def process_frame_to_event(
    frame: ProcessIllustrationFrame, session_id: str
) -> ProcessContextUpdatedEvent:
    """Convert Pipecat process frame to internal process context event."""
    return ProcessContextUpdatedEvent(
        session_id=session_id,
        process_key=frame.process_key,
        process_name=frame.process_name,
        current_step=frame.current_step,
        content=frame.content,
        steps=[
            ProcessStepState(
                key=step["key"],
                label=step["label"],
                status=step["status"],
            )
            for step in frame.steps
        ],
    )


def suggestion_event_to_frame(event: SuggestionGeneratedEvent) -> SuggestionFrame:
    """Convert internal suggestion event to Pipecat frame."""
    return SuggestionFrame(
        suggestions=[{"text": item.text, "type": item.type} for item in event.suggestions],
        service_type=event.service_type,
        latency_ms=event.latency_ms,
        process_key=event.process_key,
        tools_used=event.tools_used,
    )


def suggestion_frame_to_event(frame: SuggestionFrame, session_id: str) -> SuggestionGeneratedEvent:
    """Convert Pipecat suggestion frame to internal suggestion event."""
    return SuggestionGeneratedEvent(
        session_id=session_id,
        suggestions=[
            SuggestionItem(text=item["text"], type=item["type"]) for item in frame.suggestions
        ],
        service_type=frame.service_type,
        latency_ms=frame.latency_ms,
        process_key=frame.process_key,
        tools_used=frame.tools_used,
    )
