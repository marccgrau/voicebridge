"""Tests for VoiceBridgePipeline."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.pipeline.pipeline import VoiceBridgePipeline


@pytest.fixture
def mock_anthropic_client():
    """Create a mock Anthropic client."""
    return MagicMock()


@pytest.fixture
def pipeline(mock_anthropic_client):
    """Create a VoiceBridgePipeline."""
    return VoiceBridgePipeline(
        session_id="test-session",
        room_url="https://test.daily.co/room",
        room_token="test-token",
        anthropic_client=mock_anthropic_client,
    )


class TestVoiceBridgePipelineInitialization:
    """Tests for pipeline initialization."""

    def test_initializes_with_required_params(self, mock_anthropic_client):
        """Test pipeline initialization."""
        pipeline = VoiceBridgePipeline(
            session_id="session-123",
            room_url="https://daily.co/room",
            room_token="token-abc",
            anthropic_client=mock_anthropic_client,
        )

        assert pipeline.session_id == "session-123"
        assert pipeline.room_url == "https://daily.co/room"
        assert pipeline.room_token == "token-abc"
        assert pipeline.anthropic is mock_anthropic_client
        assert pipeline._pipeline is None
        assert pipeline._task is None
        assert pipeline._runner is None

    def test_is_running_false_when_not_started(self, pipeline):
        """Test is_running when pipeline not started."""
        assert pipeline.is_running is False


class TestPipelineStart:
    """Tests for pipeline start method."""

    @patch("src.pipeline.pipeline.PipelineRunner")
    @patch("src.pipeline.pipeline.PipelineTask")
    @patch("src.pipeline.pipeline.Pipeline")
    @patch("src.pipeline.pipeline.SuggestionComposer")
    @patch("src.pipeline.pipeline.KBLookupProcessor")
    @patch("src.pipeline.pipeline.SlotExtractionProcessor")
    @patch("src.pipeline.pipeline.ProcessSelectionProcessor")
    @patch("src.pipeline.pipeline.TranscriptWriter")
    @patch("src.pipeline.pipeline.DeepgramSTTService")
    @patch("src.pipeline.pipeline.DailyTransport")
    @patch("src.pipeline.pipeline.SileroVADAnalyzer")
    async def test_configures_vad_with_params(
        self,
        mock_vad,
        mock_transport,
        mock_stt,
        mock_transcript,
        mock_process,
        mock_slot,
        mock_kb,
        mock_suggestion,
        mock_pipeline_class,
        mock_task_class,
        mock_runner_class,
        pipeline,
    ):
        """Test VAD configuration."""
        # Mock all components
        mock_transport_instance = MagicMock()
        mock_transport_instance.input.return_value = MagicMock()
        mock_transport.return_value = mock_transport_instance

        mock_runner = MagicMock()
        mock_runner.run = AsyncMock()
        mock_runner_class.return_value = mock_runner

        await pipeline.start()

        # Verify VAD was initialized
        mock_vad.assert_called_once()
        vad_params = mock_vad.call_args.kwargs["params"]
        assert vad_params.start_secs == 0.2
        assert vad_params.stop_secs == 0.8

    @patch("src.pipeline.pipeline.PipelineRunner")
    @patch("src.pipeline.pipeline.PipelineTask")
    @patch("src.pipeline.pipeline.Pipeline")
    @patch("src.pipeline.pipeline.SuggestionComposer")
    @patch("src.pipeline.pipeline.KBLookupProcessor")
    @patch("src.pipeline.pipeline.SlotExtractionProcessor")
    @patch("src.pipeline.pipeline.ProcessSelectionProcessor")
    @patch("src.pipeline.pipeline.TranscriptWriter")
    @patch("src.pipeline.pipeline.DeepgramSTTService")
    @patch("src.pipeline.pipeline.DailyTransport")
    @patch("src.pipeline.pipeline.SileroVADAnalyzer")
    async def test_configures_daily_transport(
        self,
        mock_vad,
        mock_transport,
        mock_stt,
        mock_transcript,
        mock_process,
        mock_slot,
        mock_kb,
        mock_suggestion,
        mock_pipeline_class,
        mock_task_class,
        mock_runner_class,
        pipeline,
    ):
        """Test Daily transport configuration."""
        mock_transport_instance = MagicMock()
        mock_transport_instance.input.return_value = MagicMock()
        mock_transport.return_value = mock_transport_instance

        mock_runner = MagicMock()
        mock_runner.run = AsyncMock()
        mock_runner_class.return_value = mock_runner

        await pipeline.start()

        # Verify transport was configured
        mock_transport.assert_called_once()
        call_kwargs = mock_transport.call_args.kwargs
        assert call_kwargs["room_url"] == "https://test.daily.co/room"
        assert call_kwargs["token"] == "test-token"
        assert call_kwargs["bot_name"] == "VoiceBridge"

        # Verify audio params
        params = call_kwargs["params"]
        assert params.audio_in_enabled is True
        assert params.audio_out_enabled is False  # Listen only
        assert params.vad_enabled is True

    @patch("src.pipeline.pipeline.PipelineRunner")
    @patch("src.pipeline.pipeline.PipelineTask")
    @patch("src.pipeline.pipeline.Pipeline")
    @patch("src.pipeline.pipeline.SuggestionComposer")
    @patch("src.pipeline.pipeline.KBLookupProcessor")
    @patch("src.pipeline.pipeline.SlotExtractionProcessor")
    @patch("src.pipeline.pipeline.ProcessSelectionProcessor")
    @patch("src.pipeline.pipeline.TranscriptWriter")
    @patch("src.pipeline.pipeline.DeepgramSTTService")
    @patch("src.pipeline.pipeline.DailyTransport")
    @patch("src.pipeline.pipeline.SileroVADAnalyzer")
    @patch("src.pipeline.pipeline.settings")
    async def test_configures_deepgram_stt(
        self,
        mock_settings,
        mock_vad,
        mock_transport,
        mock_stt,
        mock_transcript,
        mock_process,
        mock_slot,
        mock_kb,
        mock_suggestion,
        mock_pipeline_class,
        mock_task_class,
        mock_runner_class,
        pipeline,
    ):
        """Test Deepgram STT configuration."""
        mock_settings.deepgram_api_key = "dg-key"
        mock_settings.stt_language = "en"

        mock_transport_instance = MagicMock()
        mock_transport_instance.input.return_value = MagicMock()
        mock_transport.return_value = mock_transport_instance

        mock_runner = MagicMock()
        mock_runner.run = AsyncMock()
        mock_runner_class.return_value = mock_runner

        await pipeline.start()

        # Verify STT was configured
        mock_stt.assert_called_once_with(
            api_key="dg-key",
            language="en",
        )

    @patch("src.pipeline.pipeline.PipelineRunner")
    @patch("src.pipeline.pipeline.PipelineTask")
    @patch("src.pipeline.pipeline.Pipeline")
    @patch("src.pipeline.pipeline.SuggestionComposer")
    @patch("src.pipeline.pipeline.KBLookupProcessor")
    @patch("src.pipeline.pipeline.SlotExtractionProcessor")
    @patch("src.pipeline.pipeline.ProcessSelectionProcessor")
    @patch("src.pipeline.pipeline.TranscriptWriter")
    @patch("src.pipeline.pipeline.DeepgramSTTService")
    @patch("src.pipeline.pipeline.DailyTransport")
    @patch("src.pipeline.pipeline.SileroVADAnalyzer")
    async def test_initializes_all_processors(
        self,
        mock_vad,
        mock_transport,
        mock_stt,
        mock_transcript,
        mock_process,
        mock_slot,
        mock_kb,
        mock_suggestion,
        mock_pipeline_class,
        mock_task_class,
        mock_runner_class,
        pipeline,
    ):
        """Test all processors are initialized."""
        mock_transport_instance = MagicMock()
        mock_transport_instance.input.return_value = MagicMock()
        mock_transport.return_value = mock_transport_instance

        mock_runner = MagicMock()
        mock_runner.run = AsyncMock()
        mock_runner_class.return_value = mock_runner

        await pipeline.start()

        # Verify all processors were created
        mock_transcript.assert_called_once_with(
            session_id="test-session",
            speaker="customer",
        )
        mock_process.assert_called_once()
        mock_slot.assert_called_once()
        mock_kb.assert_called_once_with(session_id="test-session")
        mock_suggestion.assert_called_once()

    @patch("src.pipeline.pipeline.PipelineRunner")
    @patch("src.pipeline.pipeline.PipelineTask")
    @patch("src.pipeline.pipeline.Pipeline")
    @patch("src.pipeline.pipeline.SuggestionComposer")
    @patch("src.pipeline.pipeline.KBLookupProcessor")
    @patch("src.pipeline.pipeline.SlotExtractionProcessor")
    @patch("src.pipeline.pipeline.ProcessSelectionProcessor")
    @patch("src.pipeline.pipeline.TranscriptWriter")
    @patch("src.pipeline.pipeline.DeepgramSTTService")
    @patch("src.pipeline.pipeline.DailyTransport")
    @patch("src.pipeline.pipeline.SileroVADAnalyzer")
    async def test_builds_pipeline_with_correct_order(
        self,
        mock_vad,
        mock_transport,
        mock_stt,
        mock_transcript,
        mock_process,
        mock_slot,
        mock_kb,
        mock_suggestion,
        mock_pipeline_class,
        mock_task_class,
        mock_runner_class,
        pipeline,
    ):
        """Test pipeline is built with processors in correct order."""
        mock_transport_instance = MagicMock()
        mock_transport_instance.input.return_value = MagicMock()
        mock_transport.return_value = mock_transport_instance

        mock_runner = MagicMock()
        mock_runner.run = AsyncMock()
        mock_runner_class.return_value = mock_runner

        await pipeline.start()

        # Verify Pipeline was created with processors
        mock_pipeline_class.assert_called_once()
        processors = mock_pipeline_class.call_args[0][0]
        assert len(processors) == 7  # transport, stt, 5 processors

    @patch("src.pipeline.pipeline.PipelineRunner")
    @patch("src.pipeline.pipeline.PipelineTask")
    @patch("src.pipeline.pipeline.Pipeline")
    @patch("src.pipeline.pipeline.SuggestionComposer")
    @patch("src.pipeline.pipeline.KBLookupProcessor")
    @patch("src.pipeline.pipeline.SlotExtractionProcessor")
    @patch("src.pipeline.pipeline.ProcessSelectionProcessor")
    @patch("src.pipeline.pipeline.TranscriptWriter")
    @patch("src.pipeline.pipeline.DeepgramSTTService")
    @patch("src.pipeline.pipeline.DailyTransport")
    @patch("src.pipeline.pipeline.SileroVADAnalyzer")
    async def test_creates_pipeline_task(
        self,
        mock_vad,
        mock_transport,
        mock_stt,
        mock_transcript,
        mock_process,
        mock_slot,
        mock_kb,
        mock_suggestion,
        mock_pipeline_class,
        mock_task_class,
        mock_runner_class,
        pipeline,
    ):
        """Test PipelineTask is created correctly."""
        mock_transport_instance = MagicMock()
        mock_transport_instance.input.return_value = MagicMock()
        mock_transport.return_value = mock_transport_instance

        mock_runner = MagicMock()
        mock_runner.run = AsyncMock()
        mock_runner_class.return_value = mock_runner

        await pipeline.start()

        # Verify task was created
        mock_task_class.assert_called_once()
        task_params = mock_task_class.call_args.kwargs["params"]
        assert task_params.allow_interruptions is False
        assert task_params.enable_metrics is True

    @patch("src.pipeline.pipeline.PipelineRunner")
    @patch("src.pipeline.pipeline.PipelineTask")
    @patch("src.pipeline.pipeline.Pipeline")
    @patch("src.pipeline.pipeline.SuggestionComposer")
    @patch("src.pipeline.pipeline.KBLookupProcessor")
    @patch("src.pipeline.pipeline.SlotExtractionProcessor")
    @patch("src.pipeline.pipeline.ProcessSelectionProcessor")
    @patch("src.pipeline.pipeline.TranscriptWriter")
    @patch("src.pipeline.pipeline.DeepgramSTTService")
    @patch("src.pipeline.pipeline.DailyTransport")
    @patch("src.pipeline.pipeline.SileroVADAnalyzer")
    async def test_runs_pipeline(
        self,
        mock_vad,
        mock_transport,
        mock_stt,
        mock_transcript,
        mock_process,
        mock_slot,
        mock_kb,
        mock_suggestion,
        mock_pipeline_class,
        mock_task_class,
        mock_runner_class,
        pipeline,
    ):
        """Test pipeline runner is started."""
        mock_transport_instance = MagicMock()
        mock_transport_instance.input.return_value = MagicMock()
        mock_transport.return_value = mock_transport_instance

        mock_runner = MagicMock()
        mock_runner.run = AsyncMock()
        mock_runner_class.return_value = mock_runner

        await pipeline.start()

        # Verify runner was created and run
        mock_runner_class.assert_called_once()
        mock_runner.run.assert_called_once()


class TestPipelineStop:
    """Tests for pipeline stop method."""

    async def test_cancels_task(self, pipeline):
        """Test that task is cancelled on stop."""
        mock_task = MagicMock()
        mock_task.cancel = AsyncMock()
        pipeline._task = mock_task

        await pipeline.stop()

        mock_task.cancel.assert_called_once()

    async def test_stops_runner(self, pipeline):
        """Test that runner is stopped."""
        mock_runner = MagicMock()
        mock_runner.stop = AsyncMock()
        pipeline._runner = mock_runner

        await pipeline.stop()

        mock_runner.stop.assert_called_once()

    async def test_handles_none_task(self, pipeline):
        """Test graceful handling when task is None."""
        pipeline._task = None
        pipeline._runner = None

        # Should not raise
        await pipeline.stop()

    async def test_stops_both_task_and_runner(self, pipeline):
        """Test both task and runner are stopped."""
        mock_task = MagicMock()
        mock_task.cancel = AsyncMock()
        mock_runner = MagicMock()
        mock_runner.stop = AsyncMock()

        pipeline._task = mock_task
        pipeline._runner = mock_runner

        await pipeline.stop()

        mock_task.cancel.assert_called_once()
        mock_runner.stop.assert_called_once()


class TestIsRunning:
    """Tests for is_running property."""

    def test_returns_false_when_task_is_none(self, pipeline):
        """Test is_running when task is None."""
        pipeline._task = None

        assert pipeline.is_running is False

    def test_returns_false_when_task_is_cancelled(self, pipeline):
        """Test is_running when task is cancelled."""
        mock_task = MagicMock()
        mock_task.cancelled.return_value = True
        pipeline._task = mock_task

        assert pipeline.is_running is False

    def test_returns_true_when_task_is_running(self, pipeline):
        """Test is_running when task is active."""
        mock_task = MagicMock()
        mock_task.cancelled.return_value = False
        pipeline._task = mock_task

        assert pipeline.is_running is True
