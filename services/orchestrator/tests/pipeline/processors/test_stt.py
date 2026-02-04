"""Tests for TranscriptWriter processor."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pipecat.frames.frames import TranscriptionFrame
from pipecat.processors.frame_processor import FrameDirection

from src.pipeline.processors.stt import TranscriptWriter


@pytest.fixture
def mock_transcription_frame():
    """Create a mock TranscriptionFrame."""
    frame = MagicMock(spec=TranscriptionFrame)
    frame.text = "Hello, I need help with my account"
    frame.is_final = True
    return frame


@pytest.fixture
def processor():
    """Create a TranscriptWriter processor."""
    return TranscriptWriter(session_id="test-session-123", speaker="customer")


class TestTranscriptWriterInitialization:
    """Tests for TranscriptWriter initialization."""

    def test_initializes_with_session_id(self):
        """Test processor initializes with session ID."""
        processor = TranscriptWriter(session_id="session-123")

        assert processor.session_id == "session-123"
        assert processor.speaker == "customer"  # Default
        assert processor._client is None  # Lazy initialization
        assert processor._publisher is None  # Lazy initialization

    def test_initializes_with_custom_speaker(self):
        """Test processor initializes with custom speaker."""
        processor = TranscriptWriter(session_id="session-123", speaker="agent")

        assert processor.speaker == "agent"

    @patch("src.pipeline.processors.stt.get_supabase_client")
    def test_lazy_client_initialization(self, mock_get_client):
        """Test that client is lazily initialized."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        processor = TranscriptWriter(session_id="session-123")

        # Client should not be created yet
        mock_get_client.assert_not_called()

        # Access client property
        client = processor.client

        # Now client should be created
        mock_get_client.assert_called_once()
        assert client is mock_client

        # Subsequent access should return same client
        client2 = processor.client
        assert client2 is mock_client
        mock_get_client.assert_called_once()  # Still only one call

    @patch("src.pipeline.processors.stt.get_event_publisher")
    def test_lazy_publisher_initialization(self, mock_get_publisher):
        """Test that publisher is lazily initialized."""
        mock_pub = MagicMock()
        mock_get_publisher.return_value = mock_pub

        processor = TranscriptWriter(session_id="session-123")

        # Publisher should not be created yet
        mock_get_publisher.assert_not_called()

        # Access publisher property
        publisher = processor.publisher

        # Now publisher should be created
        mock_get_publisher.assert_called_once()
        assert publisher is mock_pub


