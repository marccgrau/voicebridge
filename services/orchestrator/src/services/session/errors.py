"""Domain errors for session lifecycle operations."""


class SessionLifecycleError(Exception):
    """Base lifecycle error."""


class SessionAlreadyActiveError(SessionLifecycleError):
    """Raised when a start request targets an already active session id."""


class SessionConflictError(SessionLifecycleError):
    """Raised when a pending session cannot be accepted."""


class SessionNotFoundError(SessionLifecycleError):
    """Raised when a session is not found."""


class SessionNotActiveError(SessionLifecycleError):
    """Raised when a stop request targets a non-active/non-pending session."""
