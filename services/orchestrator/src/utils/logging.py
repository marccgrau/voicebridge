"""Session-aware logging utilities."""

import logging


class SessionLogger(logging.LoggerAdapter):
    """Logger adapter that prefixes session ID to all messages.

    Example:
        logger = get_session_logger(__name__, "session-123")
        logger.info("Processing frame")
        # Output: INFO - [session=session-123] Processing frame
    """

    def process(self, msg: str, kwargs: dict) -> tuple[str, dict]:
        """Add session prefix to log message.

        Args:
            msg: Original log message
            kwargs: Logging kwargs

        Returns:
            Tuple of (modified message, kwargs)
        """
        session_id = self.extra.get("session_id", "unknown")
        return f"[session={session_id}] {msg}", kwargs


def get_session_logger(name: str, session_id: str) -> SessionLogger:
    """Create a session-scoped logger.

    Args:
        name: Logger name (typically __name__)
        session_id: Session identifier to include in all log messages

    Returns:
        SessionLogger that prefixes session ID to all messages
    """
    base_logger = logging.getLogger(name)
    return SessionLogger(base_logger, {"session_id": session_id})
