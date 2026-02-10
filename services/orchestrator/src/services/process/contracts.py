"""Contracts for process service module."""

from dataclasses import dataclass

from src.events.contracts import ProcessContextUpdatedEvent, TranscriptSegmentEvent


@dataclass(frozen=True)
class ProcessServiceInput:
    """Input payload for process service decisions."""

    segment: TranscriptSegmentEvent


@dataclass(frozen=True)
class ProcessServiceResult:
    """Output payload from process service."""

    event: ProcessContextUpdatedEvent | None
