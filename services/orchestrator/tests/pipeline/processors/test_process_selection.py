"""Tests for ProcessSelectionProcessor."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pipecat.frames.frames import TranscriptionFrame
from pipecat.processors.frame_processor import FrameDirection

from src.pipeline.processors.process_selection import (
    ProcessSelectionFrame,
    ProcessSelectionProcessor,
)


@pytest.fixture
def mock_anthropic_client():
    """Create a mock Anthropic client."""
    client = MagicMock()
    return client


@pytest.fixture
def processor(mock_anthropic_client):
    """Create a ProcessSelectionProcessor."""
    return ProcessSelectionProcessor(
        session_id="test-session",
        anthropic_client=mock_anthropic_client,
        confidence_threshold=0.6,
    )


class TestProcessSelectionFrame:
    """Tests for ProcessSelectionFrame."""

    def test_creates_frame_with_attributes(self):
        """Test that ProcessSelectionFrame is created with correct attributes."""
        frame = ProcessSelectionFrame(
            process_key="billing-dispute",
            process_name="Billing Dispute Resolution",
            confidence=0.85,
            rationale="Customer mentioned billing issue",
            candidates=[{"processKey": "billing-dispute", "score": 0.85}],
        )

        assert frame.process_key == "billing-dispute"
        assert frame.process_name == "Billing Dispute Resolution"
        assert frame.confidence == 0.85
        assert frame.rationale == "Customer mentioned billing issue"
        assert len(frame.candidates) == 1


class TestProcessSelectionProcessorInitialization:
    """Tests for ProcessSelectionProcessor initialization."""

    def test_initializes_with_required_params(self, mock_anthropic_client):
        """Test processor initializes with required parameters."""
        processor = ProcessSelectionProcessor(
            session_id="session-123",
            anthropic_client=mock_anthropic_client,
        )

        assert processor.session_id == "session-123"
        assert processor.anthropic is mock_anthropic_client
        assert processor.model == "claude-sonnet-4-20250514"
        assert processor.confidence_threshold == 0.6
        assert processor._current_process is None
        assert processor._conversation_buffer == []
        assert processor._buffer_size == 5

    def test_initializes_with_custom_params(self, mock_anthropic_client):
        """Test processor initializes with custom parameters."""
        processor = ProcessSelectionProcessor(
            session_id="session-123",
            anthropic_client=mock_anthropic_client,
            model="claude-opus-4",
            confidence_threshold=0.7,
        )

        assert processor.model == "claude-opus-4"
        assert processor.confidence_threshold == 0.7

    @patch("src.pipeline.processors.process_selection.get_supabase_client")
    def test_lazy_client_initialization(self, mock_get_client, mock_anthropic_client):
        """Test that client is lazily initialized."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        processor = ProcessSelectionProcessor(
            session_id="session-123",
            anthropic_client=mock_anthropic_client,
        )

        mock_get_client.assert_not_called()

        client = processor.client

        mock_get_client.assert_called_once()
        assert client is mock_client


class TestConversationBuffer:
    """Tests for conversation buffer management."""

    async def test_adds_transcription_to_buffer(self, processor):
        """Test that final transcriptions are added to buffer."""
        frame = MagicMock(spec=TranscriptionFrame)
        frame.text = "I need help with billing"
        frame.is_final = True

        processor.push_frame = AsyncMock()
        processor._maybe_select_process = AsyncMock()

        await processor.process_frame(frame, FrameDirection.DOWNSTREAM)

        assert len(processor._conversation_buffer) == 1
        assert processor._conversation_buffer[0] == "I need help with billing"

    async def test_maintains_buffer_size(self, processor):
        """Test that buffer maintains maximum size."""
        processor.push_frame = AsyncMock()
        processor._maybe_select_process = AsyncMock()

        # Add 7 transcriptions (buffer size is 5)
        for i in range(7):
            frame = MagicMock(spec=TranscriptionFrame)
            frame.text = f"Message {i}"
            frame.is_final = True
            await processor.process_frame(frame, FrameDirection.DOWNSTREAM)

        assert len(processor._conversation_buffer) == 5
        assert processor._conversation_buffer[0] == "Message 2"  # Oldest kept
        assert processor._conversation_buffer[-1] == "Message 6"  # Newest

    async def test_skips_interim_transcriptions(self, processor):
        """Test that interim transcriptions are not added to buffer."""
        frame = MagicMock(spec=TranscriptionFrame)
        frame.text = "Hello"
        frame.is_final = False

        processor.push_frame = AsyncMock()
        processor._maybe_select_process = AsyncMock()

        await processor.process_frame(frame, FrameDirection.DOWNSTREAM)

        assert len(processor._conversation_buffer) == 0

    async def test_skips_empty_text(self, processor):
        """Test that empty text is not added to buffer."""
        frame = MagicMock(spec=TranscriptionFrame)
        frame.text = "   "
        frame.is_final = True

        processor.push_frame = AsyncMock()
        processor._maybe_select_process = AsyncMock()

        await processor.process_frame(frame, FrameDirection.DOWNSTREAM)

        assert len(processor._conversation_buffer) == 0


