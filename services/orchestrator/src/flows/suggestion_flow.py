"""Agent suggestion generation flow.

Handles:
- Generating agent guidance after each customer utterance
- Using process context if available (from ProcessIllustrationFrame)
- Emitting SuggestionFrame

Decoupled from ProcessFlow - listens for ProcessIllustrationFrame to get context.
"""

import logging
import time
from typing import Any

from pipecat.frames.frames import Frame, TranscriptionFrame
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor
from pipecat_flows import FlowArgs, FlowManager, FlowResult, NodeConfig

from src.frames import ProcessIllustrationFrame, SuggestionFrame

logger = logging.getLogger(__name__)


# ============================================================================
# Flow Function Schemas
# ============================================================================


publish_suggestions_schema = {
    "type": "function",
    "function": {
        "name": "publish_suggestions",
        "description": "Publish suggestions to agent UI",
        "parameters": {
            "type": "object",
            "properties": {
                "suggestions": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "text": {"type": "string"},
                            "type": {
                                "type": "string",
                                "enum": ["response", "question", "action", "escalation"],
                            },
                        },
                        "required": ["text", "type"],
                    },
                    "description": "List of suggestions for the agent",
                }
            },
            "required": ["suggestions"],
        },
    },
}


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

        system_content = f"""You are an agent guidance assistant.
Generate helpful suggestions for the agent based on the conversation.

NOTE: Conversation lines are tagged with speaker labels like [customer] or [agent].
Your suggestions should target the agent to help them respond to the customer.

Current Process: {process_name}
Current Step: {current_step + 1}

Process Steps:
{step_list}

Generate 3-5 specific, actionable suggestions:
- Reference the current process step
- Provide clear next actions
- Be professional and empathetic
- Include relevant questions to ask

Call publish_suggestions with your recommendations."""
    else:
        # No process context available
        system_content = """You are an agent guidance assistant.
Generate helpful suggestions for the agent based on the conversation.

NOTE: Conversation lines are tagged with speaker labels like [customer] or [agent].
Your suggestions should target the agent to help them respond to the customer.

Generate 3-5 specific, actionable suggestions:
- Provide clear next actions
- Be professional and empathetic
- Include relevant questions to ask
- Help the agent understand customer needs

Call publish_suggestions with your recommendations."""

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
        "functions": [publish_suggestions_schema],
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

        # Register function handlers
        self.flow_manager.register_function("publish_suggestions", self._handle_publish_suggestions)

    async def start(self) -> None:
        """Start the flow."""
        logger.info("Starting SuggestionFlow for session %s", self.session_id)

        # Initialize state
        self.flow_manager.state.update(
            {
                "conversation_buffer": [],
                "process_context": None,  # Updated from ProcessIllustrationFrame
            }
        )

        # Initialize to START
        await self.flow_manager.initialize(create_start_node())

        logger.info("SuggestionFlow initialized")

    async def stop(self) -> None:
        """Stop the flow."""
        logger.info("Stopping SuggestionFlow for session %s", self.session_id)

    async def process_frame(self, frame: Frame, direction: FrameDirection) -> None:
        """Process frames.

        Args:
            frame: The frame to process
            direction: Frame direction
        """
        # Listen for ProcessIllustrationFrame (from ProcessFlow)
        if isinstance(frame, ProcessIllustrationFrame):
            logger.debug("SuggestionFlow received process context: %s", frame.process_name)

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
            logger.debug("SuggestionFlow processing: %s", frame.text)

            try:
                # Update conversation buffer with speaker tag
                speaker = getattr(frame, "user_id", "unknown")
                self.flow_manager.state["conversation_buffer"].append(f"[{speaker}]: {frame.text}")

                current_node = self.flow_manager.current_node

                # State transitions
                if current_node["name"] == "start":
                    # First utterance - move to listening
                    await self.flow_manager.set_node(create_listening_node())

                elif current_node["name"] == "listening":
                    # Generate suggestions for every customer utterance
                    await self.flow_manager.set_node(
                        create_suggesting_node(
                            self.flow_manager.state["conversation_buffer"],
                            self.flow_manager.state.get("process_context"),
                        )
                    )

                elif current_node["name"] == "suggesting":
                    # After publishing, go back to listening
                    await self.flow_manager.set_node(create_listening_node())

            except Exception as e:
                logger.error("Error in SuggestionFlow: %s", e)

        # Always push frame downstream
        await self.push_frame(frame, direction)

    # ========================================================================
    # Function Handlers
    # ========================================================================

    async def _handle_publish_suggestions(self, args: FlowArgs) -> tuple[FlowResult, NodeConfig]:
        """Handle publish suggestions."""
        suggestions = args["suggestions"]

        latency_ms = (time.time() - self._turn_start_time) * 1000 if self._turn_start_time else 0

        logger.info(
            "SuggestionFlow: Generated %d suggestions (latency: %.1fms)",
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
