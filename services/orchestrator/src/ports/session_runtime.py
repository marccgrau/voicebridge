"""Session runtime lifecycle abstraction."""

from typing import Protocol


class SessionRuntimePort(Protocol):
    """Runtime interface for active session pipelines."""

    async def stop(self) -> None:
        """Stop the runtime gracefully."""

    @property
    def is_running(self) -> bool:
        """Return true when runtime is active."""


class SessionRuntimeRegistryPort(Protocol):
    """Registry interface for session runtimes."""

    def get(self, session_id: str) -> SessionRuntimePort | None:
        """Return active runtime for a session."""

    def set(self, session_id: str, runtime: SessionRuntimePort) -> None:
        """Register runtime for a session."""

    def remove(self, session_id: str) -> SessionRuntimePort | None:
        """Remove runtime from registry."""

    def has(self, session_id: str) -> bool:
        """Return true if session is active."""

    def clear(self) -> None:
        """Remove all runtimes from registry."""
