"""Session and summary API routes."""

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

import httpx
from fastapi import APIRouter, BackgroundTasks, HTTPException

from src.adapters import SupabaseSessionRepository, SupabaseTranscriptRepository, UtcSystemClock
from src.api.schemas import (
    GenerateSummaryResponse,
    SessionAcceptRequest,
    SessionAcceptResponse,
    SessionCreateRequest,
    SessionCreateResponse,
    SessionStartRequest,
    SessionStartResponse,
    SessionStopRequest,
    SessionStopResponse,
    SessionSummaryRequest,
    SessionSummaryResponse,
)
from src.services.session import (
    SessionAcceptParams,
    SessionAlreadyActiveError,
    SessionConflictError,
    SessionCreateParams,
    SessionLifecycleService,
    SessionNotActiveError,
    SessionStartParams,
)
from src.services.summary import SessionSummaryService
from src.services.summary.errors import (
    EmptySummaryError,
    EmptyTranscriptError,
    InvalidSessionStateError,
    SessionNotFoundError,
)


@dataclass(frozen=True)
class SessionRouterDeps:
    """Dependencies required by session routes."""

    build_session_lifecycle_service: Callable[[], SessionLifecycleService]
    get_supabase_client: Callable[[], Any]
    run_pipeline: Callable[..., Awaitable[None]]
    summary_llm_factory: Callable[[], Any]


def _build_session_summary_service(
    client: Any,
    summary_llm_factory: Callable[[], Any],
) -> SessionSummaryService:
    """Create summary application service with concrete adapters."""
    return SessionSummaryService(
        session_repository=SupabaseSessionRepository(client=client),
        transcript_repository=SupabaseTranscriptRepository(client=client),
        clock=UtcSystemClock(),
        llm_summary_factory=summary_llm_factory,
    )


