"""Shared pytest fixtures for orchestrator tests."""

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest


@pytest.fixture
def mock_supabase_client():
    """Create a mock Supabase client with table/RPC operations.

    This fixture provides a fully mocked Supabase client that can be used
    across all tests. It includes mocks for:
    - table() operations (insert, select, update, delete)
    - rpc() operations
    - channel() operations for Realtime
    """
    client = MagicMock()

    # Mock table operations
    mock_table = MagicMock()
    mock_table.insert.return_value = mock_table
    mock_table.select.return_value = mock_table
    mock_table.update.return_value = mock_table
    mock_table.delete.return_value = mock_table
    mock_table.eq.return_value = mock_table
    mock_table.single.return_value = mock_table
    mock_table.execute.return_value = MagicMock(data=None, error=None)

    client.table.return_value = mock_table

    # Mock RPC operations
    mock_rpc = MagicMock()
    mock_rpc.execute.return_value = MagicMock(data=[], error=None)
    client.rpc.return_value = mock_rpc

    # Mock channel operations for Realtime
    mock_channel = MagicMock()
    mock_channel.subscribe = AsyncMock()
    mock_channel.send_broadcast = AsyncMock()
    mock_channel.unsubscribe = AsyncMock()
    client.channel.return_value = mock_channel

    return client


@pytest.fixture
def mock_anthropic_client():
    """Create a mock Anthropic client for LLM calls.

    This fixture provides a mock for the Anthropic client with message
    creation support. By default, returns a simple text response, but
    can be configured in tests to return tool_use responses or other
    content types.
    """
    client = MagicMock()

    # Default response: simple text message
    mock_response = MagicMock()
    mock_text_block = MagicMock()
    mock_text_block.type = "text"
    mock_text_block.text = '{"result": "test"}'
    mock_response.content = [mock_text_block]
    mock_response.stop_reason = "end_turn"

    client.messages.create.return_value = mock_response

    return client


@pytest.fixture
def mock_event_publisher():
    """Create a mock EventPublisher with async methods.

    This fixture provides a mock EventPublisher that can be used to verify
    that events are being published correctly without actually sending them
    to Supabase Realtime.
    """
    publisher = MagicMock()

    # Make all publish methods async
    publisher.publish = AsyncMock()
    publisher.publish_transcript_segment = AsyncMock()
    publisher.publish_process_selection = AsyncMock()
    publisher.publish_slot_extraction = AsyncMock()
    publisher.publish_suggestions = AsyncMock()
    publisher.publish_session_state = AsyncMock()

    # Have publish methods return a mock event
    async def create_mock_event(*args, **kwargs):
        return MagicMock(
            event_id=str(uuid4()),
            session_id=kwargs.get("session_id", "test-session"),
            timestamp=datetime.now(UTC).isoformat(),
            type=args[1] if len(args) > 1 else "test",
            data={},
        )

    publisher.publish.side_effect = create_mock_event
    publisher.publish_transcript_segment.side_effect = create_mock_event
    publisher.publish_process_selection.side_effect = create_mock_event
    publisher.publish_slot_extraction.side_effect = create_mock_event
    publisher.publish_suggestions.side_effect = create_mock_event
    publisher.publish_session_state.side_effect = create_mock_event

    return publisher


@pytest.fixture
def sample_session_data() -> dict[str, Any]:
    """Create sample session data for testing.

    Returns a dictionary with typical session data that can be used
    in tests. Can be customized by updating the returned dict.
    """
    return {
        "id": str(uuid4()),
        "process_key": None,
        "state": {
            "slots": {},
            "steps": [],
        },
        "status": "active",
        "created_at": datetime.now(UTC).isoformat(),
        "updated_at": datetime.now(UTC).isoformat(),
    }


@pytest.fixture
def sample_process_data() -> dict[str, Any]:
    """Create sample process data for testing.

    Returns a dictionary with typical process catalog data that can be
    used in tests. Includes all fields from the process_catalog table.
    """
    return {
        "process_key": "test-process",
        "name": "Test Process",
        "domain": "test",
        "version": "1.0.0",
        "locale": "en",
        "queue_tags": ["test-queue"],
        "description": "A test process for unit testing",
        "steps_json": [
            {"key": "step1", "label": "First Step"},
            {"key": "step2", "label": "Second Step"},
        ],
        "slots_json": [
            {
                "key": "customer_name",
                "label": "Customer Name",
                "type": "string",
                "required": True,
            }
        ],
        "process_text": "Test process description with steps and slots",
        "embedding": None,  # Not needed for most tests
        "created_at": datetime.now(UTC).isoformat(),
        "updated_at": datetime.now(UTC).isoformat(),
    }


@pytest.fixture
def sample_transcript_segment() -> dict[str, Any]:
    """Create sample transcript segment data for testing."""
    return {
        "id": str(uuid4()),
        "session_id": str(uuid4()),
        "speaker": "customer",
        "text": "Hello, I need help with my account",
        "is_final": True,
        "confidence": 0.95,
        "timestamp": datetime.now(UTC).isoformat(),
    }


@pytest.fixture
def sample_process_selection_event() -> dict[str, Any]:
    """Create sample process selection event data for testing."""
    return {
        "eventId": str(uuid4()),
        "sessionId": str(uuid4()),
        "timestamp": datetime.now(UTC).isoformat(),
        "type": "process_selection",
        "processKey": "test-process",
        "processName": "Test Process",
        "confidence": 0.85,
        "rationale": "Customer mentioned account issues",
        "candidates": [
            {
                "process_key": "test-process",
                "name": "Test Process",
                "score": 0.85,
            }
        ],
    }


@pytest.fixture
def sample_slot_extraction_event() -> dict[str, Any]:
    """Create sample slot extraction event data for testing."""
    return {
        "eventId": str(uuid4()),
        "sessionId": str(uuid4()),
        "timestamp": datetime.now(UTC).isoformat(),
        "type": "slot_extraction",
        "intent": "account_inquiry",
        "slots": [
            {
                "key": "customer_name",
                "value": "John Doe",
                "confidence": 0.9,
            }
        ],
        "processKey": "test-process",
    }


@pytest.fixture
def sample_suggestion_data() -> dict[str, Any]:
    """Create sample suggestion data for testing."""
    return {
        "id": str(uuid4()),
        "session_id": str(uuid4()),
        "process_key": "test-process",
        "step_key": "step1",
        "suggestion_type": "response",
        "suggestion_text": "Hello John, I can help you with your account.",
        "priority": 1,
        "source": "kb_template",
        "metadata": {},
        "created_at": datetime.now(UTC).isoformat(),
    }
