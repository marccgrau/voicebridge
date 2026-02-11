"""Tests for pipeline processors."""

from unittest.mock import MagicMock, patch

import pytest
from pipecat.frames.frames import InterimTranscriptionFrame, TranscriptionFrame
from pipecat.processors.frame_processor import FrameDirection

from src.pipeline.processors import TranscriptWriter


@pytest.fixture
def mock_supabase():
    """Mock Supabase client."""
    with patch("src.pipeline.processors.get_supabase_client") as mock_get_client:
        mock_client = MagicMock()
        mock_table = MagicMock()
        mock_insert = MagicMock()
        mock_execute = MagicMock()

        mock_client.table.return_value = mock_table
        mock_table.insert.return_value = mock_insert
        mock_insert.execute.return_value = mock_execute

        mock_get_client.return_value = mock_client
        yield mock_client


@pytest.mark.asyncio
class TestTranscriptWriter:
    """Test TranscriptWriter processor."""

    async def test_speaker_mapping_first_customer(self, mock_supabase):
        """Test that first speaker is mapped to customer by default."""
        writer = TranscriptWriter(session_id="test-session")

        # Create frame with Speechmatics speaker ID "S1"
        frame = TranscriptionFrame(
            text="Hello, I need help",
            user_id="S1",
            timestamp="2024-01-01T00:00:00Z",
            finalized=True,
        )

        # Process frame
        await writer.process_frame(frame, FrameDirection.DOWNSTREAM)
        await writer.flush_writes()

        # Verify speaker was resolved to "customer"
        assert frame.user_id == "customer"

        # Verify database insert was called with correct speaker
        mock_supabase.table.assert_called_with("transcript_segments")
        insert_call = mock_supabase.table().insert.call_args[0][0]
        assert insert_call["speaker"] == "customer"
        assert insert_call["text"] == "Hello, I need help"
        assert insert_call["session_id"] == "test-session"

    async def test_speaker_mapping_second_agent(self, mock_supabase):
        """Test that second speaker is mapped to agent."""
        writer = TranscriptWriter(session_id="test-session")

        # First speaker (customer)
        frame1 = TranscriptionFrame(
            text="Hello", user_id="S1", timestamp="2024-01-01T00:00:00Z", finalized=True
        )
        await writer.process_frame(frame1, FrameDirection.DOWNSTREAM)

        # Second speaker (agent)
        frame2 = TranscriptionFrame(
            text="Hi, how can I help?",
            user_id="S2",
            timestamp="2024-01-01T00:00:01Z",
            finalized=True,
        )
        await writer.process_frame(frame2, FrameDirection.DOWNSTREAM)
        await writer.flush_writes()

        # Verify second speaker was mapped to "agent"
        assert frame2.user_id == "agent"

        # Verify database insert for second speaker
        insert_calls = mock_supabase.table().insert.call_args_list
        assert len(insert_calls) == 2
        assert insert_calls[1][0][0]["speaker"] == "agent"
        assert insert_calls[1][0][0]["text"] == "Hi, how can I help?"

    async def test_speaker_mapping_first_agent_config(self, mock_supabase):
        """Test configuring first speaker as agent."""
        writer = TranscriptWriter(session_id="test-session", first_speaker_role="agent")

        # First speaker should be agent
        frame1 = TranscriptionFrame(
            text="Hello", user_id="S1", timestamp="2024-01-01T00:00:00Z", finalized=True
        )
        await writer.process_frame(frame1, FrameDirection.DOWNSTREAM)

        # Second speaker should be customer
        frame2 = TranscriptionFrame(
            text="Hi", user_id="S2", timestamp="2024-01-01T00:00:01Z", finalized=True
        )
        await writer.process_frame(frame2, FrameDirection.DOWNSTREAM)
        await writer.flush_writes()

        # Verify mapping
        assert frame1.user_id == "agent"
        assert frame2.user_id == "customer"

        insert_calls = mock_supabase.table().insert.call_args_list
        assert insert_calls[0][0][0]["speaker"] == "agent"
        assert insert_calls[1][0][0]["speaker"] == "customer"

    async def test_speaker_mapping_consistent(self, mock_supabase):
        """Test that speaker mapping is consistent across multiple utterances."""
        writer = TranscriptWriter(session_id="test-session")

        # Multiple frames from same speakers
        frames = [
            ("S1", "First customer message"),
            ("S2", "Agent response"),
            ("S1", "Second customer message"),
            ("S2", "Second agent response"),
        ]

        for speaker_id, text in frames:
            frame = TranscriptionFrame(
                text=text, user_id=speaker_id, timestamp="2024-01-01T00:00:00Z", finalized=True
            )
            await writer.process_frame(frame, FrameDirection.DOWNSTREAM)
        await writer.flush_writes()

        # Verify mapping remained consistent
        insert_calls = mock_supabase.table().insert.call_args_list
        assert insert_calls[0][0][0]["speaker"] == "customer"
        assert insert_calls[1][0][0]["speaker"] == "agent"
        assert insert_calls[2][0][0]["speaker"] == "customer"
        assert insert_calls[3][0][0]["speaker"] == "agent"

    async def test_interim_frames_ignored(self, mock_supabase):
        """Test that interim (partial) frames are not written to database."""
        writer = TranscriptWriter(session_id="test-session")

        # Interim frame (partials use InterimTranscriptionFrame, not TranscriptionFrame)
        frame = InterimTranscriptionFrame(
            text="Partial...", user_id="S1", timestamp="2024-01-01T00:00:00Z"
        )

        await writer.process_frame(frame, FrameDirection.DOWNSTREAM)
        await writer.flush_writes()

        # Verify no database insert
        mock_supabase.table.assert_not_called()

    async def test_missing_user_id_handled(self, mock_supabase):
        """Test that frames with empty user_id are handled gracefully."""
        writer = TranscriptWriter(session_id="test-session")

        # Frame with empty user_id
        frame = TranscriptionFrame(
            text="Hello", user_id="", timestamp="2024-01-01T00:00:00Z", finalized=True
        )

        await writer.process_frame(frame, FrameDirection.DOWNSTREAM)
        await writer.flush_writes()

        # Verify speaker was resolved to "customer" (first speaker = unknown)
        insert_call = mock_supabase.table().insert.call_args[0][0]
        assert insert_call["speaker"] == "customer"
