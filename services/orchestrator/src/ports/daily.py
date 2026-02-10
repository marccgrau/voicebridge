"""Daily.co integration port definitions."""

from typing import Protocol, TypedDict


class DailyRoom(TypedDict):
    """Daily room details with owner token."""

    room_url: str
    room_name: str
    room_token: str


class DailyPort(Protocol):
    """Daily.co API abstraction."""

    async def create_room(self) -> DailyRoom:
        """Create a room and owner token."""

    async def create_meeting_token(
        self,
        room_name: str,
        is_owner: bool = False,
        user_name: str | None = None,
    ) -> str:
        """Create a meeting token for the given room/user."""
