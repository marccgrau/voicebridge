"""FastAPI entrypoint for VoiceBridge Orchestrator."""

import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import httpx
from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from src.config import settings
from src.db import get_supabase_client
from src.pipeline import VoiceBridgePipeline

# Configure logging
logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Suppress noisy warnings from Daily transport when waiting for participants
logging.getLogger("pipecat.transports.base_input").setLevel(logging.ERROR)

# Active pipelines storage
active_pipelines: dict[str, VoiceBridgePipeline] = {}


async def cleanup_all_pipelines() -> None:
    """Stop all active pipelines."""
    logger.info("Shutting down VoiceBridge Orchestrator...")
    for session_id, pipeline in list(active_pipelines.items()):
        try:
            await asyncio.wait_for(pipeline.stop(), timeout=10.0)
        except TimeoutError:
            logger.error("Timeout stopping pipeline %s", session_id)
        except Exception as e:
            logger.error("Error stopping pipeline %s: %s", session_id, e)
    active_pipelines.clear()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Application lifespan handler."""
    logger.info("VoiceBridge Orchestrator starting...")

    yield

    # Normal shutdown
    await cleanup_all_pipelines()


app = FastAPI(
    title="VoiceBridge Orchestrator",
    description="Voice pipeline orchestrator for customer service guidance",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle unexpected exceptions globally.

    Logs full traceback and returns generic 500 response without leaking
    internal details to the client.

    Args:
        request: The request that caused the exception
        exc: The exception that was raised

    Returns:
        Generic 500 JSON response
    """
    logger.error(
        "Unhandled exception in %s %s: %s",
        request.method,
        request.url.path,
        exc,
        exc_info=True,
    )

    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error",
            "type": type(exc).__name__,
        },
    )


# Request/Response models
class SessionStartRequest(BaseModel):
    """Request to start a new session."""

    session_id: str | None = Field(default=None, description="Optional session ID")
    locale: str = Field(default="en", description="Session locale")
    domain: str | None = Field(default=None, description="Optional domain filter")
    queue_tag: str | None = Field(default=None, description="Optional queue tag filter")
    metadata: dict[str, Any] | None = Field(default=None, description="Optional metadata")
    enable_process_flow: bool = Field(
        default=True,
        description="Enable process detection and step tracking",
    )
    enable_suggestion_flow: bool = Field(
        default=True,
        description="Enable agent suggestion generation",
    )
    process_flow_model: str = Field(
        default="claude-haiku-4-5-20251001",
        description="Model for process flow (fast/cheap for infrequent calls)",
    )
    suggestion_flow_model: str = Field(
        default="claude-sonnet-4-5-20250929",
        description="Model for suggestion flow (quality for frequent calls)",
    )
    process_content_path: str | None = Field(
        default=None,
        description="Path to process markdown files",
    )


class SessionStartResponse(BaseModel):
    """Response after starting a session."""

    session_id: str
    room_url: str
    room_token: str
    created_at: str
    rtvi_url: str
    services: dict[str, Any]


class SessionStopRequest(BaseModel):
    """Request to stop a session."""

    session_id: str


class SessionStopResponse(BaseModel):
    """Response after stopping a session."""

    session_id: str
    stopped_at: str
    status: str


class SessionCreateRequest(BaseModel):
    """Customer-initiated session creation request."""

    locale: str = Field(default="en", description="Session locale")
    domain: str | None = Field(default=None, description="Optional domain filter")
    metadata: dict[str, Any] | None = Field(default=None, description="Optional metadata")
    customer_id: str | None = Field(default=None, description="Optional customer UUID")


class SessionCreateResponse(BaseModel):
    """Customer-initiated session creation response."""

    session_id: str
    room_url: str
    customer_token: str