class TestProcessSelection:
    """Tests for process selection logic."""

    @patch("src.pipeline.processors.process_selection.get_supabase_client")
    @patch("src.pipeline.processors.process_selection.get_event_publisher")
    async def test_selects_process_with_tool_use(
        self, mock_get_publisher, mock_get_client, processor, mock_anthropic_client
    ):
        """Test process selection using LLM with tool use."""
        # Mock tool use response
        tool_content = MagicMock()
        tool_content.type = "tool_use"
        tool_content.name = "process_lookup"
        tool_content.id = "tool-123"
        tool_content.input = {"query": "billing issue"}

        tool_response = MagicMock()
        tool_response.content = [tool_content]

        # Mock final response
        text_content = MagicMock()
        text_content.text = "Selected billing-dispute with high confidence"
        final_response = MagicMock()
        final_response.content = [text_content]

        mock_anthropic_client.messages.create.side_effect = [
            tool_response,
            final_response,
        ]

        # Mock process lookup
        mock_lookup_result = MagicMock()
        mock_lookup_result.results = [
            MagicMock(
                process_key="billing-dispute",
                name="Billing Dispute",
                domain="billing",
                score=0.85,
            )
        ]
        processor._lookup_skill.search = MagicMock(return_value=mock_lookup_result)
        processor._lookup_skill.format_for_llm = MagicMock(return_value="Formatted results")

        # Mock DB and publisher
        mock_client = MagicMock()
        mock_table = MagicMock()
        mock_insert = MagicMock()
        mock_insert.execute.return_value = MagicMock()
        mock_table.insert.return_value = mock_insert
        mock_update = MagicMock()
        mock_update.eq.return_value = mock_update
        mock_update.execute.return_value = MagicMock()
        mock_table.update.return_value = mock_update
        mock_client.table.return_value = mock_table
        mock_get_client.return_value = mock_client

        mock_publisher = MagicMock()
        mock_publisher.publish_process_selection = AsyncMock()
        mock_get_publisher.return_value = mock_publisher

        processor.push_frame = AsyncMock()

        # Add conversation and trigger selection
        processor._conversation_buffer = ["I have a billing issue"]
        await processor._maybe_select_process()

        # Verify tool was called
        processor._lookup_skill.search.assert_called_once_with(
            query="billing issue",
            domain=None,
        )

        # Verify LLM was called twice (tool use + final)
        assert mock_anthropic_client.messages.create.call_count == 2

        # Verify process was selected
        assert processor._current_process == "billing-dispute"

        # Verify ProcessSelectionFrame was pushed
        processor.push_frame.assert_called_once()
        pushed_frame = processor.push_frame.call_args[0][0]
        assert isinstance(pushed_frame, ProcessSelectionFrame)
        assert pushed_frame.process_key == "billing-dispute"

    async def test_only_updates_on_process_change(self, processor):
        """Test that selection only updates when process changes."""
        processor._current_process = "billing-dispute"
        processor._conversation_buffer = ["Still talking about billing"]
        processor._persist_and_publish = AsyncMock()

        # Mock selection to return same process
        processor._select_process_with_llm = AsyncMock(
            return_value={
                "process_key": "billing-dispute",
                "process_name": "Billing Dispute",
                "confidence": 0.9,
                "rationale": "Same process",
                "candidates": [],
            }
        )

        await processor._maybe_select_process()

        # Should not persist/publish since process didn't change
        processor._persist_and_publish.assert_not_called()

    async def test_applies_confidence_threshold(self, processor):
        """Test that confidence threshold filters selections."""
        processor.confidence_threshold = 0.7
        processor._conversation_buffer = ["Some vague question"]
        processor._persist_and_publish = AsyncMock()

        # Mock low confidence result
        processor._select_process_with_llm = AsyncMock(
            return_value={
                "process_key": "some-process",
                "process_name": "Some Process",
                "confidence": 0.5,  # Below threshold
                "rationale": "Not sure",
                "candidates": [],
            }
        )

        await processor._maybe_select_process()

        # Should not update due to low confidence
        processor._persist_and_publish.assert_not_called()
        assert processor._current_process is None

    async def test_handles_llm_errors(self, processor):
        """Test graceful handling of LLM errors."""
        processor._conversation_buffer = ["Test message"]
        processor._select_process_with_llm = AsyncMock(
            side_effect=Exception("LLM error")
        )

        # Should not raise exception
        await processor._maybe_select_process()

        # Process should remain unset
        assert processor._current_process is None


