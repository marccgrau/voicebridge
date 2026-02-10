"""Composition root components."""

from typing import TYPE_CHECKING, Any

from .runtime import SessionRuntimeRegistry

if TYPE_CHECKING:
    from .container import OrchestratorContainer


def build_container(*args: Any, **kwargs: Any):
    """Lazy import to avoid circular imports during service module loading."""
    from .container import build_container as _build_container

    return _build_container(*args, **kwargs)


__all__ = ["OrchestratorContainer", "SessionRuntimeRegistry", "build_container"]