class SessionAcceptRequest(BaseModel):
    """Agent accepts a pending session."""

    session_id: str
    enable_process_flow: bool = Field(default=True)
    enable_suggestion_flow: bool = Field(default=True)
    process_flow_model: str = Field(default="claude-haiku-4-5-20251001")
    suggestion_flow_model: str = Field(default="claude-sonnet-4-5-20250929")
    process_content_path: str | None = Field(default=None)


class SessionAcceptResponse(BaseModel):
    """Agent accept session response."""

    session_id: str
    room_url: str
    agent_token: str
    rtvi_url: str
    services: dict[str, Any]


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    version: str
    services: dict[str, str]


# Daily.co helpers


async def create_meeting_token(
    room_name: str,
    is_owner: bool = False,
    user_name: str | None = None,
) -> str:
    """Create a Daily.co meeting token for a room.

    Args:
        room_name: The Daily room name.
        is_owner: Whether the token grants owner privileges.
        user_name: Optional display name for the participant.

    Returns:
        The meeting token string.
    """
    properties: dict[str, Any] = {
        "room_name": room_name,
        "is_owner": is_owner,
    }
    if user_name:
        properties["user_name"] = user_name

    async with httpx.AsyncClient(timeout=httpx.Timeout(settings.daily_api_timeout)) as client:
        token_response = await client.post(
            "https://api.daily.co/v1/meeting-tokens",
            headers={"Authorization": f"Bearer {settings.daily_api_key}"},
            json={"properties": properties},
        )
        token_response.raise_for_status()
        return token_response.json()["token"]


async def create_daily_room() -> dict[str, str]:
    """Create a Daily.co room and an owner token.

    Returns:
        Dict with room_url, room_name, and room_token (owner).
    """
    async with httpx.AsyncClient(timeout=httpx.Timeout(settings.daily_api_timeout)) as client:
        room_response = await client.post(
            "https://api.daily.co/v1/rooms",
            headers={"Authorization": f"Bearer {settings.daily_api_key}"},
            json={
                "properties": {
                    "exp": int((datetime.now(UTC).timestamp()) + 3600),  # 1 hour
                    "enable_chat": False,
                    "enable_screenshare": False,
                    "start_audio_off": False,
                    "start_video_off": True,
                }
            },
        )
        room_response.raise_for_status()
        room_data = room_response.json()

    token = await create_meeting_token(room_data["name"], is_owner=True)

    return {
        "room_url": room_data["url"],
        "room_name": room_data["name"],
        "room_token": token,
    }


async def _update_session_error(session_id: str, error_message: str) -> None:
    """Update session to error state.

    Best-effort operation - logs if DB write fails.

    Args:
        session_id: Session identifier
        error_message: Error message to store
    """
    try:
        client = get_supabase_client()
        client.table("sessions").update(
            {
                "status": "error",
                "error_message": error_message,
                "error_occurred_at": datetime.now(UTC).isoformat(),
                "updated_at": datetime.now(UTC).isoformat(),
            }
        ).eq("id", session_id).execute()
        logger.info("Updated session %s to error status", session_id)
    except Exception as e:
        logger.error("Failed to update session %s to error status: %s", session_id, e)


async def run_pipeline(
    session_id: str,
    room_url: str,
    room_token: str,
    enable_process_flow: bool,
    enable_suggestion_flow: bool,
    process_flow_model: str,
    suggestion_flow_model: str,
    process_content_path: str | None,
) -> None:
    """Run the pipeline in the background.

    Args:
        session_id: Session identifier
        room_url: Daily room URL
        room_token: Daily room token
        enable_process_flow: Enable process flow
        enable_suggestion_flow: Enable suggestion flow
        process_flow_model: Model for process flow
        suggestion_flow_model: Model for suggestion flow
        process_content_path: Path to process markdown files
    """
    pipeline = VoiceBridgePipeline(
        session_id=session_id,
        room_url=room_url,
        room_token=room_token,
        enable_process_flow=enable_process_flow,
        enable_suggestion_flow=enable_suggestion_flow,
        process_flow_model=process_flow_model,
        suggestion_flow_model=suggestion_flow_model,
        process_content_path=process_content_path or "process_content/",
    )

    active_pipelines[session_id] = pipeline

    try:
        # Wrap pipeline.start() with timeout
        await asyncio.wait_for(
            pipeline.start(),
            timeout=settings.pipeline_start_timeout,
        )
    except TimeoutError:
        error_msg = f"Pipeline timed out after {settings.pipeline_start_timeout}s"
        logger.error("Pipeline timeout for session %s: %s", session_id, error_msg)
        await _update_session_error(session_id, error_msg)
    except Exception as e:
        error_msg = f"Pipeline error: {type(e).__name__}: {e}"
        logger.error("Pipeline error for session %s: %s", session_id, error_msg, exc_info=True)
        await _update_session_error(session_id, error_msg)
    finally:
        active_pipelines.pop(session_id, None)


