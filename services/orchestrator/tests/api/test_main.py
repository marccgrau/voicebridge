"""Tests for FastAPI endpoints."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from src.main import active_pipelines, app

# ---------------------------------------------------------------------------
# Shared Daily.co mock helpers
# ---------------------------------------------------------------------------

DAILY_ROOM_JSON = {"url": "https://test.daily.co/test-room", "name": "test-room"}
DAILY_TOKEN_JSON = {"token": "test-token-123"}


@pytest.fixture
def client():
    """Create a FastAPI test client."""
    return TestClient(app)


@pytest.fixture(autouse=True)
def clear_active_pipelines():
    """Clear active pipelines before each test."""
    active_pipelines.clear()
    yield
    active_pipelines.clear()


@pytest.fixture
def mock_supabase_operations(mock_supabase_client):
    """Mock common Supabase operations."""
    # Mock insert
    mock_insert = MagicMock()
    mock_insert.execute.return_value = MagicMock(
        data={"id": "test-session-123"},
        error=None,
    )

    # Mock update
    mock_update = MagicMock()
    mock_update.eq.return_value = mock_update
    mock_update.execute.return_value = MagicMock(data={}, error=None)

    # Mock select
    mock_select = MagicMock()
    mock_select.eq.return_value = mock_select
    mock_select.single.return_value = mock_select
    mock_select.limit.return_value = mock_select
    mock_select.execute.return_value = MagicMock(
        data={
            "id": "test-session-123",
            "status": "active",
            "process_key": None,
            "created_at": datetime.now(UTC).isoformat(),
            "updated_at": datetime.now(UTC).isoformat(),
        },
        error=None,
    )

    # Mock table
    mock_table = MagicMock()
    mock_table.insert.return_value = mock_insert
    mock_table.update.return_value = mock_update
    mock_table.select.return_value = mock_select

    mock_supabase_client.table.return_value = mock_table

    return mock_supabase_client


class TestSessionStartEndpoint:
    """Tests for POST /sessions/start endpoint."""

    @respx.mock
    @patch("src.main.get_supabase_client")
    @patch("src.main.run_pipeline")
    def test_creates_session_successfully(
        self, mock_run_pipeline, mock_get_client, client, mock_supabase_operations
    ):
        """Test successful session creation."""
        mock_get_client.return_value = mock_supabase_operations
        mock_run_pipeline.return_value = AsyncMock()

        # Mock Daily.co API responses
        respx.post("https://api.daily.co/v1/rooms").mock(
            return_value=httpx.Response(
                200,
                json={
                    "url": "https://test.daily.co/test-room",
                    "name": "test-room",
                },
            )
        )
        respx.post("https://api.daily.co/v1/meeting-tokens").mock(
            return_value=httpx.Response(
                200,
                json={"token": "test-token-123"},
            )
        )

        response = client.post(
            "/sessions/start",
            json={"locale": "en", "domain": "billing"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "session_id" in data
        assert data["room_url"] == "https://test.daily.co/test-room"
        assert data["room_token"] == "test-token-123"
        assert "created_at" in data

    @respx.mock
    @patch("src.main.get_supabase_client")
    @patch("src.main.run_pipeline")
    def test_uses_custom_session_id(
        self, mock_run_pipeline, mock_get_client, client, mock_supabase_operations
    ):
        """Test that custom session ID is used if provided."""
        mock_get_client.return_value = mock_supabase_operations
        mock_run_pipeline.return_value = AsyncMock()

        respx.post("https://api.daily.co/v1/rooms").mock(
            return_value=httpx.Response(
                200,
                json={"url": "https://test.daily.co/test-room", "name": "test-room"},
            )
        )
        respx.post("https://api.daily.co/v1/meeting-tokens").mock(
            return_value=httpx.Response(200, json={"token": "test-token"})
        )

        custom_id = "my-custom-session-id"
        response = client.post(
            "/sessions/start",
            json={"session_id": custom_id},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["session_id"] == custom_id

    @respx.mock
    @patch("src.main.get_supabase_client")
    def test_rejects_duplicate_session_id(self, mock_get_client, client, mock_supabase_operations):
        """Test that duplicate session ID is rejected."""
        mock_get_client.return_value = mock_supabase_operations

        # Add a fake active pipeline
        active_pipelines["existing-session"] = MagicMock()

        response = client.post(
            "/sessions/start",
            json={"session_id": "existing-session"},
        )

        assert response.status_code == 400
        assert "already active" in response.json()["detail"]

    @respx.mock
    @patch("src.main.get_supabase_client")
    def test_handles_daily_api_failure(self, mock_get_client, client, mock_supabase_operations):
        """Test handling of Daily.co API failures."""
        mock_get_client.return_value = mock_supabase_operations

        # Mock Daily.co API error
        respx.post("https://api.daily.co/v1/rooms").mock(
            return_value=httpx.Response(503, json={"error": "Service unavailable"})
        )

        response = client.post(
            "/sessions/start",
            json={"locale": "en"},
        )

        assert response.status_code == 502
        assert "Failed to create voice room" in response.json()["detail"]

    @respx.mock
    @patch("src.main.get_supabase_client")
    def test_handles_database_failure(self, mock_get_client, client):
        """Test handling of database failures."""
        # Mock database error
        mock_client = MagicMock()
        mock_table = MagicMock()
        mock_insert = MagicMock()
        mock_insert.execute.side_effect = Exception("Database error")
        mock_table.insert.return_value = mock_insert
        mock_client.table.return_value = mock_table
        mock_get_client.return_value = mock_client

        # Mock successful Daily.co responses
        respx.post("https://api.daily.co/v1/rooms").mock(
            return_value=httpx.Response(
                200,
                json={"url": "https://test.daily.co/test-room", "name": "test-room"},
            )
        )
        respx.post("https://api.daily.co/v1/meeting-tokens").mock(
            return_value=httpx.Response(200, json={"token": "test-token"})
        )

        response = client.post(
            "/sessions/start",
            json={"locale": "en"},
        )

        assert response.status_code == 500

    @respx.mock
    @patch("src.main.get_supabase_client")
    @patch("src.main.run_pipeline")
    def test_creates_database_record_with_correct_structure(
        self, mock_run_pipeline, mock_get_client, client, mock_supabase_operations
    ):
        """Test that database record is created with correct structure."""
        mock_get_client.return_value = mock_supabase_operations
        mock_run_pipeline.return_value = AsyncMock()

        respx.post("https://api.daily.co/v1/rooms").mock(
            return_value=httpx.Response(
                200,
                json={"url": "https://test.daily.co/test-room", "name": "test-room"},
            )
        )
        respx.post("https://api.daily.co/v1/meeting-tokens").mock(
            return_value=httpx.Response(200, json={"token": "test-token"})
        )

        response = client.post(
            "/sessions/start",
            json={
                "locale": "es",
                "domain": "account",
                "queue_tag": "premium",
                "metadata": {"customer_id": "123"},
            },
        )

        assert response.status_code == 200

        # Verify database insert was called
        mock_supabase_operations.table.assert_called()
        insert_call = mock_supabase_operations.table.return_value.insert
        assert insert_call.called

        # Check the data structure passed to insert
        insert_data = insert_call.call_args[0][0]
        assert insert_data["status"] == "active"
        assert insert_data["state"]["locale"] == "es"
        assert insert_data["state"]["domain"] == "account"
        assert insert_data["state"]["queueTag"] == "premium"
        assert insert_data["state"]["metadata"]["customer_id"] == "123"
        assert insert_data["state"]["slots"] == {}
        assert insert_data["state"]["steps"] == []


class TestSessionStopEndpoint:
    """Tests for POST /sessions/stop endpoint."""

    @patch("src.main.get_supabase_client")
    def test_stops_active_session(self, mock_get_client, client, mock_supabase_operations):
        """Test stopping an active session."""
        mock_get_client.return_value = mock_supabase_operations

        # Add mock pipeline
        mock_pipeline = MagicMock()
        mock_pipeline.stop = AsyncMock()
        active_pipelines["test-session"] = mock_pipeline

        response = client.post(
            "/sessions/stop",
            json={"session_id": "test-session"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["session_id"] == "test-session"
        assert data["status"] == "completed"
        assert "stopped_at" in data

        # Verify pipeline was stopped
        mock_pipeline.stop.assert_called_once()

        # Verify session removed from active pipelines
        assert "test-session" not in active_pipelines

    @patch("src.main.get_supabase_client")
    def test_updates_database_status(self, mock_get_client, client, mock_supabase_operations):
        """Test that database is updated when session stops."""
        mock_get_client.return_value = mock_supabase_operations

        mock_pipeline = MagicMock()
        mock_pipeline.stop = AsyncMock()
        active_pipelines["test-session"] = mock_pipeline

        response = client.post(
            "/sessions/stop",
            json={"session_id": "test-session"},
        )

        assert response.status_code == 200

        # Verify database update was called
        mock_supabase_operations.table.assert_called_with("sessions")
        update_call = mock_supabase_operations.table.return_value.update
        assert update_call.called

        update_data = update_call.call_args[0][0]
        assert update_data["status"] == "completed"
        assert "updated_at" in update_data

    def test_returns_404_for_nonexistent_session(self, client):
        """Test that 404 is returned for non-existent session."""
        response = client.post(
            "/sessions/stop",
            json={"session_id": "nonexistent-session"},
        )

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    @patch("src.main.get_supabase_client")
    def test_handles_pipeline_stop_error(self, mock_get_client, client, mock_supabase_operations):
        """Test handling of errors during pipeline stop."""
        mock_get_client.return_value = mock_supabase_operations

        mock_pipeline = MagicMock()
        mock_pipeline.stop = AsyncMock(side_effect=Exception("Stop failed"))
        active_pipelines["test-session"] = mock_pipeline

        response = client.post(
            "/sessions/stop",
            json={"session_id": "test-session"},
        )

        # Now returns 200 with graceful error handling
        assert response.status_code == 200
        assert response.json()["status"] == "completed"


class TestHealthCheckEndpoint:
    """Tests for GET /healthz endpoint."""

    @respx.mock
    @patch("src.main.get_supabase_client")
    @patch("src.main.settings")
    def test_all_services_healthy(self, mock_settings, mock_get_client, client):
        """Test health check when all services are up."""
        # Mock successful database query
        mock_client = MagicMock()
        mock_table = MagicMock()
        mock_select = MagicMock()
        mock_select.limit.return_value = mock_select
        mock_select.execute.return_value = MagicMock(data=[])
        mock_table.select.return_value = mock_select
        mock_client.table.return_value = mock_table
        mock_get_client.return_value = mock_client

        # Mock settings
        mock_settings.speechmatics_api_key = "test-key"
        mock_settings.anthropic_api_key = "test-key"
        mock_settings.daily_api_key = "test-key"

        # Mock Daily.co health check
        respx.get("https://api.daily.co/v1").mock(
            return_value=httpx.Response(200, json={"version": "test"})
        )

        response = client.get("/healthz")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["version"] == "0.1.0"
        assert data["services"]["database"] == "up"
        assert data["services"]["stt"] == "up"
        assert data["services"]["llm"] == "up"
        assert data["services"]["daily"] == "up"

    @respx.mock
    @patch("src.main.get_supabase_client")
    @patch("src.main.settings")
    def test_degraded_state(self, mock_settings, mock_get_client, client):
        """Test health check in degraded state (some services down)."""
        # Mock database failure
        mock_client = MagicMock()
        mock_table = MagicMock()
        mock_select = MagicMock()
        mock_select.limit.return_value = mock_select
        mock_select.execute.side_effect = Exception("Database error")
        mock_table.select.return_value = mock_select
        mock_client.table.return_value = mock_table
        mock_get_client.return_value = mock_client

        # Mock settings (other services OK)
        mock_settings.speechmatics_api_key = "test-key"
        mock_settings.anthropic_api_key = "test-key"
        mock_settings.daily_api_key = "test-key"

        # Mock Daily.co health check (success)
        respx.get("https://api.daily.co/v1").mock(
            return_value=httpx.Response(200, json={"version": "test"})
        )

        response = client.get("/healthz")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "degraded"
        assert data["services"]["database"] == "down"
        assert data["services"]["stt"] == "up"
        assert data["services"]["llm"] == "up"
        assert data["services"]["daily"] == "up"

    @respx.mock
    @patch("src.main.get_supabase_client")
    @patch("src.main.settings")
    def test_unhealthy_state(self, mock_settings, mock_get_client, client):
        """Test health check in unhealthy state (all services down)."""
        # Mock database failure
        mock_client = MagicMock()
        mock_table = MagicMock()
        mock_select = MagicMock()
        mock_select.limit.return_value = mock_select
        mock_select.execute.side_effect = Exception("Database error")
        mock_table.select.return_value = mock_select
        mock_client.table.return_value = mock_table
        mock_get_client.return_value = mock_client

        # Mock missing API keys
        mock_settings.speechmatics_api_key = None
        mock_settings.anthropic_api_key = None
        mock_settings.daily_api_key = None

        # Mock Daily.co health check failure (will fail without API key)
        respx.get("https://api.daily.co/v1").mock(
            return_value=httpx.Response(401, json={"error": "Unauthorized"})
        )

        response = client.get("/healthz")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "unhealthy"
        assert data["services"]["database"] == "down"
        assert data["services"]["stt"] == "down"
        assert data["services"]["llm"] == "down"
        assert data["services"]["daily"] == "down"


class TestGetSessionStatus:
    """Tests for GET /sessions/{session_id}/status endpoint."""

    @patch("src.main.get_supabase_client")
    def test_returns_active_session_status(self, mock_get_client, client):
        """Test getting status of an active session."""
        # Mock database response
        mock_client = MagicMock()
        mock_table = MagicMock()
        mock_select = MagicMock()
        mock_select.eq.return_value = mock_select
        mock_select.single.return_value = mock_select
        mock_select.execute.return_value = MagicMock(
            data={
                "id": "test-session",
                "status": "active",
                "process_key": "billing-dispute",
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": "2024-01-01T00:05:00Z",
            }
        )
        mock_table.select.return_value = mock_select
        mock_client.table.return_value = mock_table
        mock_get_client.return_value = mock_client

        # Add to active pipelines
        active_pipelines["test-session"] = MagicMock()

        response = client.get("/sessions/test-session/status")

        assert response.status_code == 200
        data = response.json()
        assert data["session_id"] == "test-session"
        assert data["is_active"] is True
        assert data["status"] == "active"
        assert data["process_key"] == "billing-dispute"
        assert "created_at" in data
        assert "updated_at" in data

    @patch("src.main.get_supabase_client")
    def test_returns_completed_session_status(self, mock_get_client, client):
        """Test getting status of a completed session."""
        mock_client = MagicMock()
        mock_table = MagicMock()
        mock_select = MagicMock()
        mock_select.eq.return_value = mock_select
        mock_select.single.return_value = mock_select
        mock_select.execute.return_value = MagicMock(
            data={
                "id": "completed-session",
                "status": "completed",
                "process_key": "account-support",
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": "2024-01-01T00:30:00Z",
            }
        )
        mock_table.select.return_value = mock_select
        mock_client.table.return_value = mock_table
        mock_get_client.return_value = mock_client

        # Not in active pipelines
        response = client.get("/sessions/completed-session/status")

        assert response.status_code == 200
        data = response.json()
        assert data["session_id"] == "completed-session"
        assert data["is_active"] is False
        assert data["status"] == "completed"

    @patch("src.main.get_supabase_client")
    def test_returns_404_for_missing_session(self, mock_get_client, client):
        """Test that 404 is returned for missing session."""
        mock_client = MagicMock()
        mock_table = MagicMock()
        mock_select = MagicMock()
        mock_select.eq.return_value = mock_select
        mock_select.single.return_value = mock_select
        mock_select.execute.side_effect = Exception("Not found")
        mock_table.select.return_value = mock_select
        mock_client.table.return_value = mock_table
        mock_get_client.return_value = mock_client

        response = client.get("/sessions/missing-session/status")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()


class TestSessionCreateEndpoint:
    """Tests for POST /sessions/create (customer-initiated) endpoint."""

    @respx.mock
    @patch("src.main.get_supabase_client")
    @patch("src.main.run_pipeline")
    def test_creates_pending_session(
        self, mock_run_pipeline, mock_get_client, client, mock_supabase_operations
    ):
        """Test successful customer-initiated session creation."""
        mock_get_client.return_value = mock_supabase_operations
        mock_run_pipeline.return_value = AsyncMock()

        respx.post("https://api.daily.co/v1/rooms").mock(
            return_value=httpx.Response(200, json=DAILY_ROOM_JSON)
        )
        # Two token calls: owner (bot) + customer
        respx.post("https://api.daily.co/v1/meeting-tokens").mock(
            return_value=httpx.Response(200, json=DAILY_TOKEN_JSON)
        )

        response = client.post(
            "/sessions/create",
            json={"locale": "en", "domain": "billing"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "session_id" in data
        assert data["room_url"] == "https://test.daily.co/test-room"
        assert "customer_token" in data

        # Verify database insert has status=pending
        insert_call = mock_supabase_operations.table.return_value.insert
        assert insert_call.called
        insert_data = insert_call.call_args[0][0]
        assert insert_data["status"] == "pending"
        assert insert_data["room_url"] == "https://test.daily.co/test-room"
        assert insert_data["room_name"] == "test-room"

    @respx.mock
    @patch("src.main.get_supabase_client")
    @patch("src.main.run_pipeline")
    def test_creates_session_with_customer_id(
        self, mock_run_pipeline, mock_get_client, client, mock_supabase_operations
    ):
        """Test session creation with customer_id."""
        mock_get_client.return_value = mock_supabase_operations
        mock_run_pipeline.return_value = AsyncMock()

        respx.post("https://api.daily.co/v1/rooms").mock(
            return_value=httpx.Response(200, json=DAILY_ROOM_JSON)
        )
        respx.post("https://api.daily.co/v1/meeting-tokens").mock(
            return_value=httpx.Response(200, json=DAILY_TOKEN_JSON)
        )

        customer_id = "c1a1a1a1-1111-1111-1111-111111111111"
        response = client.post(
            "/sessions/create",
            json={"locale": "de", "customer_id": customer_id},
        )

        assert response.status_code == 200
        data = response.json()
        assert "session_id" in data

        # Verify customer_id is in database insert
        insert_call = mock_supabase_operations.table.return_value.insert
        assert insert_call.called
        insert_data = insert_call.call_args[0][0]
        assert insert_data["customer_id"] == customer_id
        assert insert_data["status"] == "pending"

    @respx.mock
    @patch("src.main.get_supabase_client")
    def test_handles_daily_failure(self, mock_get_client, client, mock_supabase_operations):
        """Test handling of Daily.co API failure during create."""
        mock_get_client.return_value = mock_supabase_operations

        respx.post("https://api.daily.co/v1/rooms").mock(
            return_value=httpx.Response(503, json={"error": "Service unavailable"})
        )

        response = client.post("/sessions/create", json={})

        assert response.status_code == 502
        assert "Failed to create voice room" in response.json()["detail"]


class TestSessionSummaryEndpoint:
    """Tests for POST /sessions/summary endpoint."""

    @patch("src.main.get_supabase_client")
    def test_saves_summary_on_completed_session(self, mock_get_client, client):
        """Test successful summary save on a completed session."""
        mock_client = MagicMock()
        mock_table = MagicMock()

        # Mock select for status check
        mock_select = MagicMock()
        mock_select.eq.return_value = mock_select
        mock_select.single.return_value = mock_select
        mock_select.execute.return_value = MagicMock(data={"status": "completed"})

        # Mock update
        mock_update = MagicMock()
        mock_update.eq.return_value = mock_update
        mock_update.execute.return_value = MagicMock(data={}, error=None)

        mock_table.select.return_value = mock_select
        mock_table.update.return_value = mock_update
        mock_client.table.return_value = mock_table
        mock_get_client.return_value = mock_client

        response = client.post(
            "/sessions/summary",
            json={
                "session_id": "test-session-123",
                "summary_text": "Customer needed help with billing.",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["session_id"] == "test-session-123"
        assert data["summary_text"] == "Customer needed help with billing."
        assert data["updated_by"] == "agent"
        assert "updated_at" in data

        # Verify update was called with summary data
        update_call = mock_table.update
        assert update_call.called
        update_data = update_call.call_args[0][0]
        assert update_data["summary_text"] == "Customer needed help with billing."
        assert "summary_updated_at" in update_data
        assert update_data["summary_updated_by"] == "agent"

    @patch("src.main.get_supabase_client")
    def test_rejects_summary_for_active_session(self, mock_get_client, client):
        """Test that saving summary on active session returns 400."""
        mock_client = MagicMock()
        mock_table = MagicMock()
        mock_select = MagicMock()
        mock_select.eq.return_value = mock_select
        mock_select.single.return_value = mock_select
        mock_select.execute.return_value = MagicMock(data={"status": "active"})
        mock_table.select.return_value = mock_select
        mock_client.table.return_value = mock_table
        mock_get_client.return_value = mock_client

        response = client.post(
            "/sessions/summary",
            json={
                "session_id": "test-session-123",
                "summary_text": "Some summary",
            },
        )

        assert response.status_code == 400
        assert "terminal" in response.json()["detail"].lower()

    @patch("src.main.get_supabase_client")
    def test_rejects_summary_for_pending_session(self, mock_get_client, client):
        """Test that saving summary on pending session returns 400."""
        mock_client = MagicMock()
        mock_table = MagicMock()
        mock_select = MagicMock()
        mock_select.eq.return_value = mock_select
        mock_select.single.return_value = mock_select
        mock_select.execute.return_value = MagicMock(data={"status": "pending"})
        mock_table.select.return_value = mock_select
        mock_client.table.return_value = mock_table
        mock_get_client.return_value = mock_client

        response = client.post(
            "/sessions/summary",
            json={
                "session_id": "test-session-123",
                "summary_text": "Some summary",
            },
        )

        assert response.status_code == 400

    @patch("src.main.get_supabase_client")
    def test_returns_404_for_nonexistent_session(self, mock_get_client, client):
        """Test that saving summary for nonexistent session returns 404."""
        mock_client = MagicMock()
        mock_table = MagicMock()
        mock_select = MagicMock()
        mock_select.eq.return_value = mock_select
        mock_select.single.return_value = mock_select
        mock_select.execute.side_effect = Exception("Not found")
        mock_table.select.return_value = mock_select
        mock_client.table.return_value = mock_table
        mock_get_client.return_value = mock_client

        response = client.post(
            "/sessions/summary",
            json={
                "session_id": "nonexistent-session",
                "summary_text": "Some summary",
            },
        )

        assert response.status_code == 500

    @patch("src.main.get_supabase_client")
    def test_idempotent_overwrite(self, mock_get_client, client):
        """Test that saving summary twice overwrites the first."""
        mock_client = MagicMock()
        mock_table = MagicMock()
        mock_select = MagicMock()
        mock_select.eq.return_value = mock_select
        mock_select.single.return_value = mock_select
        mock_select.execute.return_value = MagicMock(data={"status": "completed"})
        mock_update = MagicMock()
        mock_update.eq.return_value = mock_update
        mock_update.execute.return_value = MagicMock(data={}, error=None)
        mock_table.select.return_value = mock_select
        mock_table.update.return_value = mock_update
        mock_client.table.return_value = mock_table
        mock_get_client.return_value = mock_client

        # First save
        response1 = client.post(
            "/sessions/summary",
            json={
                "session_id": "test-session-123",
                "summary_text": "First summary",
            },
        )
        assert response1.status_code == 200
        assert response1.json()["summary_text"] == "First summary"

        # Second save overwrites
        response2 = client.post(
            "/sessions/summary",
            json={
                "session_id": "test-session-123",
                "summary_text": "Updated summary",
            },
        )
        assert response2.status_code == 200
        assert response2.json()["summary_text"] == "Updated summary"

    def test_rejects_empty_summary(self, client):
        """Test that empty/whitespace summary is rejected."""
        response = client.post(
            "/sessions/summary",
            json={
                "session_id": "test-session-123",
                "summary_text": "   ",
            },
        )

        assert response.status_code == 400
        assert "empty" in response.json()["detail"].lower()


class TestGenerateSummaryEndpoint:
    """Tests for POST /sessions/{id}/generate-summary endpoint."""

    @patch("src.main.SummaryService")
    @patch("src.main.get_supabase_client")
    def test_generates_summary_for_completed_session(
        self, mock_get_client, mock_summary_service_class, client
    ):
        """Test successful summary generation from transcript."""
        mock_client = MagicMock()

        # Mock select for session status
        mock_select = MagicMock()
        mock_select.eq.return_value = mock_select
        mock_select.single.return_value = mock_select
        mock_select.execute.return_value = MagicMock(
            data={"status": "completed", "summary_text": None}
        )

        # Mock select for transcript segments
        mock_transcript_select = MagicMock()
        mock_transcript_select.eq.return_value = mock_transcript_select
        mock_transcript_select.order.return_value = mock_transcript_select
        mock_transcript_select.execute.return_value = MagicMock(
            data=[
                {
                    "speaker": "customer",
                    "text": "I need help with billing",
                    "ts": "2024-01-01T00:00:00Z",
                },
                {"speaker": "agent", "text": "I can help with that", "ts": "2024-01-01T00:00:05Z"},
            ]
        )

        # Mock update
        mock_update = MagicMock()
        mock_update.eq.return_value = mock_update
        mock_update.execute.return_value = MagicMock(data={}, error=None)

        # Route table calls: first for sessions (status check), second for transcript_segments, third for sessions (update)
        call_count = {"n": 0}

        def table_router(name):
            call_count["n"] += 1
            if name == "transcript_segments":
                return mock_transcript_select
            # sessions table
            mock_t = MagicMock()
            mock_t.select.return_value = mock_select
            mock_t.update.return_value = mock_update
            return mock_t

        mock_client.table.side_effect = table_router
        mock_get_client.return_value = mock_client

        # Mock SummaryService
        mock_summary_service = MagicMock()
        mock_summary_service.generate_summary.return_value = (
            "The customer requested help with billing. The agent assisted with the issue."
        )
        mock_summary_service_class.return_value = mock_summary_service

        response = client.post("/sessions/test-session-123/generate-summary")

        assert response.status_code == 200
        data = response.json()
        assert data["session_id"] == "test-session-123"
        assert "billing" in data["summary_text"].lower()
        assert data["updated_by"] == "ai"
        assert "updated_at" in data

        # Verify SummaryService was instantiated and generate_summary was called
        mock_summary_service_class.assert_called_once()
        mock_summary_service.generate_summary.assert_called_once()

    @patch("src.main.get_supabase_client")
    def test_rejects_active_session(self, mock_get_client, client):
        """Test that generating summary for active session returns 400."""
        mock_client = MagicMock()
        mock_table = MagicMock()
        mock_select = MagicMock()
        mock_select.eq.return_value = mock_select
        mock_select.single.return_value = mock_select
        mock_select.execute.return_value = MagicMock(
            data={"status": "active", "summary_text": None}
        )
        mock_table.select.return_value = mock_select
        mock_client.table.return_value = mock_table
        mock_get_client.return_value = mock_client

        response = client.post("/sessions/test-session-123/generate-summary")

        assert response.status_code == 400
        assert "terminal" in response.json()["detail"].lower()

    @patch("src.main.get_supabase_client")
    def test_rejects_empty_transcript(self, mock_get_client, client):
        """Test that generating summary with no transcript returns 400."""
        mock_client = MagicMock()

        mock_select = MagicMock()
        mock_select.eq.return_value = mock_select
        mock_select.single.return_value = mock_select
        mock_select.execute.return_value = MagicMock(
            data={"status": "completed", "summary_text": None}
        )

        mock_transcript_chain = MagicMock()
        mock_transcript_chain.select.return_value = mock_transcript_chain
        mock_transcript_chain.eq.return_value = mock_transcript_chain
        mock_transcript_chain.order.return_value = mock_transcript_chain
        mock_transcript_chain.execute.return_value = MagicMock(data=[])

        def table_router(name):
            if name == "transcript_segments":
                return mock_transcript_chain
            mock_t = MagicMock()
            mock_t.select.return_value = mock_select
            return mock_t

        mock_client.table.side_effect = table_router
        mock_get_client.return_value = mock_client

        response = client.post("/sessions/test-session-123/generate-summary")

        assert response.status_code == 400
        assert "transcript" in response.json()["detail"].lower()


class TestSessionAcceptEndpoint:
    """Tests for POST /sessions/accept (agent accepts pending session) endpoint."""

    @respx.mock
    @patch("src.main.get_supabase_client")
    def test_accepts_pending_session(self, mock_get_client, client):
        """Test successful session acceptance."""
        mock_client = MagicMock()
        mock_table = MagicMock()

        # Atomic update returns the updated row
        mock_update = MagicMock()
        mock_update.eq.return_value = mock_update
        mock_update.execute.return_value = MagicMock(
            data=[
                {
                    "id": "123e4567-e89b-12d3-a456-426614174000",
                    "status": "active",
                    "room_url": "https://test.daily.co/test-room",
                    "room_name": "test-room",
                }
            ]
        )
        mock_table.update.return_value = mock_update
        mock_client.table.return_value = mock_table
        mock_get_client.return_value = mock_client

        # Mock token creation
        respx.post("https://api.daily.co/v1/meeting-tokens").mock(
            return_value=httpx.Response(200, json={"token": "agent-token-abc"})
        )

        response = client.post(
            "/sessions/accept",
            json={"session_id": "123e4567-e89b-12d3-a456-426614174000"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["session_id"] == "123e4567-e89b-12d3-a456-426614174000"
        assert data["room_url"] == "https://test.daily.co/test-room"
        assert data["agent_token"] == "agent-token-abc"
        assert "rtvi_url" in data

    @patch("src.main.get_supabase_client")
    def test_rejects_already_accepted_session(self, mock_get_client, client):
        """Test that accepting an already-active session returns 409."""
        mock_client = MagicMock()
        mock_table = MagicMock()

        # Atomic update returns empty (no rows matched pending status)
        mock_update = MagicMock()
        mock_update.eq.return_value = mock_update
        mock_update.execute.return_value = MagicMock(data=[])
        mock_table.update.return_value = mock_update
        mock_client.table.return_value = mock_table
        mock_get_client.return_value = mock_client

        response = client.post(
            "/sessions/accept",
            json={"session_id": "123e4567-e89b-12d3-a456-426614174000"},
        )

        assert response.status_code == 409
        assert "not pending" in response.json()["detail"].lower()
