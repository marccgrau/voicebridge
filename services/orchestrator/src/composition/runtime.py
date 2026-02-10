"""Runtime registry primitives for orchestrator sessions."""

from dataclasses import dataclass, field

from src.ports.session_runtime import SessionRuntimePort


@dataclass
class SessionRuntimeRegistry:
    """In-memory runtime registry for active session pipelines."""

    _runtimes: dict[str, SessionRuntimePort] = field(default_factory=dict)

    def get(self, session_id: str) -> SessionRuntimePort | None:
        """Return active runtime for session id."""
        return self._runtimes.get(session_id)

    def set(self, session_id: str, runtime: SessionRuntimePort) -> None:
        """Register runtime for session id."""
        self._runtimes[session_id] = runtime

    def remove(self, session_id: str) -> SessionRuntimePort | None:
        """Remove runtime for session id."""
        return self._runtimes.pop(session_id, None)

    def has(self, session_id: str) -> bool:
        """Return true when a runtime exists."""
        return session_id in self._runtimes

    def list_session_ids(self) -> list[str]:
        """Return snapshot of active session ids."""
        return list(self._runtimes.keys())

    def clear(self) -> None:
        """Remove all runtimes."""
        self._runtimes.clear()
