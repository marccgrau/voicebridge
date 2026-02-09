"""Tests for SummaryService."""

from unittest.mock import MagicMock, patch

import anthropic
import pytest

from src.llm.summary_service import SummaryService, TranscriptSegment


class TestSummaryService:
    """Tests for SummaryService class."""

    def test_initialization_with_api_key(self):
        """Test service initialization with explicit API key."""
        service = SummaryService(api_key="test-key", model="claude-haiku-4-5-20251001")
        assert service.api_key == "test-key"
        assert service.model == "claude-haiku-4-5-20251001"

    @patch("src.llm.summary_service.settings")
    def test_initialization_from_settings(self, mock_settings):
        """Test service initialization from settings."""
        mock_settings.anthropic_api_key = "settings-key"
        service = SummaryService()
        assert service.api_key == "settings-key"
        assert service.model == "claude-haiku-4-5-20251001"

    @patch("src.llm.summary_service.settings")
    def test_initialization_fails_without_api_key(self, mock_settings):
        """Test service initialization fails without API key."""
        mock_settings.anthropic_api_key = None
        with pytest.raises(ValueError, match="ANTHROPIC_API_KEY is required"):
            SummaryService()

    @patch("src.llm.summary_service.anthropic.Anthropic")
    def test_generate_summary_success(self, mock_anthropic_class):
        """Test successful summary generation."""
        # Mock the Anthropic client
        mock_client = MagicMock()
        mock_message = MagicMock()
        mock_text_block = MagicMock()
        mock_text_block.text = "The customer reported a billing issue. The agent helped resolve it."
        mock_message.content = [mock_text_block]
        mock_client.messages.create.return_value = mock_message
        mock_anthropic_class.return_value = mock_client

        service = SummaryService(api_key="test-key")

        segments: list[TranscriptSegment] = [
            {
                "speaker": "customer",
                "text": "I have a billing problem",
                "ts": "2024-01-01T00:00:00Z",
            },
            {"speaker": "agent", "text": "Let me help you with that", "ts": "2024-01-01T00:00:05Z"},
        ]

        result = service.generate_summary(segments)

        assert result == "The customer reported a billing issue. The agent helped resolve it."
        mock_client.messages.create.assert_called_once()

        # Verify the prompt includes the transcript
        call_args = mock_client.messages.create.call_args
        assert call_args.kwargs["model"] == "claude-haiku-4-5-20251001"
        assert call_args.kwargs["max_tokens"] == 512
        content = call_args.kwargs["messages"][0]["content"]
        assert "[CUSTOMER] I have a billing problem" in content
        assert "[AGENT] Let me help you with that" in content

    @patch("src.llm.summary_service.anthropic.Anthropic")
    def test_generate_summary_with_custom_max_tokens(self, mock_anthropic_class):
        """Test summary generation with custom max_tokens."""
        mock_client = MagicMock()
        mock_message = MagicMock()
        mock_text_block = MagicMock()
        mock_text_block.text = "Summary text"
        mock_message.content = [mock_text_block]
        mock_client.messages.create.return_value = mock_message
        mock_anthropic_class.return_value = mock_client

        service = SummaryService(api_key="test-key")
        segments: list[TranscriptSegment] = [
            {"speaker": "customer", "text": "Hello", "ts": "2024-01-01T00:00:00Z"},
        ]

        service.generate_summary(segments, max_tokens=1024)

        call_args = mock_client.messages.create.call_args
        assert call_args.kwargs["max_tokens"] == 1024

    def test_generate_summary_fails_with_empty_segments(self):
        """Test that generate_summary raises error with empty segments."""
        service = SummaryService(api_key="test-key")

        with pytest.raises(ValueError, match="Cannot generate summary from empty transcript"):
            service.generate_summary([])

    @patch("src.llm.summary_service.anthropic.Anthropic")
    def test_generate_summary_api_error(self, mock_anthropic_class):
        """Test that API errors are propagated."""
        mock_client = MagicMock()
        # Create a proper APIError with required request argument
        mock_request = MagicMock()
        mock_client.messages.create.side_effect = anthropic.APIError(
            "API Error", request=mock_request, body=None
        )
        mock_anthropic_class.return_value = mock_client

        service = SummaryService(api_key="test-key")
        segments: list[TranscriptSegment] = [
            {"speaker": "customer", "text": "Hello", "ts": "2024-01-01T00:00:00Z"},
        ]

        with pytest.raises(anthropic.APIError):
            service.generate_summary(segments)

    @patch("src.llm.summary_service.anthropic.Anthropic")
    def test_generate_summary_strips_whitespace(self, mock_anthropic_class):
        """Test that summary text is stripped of leading/trailing whitespace."""
        mock_client = MagicMock()
        mock_message = MagicMock()
        mock_text_block = MagicMock()
        mock_text_block.text = "  \n  Summary with whitespace  \n  "
        mock_message.content = [mock_text_block]
        mock_client.messages.create.return_value = mock_message
        mock_anthropic_class.return_value = mock_client

        service = SummaryService(api_key="test-key")
        segments: list[TranscriptSegment] = [
            {"speaker": "customer", "text": "Hello", "ts": "2024-01-01T00:00:00Z"},
        ]

        result = service.generate_summary(segments)
        assert result == "Summary with whitespace"
