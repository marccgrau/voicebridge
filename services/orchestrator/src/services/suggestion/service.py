"""Domain logic for agent suggestion generation."""

from typing import Any

from pipecat_flows import FlowsFunctionSchema, NodeConfig

from src.frames import ProcessIllustrationFrame, SuggestionFrame


class SuggestionService:
    """Encapsulates suggestion-domain state and prompt/node construction."""

    @staticmethod
    def initial_state() -> dict[str, Any]:
        """Return initial state map for SuggestionFlow."""
        return {
            "conversation_buffer": [],
            "process_context": None,
        }

    @staticmethod
    def create_start_node() -> NodeConfig:
        """Create START node."""
        return {
            "name": "start",
            "role_messages": [
                {
                    "role": "system",
                    "content": "Agent guidance system ready. Waiting for customer conversation.",
                }
            ],
            "task_messages": [],
            "functions": [],
        }

    @staticmethod
    def create_listening_node() -> NodeConfig:
        """Create LISTENING node."""
        return {
            "name": "listening",
            "role_messages": [
                {
                    "role": "system",
                    "content": "Listening to customer conversation. Ready to generate suggestions.",
                }
            ],
            "task_messages": [],
            "functions": [],
        }

    @staticmethod
    def create_suggesting_node(
        conversation_buffer: list[str],
        process_context: dict[str, Any] | None,
        publish_suggestions_fn: FlowsFunctionSchema,
    ) -> NodeConfig:
        """Create SUGGESTING node."""
        if process_context:
            process_name = process_context.get("process_name", "Unknown")
            current_step = process_context.get("current_step", 0)
            steps = process_context.get("steps", [])

            step_list = "\n".join(
                [f"{i + 1}. {s['label']} [{s['status']}]" for i, s in enumerate(steps)]
            )

            system_content = f"""You are an agent guidance assistant that observes a conversation between an agent and a customer.
            Your task is to provide helpful suggestions to the agent based on the conversation and the current process context.
            Generate exactly 3 concise suggestions for the agent.
            The conversation is recorded with a STT model. Therefore, the conversation may contain transcription errors.
            Use your judgment to interpret the conversation and provide relevant suggestions.

            Conversation lines are tagged with [customer] or [agent].

            Make sure that the suggestions are relevant to the current process step.
            If the customer utterance indicates an issue or question related to the current step, tailor your suggestions to help the agent address it effectively.

            Current Process: {process_name} (Step {current_step + 1})
            Steps: {step_list}

            Rules:
            - Exactly 3 suggestions, each one short sentence
            - Reference the current process step when relevant
            - No preamble, just call publish_suggestions immediately

            Call publish_suggestions with exactly 3 suggestions."""
        else:
            system_content = """You are an agent guidance assistant. Generate exactly 3 concise suggestions for the agent.
            Your task is to provide helpful suggestions to the agent based on the conversation and the current process context.
            Generate exactly 3 concise suggestions for the agent.
            The conversation is recorded with a STT model. Therefore, the conversation may contain transcription errors.
            Use your judgment to interpret the conversation and provide relevant suggestions.

            Conversation lines are tagged with [customer] or [agent].

            The intent of the customer is not yet known.
            Make suggestions based on the latest customer utterance, and keep them general enough to be useful to identify the customer's intent and next steps.

            Rules:
            - Exactly 3 suggestions, each one short sentence
            - No preamble, just call publish_suggestions immediately

            Call publish_suggestions with exactly 3 suggestions."""

        return {
            "name": "suggesting",
            "role_messages": [
                {
                    "role": "system",
                    "content": system_content,
                }
            ],
            "task_messages": [
                {
                    "role": "user",
                    "content": f"Latest customer message:\n{conversation_buffer[-1] if conversation_buffer else '(waiting)'}",
                }
            ],
            "functions": [publish_suggestions_fn],
        }

    @staticmethod
    def update_process_context(
        state: dict[str, Any],
        frame: ProcessIllustrationFrame,
    ) -> None:
        """Update suggestion state with latest process context."""
        state["process_context"] = {
            "process_key": frame.process_key,
            "process_name": frame.process_name,
            "current_step": frame.current_step,
            "steps": frame.steps,
            "content": frame.content,
        }

    @staticmethod
    def add_conversation_line(state: dict[str, Any], speaker: str, text: str) -> None:
        """Append one tagged conversation line to state."""
        state["conversation_buffer"].append(f"[{speaker}]: {text}")

    @staticmethod
    def should_generate_for_speaker(speaker: str) -> bool:
        """Return true when suggestions should be generated for this speaker."""
        return speaker == "customer"

    @staticmethod
    def is_stale_turn(turn_id: int | None, latest_turn_id: int) -> bool:
        """Return true when a suggestion callback belongs to an old turn."""
        return turn_id is not None and turn_id < latest_turn_id

    @staticmethod
    def build_suggestion_frame(
        suggestions: list[dict[str, Any]],
        process_context: dict[str, Any] | None,
        latency_ms: float,
    ) -> SuggestionFrame:
        """Build SuggestionFrame from generated suggestions and process context."""
        process_key = process_context.get("process_key") if process_context else None
        return SuggestionFrame(
            suggestions=suggestions,
            service_type="suggestion_flow",
            latency_ms=latency_ms,
            process_key=process_key,
            tools_used=["flow_manager"],
        )
