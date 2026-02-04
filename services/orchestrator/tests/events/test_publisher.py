"""Tests for the EventPublisher class."""

from datetime import datetime
from unittest.mock import MagicMock, patch
from uuid import UUID

import pytest

from src.events.publisher import Event, EventPublisher, get_event_publisher


class TestEvent:
    """Tests for the Event dataclass."""

    def test_event_creation(self):
        """Test that Event can be created with required fields."""
        event = Event(
            event_id="test-id",
            session_id="session-123",
            timestamp="2024-01-01T00:00:00Z",
            type="test_event",
            data={"key": "value"},
        )

        assert event.event_id == "test-id"
        assert event.session_id == "session-123"
        assert event.timestamp == "2024-01-01T00:00:00Z"
        assert event.type == "test_event"
        assert event.data == {"key": "value"}

    def test_event_to_dict(self):
        """Test that Event.to_dict() produces correct structure."""
        event = Event(
            event_id="test-id",
            session_id="session-123",
            timestamp="2024-01-01T00:00:00Z",
            type="test_event",
            data={"field1": "value1", "field2": 123},
        )

        result = event.to_dict()

        assert result["eventId"] == "test-id"
        assert result["sessionId"] == "session-123"
        assert result["timestamp"] == "2024-01-01T00:00:00Z"
        assert result["type"] == "test_event"
        assert result["field1"] == "value1"
        assert result["field2"] == 123
        # Ensure data is merged, not nested
        assert "data" not in result