class TestPersistAndPublish:
    """Tests for persistence and publishing."""

    @patch("src.pipeline.processors.process_selection.get_supabase_client")
    @patch("src.pipeline.processors.process_selection.get_event_publisher")
    async def test_persists_to_database(
        self, mock_get_publisher, mock_get_client, processor
    ):
        """Test that selection is persisted to database."""
        mock_client = MagicMock()
        mock_table = MagicMock()
        mock_insert = MagicMock()
        mock_insert.execute.return_value = MagicMock()
        mock_table.insert.return_value = mock_insert
        mock_table.update.return_value = MagicMock(
            eq=lambda _: MagicMock(execute=lambda: MagicMock())
        )
        mock_client.table.return_value = mock_table
        mock_get_client.return_value = mock_client

        mock_publisher = MagicMock()
        mock_publisher.publish_process_selection = AsyncMock()
        mock_get_publisher.return_value = mock_publisher

        result = {
            "process_key": "billing-dispute",
            "process_name": "Billing Dispute",
            "confidence": 0.85,
            "rationale": "Customer has billing issue",
            "candidates": [{"processKey": "billing-dispute"}],
        }

        await processor._persist_and_publish(result, "I have a billing issue")

        # Verify process_selection_events insert
        assert mock_table.insert.called
        insert_data = mock_table.insert.call_args[0][0]
        assert insert_data["session_id"] == "test-session"
        assert insert_data["process_key"] == "billing-dispute"
        assert insert_data["confidence"] == 0.85

    @patch("src.pipeline.processors.process_selection.get_supabase_client")
    @patch("src.pipeline.processors.process_selection.get_event_publisher")
    async def test_updates_session(self, mock_get_publisher, mock_get_client, processor):
        """Test that session is updated with process_key."""
        mock_client = MagicMock()
        mock_table = MagicMock()
        mock_insert = MagicMock()
        mock_insert.execute.return_value = MagicMock()
        mock_table.insert.return_value = mock_insert
        mock_update = MagicMock()
        mock_update.eq.return_value = mock_update
        mock_update.execute.return_value = MagicMock()
        mock_table.update.return_value = mock_update
        mock_client.table.return_value = mock_table
        mock_get_client.return_value = mock_client

        mock_publisher = MagicMock()
        mock_publisher.publish_process_selection = AsyncMock()
        mock_get_publisher.return_value = mock_publisher

        result = {
            "process_key": "account-support",
            "process_name": "Account Support",
            "confidence": 0.9,
            "rationale": "Account issue",
            "candidates": [],
        }

        await processor._persist_and_publish(result, "Account problem")

        # Verify sessions update
        mock_table.update.assert_called()
        update_data = mock_table.update.call_args[0][0]
        assert update_data["process_key"] == "account-support"

    @patch("src.pipeline.processors.process_selection.get_supabase_client")
    @patch("src.pipeline.processors.process_selection.get_event_publisher")
    async def test_publishes_event(self, mock_get_publisher, mock_get_client, processor):
        """Test that event is published."""
        mock_client = MagicMock()
        mock_table = MagicMock()
        mock_insert = MagicMock()
        mock_insert.execute.return_value = MagicMock()
        mock_table.insert.return_value = mock_insert
        mock_table.update.return_value = MagicMock(
            eq=lambda _: MagicMock(execute=lambda: MagicMock())
        )
        mock_client.table.return_value = mock_table
        mock_get_client.return_value = mock_client

        mock_publisher = MagicMock()
        mock_publisher.publish_process_selection = AsyncMock()
        mock_get_publisher.return_value = mock_publisher

        result = {
            "process_key": "refund-request",
            "process_name": "Refund Request",
            "confidence": 0.75,
            "rationale": "Customer wants refund",
            "candidates": [],
        }

        await processor._persist_and_publish(result, "I want a refund")

        # Verify event published
        mock_publisher.publish_process_selection.assert_called_once_with(
            session_id="test-session",
            process_key="refund-request",
            process_name="Refund Request",
            confidence=0.75,
            rationale="Customer wants refund",
            candidates=[],
        )

    @patch("src.pipeline.processors.process_selection.get_supabase_client")
    @patch("src.pipeline.processors.process_selection.get_event_publisher")
    async def test_handles_db_errors_gracefully(
        self, mock_get_publisher, mock_get_client, processor
    ):
        """Test that database errors don't crash the processor."""
        mock_client = MagicMock()
        mock_table = MagicMock()
        mock_insert = MagicMock()
        mock_insert.execute.side_effect = Exception("DB error")
        mock_table.insert.return_value = mock_insert
        mock_table.update.return_value = MagicMock(
            eq=lambda _: MagicMock(execute=MagicMock(side_effect=Exception("DB error")))
        )
        mock_client.table.return_value = mock_table
        mock_get_client.return_value = mock_client

        mock_publisher = MagicMock()
        mock_publisher.publish_process_selection = AsyncMock()
        mock_get_publisher.return_value = mock_publisher

        result = {
            "process_key": "test",
            "process_name": "Test",
            "confidence": 0.8,
            "rationale": "Test",
            "candidates": [],
        }

        # Should not raise
        await processor._persist_and_publish(result, "Test")

        # Event should still be published
        mock_publisher.publish_process_selection.assert_called_once()


