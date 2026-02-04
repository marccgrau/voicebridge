"""Tests for Daily.co integration."""

from unittest.mock import patch

import httpx
import pytest
import respx

from src.main import create_daily_room


class TestCreateDailyRoom:
    """Tests for the create_daily_room function."""

    @respx.mock
    @patch("src.main.settings")
    async def test_creates_room_successfully(self, mock_settings):
        """Test successful Daily.co room creation."""
        mock_settings.daily_api_key = "test-api-key"

        # Mock Daily.co API responses
        respx.post("https://api.daily.co/v1/rooms").mock(
            return_value=httpx.Response(
                200,
                json={
                    "url": "https://test.daily.co/test-room-123",
                    "name": "test-room-123",
                    "id": "room-id-123",
                },
            )
        )
        respx.post("https://api.daily.co/v1/meeting-tokens").mock(
            return_value=httpx.Response(
                200,
                json={"token": "meeting-token-xyz"},
            )
        )

        result = await create_daily_room()

        assert result["room_url"] == "https://test.daily.co/test-room-123"
        assert result["room_token"] == "meeting-token-xyz"

    @respx.mock
    @patch("src.main.settings")
    async def test_sends_correct_room_properties(self, mock_settings):
        """Test that room is created with correct properties."""
        mock_settings.daily_api_key = "test-api-key"

        room_route = respx.post("https://api.daily.co/v1/rooms").mock(
            return_value=httpx.Response(
                200,
                json={
                    "url": "https://test.daily.co/test-room",
                    "name": "test-room",
                },
            )
        )
        respx.post("https://api.daily.co/v1/meeting-tokens").mock(
            return_value=httpx.Response(200, json={"token": "token"})
        )

        await create_daily_room()

        # Verify request was made
        assert room_route.called

        # Verify request body
        request = room_route.calls[0].request
        body = request.read()
        import json

        data = json.loads(body)

        assert "properties" in data
        props = data["properties"]
        assert props["enable_chat"] is False
        assert props["enable_screenshare"] is False
        assert props["start_audio_off"] is False
        assert props["start_video_off"] is True
        assert "exp" in props  # Expiration time

    @respx.mock
    @patch("src.main.settings")
    async def test_sets_room_expiration_to_1_hour(self, mock_settings):
        """Test that room expiration is set to 1 hour."""
        import time

        mock_settings.daily_api_key = "test-api-key"

        room_route = respx.post("https://api.daily.co/v1/rooms").mock(
            return_value=httpx.Response(
                200,
                json={
                    "url": "https://test.daily.co/test-room",
                    "name": "test-room",
                },
            )
        )
        respx.post("https://api.daily.co/v1/meeting-tokens").mock(
            return_value=httpx.Response(200, json={"token": "token"})
        )

        await create_daily_room()

        # Get the expiration time from request
        request = room_route.calls[0].request
        body = request.read()
        import json

        data = json.loads(body)
        exp_time = data["properties"]["exp"]

        # Verify it's approximately 1 hour from now (allow 5 second tolerance)
        now = time.time()
        expected_exp = now + 3600
        assert abs(exp_time - expected_exp) < 5

    @respx.mock
    @patch("src.main.settings")
    async def test_creates_meeting_token_with_correct_properties(self, mock_settings):
        """Test that meeting token is created with correct properties."""
        mock_settings.daily_api_key = "test-api-key"

        respx.post("https://api.daily.co/v1/rooms").mock(
            return_value=httpx.Response(
                200,
                json={
                    "url": "https://test.daily.co/my-room",
                    "name": "my-room",
                },
            )
        )

        token_route = respx.post("https://api.daily.co/v1/meeting-tokens").mock(
            return_value=httpx.Response(200, json={"token": "token-123"})
        )

        await create_daily_room()

        # Verify token request
        assert token_route.called

        request = token_route.calls[0].request
        body = request.read()
        import json

        data = json.loads(body)

        assert "properties" in data
        props = data["properties"]
        assert props["room_name"] == "my-room"
        assert props["is_owner"] is True

    @respx.mock
    @patch("src.main.settings")
    async def test_includes_authorization_header(self, mock_settings):
        """Test that Authorization header is sent correctly."""
        mock_settings.daily_api_key = "my-secret-key"

        room_route = respx.post("https://api.daily.co/v1/rooms").mock(
            return_value=httpx.Response(
                200,
                json={"url": "https://test.daily.co/room", "name": "room"},
            )
        )
        token_route = respx.post("https://api.daily.co/v1/meeting-tokens").mock(
            return_value=httpx.Response(200, json={"token": "token"})
        )

        await create_daily_room()

        # Check both requests have correct auth header
        room_request = room_route.calls[0].request
        assert room_request.headers["Authorization"] == "Bearer my-secret-key"

        token_request = token_route.calls[0].request
        assert token_request.headers["Authorization"] == "Bearer my-secret-key"

    @respx.mock
    @patch("src.main.settings")
    async def test_handles_room_creation_failure(self, mock_settings):
        """Test handling of room creation failures."""
        mock_settings.daily_api_key = "test-api-key"

        # Mock failed room creation
        respx.post("https://api.daily.co/v1/rooms").mock(
            return_value=httpx.Response(
                500,
                json={"error": "Internal server error"},
            )
        )

        with pytest.raises(httpx.HTTPStatusError):
            await create_daily_room()

    @respx.mock
    @patch("src.main.settings")
    async def test_handles_token_creation_failure(self, mock_settings):
        """Test handling of token creation failures."""
        mock_settings.daily_api_key = "test-api-key"

        # Mock successful room but failed token
        respx.post("https://api.daily.co/v1/rooms").mock(
            return_value=httpx.Response(
                200,
                json={"url": "https://test.daily.co/room", "name": "room"},
            )
        )
        respx.post("https://api.daily.co/v1/meeting-tokens").mock(
            return_value=httpx.Response(
                403,
                json={"error": "Forbidden"},
            )
        )

        with pytest.raises(httpx.HTTPStatusError):
            await create_daily_room()

    @respx.mock
    @patch("src.main.settings")
    async def test_handles_network_error(self, mock_settings):
        """Test handling of network errors."""
        mock_settings.daily_api_key = "test-api-key"

        # Mock network error
        respx.post("https://api.daily.co/v1/rooms").mock(
            side_effect=httpx.ConnectError("Connection failed")
        )

        with pytest.raises(httpx.ConnectError):
            await create_daily_room()

    @respx.mock
    @patch("src.main.settings")
    async def test_handles_timeout(self, mock_settings):
        """Test handling of request timeouts."""
        mock_settings.daily_api_key = "test-api-key"

        # Mock timeout
        respx.post("https://api.daily.co/v1/rooms").mock(
            side_effect=httpx.TimeoutException("Request timed out")
        )

        with pytest.raises(httpx.TimeoutException):
            await create_daily_room()
