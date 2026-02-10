"""Dependency container for orchestrator composition."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from src.composition.runtime import SessionRuntimeRegistry
from src.services.session import SessionLifecycleService


def _missing(name: str):
    """Return a callable that raises for missing container dependency."""

    def _raise(*_args, **_kwargs):
        raise RuntimeError(f"Missing required container dependency: {name}")

    return _raise


@dataclass(frozen=True)
class OrchestratorContainer:
    """Container holding application dependency callables."""

    runtime_registry: SessionRuntimeRegistry
    get_supabase_client: Callable[[], Any]
    get_settings: Callable[[], Any]
    create_daily_room: Callable[[], Awaitable[dict[str, str]]]
    create_meeting_token: Callable[[str, bool, str | None], Awaitable[str]]
    run_pipeline: Callable[..., Awaitable[None]]
    summary_llm_factory: Callable[[], Any]

    def build_session_lifecycle_service(self) -> SessionLifecycleService:
        """Create session lifecycle service from container dependencies."""
        return SessionLifecycleService(
            runtime_registry=self.runtime_registry,
            get_supabase_client=self.get_supabase_client,
            create_daily_room=self.create_daily_room,
            create_meeting_token=self.create_meeting_token,
        )


def build_container(
    *,
    runtime_registry: SessionRuntimeRegistry | None = None,
    get_supabase_client: Callable[[], Any] | None = None,
    get_settings: Callable[[], Any] | None = None,
    create_daily_room: Callable[[], Awaitable[dict[str, str]]] | None = None,
    create_meeting_token: Callable[[str, bool, str | None], Awaitable[str]] | None = None,
    run_pipeline: Callable[..., Awaitable[None]] | None = None,
    summary_llm_factory: Callable[[], Any] | None = None,
) -> OrchestratorContainer:
    """Create dependency container for app wiring."""
    return OrchestratorContainer(
        runtime_registry=runtime_registry or SessionRuntimeRegistry(),
        get_supabase_client=get_supabase_client or _missing("get_supabase_client"),
        get_settings=get_settings or _missing("get_settings"),
        create_daily_room=create_daily_room or _missing("create_daily_room"),
        create_meeting_token=create_meeting_token or _missing("create_meeting_token"),
        run_pipeline=run_pipeline or _missing("run_pipeline"),
        summary_llm_factory=summary_llm_factory or _missing("summary_llm_factory"),
    )
