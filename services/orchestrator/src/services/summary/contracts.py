"""Contracts for summary service module."""

from dataclasses import dataclass


@dataclass(frozen=True)
class SummaryResult:
    """Summary operation result."""

    session_id: str
    summary_text: str
    updated_at: str
    updated_by: str
