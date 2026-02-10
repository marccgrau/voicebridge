"""Contracts for suggestion service module."""

from dataclasses import dataclass

from src.events.contracts import (
    ProcessContextUpdatedEvent,
    SuggestionGeneratedEvent,
    TranscriptSegmentEvent,
)


@dataclass(frozen=True)
class SuggestionServiceInput:
    """Input payload for suggestion generation."""

    segment: TranscriptSegmentEvent
    process_context: ProcessContextUpdatedEvent | None = None


@dataclass(frozen=True)
class SuggestionServiceResult:
    """Output payload from suggestion service."""

    event: SuggestionGeneratedEvent | None
