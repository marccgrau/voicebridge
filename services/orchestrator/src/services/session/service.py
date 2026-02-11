"""Application service for session lifecycle endpoints."""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from src.ports.session_runtime import SessionRuntimeRegistryPort

from .contracts import (
    SessionAcceptParams,
    SessionAcceptResult,
    SessionCreateParams,
    SessionCreateResult,
    SessionStartParams,
    SessionStartResult,
    SessionStopResult,
)
from .errors import (
    SessionAlreadyActiveError,
    SessionConflictError,
    SessionNotActiveError,
    SessionNotFoundError,
)


class SessionLifecycleService:
    """Encapsulates session lifecycle business rules."""

    def __init__(
        self,
        runtime_registry: SessionRuntimeRegistryPort,
        get_supabase_client: Callable[[], Any],
        create_daily_room: Callable[[], Awaitable[dict[str, str]]],
        create_meeting_token: Callable[[str, bool, str | None], Awaitable[str]],
        pipeline_stop_timeout: float,
    ):
        self.runtime_registry = runtime_registry
        self.get_supabase_client = get_supabase_client
        self.create_daily_room = create_daily_room
        self.create_meeting_token = create_meeting_token
        self._pipeline_stop_timeout = pipeline_stop_timeout
        self.logger = logging.getLogger(__name__)

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(UTC).isoformat()

    @staticmethod
    def _build_rtvi_url(room_url_or_name: str) -> str:
        room_name = room_url_or_name.split("/")[-1]
        return f"wss://api.daily.co/v1/rooms/{room_name}/rtvi"

    @staticmethod
    def _build_services_payload(
        enable_process_flow: bool,
        enable_suggestion_flow: bool,
        process_flow_provider: str,
        process_flow_model: str,
        suggestion_flow_provider: str,
        suggestion_flow_model: str,
    ) -> dict[str, Any]:
        return {
            "processFlowEnabled": enable_process_flow,
            "suggestionFlowEnabled": enable_suggestion_flow,
            "processFlowProvider": process_flow_provider,
            "processFlowModel": process_flow_model,
            "suggestionFlowProvider": suggestion_flow_provider,
            "suggestionFlowModel": suggestion_flow_model,
            "guidanceMode": "direct_call",
        }

    async def start_session(
        self,
        params: SessionStartParams,
        schedule_pipeline: Callable[..., None],
    ) -> SessionStartResult:
        """Create active session and schedule pipeline start."""
        session_id = params.session_id or str(uuid4())

        if self.runtime_registry.has(session_id):
            raise SessionAlreadyActiveError(f"Session {session_id} is already active")

        room = await self.create_daily_room()

        client = self.get_supabase_client()
        client.table("sessions").insert(
            {
                "id": session_id,
                "state": {
                    "locale": params.locale,
                    "domain": params.domain,
                    "queueTag": params.queue_tag,
                    "metadata": params.metadata,
                    "slots": {},
                    "steps": [],
                },
                "status": "active",
                "suggestion_service": "direct_call",
                "process_illustration_enabled": params.enable_process_flow,
            }
        ).execute()

        schedule_pipeline(
            session_id,
            room["room_url"],
            room["room_token"],
            params.enable_process_flow,
            params.enable_suggestion_flow,
            params.process_flow_provider,
            params.process_flow_model,
            params.suggestion_flow_provider,
            params.suggestion_flow_model,
            params.process_content_path,
        )

        return SessionStartResult(
            session_id=session_id,
            room_url=room["room_url"],
            room_token=room["room_token"],
            created_at=self._now_iso(),
            rtvi_url=self._build_rtvi_url(room["room_url"]),
            services=self._build_services_payload(
                params.enable_process_flow,
                params.enable_suggestion_flow,
                params.process_flow_provider,
                params.process_flow_model,
                params.suggestion_flow_provider,
                params.suggestion_flow_model,
            ),
        )

    async def create_session(
        self,
        params: SessionCreateParams,
        schedule_pipeline: Callable[..., None],
    ) -> SessionCreateResult:
        """Create pending customer-initiated session and schedule bot pipeline."""
        session_id = str(uuid4())
        room = await self.create_daily_room()
        customer_token = await self.create_meeting_token(
            room["room_name"],
            False,
            "customer",
        )

        client = self.get_supabase_client()
        client.table("sessions").insert(
            {
                "id": session_id,
                "state": {
                    "locale": params.locale,
                    "domain": params.domain,
                    "metadata": params.metadata,
                    "slots": {},
                    "steps": [],
                },
                "status": "pending",
                "room_url": room["room_url"],
                "room_name": room["room_name"],
                "customer_id": params.customer_id,
                "customer_joined_at": self._now_iso(),
                "suggestion_service": "direct_call",
                "process_illustration_enabled": True,
            }
        ).execute()

        schedule_pipeline(
            session_id,
            room["room_url"],
            room["room_token"],
            True,
            True,
            None,
            None,
            None,
            None,
            None,
        )

        return SessionCreateResult(
            session_id=session_id,
            room_url=room["room_url"],
            customer_token=customer_token,
        )

    async def accept_session(self, params: SessionAcceptParams) -> SessionAcceptResult:
        """Accept pending session and return agent connection details."""
        client = self.get_supabase_client()
        result = (
            client.table("sessions")
            .update(
                {
                    "status": "active",
                    "agent_joined_at": self._now_iso(),
                    "updated_at": self._now_iso(),
                }
            )
            .eq("id", params.session_id)
            .eq("status", "pending")
            .execute()
        )

        if not result.data:
            raise SessionConflictError(
                f"Session {params.session_id} is not pending or does not exist"
            )

        session_data = result.data[0]
        room_url = session_data["room_url"]
        room_name = session_data["room_name"]

        agent_token = await self.create_meeting_token(room_name, False, "agent")

        return SessionAcceptResult(
            session_id=params.session_id,
            room_url=room_url,
            agent_token=agent_token,
            rtvi_url=self._build_rtvi_url(room_name),
            services=self._build_services_payload(
                params.enable_process_flow,
                params.enable_suggestion_flow,
                params.process_flow_provider,
                params.process_flow_model,
                params.suggestion_flow_provider,
                params.suggestion_flow_model,
            ),
        )

    async def stop_session(self, session_id: str) -> SessionStopResult:
        """Stop active session runtime and mark completion."""
        pipeline = self.runtime_registry.get(session_id)
        if not pipeline:
            client = self.get_supabase_client()
            try:
                resp = (
                    client.table("sessions")
                    .select("status")
                    .eq("id", session_id)
                    .single()
                    .execute()
                )
                if resp.data and resp.data["status"] in ("pending", "active"):
                    client.table("sessions").update(
                        {
                            "status": "abandoned",
                            "updated_at": self._now_iso(),
                        }
                    ).eq("id", session_id).execute()
                    return SessionStopResult(
                        session_id=session_id,
                        stopped_at=self._now_iso(),
                        status="abandoned",
                    )
            except Exception as e:
                self.logger.error("Failed to check session %s in database: %s", session_id, e)

            raise SessionNotActiveError(f"Session {session_id} not found or not active")

        stop_error = None
        try:
            await asyncio.wait_for(
                pipeline.stop(),
                timeout=self._pipeline_stop_timeout,
            )
            self.logger.info("Pipeline stopped successfully for session %s", session_id)
        except TimeoutError:
            stop_error = f"Pipeline stop timed out after {self._pipeline_stop_timeout}s"
            self.logger.error("Stop timeout for session %s: %s", session_id, stop_error)
        except Exception as e:
            stop_error = f"Pipeline stop failed: {e}"
            self.logger.error(
                "Stop error for session %s: %s", session_id, stop_error, exc_info=True
            )
        finally:
            self.runtime_registry.remove(session_id)
            try:
                client = self.get_supabase_client()
                client.table("sessions").update(
                    {
                        "status": "completed",
                        "updated_at": self._now_iso(),
                    }
                ).eq("id", session_id).execute()
            except Exception as e:
                self.logger.error("Failed to update session %s status: %s", session_id, e)

        if stop_error:
            self.logger.warning("Session %s stopped with errors: %s", session_id, stop_error)

        return SessionStopResult(
            session_id=session_id,
            stopped_at=self._now_iso(),
            status="completed",
        )

    def get_session_status(self, session_id: str) -> dict[str, Any]:
        """Return session status payload."""
        client = self.get_supabase_client()
        response = client.table("sessions").select("*").eq("id", session_id).single().execute()
        if not response.data:
            raise SessionNotFoundError(f"Session {session_id} not found")

        return {
            "session_id": session_id,
            "is_active": self.runtime_registry.has(session_id),
            "status": response.data["status"],
            "process_key": response.data.get("process_key"),
            "created_at": response.data["created_at"],
            "updated_at": response.data["updated_at"],
        }
