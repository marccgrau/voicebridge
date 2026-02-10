"""FastAPI entrypoint for VoiceBridge Orchestrator."""

import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any

import httpx
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.api.routes.health import HealthRouterDeps, build_health_router
from src.api.routes.sessions import SessionRouterDeps, build_sessions_router
from src.api.schemas import LLMProvider
from src.composition import SessionRuntimeRegistry, build_container
from src.config import settings
from src.db import get_supabase_client
from src.llm import LLMServiceFactory, SummaryService
from src.pipeline import VoiceBridgePipeline

# Configure logging
logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Suppress noisy warnings from Daily transport when waiting for participants
logging.getLogger("pipecat.transports.base_input").setLevel(logging.ERROR)

# Active pipelines storage (kept for compatibility with tests)
active_pipelines: dict[str, VoiceBridgePipeline] = {}
runtime_registry = SessionRuntimeRegistry(_runtimes=active_pipelines)


async def cleanup_all_pipelines() -> None:
    """Stop all active pipelines."""
    logger.info("Shutting down VoiceBridge Orchestrator...")
    for session_id in runtime_registry.list_session_ids():
        pipeline = runtime_registry.get(session_id)
        if not pipeline:
            continue
        try:
            await asyncio.wait_for(pipeline.stop(), timeout=10.0)
        except TimeoutError:
            logger.error("Timeout stopping pipeline %s", session_id)
        except Exception as e:
            logger.error("Error stopping pipeline %s: %s", session_id, e)
    runtime_registry.clear()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Application lifespan handler."""
    logger.info("VoiceBridge Orchestrator starting...")
    yield
    await cleanup_all_pipelines()


app = FastAPI(
    title="VoiceBridge Orchestrator",
    description="Voice pipeline orchestrator for customer service guidance",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle unexpected exceptions globally."""
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


async def create_meeting_token(
    room_name: str,
    is_owner: bool = False,
    user_name: str | None = None,
) -> str:
    """Create a Daily.co meeting token for a room."""
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
    """Create a Daily.co room and an owner token."""
    async with httpx.AsyncClient(timeout=httpx.Timeout(settings.daily_api_timeout)) as client:
        room_response = await client.post(
            "https://api.daily.co/v1/rooms",
            headers={"Authorization": f"Bearer {settings.daily_api_key}"},
            json={
                "properties": {
                    "exp": int((datetime.now(UTC).timestamp()) + 3600),
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
    """Update session to error state."""
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
    process_flow_provider: LLMProvider,
    process_flow_model: str,
    suggestion_flow_provider: LLMProvider,
    suggestion_flow_model: str,
    process_content_path: str | None,
) -> None:
    """Run the pipeline in the background."""
    if enable_process_flow:
        LLMServiceFactory.validate_provider_config(process_flow_provider)
    if enable_suggestion_flow:
        LLMServiceFactory.validate_provider_config(suggestion_flow_provider)

    pipeline = VoiceBridgePipeline(
        session_id=session_id,
        room_url=room_url,
        room_token=room_token,
        enable_process_flow=enable_process_flow,
        enable_suggestion_flow=enable_suggestion_flow,
        process_flow_provider=process_flow_provider,
        process_flow_model=process_flow_model,
        suggestion_flow_provider=suggestion_flow_provider,
        suggestion_flow_model=suggestion_flow_model,
        process_content_path=process_content_path or "process_content/",
    )

    runtime_registry.set(session_id, pipeline)

    try:
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
        runtime_registry.remove(session_id)


async def _run_pipeline_proxy(*args, **kwargs) -> None:
    """Proxy used by routes to preserve patchability of run_pipeline in tests."""
    await run_pipeline(*args, **kwargs)


def _get_supabase_client_proxy():
    """Proxy used by routes to preserve patchability of get_supabase_client in tests."""
    return get_supabase_client()


def _get_settings_proxy():
    """Proxy used by routes to preserve patchability of settings in tests."""
    return settings


container = build_container(
    runtime_registry=runtime_registry,
    get_supabase_client=_get_supabase_client_proxy,
    get_settings=_get_settings_proxy,
    create_daily_room=create_daily_room,
    create_meeting_token=create_meeting_token,
    run_pipeline=_run_pipeline_proxy,
    summary_llm_factory=lambda: SummaryService(),
)


app.include_router(
    build_sessions_router(
        SessionRouterDeps(
            build_session_lifecycle_service=container.build_session_lifecycle_service,
            get_supabase_client=container.get_supabase_client,
            run_pipeline=container.run_pipeline,
            summary_llm_factory=container.summary_llm_factory,
        )
    )
)

app.include_router(
    build_health_router(
        HealthRouterDeps(
            get_supabase_client=container.get_supabase_client,
            get_settings=container.get_settings,
        )
    )
)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "src.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )
