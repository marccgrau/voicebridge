"""Tests for SlotExtractionProcessor."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pipecat.frames.frames import TranscriptionFrame
from pipecat.processors.frame_processor import FrameDirection

from src.pipeline.processors.process_selection import ProcessSelectionFrame
from src.pipeline.processors.slot_extraction import (
    SlotExtractionFrame,
    SlotExtractionProcessor,
)


@pytest.fixture
def mock_anthropic_client():
    """Create a mock Anthropic client."""
    return MagicMock()


@pytest.fixture
def processor(mock_anthropic_client):
    """Create a SlotExtractionProcessor."""
    return SlotExtractionProcessor(
        session_id="test-session",
        anthropic_client=mock_anthropic_client,
    )


class TestSlotExtractionFrame:
    """Tests for SlotExtractionFrame."""

    def test_creates_frame_with_attributes(self):
        """Test that SlotExtractionFrame is created correctly."""
        frame = SlotExtractionFrame(
            intent="dispute_charge",
            slots=[{"key": "amount", "value": "$50.00"}],
            process_key="billing-dispute",
        )

        assert frame.intent == "dispute_charge"
        assert len(frame.slots) == 1
        assert frame.process_key == "billing-dispute"


class TestSlotExtractionProcessorInitialization:
    """Tests for SlotExtractionProcessor initialization."""

    def test_initializes_with_required_params(self, mock_anthropic_client):
        """Test processor initializes correctly."""
        processor = SlotExtractionProcessor(
            session_id="session-123",
            anthropic_client=mock_anthropic_client,
        )

        assert processor.session_id == "session-123"
        assert processor.anthropic is mock_anthropic_client
        assert processor.model == "claude-sonnet-4-20250514"
        assert processor._current_process is None
        assert processor._extracted_slots == {}
        assert processor._conversation_buffer == []
        assert processor._buffer_size == 3


class TestProcessTracking:
    """Tests for process selection tracking."""

    async def test_tracks_process_selection_frame(self, processor):
        """Test that ProcessSelectionFrame updates current process."""
        frame = ProcessSelectionFrame(
            process_key="billing-dispute",
            process_name="Billing Dispute",
            confidence=0.85,
            rationale="Test",
            candidates=[],
        )

        processor.push_frame = AsyncMock()

        await processor.process_frame(frame, FrameDirection.DOWNSTREAM)

        assert processor._current_process == "billing-dispute"
        processor.push_frame.assert_called_once()


class TestConversationBuffer:
    """Tests for conversation buffer management."""

    async def test_adds_transcription_to_buffer(self, processor):
        """Test that final transcriptions are added to buffer."""
        frame = MagicMock(spec=TranscriptionFrame)
        frame.text = "My order number is 12345"
        frame.is_final = True

        processor.push_frame = AsyncMock()
        processor._extract_slots = AsyncMock()

        await processor.process_frame(frame, FrameDirection.DOWNSTREAM)

        assert len(processor._conversation_buffer) == 1
        assert processor._conversation_buffer[0] == "My order number is 12345"

    async def test_maintains_buffer_size(self, processor):
        """Test that buffer maintains maximum size of 3."""
        processor.push_frame = AsyncMock()
        processor._extract_slots = AsyncMock()

        # Add 5 transcriptions
        for i in range(5):
            frame = MagicMock(spec=TranscriptionFrame)
            frame.text = f"Message {i}"
            frame.is_final = True
            await processor.process_frame(frame, FrameDirection.DOWNSTREAM)

        assert len(processor._conversation_buffer) == 3
        assert processor._conversation_buffer[0] == "Message 2"
        assert processor._conversation_buffer[-1] == "Message 4"


class TestSlotExtraction:
    """Tests for slot extraction logic."""

    @patch("src.pipeline.processors.slot_extraction.get_event_publisher")
    async def test_extracts_slots_from_conversation(
        self, mock_get_publisher, processor, mock_anthropic_client
    ):
        """Test slot extraction with LLM."""
        # Mock LLM response with JSON
        text_content = MagicMock()
        text_content.text = json.dumps({
            "intent": "check_order",
            "slots": [
                {"key": "order_number", "value": "12345", "confidence": 0.95}
            ]
        })
        response = MagicMock()
        response.content = [text_content]
        mock_anthropic_client.messages.create.return_value = response

        # Mock publisher
        mock_publisher = MagicMock()
        mock_publisher.publish_slot_extraction = AsyncMock()
        mock_get_publisher.return_value = mock_publisher

        processor.push_frame = AsyncMock()
        processor._conversation_buffer = ["My order number is 12345"]

        await processor._extract_slots()

        # Verify slot was extracted
        assert "order_number" in processor._extracted_slots
        assert processor._extracted_slots["order_number"] == "12345"

        # Verify event was published
        mock_publisher.publish_slot_extraction.assert_called_once()

        # Verify frame was pushed
        processor.push_frame.assert_called_once()
        pushed_frame = processor.push_frame.call_args[0][0]
        assert isinstance(pushed_frame, SlotExtractionFrame)
        assert pushed_frame.intent == "check_order"

    async def test_merges_slots_incrementally(self, processor, mock_anthropic_client):
        """Test that new slots are merged with existing slots."""
        # Set up existing slots
        processor._extracted_slots = {"order_number": "12345"}

        # Mock LLM response with new slot
        text_content = MagicMock()
        text_content.text = json.dumps({
            "intent": "check_order",
            "slots": [
                {"key": "email", "value": "test@example.com", "confidence": 0.9}
            ]
        })
        response = MagicMock()
        response.content = [text_content]
        mock_anthropic_client.messages.create.return_value = response

        processor.push_frame = AsyncMock()
        processor._conversation_buffer = ["My email is test@example.com"]

        # Mock publisher to avoid errors
        with patch("src.pipeline.processors.slot_extraction.get_event_publisher") as mock_get_pub:
            mock_publisher = MagicMock()
            mock_publisher.publish_slot_extraction = AsyncMock()
            mock_get_pub.return_value = mock_publisher

            await processor._extract_slots()

        # Both slots should exist
        assert "order_number" in processor._extracted_slots
        assert "email" in processor._extracted_slots
        assert processor._extracted_slots["order_number"] == "12345"
        assert processor._extracted_slots["email"] == "test@example.com"

    async def test_handles_invalid_json_response(self, processor, mock_anthropic_client):
        """Test graceful handling of invalid JSON."""
        # Mock LLM response with invalid JSON
        text_content = MagicMock()
        text_content.text = "This is not valid JSON"
        response = MagicMock()
        response.content = [text_content]
        mock_anthropic_client.messages.create.return_value = response

        processor._conversation_buffer = ["Test message"]

        # Should not raise exception
        await processor._extract_slots()

        # No slots should be extracted
        assert len(processor._extracted_slots) == 0

    async def test_handles_llm_errors(self, processor, mock_anthropic_client):
        """Test graceful handling of LLM errors."""
        mock_anthropic_client.messages.create.side_effect = Exception("LLM error")

        processor._conversation_buffer = ["Test message"]

        # Should not raise exception
        await processor._extract_slots()

        # No slots should be extracted
        assert len(processor._extracted_slots) == 0


class TestExtractWithLLM:
    """Tests for LLM extraction method."""

    async def test_parses_json_from_response(self, processor, mock_anthropic_client):
        """Test JSON parsing from LLM response."""
        text_content = MagicMock()
        text_content.text = 'Here is the data: {"intent": "test", "slots": []}'
        response = MagicMock()
        response.content = [text_content]
        mock_anthropic_client.messages.create.return_value = response

        result = await processor._extract_with_llm("Test context")

        assert result is not None
        assert result["intent"] == "test"
        assert result["slots"] == []

    async def test_includes_process_context(self, processor, mock_anthropic_client):
        """Test that current process is included in context."""
        processor._current_process = "billing-dispute"

        text_content = MagicMock()
        text_content.text = '{"intent": "test", "slots": []}'
        response = MagicMock()
        response.content = [text_content]
        mock_anthropic_client.messages.create.return_value = response

        await processor._extract_with_llm("Test conversation")

        # Verify process was included in prompt
        call_args = mock_anthropic_client.messages.create.call_args
        messages = call_args.kwargs["messages"]
        assert "billing-dispute" in messages[0]["content"]


class TestPublishExtraction:
    """Tests for event publishing."""

    @patch("src.pipeline.processors.slot_extraction.get_event_publisher")
    async def test_publishes_extraction_event(self, mock_get_publisher, processor):
        """Test that extraction event is published."""
        mock_publisher = MagicMock()
        mock_publisher.publish_slot_extraction = AsyncMock()
        mock_get_publisher.return_value = mock_publisher

        processor._current_process = "test-process"

        result = {
            "intent": "check_order",
            "slots": [{"key": "order_number", "value": "12345"}]
        }

        await processor._publish_extraction(result)

        mock_publisher.publish_slot_extraction.assert_called_once_with(
            session_id="test-session",
            intent="check_order",
            slots=[{"key": "order_number", "value": "12345"}],
            process_key="test-process",
        )

    @patch("src.pipeline.processors.slot_extraction.get_event_publisher")
    async def test_handles_publish_errors(self, mock_get_publisher, processor):
        """Test graceful handling of publish errors."""
        mock_publisher = MagicMock()
        mock_publisher.publish_slot_extraction = AsyncMock(
            side_effect=Exception("Publish error")
        )
        mock_get_publisher.return_value = mock_publisher

        result = {"intent": "test", "slots": []}

        # Should not raise
        await processor._publish_extraction(result)