class TestTranscriptWriterProcessFrame:
    """Tests for process_frame method."""

    @patch("src.pipeline.processors.stt.get_supabase_client")
    @patch("src.pipeline.processors.stt.get_event_publisher")
    async def test_handles_transcription_frame(
        self, mock_get_publisher, mock_get_client, mock_transcription_frame
    ):
        """Test that TranscriptionFrame is handled."""
        mock_client = MagicMock()
        mock_table = MagicMock()
        mock_insert = MagicMock()
        mock_insert.execute.return_value = MagicMock()
        mock_table.insert.return_value = mock_insert
        mock_client.table.return_value = mock_table
        mock_get_client.return_value = mock_client

        mock_publisher = MagicMock()
        mock_publisher.publish_transcript_segment = AsyncMock()
        mock_get_publisher.return_value = mock_publisher

        processor = TranscriptWriter(session_id="test-session")

        # Process the frame
        await processor.process_frame(mock_transcription_frame, FrameDirection.DOWNSTREAM)

        # Verify database insert was called (final transcript)
        mock_client.table.assert_called_with("transcript_segments")
        mock_table.insert.assert_called_once()
        insert_data = mock_table.insert.call_args[0][0]
        assert insert_data["session_id"] == "test-session"
        assert insert_data["speaker"] == "customer"
        assert insert_data["text"] == "Hello, I need help with my account"
        assert insert_data["is_final"] is True

        # Verify event was published
        mock_publisher.publish_transcript_segment.assert_called_once_with(
            session_id="test-session",
            speaker="customer",
            text="Hello, I need help with my account",
            is_final=True,
        )

    @patch("src.pipeline.processors.stt.get_supabase_client")
    @patch("src.pipeline.processors.stt.get_event_publisher")
    async def test_persists_only_final_transcripts(
        self, mock_get_publisher, mock_get_client
    ):
        """Test that only final transcripts are persisted to database."""
        mock_client = MagicMock()
        mock_table = MagicMock()
        mock_insert = MagicMock()
        mock_insert.execute.return_value = MagicMock()
        mock_table.insert.return_value = mock_insert
        mock_client.table.return_value = mock_table
        mock_get_client.return_value = mock_client

        mock_publisher = MagicMock()
        mock_publisher.publish_transcript_segment = AsyncMock()
        mock_get_publisher.return_value = mock_publisher

        processor = TranscriptWriter(session_id="test-session")

        # Create interim frame
        interim_frame = MagicMock(spec=TranscriptionFrame)
        interim_frame.text = "Hello"
        interim_frame.is_final = False

        await processor.process_frame(interim_frame, FrameDirection.DOWNSTREAM)

        # Database insert should NOT be called for interim
        mock_table.insert.assert_not_called()

        # But event should still be published
        mock_publisher.publish_transcript_segment.assert_called_once_with(
            session_id="test-session",
            speaker="customer",
            text="Hello",
            is_final=False,
        )

    @patch("src.pipeline.processors.stt.get_supabase_client")
    @patch("src.pipeline.processors.stt.get_event_publisher")
    async def test_publishes_all_transcripts(
        self, mock_get_publisher, mock_get_client
    ):
        """Test that both final and interim transcripts are published."""
        mock_client = MagicMock()
        mock_table = MagicMock()
        mock_insert = MagicMock()
        mock_insert.execute.return_value = MagicMock()
        mock_table.insert.return_value = mock_insert
        mock_client.table.return_value = mock_table
        mock_get_client.return_value = mock_client

        mock_publisher = MagicMock()
        mock_publisher.publish_transcript_segment = AsyncMock()
        mock_get_publisher.return_value = mock_publisher

        processor = TranscriptWriter(session_id="test-session")

        # Process interim frame
        interim_frame = MagicMock(spec=TranscriptionFrame)
        interim_frame.text = "Hello"
        interim_frame.is_final = False
        await processor.process_frame(interim_frame, FrameDirection.DOWNSTREAM)

        # Process final frame
        final_frame = MagicMock(spec=TranscriptionFrame)
        final_frame.text = "Hello, how are you?"
        final_frame.is_final = True
        await processor.process_frame(final_frame, FrameDirection.DOWNSTREAM)

        # Both should be published
        assert mock_publisher.publish_transcript_segment.call_count == 2

    @patch("src.pipeline.processors.stt.get_event_publisher")
    async def test_skips_empty_text(self, mock_get_publisher):
        """Test that empty text is skipped."""
        mock_publisher = MagicMock()
        mock_publisher.publish_transcript_segment = AsyncMock()
        mock_get_publisher.return_value = mock_publisher

        processor = TranscriptWriter(session_id="test-session")

        # Create frame with empty text
        empty_frame = MagicMock(spec=TranscriptionFrame)
        empty_frame.text = "   "  # Whitespace only
        empty_frame.is_final = True

        await processor.process_frame(empty_frame, FrameDirection.DOWNSTREAM)

        # Nothing should be published
        mock_publisher.publish_transcript_segment.assert_not_called()

    @patch("src.pipeline.processors.stt.get_supabase_client")
    @patch("src.pipeline.processors.stt.get_event_publisher")
    async def test_handles_db_error_gracefully(
        self, mock_get_publisher, mock_get_client, mock_transcription_frame
    ):
        """Test that database errors are caught and logged."""
        # Mock database error
        mock_client = MagicMock()
        mock_table = MagicMock()
        mock_insert = MagicMock()
        mock_insert.execute.side_effect = Exception("Database error")
        mock_table.insert.return_value = mock_insert
        mock_client.table.return_value = mock_table
        mock_get_client.return_value = mock_client

        mock_publisher = MagicMock()
        mock_publisher.publish_transcript_segment = AsyncMock()
        mock_get_publisher.return_value = mock_publisher

        processor = TranscriptWriter(session_id="test-session")

        # Should not raise exception
        await processor.process_frame(mock_transcription_frame, FrameDirection.DOWNSTREAM)

        # Event should still be published despite DB error
        mock_publisher.publish_transcript_segment.assert_called_once()

    @patch("src.pipeline.processors.stt.get_supabase_client")
    @patch("src.pipeline.processors.stt.get_event_publisher")
    async def test_handles_publish_error_gracefully(
        self, mock_get_publisher, mock_get_client, mock_transcription_frame
    ):
        """Test that publish errors are caught and logged."""
        mock_client = MagicMock()
        mock_table = MagicMock()
        mock_insert = MagicMock()
        mock_insert.execute.return_value = MagicMock()
        mock_table.insert.return_value = mock_insert
        mock_client.table.return_value = mock_table
        mock_get_client.return_value = mock_client

        # Mock publish error
        mock_publisher = MagicMock()
        mock_publisher.publish_transcript_segment = AsyncMock(
            side_effect=Exception("Publish error")
        )
        mock_get_publisher.return_value = mock_publisher

        processor = TranscriptWriter(session_id="test-session")

        # Should not raise exception
        await processor.process_frame(mock_transcription_frame, FrameDirection.DOWNSTREAM)

        # Database insert should still have been attempted
        mock_client.table.assert_called()

    @patch("src.pipeline.processors.stt.get_event_publisher")
    async def test_handles_frame_without_is_final_attribute(self, mock_get_publisher):
        """Test handling frame that doesn't have is_final attribute."""
        mock_publisher = MagicMock()
        mock_publisher.publish_transcript_segment = AsyncMock()
        mock_get_publisher.return_value = mock_publisher

        processor = TranscriptWriter(session_id="test-session")

        # Create frame without is_final
        frame = MagicMock(spec=TranscriptionFrame)
        frame.text = "Test text"
        delattr(frame, "is_final")  # Remove is_final attribute

        await processor.process_frame(frame, FrameDirection.DOWNSTREAM)

        # Should default to True and publish
        mock_publisher.publish_transcript_segment.assert_called_once_with(
            session_id="test-session",
            speaker="customer",
            text="Test text",
            is_final=True,
        )

    @patch("src.pipeline.processors.stt.get_supabase_client")
    @patch("src.pipeline.processors.stt.get_event_publisher")
    async def test_trims_whitespace(self, mock_get_publisher, mock_get_client):
        """Test that text is trimmed before processing."""
        mock_client = MagicMock()
        mock_table = MagicMock()
        mock_insert = MagicMock()
        mock_insert.execute.return_value = MagicMock()
        mock_table.insert.return_value = mock_insert
        mock_client.table.return_value = mock_table
        mock_get_client.return_value = mock_client

        mock_publisher = MagicMock()
        mock_publisher.publish_transcript_segment = AsyncMock()
        mock_get_publisher.return_value = mock_publisher

        processor = TranscriptWriter(session_id="test-session")

        # Create frame with whitespace
        frame = MagicMock(spec=TranscriptionFrame)
        frame.text = "  Hello, world!  \n"
        frame.is_final = True

        await processor.process_frame(frame, FrameDirection.DOWNSTREAM)

        # Verify trimmed text
        mock_publisher.publish_transcript_segment.assert_called_once_with(
            session_id="test-session",
            speaker="customer",
            text="Hello, world!",
            is_final=True,
        )

    async def test_passes_through_non_transcription_frames(self):
        """Test that non-TranscriptionFrame frames are passed through."""
        processor = TranscriptWriter(session_id="test-session")

        # Create a non-TranscriptionFrame
        other_frame = MagicMock()
        other_frame.__class__.__name__ = "OtherFrame"

        # Mock push_frame to verify it's called
        processor.push_frame = AsyncMock()

        await processor.process_frame(other_frame, FrameDirection.DOWNSTREAM)

        # Frame should be pushed downstream
        processor.push_frame.assert_called_once_with(
            other_frame, FrameDirection.DOWNSTREAM
        )

    @patch("src.pipeline.processors.stt.get_supabase_client")
    @patch("src.pipeline.processors.stt.get_event_publisher")
    async def test_uses_correct_timestamp(
        self, mock_get_publisher, mock_get_client, mock_transcription_frame
    ):
        """Test that timestamp is generated correctly."""
        from datetime import datetime

        mock_client = MagicMock()
        mock_table = MagicMock()
        mock_insert = MagicMock()
        mock_insert.execute.return_value = MagicMock()
        mock_table.insert.return_value = mock_insert
        mock_client.table.return_value = mock_table
        mock_get_client.return_value = mock_client

        mock_publisher = MagicMock()
        mock_publisher.publish_transcript_segment = AsyncMock()
        mock_get_publisher.return_value = mock_publisher

        processor = TranscriptWriter(session_id="test-session")

        await processor.process_frame(mock_transcription_frame, FrameDirection.DOWNSTREAM)

        # Verify timestamp format
        insert_data = mock_table.insert.call_args[0][0]
        assert "ts" in insert_data
        # Verify it's ISO format
        datetime.fromisoformat(insert_data["ts"].replace("Z", "+00:00"))
