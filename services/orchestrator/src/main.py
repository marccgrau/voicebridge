"""FastAPI entrypoint for VoiceBridge Orchestrator."""

import logging
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import anthropic
import httpx
from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
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

# Active pipelines storage
active_pipelines: dict[str, VoiceBridgePipeline] = {}


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Application lifespan handler."""
    logger.info("VoiceBridge Orchestrator starting...")
    yield
    # Cleanup on shutdown
    logger.info("Shutting down VoiceBridge Orchestrator...")
    for session_id, pipeline in list(active_pipelines.items()):
        try:
            await pipeline.stop()
        except Exception as e:
            logger.error("Error stopping pipeline %s: %s", session_id, e)
    active_pipelines.clear()


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


# Request/Response models
class SessionStartRequest(BaseModel):
    """Request to start a new session."""

    session_id: str | None = Field(default=None, description="Optional session ID")
    locale: str = Field(default="en", description="Session locale")
    domain: str | None = Field(default=None, description="Optional domain filter")
    queue_tag: str | None = Field(default=None, description="Optional queue tag filter")
    metadata: dict[str, Any] | None = Field(default=None, description="Optional metadata")


class SessionStartResponse(BaseModel):
    """Response after starting a session."""

    session_id: str
    room_url: str
    room_token: str
    created_at: str


class SessionStopRequest(BaseModel):
    """Request to stop a session."""

    session_id: str


class SessionStopResponse(BaseModel):
    """Response after stopping a session."""

    session_id: str
    stopped_at: str
    status: str


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    version: str
    services: dict[str, str]


# Daily.co room creation
async def create_daily_room() -> dict[str, str]:
    """Create a Daily.co room for the session.

    Returns:
        Dict with room_url and room_token
    """
    async with httpx.AsyncClient() as client:
        # Create room
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

        # Create meeting token
        token_response = await client.post(
            "https://api.daily.co/v1/meeting-tokens",
            headers={"Authorization": f"Bearer {settings.daily_api_key}"},
            json={
                "properties": {
                    "room_name": room_data["name"],
                    "is_owner": True,
                }
            },
        )
        token_response.raise_for_status()
        token_data = token_response.json()

        return {
            "room_url": room_data["url"],
            "room_token": token_data["token"],
        }


async def run_pipeline(session_id: str, room_url: str, room_token: str) -> None:
    """Run the pipeline in the background.

    Args:
        session_id: Session identifier
        room_url: Daily room URL
        room_token: Daily room token
    """
    anthropic_client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    pipeline = VoiceBridgePipeline(
        session_id=session_id,
        room_url=room_url,
        room_token=room_token,
        anthropic_client=anthropic_client,
    )

    active_pipelines[session_id] = pipeline

    try:
        await pipeline.start()
    except Exception as e:
        logger.error("Pipeline error for session %s: %s", session_id, e)
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
            }
        ).execute()

        # Start pipeline in background
        background_tasks.add_task(
            run_pipeline,
            session_id,
            room["room_url"],
            room["room_token"],
        )

        return SessionStartResponse(
            session_id=session_id,
            room_url=room["room_url"],
            room_token=room["room_token"],
            created_at=datetime.now(UTC).isoformat(),
        )

    except httpx.HTTPError as e:
        logger.error("Failed to create Daily room: %s", e)
        raise HTTPException(status_code=502, detail="Failed to create voice room") from e
    except Exception as e:
        logger.error("Failed to start session: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/sessions/stop", response_model=SessionStopResponse)
async def stop_session(request: SessionStopRequest) -> SessionStopResponse:
    """Stop an active voice session.

    Stops the pipeline and updates the session status.
    """
    session_id = request.session_id

    pipeline = active_pipelines.get(session_id)
    if not pipeline:
        raise HTTPException(
            status_code=404,
            detail=f"Session {session_id} not found or not active",
        )

    try:
        await pipeline.stop()
        active_pipelines.pop(session_id, None)

        # Update session status
        client = get_supabase_client()
        client.table("sessions").update(
            {
                "status": "completed",
                "updated_at": datetime.now(UTC).isoformat(),
            }
        ).eq("id", session_id).execute()

        return SessionStopResponse(
            session_id=session_id,
            stopped_at=datetime.now(UTC).isoformat(),
            status="completed",
        )

    except Exception as e:
        logger.error("Failed to stop session %s: %s", session_id, e)
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/healthz", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Health check endpoint."""
    services = {
        "database": "down",
        "stt": "down",
        "llm": "down",
        "daily": "down",
    }

    # Check database
    try:
        client = get_supabase_client()
        client.table("sessions").select("id").limit(1).execute()
        services["database"] = "up"
    except Exception as e:
        logger.warning("Database health check failed: %s", e)

    # Check Deepgram (simple key validation)
    if settings.deepgram_api_key:
        services["stt"] = "up"

    # Check Anthropic (simple key validation)
    if settings.anthropic_api_key:
        services["llm"] = "up"

    # Check Daily (simple key validation)
    if settings.daily_api_key:
        services["daily"] = "up"

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
