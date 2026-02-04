"""Tests for SuggestionComposer."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pipecat.processors.frame_processor import FrameDirection

from src.pipeline.processors.kb_lookup import KBSnippetFrame
from src.pipeline.processors.slot_extraction import SlotExtractionFrame
from src.pipeline.processors.suggestion_composer import (
    SuggestionComposer,
    SuggestionFrame,
)


@pytest.fixture
def mock_anthropic_client():
    """Create a mock Anthropic client."""
    return MagicMock()


@pytest.fixture
def processor(mock_anthropic_client):
    """Create a SuggestionComposer."""
    return SuggestionComposer(
        session_id="test-session",
        anthropic_client=mock_anthropic_client,
        enable_rewrite=False,  # Disable for most tests
    )


class TestSuggestionFrame:
    """Tests for SuggestionFrame."""

    def test_creates_frame_with_attributes(self):
        """Test frame creation."""
        frame = SuggestionFrame(
            suggestions=[{"text": "Hello"}],
            process_key="billing",
            step_key="verify",
        )

        assert len(frame.suggestions) == 1
        assert frame.process_key == "billing"


class TestSuggestionComposerInitialization:
    """Tests for initialization."""

    def test_initializes_with_params(self, mock_anthropic_client):
        """Test initialization."""
        processor = SuggestionComposer(
            session_id="session-123",
            anthropic_client=mock_anthropic_client,
            min_suggestions=2,
            max_suggestions=5,
        )

        assert processor.session_id == "session-123"
        assert processor.min_suggestions == 2
        assert processor.max_suggestions == 5


class TestFrameProcessing:
    """Tests for frame processing."""

    @patch("src.pipeline.processors.suggestion_composer.get_event_publisher")
    @patch("src.pipeline.processors.suggestion_composer.get_supabase_client")
    async def test_processes_kb_snippet_frame(
        self, mock_get_client, mock_get_publisher, processor
    ):
        """Test processing KBSnippetFrame."""
        # Mock DB and publisher
        mock_client = MagicMock()
        mock_table = MagicMock()
        mock_insert = MagicMock()
        mock_insert.execute.return_value = MagicMock()
        mock_table.insert.return_value = mock_insert
        mock_client.table.return_value = mock_table
        mock_get_client.return_value = mock_client

        mock_publisher = MagicMock()
        mock_publisher.publish_suggestions = AsyncMock()
        mock_get_publisher.return_value = mock_publisher

        frame = KBSnippetFrame(
            snippets=[{"id": "1", "template": "Hello {{name}}"}],
            process_key="billing",
            step_key="verify",
            intent_key=None,
        )

        processor.push_frame = AsyncMock()
        processor._slots = {"name": "John"}

        await processor.process_frame(frame, FrameDirection.DOWNSTREAM)

        assert processor._kb_snippets == frame.snippets
        assert processor._current_process == "billing"

    async def test_processes_slot_extraction_frame(self, processor):
        """Test processing SlotExtractionFrame."""
        frame = SlotExtractionFrame(
            intent="check_order",
            slots=[{"key": "order_number", "value": "12345"}],
            process_key="billing",
        )

        processor.push_frame = AsyncMock()
        processor._generate_suggestions = AsyncMock()

        await processor.process_frame(frame, FrameDirection.DOWNSTREAM)

        assert processor._slots["order_number"] == "12345"


class TestTemplateFilling:
    """Tests for template filling."""

    def test_fills_template_with_slots(self, processor):
        """Test template placeholder filling."""
        processor._slots = {
            "customer_name": "John Doe",
            "order_id": "ORD-123",
        }

        template = "Hello {{customer_name}}, your order {{order_id}} is ready."
        result = processor._fill_template(template)

        assert result == "Hello John Doe, your order ORD-123 is ready."

    def test_handles_missing_slots(self, processor):
        """Test unfilled placeholders remain."""
        processor._slots = {"name": "John"}

        template = "Hello {{name}}, your order {{order_id}} is ready."
        result = processor._fill_template(template)

        assert result == "Hello John, your order {{order_id}} is ready."


class TestSuggestionClassification:
    """Tests for suggestion type classification."""

    def test_classifies_question(self, processor):
        """Test question classification."""
        assert processor._classify_suggestion("What is your email?") == "question"
        assert processor._classify_suggestion("Can you confirm?") == "question"

    def test_classifies_escalation(self, processor):
        """Test escalation classification."""
        assert processor._classify_suggestion("Let me escalate this") == "escalation"
        assert processor._classify_suggestion("Transfer to supervisor") == "escalation"

    def test_classifies_action(self, processor):
        """Test action classification."""
        assert processor._classify_suggestion("Refund processed") == "action"
        assert processor._classify_suggestion("Completed successfully") == "action"

    def test_classifies_response(self, processor):
        """Test response classification."""
        assert processor._classify_suggestion("I understand your concern") == "response"


class TestSuggestionGeneration:
    """Tests for suggestion generation."""

    @patch("src.pipeline.processors.suggestion_composer.get_event_publisher")
    @patch("src.pipeline.processors.suggestion_composer.get_supabase_client")
    async def test_generates_suggestions_from_templates(
        self, mock_get_client, mock_get_publisher, processor
    ):
        """Test suggestion generation."""
        # Mock DB and publisher
        mock_client = MagicMock()
        mock_table = MagicMock()
        mock_insert = MagicMock()
        mock_insert.execute.return_value = MagicMock()
        mock_table.insert.return_value = mock_insert
        mock_client.table.return_value = mock_table
        mock_get_client.return_value = mock_client

        mock_publisher = MagicMock()
        mock_publisher.publish_suggestions = AsyncMock()
        mock_get_publisher.return_value = mock_publisher

        processor._kb_snippets = [
            {"id": "1", "template": "Hello {{name}}"},
            {"id": "2", "template": "Your order {{order_id}}"},
        ]
        processor._slots = {"name": "John", "order_id": "123"}
        processor.push_frame = AsyncMock()

        await processor._generate_suggestions()

        # Verify frame was pushed
        processor.push_frame.assert_called()
        pushed_frame = processor.push_frame.call_args[0][0]
        assert isinstance(pushed_frame, SuggestionFrame)
        # With 2 snippets and min_suggestions=3, fallback suggestions are added
        assert len(pushed_frame.suggestions) >= 2

    @patch("src.pipeline.processors.suggestion_composer.get_event_publisher")
    @patch("src.pipeline.processors.suggestion_composer.get_supabase_client")
    async def test_respects_max_suggestions(
        self, mock_get_client, mock_get_publisher, processor
    ):
        """Test max suggestions limit."""
        # Mock DB and publisher
        mock_client = MagicMock()
        mock_table = MagicMock()
        mock_insert = MagicMock()
        mock_insert.execute.return_value = MagicMock()
        mock_table.insert.return_value = mock_insert
        mock_client.table.return_value = mock_table
        mock_get_client.return_value = mock_client

        mock_publisher = MagicMock()
        mock_publisher.publish_suggestions = AsyncMock()
        mock_get_publisher.return_value = mock_publisher

        processor.max_suggestions = 3
        processor._kb_snippets = [
            {"id": str(i), "template": f"Suggestion {i}"} for i in range(10)
        ]
        processor.push_frame = AsyncMock()

        await processor._generate_suggestions()

        pushed_frame = processor.push_frame.call_args[0][0]
        assert len(pushed_frame.suggestions) <= 3

    @patch("src.pipeline.processors.suggestion_composer.get_event_publisher")
    @patch("src.pipeline.processors.suggestion_composer.get_supabase_client")
    async def test_adds_fallback_suggestions(
        self, mock_get_client, mock_get_publisher, processor
    ):
        """Test fallback suggestions when below minimum."""
        # Mock DB and publisher
        mock_client = MagicMock()
        mock_table = MagicMock()
        mock_insert = MagicMock()
        mock_insert.execute.return_value = MagicMock()
        mock_table.insert.return_value = mock_insert
        mock_client.table.return_value = mock_table
        mock_get_client.return_value = mock_client

        mock_publisher = MagicMock()
        mock_publisher.publish_suggestions = AsyncMock()
        mock_get_publisher.return_value = mock_publisher

        processor.min_suggestions = 3
        processor._kb_snippets = [{"id": "1", "template": "One suggestion"}]
        processor.push_frame = AsyncMock()

        await processor._generate_suggestions()

        pushed_frame = processor.push_frame.call_args[0][0]
        assert len(pushed_frame.suggestions) >= processor.min_suggestions


class TestLLMRewrite:
    """Tests for LLM rewriting."""

    async def test_rewrites_with_llm(self, mock_anthropic_client):
        """Test LLM rewriting."""
        processor = SuggestionComposer(
            session_id="test-session",
            anthropic_client=mock_anthropic_client,
            enable_rewrite=True,
        )

        text_content = MagicMock()
        text_content.text = "I can certainly help you with that"
        response = MagicMock()
        response.content = [text_content]
        mock_anthropic_client.messages.create.return_value = response

        result = await processor._rewrite_suggestion("I can help you")

        assert result == "I can certainly help you with that"

    async def test_handles_llm_errors(self, mock_anthropic_client):
        """Test error handling in rewrite."""
        processor = SuggestionComposer(
            session_id="test-session",
            anthropic_client=mock_anthropic_client,
            enable_rewrite=True,
        )

        mock_anthropic_client.messages.create.side_effect = Exception("LLM error")

        result = await processor._rewrite_suggestion("Original text")

        # Should return original on error
        assert result == "Original text"


class TestPersistence:
    """Tests for database persistence."""

    @patch("src.pipeline.processors.suggestion_composer.get_event_publisher")
    @patch("src.pipeline.processors.suggestion_composer.get_supabase_client")
    async def test_persists_to_database(
        self, mock_get_client, mock_get_publisher, processor
    ):
        """Test database persistence."""
        mock_client = MagicMock()
        mock_table = MagicMock()
        mock_insert = MagicMock()
        mock_insert.execute.return_value = MagicMock()
        mock_table.insert.return_value = mock_insert
        mock_client.table.return_value = mock_table
        mock_get_client.return_value = mock_client

        mock_publisher = MagicMock()
        mock_publisher.publish_suggestions = AsyncMock()
        mock_get_publisher.return_value = mock_publisher

        suggestions = [{"text": "Test"}]
        processor._current_process = "billing"

        await processor._persist_suggestions(suggestions)

        mock_table.insert.assert_called_once()
        insert_data = mock_table.insert.call_args[0][0]
        assert insert_data["session_id"] == "test-session"
        assert insert_data["suggestions_json"] == suggestions
