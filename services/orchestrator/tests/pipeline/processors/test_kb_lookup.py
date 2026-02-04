"""Tests for KBLookupProcessor."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pipecat.processors.frame_processor import FrameDirection

from src.pipeline.processors.kb_lookup import KBLookupProcessor, KBSnippetFrame
from src.pipeline.processors.process_selection import ProcessSelectionFrame
from src.pipeline.processors.slot_extraction import SlotExtractionFrame


@pytest.fixture
def processor():
    """Create a KBLookupProcessor."""
    return KBLookupProcessor(session_id="test-session")


class TestKBSnippetFrame:
    """Tests for KBSnippetFrame."""

    def test_creates_frame_with_attributes(self):
        """Test frame creation."""
        frame = KBSnippetFrame(
            snippets=[{"id": "1", "template": "Hello {{name}}"}],
            process_key="billing",
            step_key="verify",
            intent_key="check_order",
        )

        assert len(frame.snippets) == 1
        assert frame.process_key == "billing"


class TestKBLookupProcessorInitialization:
    """Tests for KBLookupProcessor initialization."""

    def test_initializes_with_session_id(self):
        """Test initialization."""
        processor = KBLookupProcessor(session_id="session-123")

        assert processor.session_id == "session-123"
        assert processor._current_process is None
        assert processor._current_step is None


class TestProcessTracking:
    """Tests for process tracking."""

    @patch("src.pipeline.processors.kb_lookup.get_supabase_client")
    async def test_tracks_process_selection(self, mock_get_client, processor):
        """Test ProcessSelectionFrame tracking."""
        # Mock DB response
        mock_client = MagicMock()
        mock_table = MagicMock()
        mock_select = MagicMock()
        mock_select.eq.return_value = mock_select
        mock_select.or_.return_value = mock_select
        mock_select.order.return_value = mock_select
        mock_select.limit.return_value = mock_select
        mock_select.execute.return_value = MagicMock(data=[
            {"id": "1", "template": "Test", "priority": 1}
        ])
        mock_table.select.return_value = mock_select
        mock_client.table.return_value = mock_table
        mock_get_client.return_value = mock_client

        frame = ProcessSelectionFrame(
            process_key="billing",
            process_name="Billing",
            confidence=0.8,
            rationale="Test",
            candidates=[],
        )

        processor.push_frame = AsyncMock()

        await processor.process_frame(frame, FrameDirection.DOWNSTREAM)

        assert processor._current_process == "billing"
        # Should trigger lookup and push KB frame
        assert processor.push_frame.call_count >= 1

    async def test_tracks_slot_extraction_intent(self, processor):
        """Test SlotExtractionFrame tracking."""
        frame = SlotExtractionFrame(
            intent="check_order",
            slots=[],
            process_key="billing",
        )

        processor._current_process = "billing"  # Must have process
        processor.push_frame = AsyncMock()
        processor._lookup_and_push = AsyncMock()

        await processor.process_frame(frame, FrameDirection.DOWNSTREAM)

        assert processor._current_intent == "check_order"


class TestKBLookup:
    """Tests for KB snippet lookup."""

    @patch("src.pipeline.processors.kb_lookup.get_supabase_client")
    async def test_queries_kb_snippets(self, mock_get_client, processor):
        """Test KB snippet query."""
        mock_client = MagicMock()
        mock_table = MagicMock()
        mock_select = MagicMock()
        mock_select.eq.return_value = mock_select
        mock_select.or_.return_value = mock_select
        mock_select.order.return_value = mock_select
        mock_select.limit.return_value = mock_select
        mock_select.execute.return_value = MagicMock(data=[
            {
                "id": "snippet-1",
                "template": "Hello {{customer_name}}",
                "step_key": None,
                "intent_key": None,
                "constraints": {},
                "priority": 10,
            }
        ])
        mock_table.select.return_value = mock_select
        mock_client.table.return_value = mock_table
        mock_get_client.return_value = mock_client

        processor._current_process = "billing"

        snippets = await processor._lookup_snippets()

        assert len(snippets) == 1
        assert snippets[0]["id"] == "snippet-1"
        assert snippets[0]["template"] == "Hello {{customer_name}}"

    @patch("src.pipeline.processors.kb_lookup.get_supabase_client")
    async def test_orders_by_priority(self, mock_get_client, processor):
        """Test snippets ordered by priority."""
        mock_client = MagicMock()
        mock_table = MagicMock()
        mock_select = MagicMock()
        mock_select.eq.return_value = mock_select
        mock_select.or_.return_value = mock_select
        mock_select.order.return_value = mock_select
        mock_select.limit.return_value = mock_select
        mock_select.execute.return_value = MagicMock(data=[])
        mock_table.select.return_value = mock_select
        mock_client.table.return_value = mock_table
        mock_get_client.return_value = mock_client

        processor._current_process = "billing"
        await processor._lookup_snippets()

        # Verify order was called with priority desc
        mock_select.order.assert_called_with("priority", desc=True)

    @patch("src.pipeline.processors.kb_lookup.get_supabase_client")
    async def test_handles_db_errors(self, mock_get_client, processor):
        """Test graceful error handling."""
        mock_client = MagicMock()
        mock_table = MagicMock()
        mock_select = MagicMock()
        mock_select.eq.return_value = mock_select
        mock_select.or_.return_value = mock_select
        mock_select.order.return_value = mock_select
        mock_select.limit.return_value = mock_select
        mock_select.execute.side_effect = Exception("DB error")
        mock_table.select.return_value = mock_select
        mock_client.table.return_value = mock_table
        mock_get_client.return_value = mock_client

        processor._current_process = "billing"
        processor.push_frame = AsyncMock()

        # Should not raise
        await processor._lookup_and_push()


class TestSetCurrentStep:
    """Tests for set_current_step method."""

    def test_sets_current_step(self, processor):
        """Test setting current step."""
        processor.set_current_step("verify_identity")

        assert processor._current_step == "verify_identity"