@app.post("/sessions/start", response_model=SessionStartResponse)
async def start_session(
    request: SessionStartRequest,
    background_tasks: BackgroundTasks,
) -> SessionStartResponse:
    """Start a new voice session.

    Creates a Daily.co room, initializes the session in the database,
    and starts the voice pipeline.
    """
    session_id = request.session_id or str(uuid4())

    if session_id in active_pipelines:
        raise HTTPException(
            status_code=400,
            detail=f"Session {session_id} is already active",
        )

    try:
        # Create Daily room
        room = await create_daily_room()

        # Create session in database
        client = get_supabase_client()
        client.table("sessions").insert(
            {
                "id": session_id,
                "state": {
                    "locale": request.locale,
                    "domain": request.domain,
                    "queueTag": request.queue_tag,
                    "metadata": request.metadata,
                    "slots": {},
                    "steps": [],
                },
                "status": "active",
                "suggestion_service": "split_flows",  # New architecture
                "process_illustration_enabled": request.enable_process_flow,
            }
        ).execute()

        # Start pipeline in background
        background_tasks.add_task(
            run_pipeline,
            session_id,
            room["room_url"],
            room["room_token"],
            request.enable_process_flow,
            request.enable_suggestion_flow,
            request.process_flow_model,
            request.suggestion_flow_model,
            request.process_content_path,
        )

        # RTVI URL (WebSocket connection)
        # For now, use the Daily room URL as RTVI endpoint
        # In production, this could be a separate WebSocket server
        rtvi_url = f"wss://api.daily.co/v1/rooms/{room['room_url'].split('/')[-1]}/rtvi"

        return SessionStartResponse(
            session_id=session_id,
            room_url=room["room_url"],
            room_token=room["room_token"],
            created_at=datetime.now(UTC).isoformat(),
            rtvi_url=rtvi_url,
            services={
                "processFlowEnabled": request.enable_process_flow,
                "suggestionFlowEnabled": request.enable_suggestion_flow,
                "processFlowModel": request.process_flow_model,
                "suggestionFlowModel": request.suggestion_flow_model,
            },
        )

    except httpx.TimeoutException as e:
        logger.error("Daily.co API timeout: %s", e)
        raise HTTPException(status_code=504, detail="Voice room creation timed out") from e
    except httpx.HTTPError as e:
        logger.error("Failed to create Daily room: %s", e)
        raise HTTPException(status_code=502, detail="Failed to create voice room") from e
    except Exception as e:
        logger.error("Failed to start session: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/sessions/create", response_model=SessionCreateResponse)