class TestParseSelectionResponse:
    """Tests for parsing LLM responses."""

    def test_parses_response_with_candidates(self, processor):
        """Test parsing response with candidates."""
        text_content = MagicMock()
        text_content.text = "The billing-dispute process is most relevant with high confidence."
        response = MagicMock()
        response.content = [text_content]

        candidates = [
            {
                "processKey": "billing-dispute",
                "name": "Billing Dispute",
                "domain": "billing",
                "score": 0.85,
            }
        ]

        result = processor._parse_selection_response(response, candidates)

        assert result is not None
        assert result["process_key"] == "billing-dispute"
        assert result["process_name"] == "Billing Dispute"
        assert result["confidence"] == 0.9  # High confidence detected
        assert "billing-dispute" in result["rationale"]

    def test_returns_none_without_candidates(self, processor):
        """Test that None is returned when no candidates."""
        text_content = MagicMock()
        text_content.text = "No relevant process found"
        response = MagicMock()
        response.content = [text_content]

        result = processor._parse_selection_response(response, [])

        assert result is None

    def test_detects_low_confidence(self, processor):
        """Test detection of low confidence in text."""
        text_content = MagicMock()
        text_content.text = "I have low confidence in this selection"
        response = MagicMock()
        response.content = [text_content]

        candidates = [{"processKey": "test", "name": "Test", "score": 0.5}]

        result = processor._parse_selection_response(response, candidates)

        assert result["confidence"] == 0.4  # Low confidence
