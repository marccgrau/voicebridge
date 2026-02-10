"""Daily.co adapter implementation."""

from datetime import UTC, datetime

import httpx

from src.config import settings
from src.ports.daily import DailyPort, DailyRoom


class DailyHttpAdapter(DailyPort):
    """DailyPort implementation over Daily REST API."""

    async def create_meeting_token(
        self,
        room_name: str,
        is_owner: bool = False,
        user_name: str | None = None,
    ) -> str:
        """Create a meeting token for a Daily room."""
        async with httpx.AsyncClient(timeout=httpx.Timeout(settings.daily_api_timeout)) as client:
            token_response = await client.post(
                "https://api.daily.co/v1/meeting-tokens",
                headers={"Authorization": f"Bearer {settings.daily_api_key}"},
                json={
                    "properties": {
                        "room_name": room_name,
                        "is_owner": is_owner,
                        "user_name": user_name,
                    }
                },
            )
            token_response.raise_for_status()
            return token_response.json()["token"]

    async def create_room(self) -> DailyRoom:
        """Create a Daily room and owner token."""
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

        room_token = await self.create_meeting_token(room_data["name"], is_owner=True)
        return {
            "room_url": room_data["url"],
            "room_name": room_data["name"],
            "room_token": room_token,
        }
