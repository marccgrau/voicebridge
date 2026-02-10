"""Health API routes."""

import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import httpx
from fastapi import APIRouter

from src.api.schemas import HealthResponse


@dataclass(frozen=True)
class HealthRouterDeps:
    """Dependencies required by health routes."""

    get_supabase_client: Callable[[], Any]
    get_settings: Callable[[], Any]


def build_health_router(deps: HealthRouterDeps) -> APIRouter:
    """Build health routes router."""
    logger = logging.getLogger(__name__)
    router = APIRouter()

    @router.get("/healthz", response_model=HealthResponse)
    async def health_check() -> HealthResponse:
        """Health check endpoint with actual service checks."""
        current_settings = deps.get_settings()
        services = {
            "database": "down",
            "stt": "down",
            "llm": "down",
            "daily": "down",
        }

        try:

            async def check_db():
                client = deps.get_supabase_client()
                client.table("sessions").select("id").limit(1).execute()

            await asyncio.wait_for(check_db(), timeout=2.0)
            services["database"] = "up"
        except TimeoutError:
            logger.warning("Database health check timed out")
        except Exception as e:
            logger.warning("Database health check failed: %s", e)

        try:

            async def check_daily():
                async with httpx.AsyncClient(timeout=httpx.Timeout(2.0)) as client:
                    response = await client.get(
                        "https://api.daily.co/v1",
                        headers={"Authorization": f"Bearer {current_settings.daily_api_key}"},
                    )
                    response.raise_for_status()

            await asyncio.wait_for(check_daily(), timeout=2.5)
            services["daily"] = "up"
        except TimeoutError:
            logger.warning("Daily.co health check timed out")
        except Exception as e:
            logger.warning("Daily.co health check failed: %s", e)

        if current_settings.speechmatics_api_key:
            services["stt"] = "up"

        if current_settings.anthropic_api_key:
            services["llm"] = "up"

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

    return router