class TestEventPublisher:
    """Tests for the EventPublisher class."""

    def test_init_with_client(self, mock_supabase_client):
        """Test initialization with provided client."""
        publisher = EventPublisher(client=mock_supabase_client)

        assert publisher._client is mock_supabase_client
        assert publisher.client is mock_supabase_client

    def test_init_without_client(self):
        """Test initialization without client (lazy loading)."""
        publisher = EventPublisher()

        assert publisher._client is None

    @patch("src.events.publisher.get_supabase_client")
    def test_lazy_client_initialization(self, mock_get_client):
        """Test that client is lazily initialized when accessed."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        publisher = EventPublisher()
        client = publisher.client

        assert client is mock_client
        mock_get_client.assert_called_once()

    def test_get_channel_name(self, mock_supabase_client):
        """Test channel name formatting."""
        publisher = EventPublisher(client=mock_supabase_client)

        channel_name = publisher._get_channel_name("session-123")

        assert channel_name == "session:session-123:events"

    def test_create_event(self, mock_supabase_client):
        """Test event creation with metadata."""
        publisher = EventPublisher(client=mock_supabase_client)

        event = publisher._create_event(
            session_id="session-123",
            event_type="test_event",
            data={"key": "value"},
        )

        assert isinstance(event, Event)
        assert UUID(event.event_id)  # Validate UUID format
        assert event.session_id == "session-123"
        assert event.type == "test_event"
        assert event.data == {"key": "value"}
        # Validate timestamp is ISO format
        datetime.fromisoformat(event.timestamp.replace("Z", "+00:00"))

    @pytest.mark.asyncio
    async def test_publish_creates_and_sends_event(self, mock_supabase_client):
        """Test that publish creates event and sends via Realtime."""
        publisher = EventPublisher(client=mock_supabase_client)
        mock_channel = mock_supabase_client.channel.return_value

        event = await publisher.publish(
            session_id="session-123",
            event_type="test_event",
            data={"field": "value"},
        )

        # Verify channel was created with correct name
        mock_supabase_client.channel.assert_called_once_with("session:session-123:events")

        # Verify channel operations
        mock_channel.subscribe.assert_called_once()
        mock_channel.send_broadcast.assert_called_once()
        mock_channel.unsubscribe.assert_called_once()

        # Verify broadcast payload
        call_args = mock_channel.send_broadcast.call_args
        assert call_args.kwargs["event"] == "event"
        payload = call_args.kwargs["payload"]
        assert payload["sessionId"] == "session-123"
        assert payload["type"] == "test_event"
        assert payload["field"] == "value"

        # Verify returned event
        assert isinstance(event, Event)
        assert event.session_id == "session-123"
        assert event.type == "test_event"

    @pytest.mark.asyncio
    async def test_publish_transcript_segment(self, mock_supabase_client):
        """Test publish_transcript_segment convenience method."""
        publisher = EventPublisher(client=mock_supabase_client)
        mock_channel = mock_supabase_client.channel.return_value

        event = await publisher.publish_transcript_segment(
            session_id="session-123",
            speaker="customer",
            text="Hello world",
            is_final=True,
            confidence=0.95,
        )

        # Verify event type and data
        assert event.type == "transcript_segment"
        assert event.data["speaker"] == "customer"
        assert event.data["text"] == "Hello world"
        assert event.data["isFinal"] is True
        assert event.data["confidence"] == 0.95

        # Verify broadcast was called
        mock_channel.send_broadcast.assert_called_once()
        payload = mock_channel.send_broadcast.call_args.kwargs["payload"]
        assert payload["speaker"] == "customer"
        assert payload["text"] == "Hello world"

    @pytest.mark.asyncio
    async def test_publish_transcript_segment_without_confidence(self, mock_supabase_client):
        """Test publish_transcript_segment with optional confidence."""
        publisher = EventPublisher(client=mock_supabase_client)

        event = await publisher.publish_transcript_segment(
            session_id="session-123",
            speaker="agent",
            text="Test",
            is_final=False,
        )

        assert event.data["confidence"] is None

    @pytest.mark.asyncio
    async def test_publish_process_selection(self, mock_supabase_client):
        """Test publish_process_selection convenience method."""
        publisher = EventPublisher(client=mock_supabase_client)
        mock_channel = mock_supabase_client.channel.return_value

        candidates = [
            {"process_key": "billing", "name": "Billing", "score": 0.8}
        ]

        event = await publisher.publish_process_selection(
            session_id="session-123",
            process_key="billing-dispute",
            process_name="Billing Dispute",
            confidence=0.85,
            rationale="Customer mentioned billing issue",
            candidates=candidates,
        )

        # Verify event type and data
        assert event.type == "process_selection"
        assert event.data["processKey"] == "billing-dispute"
        assert event.data["processName"] == "Billing Dispute"
        assert event.data["confidence"] == 0.85
        assert event.data["rationale"] == "Customer mentioned billing issue"
        assert event.data["candidates"] == candidates

        # Verify broadcast
        payload = mock_channel.send_broadcast.call_args.kwargs["payload"]
        assert payload["processKey"] == "billing-dispute"

    @pytest.mark.asyncio
    async def test_publish_slot_extraction(self, mock_supabase_client):
        """Test publish_slot_extraction convenience method."""
        publisher = EventPublisher(client=mock_supabase_client)
        mock_channel = mock_supabase_client.channel.return_value

        slots = [
            {"key": "customer_name", "value": "John Doe", "confidence": 0.9}
        ]

        event = await publisher.publish_slot_extraction(
            session_id="session-123",
            intent="account_inquiry",
            slots=slots,
            process_key="account-support",
        )

        # Verify event type and data
        assert event.type == "slot_extraction"
        assert event.data["intent"] == "account_inquiry"
        assert event.data["slots"] == slots
        assert event.data["processKey"] == "account-support"

        # Verify broadcast
        payload = mock_channel.send_broadcast.call_args.kwargs["payload"]
        assert payload["intent"] == "account_inquiry"

    @pytest.mark.asyncio
    async def test_publish_slot_extraction_optional_fields(self, mock_supabase_client):
        """Test publish_slot_extraction with optional fields."""
        publisher = EventPublisher(client=mock_supabase_client)

        event = await publisher.publish_slot_extraction(
            session_id="session-123",
            intent=None,
            slots=[],
        )

        assert event.data["intent"] is None
        assert event.data["processKey"] is None

    @pytest.mark.asyncio
    async def test_publish_suggestions(self, mock_supabase_client):
        """Test publish_suggestions convenience method."""
        publisher = EventPublisher(client=mock_supabase_client)

        suggestions = [
            {
                "type": "response",
                "text": "Try restarting your device",
                "priority": 1,
            }
        ]

        event = await publisher.publish_suggestions(
            session_id="session-123",
            suggestions=suggestions,
            process_key="troubleshooting",
            step_key="initial_steps",
        )

        # Verify event type and data
        assert event.type == "suggestion"
        assert event.data["suggestions"] == suggestions
        assert event.data["processKey"] == "troubleshooting"
        assert event.data["stepKey"] == "initial_steps"

    @pytest.mark.asyncio
    async def test_publish_suggestions_optional_fields(self, mock_supabase_client):
        """Test publish_suggestions with optional fields."""
        publisher = EventPublisher(client=mock_supabase_client)

        event = await publisher.publish_suggestions(
            session_id="session-123",
            suggestions=[],
        )

        assert event.data["processKey"] is None
        assert event.data["stepKey"] is None

    @pytest.mark.asyncio
    async def test_publish_session_state(self, mock_supabase_client):
        """Test publish_session_state convenience method."""
        publisher = EventPublisher(client=mock_supabase_client)

        steps = [
            {"key": "step1", "label": "Verify", "completed": True},
            {"key": "step2", "label": "Resolve", "completed": False},
        ]
        slots = {"customer_name": "John Doe", "account_id": "12345"}

        event = await publisher.publish_session_state(
            session_id="session-123",
            process_key="billing-dispute",
            process_name="Billing Dispute",
            current_step="step2",
            steps=steps,
            slots=slots,
            status="active",
        )

        # Verify event type and data
        assert event.type == "session_state"
        assert event.data["processKey"] == "billing-dispute"
        assert event.data["processName"] == "Billing Dispute"
        assert event.data["currentStep"] == "step2"
        assert event.data["steps"] == steps
        assert event.data["slots"] == slots
        assert event.data["status"] == "active"

    @pytest.mark.asyncio
    async def test_publish_session_state_with_nulls(self, mock_supabase_client):
        """Test publish_session_state with null process info."""
        publisher = EventPublisher(client=mock_supabase_client)

        event = await publisher.publish_session_state(
            session_id="session-123",
            process_key=None,
            process_name=None,
            current_step=None,
            steps=[],
            slots={},
            status="pending",
        )

        assert event.data["processKey"] is None
        assert event.data["processName"] is None
        assert event.data["currentStep"] is None


class TestGetEventPublisher:
    """Tests for the get_event_publisher singleton function."""

    def test_get_event_publisher_returns_instance(self):
        """Test that get_event_publisher returns an EventPublisher instance."""
        # Clear any existing singleton
        import src.events.publisher as publisher_module

        publisher_module._publisher = None

        publisher = get_event_publisher()

        assert isinstance(publisher, EventPublisher)

    def test_get_event_publisher_singleton(self):
        """Test that get_event_publisher returns the same instance."""
        # Clear any existing singleton
        import src.events.publisher as publisher_module

        publisher_module._publisher = None

        publisher1 = get_event_publisher()
        publisher2 = get_event_publisher()

        assert publisher1 is publisher2

    def test_get_event_publisher_with_existing_singleton(self):
        """Test that get_event_publisher uses existing instance."""
        import src.events.publisher as publisher_module

        existing = EventPublisher()
        publisher_module._publisher = existing

        publisher = get_event_publisher()

        assert publisher is existing