def build_sessions_router(deps: SessionRouterDeps) -> APIRouter:
    """Build the router for session and summary endpoints."""
    logger = logging.getLogger(__name__)
    router = APIRouter()

    @router.post("/sessions/start", response_model=SessionStartResponse)
    async def start_session(
        request: SessionStartRequest,
        background_tasks: BackgroundTasks,
    ) -> SessionStartResponse:
        """Start a new voice session."""
        try:
            service = deps.build_session_lifecycle_service()
            result = await service.start_session(
                params=SessionStartParams(
                    session_id=request.session_id or str(uuid4()),
                    locale=request.locale,
                    domain=request.domain,
                    queue_tag=request.queue_tag,
                    metadata=request.metadata,
                    enable_process_flow=request.enable_process_flow,
                    enable_suggestion_flow=request.enable_suggestion_flow,
                    process_flow_provider=request.process_flow_provider,
                    process_flow_model=request.process_flow_model,
                    suggestion_flow_provider=request.suggestion_flow_provider,
                    suggestion_flow_model=request.suggestion_flow_model,
                    process_content_path=request.process_content_path,
                ),
                schedule_pipeline=lambda *args: background_tasks.add_task(deps.run_pipeline, *args),
            )

            return SessionStartResponse(
                session_id=result.session_id,
                room_url=result.room_url,
                room_token=result.room_token,
                created_at=result.created_at,
                rtvi_url=result.rtvi_url,
                services=result.services,
            )
        except SessionAlreadyActiveError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        except httpx.TimeoutException as e:
            logger.error("Daily.co API timeout: %s", e)
            raise HTTPException(status_code=504, detail="Voice room creation timed out") from e
        except httpx.HTTPError as e:
            logger.error("Failed to create Daily room: %s", e)
            raise HTTPException(status_code=502, detail="Failed to create voice room") from e
        except Exception as e:
            logger.error("Failed to start session: %s", e)
            raise HTTPException(status_code=500, detail=str(e)) from e

    @router.post("/sessions/create", response_model=SessionCreateResponse)
    async def create_session(
        request: SessionCreateRequest,
        background_tasks: BackgroundTasks,
    ) -> SessionCreateResponse:
        """Create a customer-initiated session."""
        try:
            service = deps.build_session_lifecycle_service()
            result = await service.create_session(
                params=SessionCreateParams(
                    locale=request.locale,
                    domain=request.domain,
                    metadata=request.metadata,
                    customer_id=request.customer_id,
                ),
                schedule_pipeline=lambda *args: background_tasks.add_task(deps.run_pipeline, *args),
            )

            return SessionCreateResponse(
                session_id=result.session_id,
                room_url=result.room_url,
                customer_token=result.customer_token,
            )
        except httpx.TimeoutException as e:
            logger.error("Daily.co API timeout: %s", e)
            raise HTTPException(status_code=504, detail="Voice room creation timed out") from e
        except httpx.HTTPError as e:
            logger.error("Failed to create Daily room: %s", e)
            raise HTTPException(status_code=502, detail="Failed to create voice room") from e
        except Exception as e:
            logger.error("Failed to create session: %s", e)
            raise HTTPException(status_code=500, detail=str(e)) from e

    @router.post("/sessions/accept", response_model=SessionAcceptResponse)
    async def accept_session(request: SessionAcceptRequest) -> SessionAcceptResponse:
        """Agent accepts a pending session."""
        try:
            service = deps.build_session_lifecycle_service()
            result = await service.accept_session(
                SessionAcceptParams(
                    session_id=request.session_id,
                    enable_process_flow=request.enable_process_flow,
                    enable_suggestion_flow=request.enable_suggestion_flow,
                    process_flow_provider=request.process_flow_provider,
                    process_flow_model=request.process_flow_model,
                    suggestion_flow_provider=request.suggestion_flow_provider,
                    suggestion_flow_model=request.suggestion_flow_model,
                )
            )

            return SessionAcceptResponse(
                session_id=result.session_id,
                room_url=result.room_url,
                agent_token=result.agent_token,
                rtvi_url=result.rtvi_url,
                services=result.services,
            )
        except SessionConflictError as e:
            raise HTTPException(status_code=409, detail=str(e)) from e
        except Exception as e:
            logger.error("Failed to accept session %s: %s", request.session_id, e)
            raise HTTPException(status_code=500, detail=str(e)) from e

    @router.post("/sessions/stop", response_model=SessionStopResponse)
    async def stop_session(request: SessionStopRequest) -> SessionStopResponse:
        """Stop an active or pending voice session."""
        try:
            service = deps.build_session_lifecycle_service()
            result = await service.stop_session(request.session_id)
            return SessionStopResponse(
                session_id=result.session_id,
                stopped_at=result.stopped_at,
                status=result.status,
            )
        except SessionNotActiveError as e:
            raise HTTPException(status_code=404, detail=str(e)) from e

    @router.post("/sessions/summary", response_model=SessionSummaryResponse)
    async def save_session_summary(request: SessionSummaryRequest) -> SessionSummaryResponse:
        """Save or update a session summary (postcall notes)."""
        session_id = request.session_id

        try:
            client = deps.get_supabase_client()
            summary_service = _build_session_summary_service(
                client,
                deps.summary_llm_factory,
            )
            result = summary_service.save_manual_summary(
                session_id=session_id,
                summary_text=request.summary_text,
                updated_by=request.updated_by,
            )

            return SessionSummaryResponse(
                session_id=result.session_id,
                summary_text=result.summary_text,
                updated_at=result.updated_at,
                updated_by=result.updated_by,
            )
        except EmptySummaryError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        except SessionNotFoundError as e:
            raise HTTPException(status_code=404, detail=str(e)) from e
        except InvalidSessionStateError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        except Exception as e:
            logger.error("Failed to save summary for session %s: %s", session_id, e)
            raise HTTPException(status_code=500, detail=str(e)) from e

    @router.post("/sessions/{session_id}/generate-summary", response_model=GenerateSummaryResponse)
    async def generate_session_summary(session_id: str) -> GenerateSummaryResponse:
        """Generate a summary from transcript segments using an LLM."""
        try:
            client = deps.get_supabase_client()
            summary_service = _build_session_summary_service(
                client,
                deps.summary_llm_factory,
            )
            result = summary_service.generate_ai_summary(session_id)

            return GenerateSummaryResponse(
                session_id=result.session_id,
                summary_text=result.summary_text,
                updated_at=result.updated_at,
                updated_by=result.updated_by,
            )
        except SessionNotFoundError as e:
            raise HTTPException(status_code=404, detail=str(e)) from e
        except InvalidSessionStateError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        except EmptyTranscriptError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        except Exception as e:
            logger.error("Failed to generate summary for session %s: %s", session_id, e)
            raise HTTPException(status_code=500, detail=str(e)) from e

    @router.get("/sessions/{session_id}/status")
    async def get_session_status(session_id: str) -> dict[str, Any]:
        """Get the status of a session."""
        try:
            service = deps.build_session_lifecycle_service()
            return service.get_session_status(session_id)
        except Exception as e:
            raise HTTPException(status_code=404, detail=f"Session not found: {e}") from e

    return router
