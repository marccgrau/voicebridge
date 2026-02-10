"""Tests for ProcessService domain logic."""

from unittest.mock import MagicMock

from src.services.process.service import ProcessDefinition, ProcessService, ProcessStep


class TestProcessService:
    """ProcessService behavior tests."""

    def test_handle_transcription_switches_to_detecting_after_min_utterances(self):
        service = ProcessService(min_utterances_before_detection=3)
        state = service.initial_state(
            {
                "billing": ProcessDefinition(
                    process_key="billing",
                    name="Billing",
                    domain="billing",
                    intents=["bill"],
                    steps=[],
                    full_content="",
                )
            }
        )

        select_schema = object()
        more_context_schema = object()
        update_schema = object()

        phase, node = service.handle_transcription(
            state,
            "customer",
            "hello",
            "idle",
            select_schema,
            more_context_schema,
            update_schema,
        )
        assert phase is None
        assert node is None

        service.handle_transcription(
            state,
            "agent",
            "hi",
            "idle",
            select_schema,
            more_context_schema,
            update_schema,
        )
        phase, node = service.handle_transcription(
            state,
            "customer",
            "need help",
            "idle",
            select_schema,
            more_context_schema,
            update_schema,
        )

        assert phase == "detecting"
        assert node is not None
        assert node["name"] == "detecting"

    def test_handle_transcription_detecting_uses_full_conversation(self):
        service = ProcessService(min_utterances_before_detection=2)
        state = service.initial_state(
            {
                "billing": ProcessDefinition(
                    process_key="billing",
                    name="Billing",
                    domain="billing",
                    intents=["bill"],
                    steps=[],
                    full_content="",
                )
            }
        )

        select_schema = object()
        more_context_schema = object()
        update_schema = object()

        service.handle_transcription(
            state,
            "customer",
            "first utterance",
            "idle",
            select_schema,
            more_context_schema,
            update_schema,
        )
        _, node = service.handle_transcription(
            state,
            "agent",
            "second utterance",
            "idle",
            select_schema,
            more_context_schema,
            update_schema,
        )

        assert node is not None
        assert node["name"] == "detecting"
        prompt = node["task_messages"][0]["content"]
        assert "[customer]: first utterance" in prompt
        assert "[agent]: second utterance" in prompt

    def test_handle_select_process_success_returns_frame_and_tracking_node(self):
        service = ProcessService()
        process = ProcessDefinition(
            process_key="billing",
            name="Billing",
            domain="billing",
            intents=["bill"],
            steps=[
                ProcessStep(key="step_1", label="Verify", content="...", order=1),
                ProcessStep(key="step_2", label="Resolve", content="...", order=2),
            ],
            full_content="content",
        )
        state = service.initial_state({"billing": process})
        state["conversation_buffer"] = ["[customer]: help"]

        result, next_node, frame = service.handle_select_process(
            args={"process_key": "billing", "confidence": 0.8, "rationale": "intent match"},
            state=state,
            update_step_schema=object(),
            logger=MagicMock(),
        )

        assert result["status"] == "selected"
        assert next_node["name"] == "tracking"
        assert frame is not None
        assert frame.process_key == "billing"
        assert state["detected_process"] is process

    def test_handle_update_step_invalid_returns_tracking_without_frame(self):
        service = ProcessService()
        process = ProcessDefinition(
            process_key="billing",
            name="Billing",
            domain="billing",
            intents=["bill"],
            steps=[ProcessStep(key="step_1", label="Verify", content="...", order=1)],
            full_content="content",
        )
        state = service.initial_state({"billing": process})
        state["detected_process"] = process
        state["conversation_buffer"] = ["[customer]: help"]

        result, next_node, frame = service.handle_update_step(
            args={"step_number": 3, "rationale": "bad"},
            state=state,
            update_step_schema=object(),
            logger=MagicMock(),
        )

        assert result["status"] == "invalid_step"
        assert next_node["name"] == "tracking"
        assert frame is None

    def test_handle_transcription_tracking_uses_last_eight_utterances(self):
        service = ProcessService(conversation_window_size=8)
        process = ProcessDefinition(
            process_key="billing",
            name="Billing",
            domain="billing",
            intents=["bill"],
            steps=[ProcessStep(key="step_1", label="Verify", content="...", order=1)],
            full_content="content",
        )
        state = service.initial_state({"billing": process})
        state["detected_process"] = process
        state["conversation_buffer"] = [f"[customer]: utt_{index:02d}" for index in range(1, 10)]

        _, node = service.handle_transcription(
            state=state,
            speaker="agent",
            text="utt_10",
            current_node="tracking",
            select_process_schema=object(),
            need_more_context_schema=object(),
            update_step_schema=object(),
        )

        assert node is not None
        assert node["name"] == "tracking"
        prompt = node["task_messages"][0]["content"]
        assert "utt_01" not in prompt
        assert "utt_02" not in prompt
        assert "utt_03" in prompt
        assert "utt_10" in prompt