async def create_session(
    request: SessionCreateRequest,
    background_tasks: BackgroundTasks,
) -> SessionCreateResponse:
    """Create a customer-initiated session.

    Creates a Daily.co room, generates tokens for customer and bot,
    inserts the session as 'pending', and starts the pipeline bot immediately
    so transcription begins when the customer speaks.
    """
    session_id = str(uuid4())

    try:
        # Create Daily room
        room = await create_daily_room()

        # Generate customer token (non-owner)
        customer_token = await create_meeting_token(
            room["room_name"], is_owner=False, user_name="customer"
        )

        # Create session in database with pending status
        client = get_supabase_client()
        client.table("sessions").insert(
            {
                "id": session_id,
                "state": {
                    "locale": request.locale,
                    "domain": request.domain,
                    "metadata": request.metadata,
                    "slots": {},
                    "steps": [],
                },
                "status": "pending",
                "room_url": room["room_url"],
                "room_name": room["room_name"],
                "customer_id": request.customer_id,
                "customer_joined_at": datetime.now(UTC).isoformat(),
                "suggestion_service": "split_flows",
                "process_illustration_enabled": True,
            }
        ).execute()

        # Start pipeline bot immediately (uses the owner token from create_daily_room)
        background_tasks.add_task(
            run_pipeline,
            session_id,
            room["room_url"],
            room["room_token"],  # bot gets the owner token
            True,  # enable_process_flow
            True,  # enable_suggestion_flow
            "claude-haiku-4-5-20251001",
            "claude-sonnet-4-5-20250929",
            None,
        )

        return SessionCreateResponse(
            session_id=session_id,
            room_url=room["room_url"],
            customer_token=customer_token,
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


@app.post("/sessions/accept", response_model=SessionAcceptResponse)
async def accept_session(request: SessionAcceptRequest) -> SessionAcceptResponse:
    """Agent accepts a pending session.

    Uses atomic UPDATE ... WHERE status='pending' to prevent race conditions.
    Generates an agent token, updates session to active, and returns connection info.
    """
    session_id = request.session_id

    try:
        client = get_supabase_client()

        # Atomic update: only succeed if session is still pending
        result = (
            client.table("sessions")
            .update(
                {
                    "status": "active",
                    "agent_joined_at": datetime.now(UTC).isoformat(),
                    "updated_at": datetime.now(UTC).isoformat(),
                }
            )
            .eq("id", session_id)
            .eq("status", "pending")
            .execute()
        )

        if not result.data:
            raise HTTPException(
                status_code=409,
                detail=f"Session {session_id} is not pending or does not exist",
            )

        session_data = result.data[0]
        room_url = session_data["room_url"]
        room_name = session_data["room_name"]

        # Generate agent token (non-owner, with audio)
        agent_token = await create_meeting_token(room_name, is_owner=False, user_name="agent")

        rtvi_url = f"wss://api.daily.co/v1/rooms/{room_name}/rtvi"

        return SessionAcceptResponse(
            session_id=session_id,
            room_url=room_url,
            agent_token=agent_token,
            rtvi_url=rtvi_url,
            services={
                "processFlowEnabled": request.enable_process_flow,
                "suggestionFlowEnabled": request.enable_suggestion_flow,
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to accept session %s: %s", session_id, e)
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/sessions/stop", response_model=SessionStopResponse)
async def stop_session(request: SessionStopRequest) -> SessionStopResponse:
    """Stop an active or pending voice session.

    Stops the pipeline and updates the session status.
    """
    session_id = request.session_id

    pipeline = active_pipelines.get(session_id)
    if not pipeline:
        # Check if session exists in database (could be pending with no local pipeline ref yet)
        try:
            client = get_supabase_client()
            resp = client.table("sessions").select("status").eq("id", session_id).single().execute()
            if resp.data and resp.data["status"] in ("pending", "active"):
                # Session exists but pipeline not tracked locally — update DB only
                client.table("sessions").update(
                    {
                        "status": "abandoned",
                        "updated_at": datetime.now(UTC).isoformat(),
                    }
                ).eq("id", session_id).execute()
                return SessionStopResponse(
                    session_id=session_id,
                    stopped_at=datetime.now(UTC).isoformat(),
                    status="abandoned",
                )
        except Exception as e:
            logger.error("Failed to check session %s in database: %s", session_id, e)

        raise HTTPException(
            status_code=404,
            detail=f"Session {session_id} not found or not active",
        )

    stop_error = None
    try:
        # Stop pipeline with timeout
        await asyncio.wait_for(
            pipeline.stop(),
            timeout=settings.pipeline_stop_timeout,
        )
        logger.info("Pipeline stopped successfully for session %s", session_id)
    except TimeoutError:
        error_msg = f"Pipeline stop timed out after {settings.pipeline_stop_timeout}s"
        logger.error("Stop timeout for session %s: %s", session_id, error_msg)
        stop_error = error_msg
    except Exception as e:
        error_msg = f"Pipeline stop failed: {e}"
        logger.error("Stop error for session %s: %s", session_id, error_msg, exc_info=True)
        stop_error = error_msg
    finally:
        # Always remove from active pipelines
        active_pipelines.pop(session_id, None)

        # Always update DB to completed (even if stop had errors)
        try:
            client = get_supabase_client()
            client.table("sessions").update(
                {
                    "status": "completed",
                    "updated_at": datetime.now(UTC).isoformat(),
                }
            ).eq("id", session_id).execute()
        except Exception as e:
            logger.error("Failed to update session %s status: %s", session_id, e)

    if stop_error:
        # Pipeline stop had issues, but we still updated DB
        logger.warning("Session %s stopped with errors: %s", session_id, stop_error)

    return SessionStopResponse(
        session_id=session_id,
        stopped_at=datetime.now(UTC).isoformat(),
        status="completed",
    )


@app.get("/healthz", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Health check endpoint with actual service checks."""
    services = {
        "database": "down",
        "stt": "down",
        "llm": "down",
        "daily": "down",
    }

    # Check database with actual query + timeout
    try:

        async def check_db():
            client = get_supabase_client()
            client.table("sessions").select("id").limit(1).execute()

        await asyncio.wait_for(check_db(), timeout=2.0)
        services["database"] = "up"
    except TimeoutError:
        logger.warning("Database health check timed out")
    except Exception as e:
        logger.warning("Database health check failed: %s", e)

    # Check Daily.co with lightweight API call + timeout
    try:

        async def check_daily():
            # Use a lightweight endpoint to verify connectivity
            async with httpx.AsyncClient(timeout=httpx.Timeout(2.0)) as client:
                response = await client.get(
                    "https://api.daily.co/v1",
                    headers={"Authorization": f"Bearer {settings.daily_api_key}"},
                )
                response.raise_for_status()

        await asyncio.wait_for(check_daily(), timeout=2.5)
        services["daily"] = "up"
    except TimeoutError:
        logger.warning("Daily.co health check timed out")
    except Exception as e:
        logger.warning("Daily.co health check failed: %s", e)

    # Check Speechmatics (simple key validation - no cheap API to test)
    if settings.speechmatics_api_key:
        services["stt"] = "up"

    # Check Anthropic (simple key validation - no cheap API to test)
    if settings.anthropic_api_key:
        services["llm"] = "up"

    # Overall status
    all_up = all(s == "up" for s in services.values())
    some_up = any(s == "up" for s in services.values())

    if all_up:
        status = "healthy"
    elif some_up:
        status = "degraded"
    else:
        status = "unhealthy"

    return HealthResponse(
        status=status,
        version="0.1.0",
        services=services,
    )


@app.get("/sessions/{session_id}/status")
async def get_session_status(session_id: str) -> dict[str, Any]:
    """Get the status of a session."""
    try:
        client = get_supabase_client()
        response = client.table("sessions").select("*").eq("id", session_id).single().execute()

        is_active = session_id in active_pipelines

        return {
            "session_id": session_id,
            "is_active": is_active,
            "status": response.data["status"],
            "process_key": response.data.get("process_key"),
            "created_at": response.data["created_at"],
            "updated_at": response.data["updated_at"],
        }

    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Session not found: {e}") from e


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "src.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )
