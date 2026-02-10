"""Domain errors for summary application service."""


class SummaryServiceError(Exception):
    """Base summary service error."""


class SessionNotFoundError(SummaryServiceError):
    """Raised when target session does not exist."""


class InvalidSessionStateError(SummaryServiceError):
    """Raised when operation requires a terminal session status."""


class EmptySummaryError(SummaryServiceError):
    """Raised when manual summary text is empty."""


class EmptyTranscriptError(SummaryServiceError):
    """Raised when AI summary generation has no transcript segments."""
