"""Agent suggestion generation flow.

Handles:
- Generating agent guidance after each customer utterance
- Using process context if available (from ProcessIllustrationFrame)
- Emitting SuggestionFrame

Decoupled from ProcessFlow - listens for ProcessIllustrationFrame to get context.
"""

import asyncio
import time
from typing import Any

from pipecat.frames.frames import Frame, TranscriptionFrame
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor
from pipecat_flows import FlowArgs, FlowManager, FlowResult, FlowsFunctionSchema, NodeConfig

from src.config import settings
from src.frames import ProcessIllustrationFrame, SuggestionFrame
from src.utils.logging import get_session_logger

# ============================================================================
# Node Creation Functions
# ============================================================================


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


def create_suggesting_node(
    conversation_buffer: list[str],
    process_context: dict[str, Any] | None,
    publish_suggestions_fn: FlowsFunctionSchema,
) -> NodeConfig:
    """Create SUGGESTING node.

    Args:
        conversation_buffer: Recent conversation
        process_context: Process context from ProcessIllustrationFrame (if available)

    Returns:
        NodeConfig for suggestion generation
    """
    # Build system message with optional process context
    if process_context:
        process_name = process_context.get("process_name", "Unknown")
        current_step = process_context.get("current_step", 0)
        steps = process_context.get("steps", [])

        step_list = "\n".join(
            [f"{i + 1}. {s['label']} [{s['status']}]" for i, s in enumerate(steps)]
        )

        system_content = f"""You are an agent guidance assistant. Generate exactly 3 concise suggestions for the agent.

Conversation lines are tagged with [customer] or [agent].

Current Process: {process_name} (Step {current_step + 1})
Steps: {step_list}

Rules:
- Exactly 3 suggestions, each one short sentence
- Reference the current process step when relevant
- No preamble, just call publish_suggestions immediately

Call publish_suggestions with exactly 3 suggestions."""
    else:
        system_content = """You are an agent guidance assistant. Generate exactly 3 concise suggestions for the agent.

Conversation lines are tagged with [customer] or [agent].

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


# ============================================================================
# SuggestionFlow
# ============================================================================


class SuggestionFlow(FrameProcessor):
    """Agent suggestion generation flow.

    Responsibilities:
    - Generate agent guidance after each customer utterance
    - Use process context if available (from ProcessIllustrationFrame)
    - Emit SuggestionFrame for frontend

    Decoupled from ProcessFlow - only listens to ProcessIllustrationFrame.
    """

    def __init__(
        self,
        session_id: str,
        flow_manager: FlowManager,
        **kwargs,
    ):
        """Initialize suggestion flow.

        Args:
            session_id: Session identifier
            flow_manager: FlowManager instance
        """
        super().__init__(**kwargs)
        self.session_id = session_id
        self.flow_manager = flow_manager
        self._turn_start_time: float | None = None

        # Session-scoped logger
        self.logger = get_session_logger(__name__, session_id)

        # Create function schema with handler bound to this instance
        self.publish_suggestions_schema = FlowsFunctionSchema(
            name="publish_suggestions",
            description="Publish suggestions to agent UI",
            properties={
                "suggestions": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "text": {"type": "string", "description": "One concise sentence"},
                            "type": {
                                "type": "string",
                                "enum": ["response", "question", "action", "escalation"],
                            },
                        },
                        "required": ["text", "type"],
                    },
                    "minItems": 3,
                    "maxItems": 3,
                    "description": "Exactly 3 concise suggestions",
                },
            },
            required=["suggestions"],
            handler=self._handle_publish_suggestions,
        )

    async def start(self) -> None:
        """Start the flow."""
        self.logger.info("Starting SuggestionFlow")

        # Initialize state
        self.flow_manager.state.update(
            {
                "conversation_buffer": [],
                "process_context": None,  # Updated from ProcessIllustrationFrame
            }
        )

        # Initialize to START
        await self.flow_manager.initialize(create_start_node())

        self.logger.info("SuggestionFlow initialized")

    async def stop(self) -> None:
        """Stop the flow."""
        self.logger.info("Stopping SuggestionFlow")

    async def process_frame(self, frame: Frame, direction: FrameDirection) -> None:
        """Process frames.

        Args:
            frame: The frame to process
            direction: Frame direction
        """
        await super().process_frame(frame, direction)

        # Listen for ProcessIllustrationFrame (from ProcessFlow)
        if isinstance(frame, ProcessIllustrationFrame):
            self.logger.debug("Received process context: %s", frame.process_name)

            # Update process context (decoupled communication!)
            self.flow_manager.state["process_context"] = {
                "process_key": frame.process_key,
                "process_name": frame.process_name,
                "current_step": frame.current_step,
                "steps": frame.steps,
                "content": frame.content,
            }

        # Process transcription frames
        elif isinstance(frame, TranscriptionFrame) and frame.finalized:
            self._turn_start_time = time.time()
            self.logger.debug("Processing: %s", frame.text)

            try:
                # Update conversation buffer with speaker tag
                speaker = getattr(frame, "user_id", "unknown")
                self.flow_manager.state["conversation_buffer"].append(f"[{speaker}]: {frame.text}")

                current_node = self.flow_manager.current_node

                # State transitions
                if current_node == "start":
                    # First utterance - move to listening
                    await self.flow_manager.set_node_from_config(create_listening_node())

                elif current_node == "listening":
                    # Generate suggestions for every customer utterance
                    try:
                        await asyncio.wait_for(
                            self.flow_manager.set_node_from_config(
                                create_suggesting_node(
                                    self.flow_manager.state["conversation_buffer"],
                                    self.flow_manager.state.get("process_context"),
                                    self.publish_suggestions_schema,
                                )
                            ),
                            timeout=settings.llm_timeout,
                        )
                    except TimeoutError:
                        self.logger.error("LLM timeout (suggesting)")
                        # Return to listening on timeout
                        await self.flow_manager.set_node_from_config(create_listening_node())

                elif current_node == "suggesting":
                    # After publishing, go back to listening
                    await self.flow_manager.set_node_from_config(create_listening_node())

            except Exception as e:
                self.logger.error("Error in SuggestionFlow: %s", e)

        # Always push frame downstream
        await self.push_frame(frame, direction)

    # ========================================================================
    # Function Handlers
    # ========================================================================

    async def _handle_publish_suggestions(self, args: FlowArgs) -> tuple[FlowResult, NodeConfig]:
        """Handle publish suggestions."""
        suggestions = args["suggestions"]

        latency_ms = (time.time() - self._turn_start_time) * 1000 if self._turn_start_time else 0

        self.logger.info(
            "Generated %d suggestions (latency: %.1fms)",
            len(suggestions),
            latency_ms,
        )

        process_context = self.flow_manager.state.get("process_context")
        process_key = process_context.get("process_key") if process_context else None

        # Emit SuggestionFrame
        suggestion_frame = SuggestionFrame(
            suggestions=suggestions,
            service_type="suggestion_flow",
            latency_ms=latency_ms,
            process_key=process_key,
            tools_used=["flow_manager"],
        )

        await self.push_frame(suggestion_frame)

        # Return to listening
        next_node = create_listening_node()

        return {"status": "published", "count": len(suggestions)}, next_node
