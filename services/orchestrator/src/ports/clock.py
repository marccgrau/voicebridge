"""Time source abstraction for deterministic services."""

from datetime import datetime
from typing import Protocol


class ClockPort(Protocol):
    """Clock abstraction."""

    def now_utc(self) -> datetime:
        """Return current UTC time."""
