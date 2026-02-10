"""Clock adapter implementations."""

from datetime import UTC, datetime

from src.ports.clock import ClockPort


class UtcSystemClock(ClockPort):
    """ClockPort implementation using system UTC time."""

    def now_utc(self) -> datetime:
        """Return current UTC time."""
        return datetime.now(UTC)
