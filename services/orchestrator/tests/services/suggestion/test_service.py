"""Tests for SuggestionService domain logic."""

from src.frames import ProcessIllustrationFrame
from src.services.suggestion.service import SuggestionService


class TestSuggestionService:
    """SuggestionService behavior tests."""

    def test_process_context_update(self):
        service = SuggestionService()
        state = service.initial_state()

        service.update_process_context(
            state,
            ProcessIllustrationFrame(
                process_key="billing",
                process_name="Billing",
                steps=[{"key": "s1", "label": "Verify", "status": "pending"}],
                current_step=0,
                content="content",
            ),
        )

        assert state["process_context"]["process_key"] == "billing"
        assert state["process_context"]["process_name"] == "Billing"

    def test_customer_turn_filter_and_stale_detection(self):
        service = SuggestionService()

        assert service.should_generate_for_speaker("customer") is True
        assert service.should_generate_for_speaker("agent") is False
        assert service.is_stale_turn(turn_id=1, latest_turn_id=2) is True
        assert service.is_stale_turn(turn_id=2, latest_turn_id=2) is False

    def test_build_suggestion_frame(self):
        service = SuggestionService()
        frame = service.build_suggestion_frame(
            suggestions=[
                {"text": "A", "type": "response"},
                {"text": "B", "type": "question"},
                {"text": "C", "type": "action"},
            ],
            process_context={"process_key": "billing"},
            latency_ms=12.3,
        )

        assert frame.service_type == "suggestion_flow"
        assert frame.process_key == "billing"
        assert frame.latency_ms == 12.3
        assert len(frame.suggestions) == 3

    def test_create_suggesting_node_uses_last_window_utterances(self):
        service = SuggestionService(conversation_window_size=3)

        node = service.create_suggesting_node(
            conversation_buffer=[
                "[customer]: turn_1",
                "[agent]: turn_2",
                "[customer]: turn_3",
                "[agent]: turn_4",
                "[customer]: turn_5",
            ],
            process_context=None,
            publish_suggestions_fn=object(),
        )

        prompt = node["task_messages"][0]["content"]
        assert "Conversation (last 3 utterances):" in prompt
        assert "turn_1" not in prompt
        assert "turn_2" not in prompt
        assert "turn_3" in prompt
        assert "turn_4" in prompt
        assert "turn_5" in prompt
