"""Process detection and step tracking flow.

Handles:
- Process detection from markdown catalog
- Step progress tracking
- Process illustration frame emission

Communicates via ProcessIllustrationFrame (decoupled from SuggestionFlow).
"""

import asyncio
import logging
import re
from dataclasses import dataclass
from pathlib import Path

import frontmatter
from pipecat.frames.frames import Frame, TranscriptionFrame
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor
from pipecat_flows import FlowArgs, FlowManager, FlowResult, FlowsFunctionSchema, NodeConfig

from src.config import settings
from src.frames import ProcessIllustrationFrame
from src.utils.logging import get_session_logger

# ============================================================================
# Data Models
# ============================================================================


@dataclass
class ProcessStep:
    """Process step definition."""

    key: str
    label: str
    content: str
    order: int


@dataclass
class ProcessDefinition:
    """Process definition from markdown."""

    process_key: str
    name: str
    domain: str | None
    intents: list[str]
    steps: list[ProcessStep]
    full_content: str


# ============================================================================
# Helper Functions
# ============================================================================


def extract_steps_from_markdown(content: str) -> list[ProcessStep]:
    """Extract steps from markdown content."""
    steps = []
    step_pattern = re.compile(r"^##\s+Step\s+(\d+):\s+(.+)$", re.MULTILINE)
    matches = list(step_pattern.finditer(content))

    for i, match in enumerate(matches):
        step_num = int(match.group(1))
        step_label = match.group(2).strip()

        start_pos = match.end()
        end_pos = matches[i + 1].start() if i + 1 < len(matches) else len(content)
        step_content = content[start_pos:end_pos].strip()

        steps.append(
            ProcessStep(
                key=f"step_{step_num}",
                label=step_label,
                content=step_content,
                order=step_num,
            )
        )

    return steps


async def load_process_catalog(
    process_path: Path, logger: logging.Logger | logging.LoggerAdapter
) -> dict[str, ProcessDefinition]:
    """Load process definitions from markdown files."""
    processes = {}

    if not process_path.exists():
        logger.warning("Process content path does not exist: %s", process_path)
        return processes

    for md_file in process_path.glob("*.md"):
        try:
            content = md_file.read_text()
            post = frontmatter.loads(content)

            steps = extract_steps_from_markdown(post.content)

            process_def = ProcessDefinition(
                process_key=post.metadata["process_key"],
                name=post.metadata["name"],
                domain=post.metadata.get("domain"),
                intents=post.metadata.get("intents", []),
                steps=steps,
                full_content=post.content,
            )

            processes[process_def.process_key] = process_def
            logger.debug("Loaded process: %s (%d steps)", process_def.name, len(steps))

        except Exception as e:
            logger.error("Failed to load process file %s: %s", md_file, e)

    return processes


# ============================================================================
# Node Creation Functions
# ============================================================================


def create_idle_node() -> NodeConfig:
    """Create IDLE node (waiting for enough context)."""
    return {
        "name": "idle",
        "role_messages": [
            {
                "role": "system",
                "content": "Waiting for customer conversation to begin.",
            }
        ],
        "task_messages": [],
        "functions": [],
    }


def create_detecting_node(
    conversation_buffer: list[str],
    available_processes: dict[str, ProcessDefinition],
    select_process_fn: FlowsFunctionSchema,
    need_more_context_fn: FlowsFunctionSchema,
) -> NodeConfig:
    """Create DETECTING node (process detection)."""
    process_list = "\n".join(
        [
            f"- {key}: {proc.name} (intents: {', '.join(proc.intents)})"
            for key, proc in available_processes.items()
        ]
    )

    return {
        "name": "detecting",
        "role_messages": [
            {
                "role": "system",
                "content": f"""You are a process detection expert.
                Your task is to analyze a conversation between a customer and an agent and identify which process best matches the customer's intent, based on the conversation and the list of available processes.
                Below you find the conversation so far and the list of available processes you can choose from.
                The conversation is recorded with a STT model. Therefore, the conversation may contain transcription errors.
                Use your judgment to interpret the conversation and identify the most appropriate process.

                Conversation lines are tagged with speaker labels like [customer] or [agent].

                Available processes:
                {process_list}

                Call select_process when you've identified the right process with confidence > 0.6.
                Call need_more_context if you need more conversation to make a decision.""",
            }
        ],
        "task_messages": [
            {
                "role": "user",
                "content": f"Conversation:\n{chr(10).join(conversation_buffer)}\n\nWhich process matches?",
            }
        ],
        "functions": [select_process_fn, need_more_context_fn],
    }


def create_tracking_node(
    current_process: ProcessDefinition,
    conversation_buffer: list[str],
    current_step: int,
    update_step_fn: FlowsFunctionSchema,
) -> NodeConfig:
    """Create TRACKING node (step progress tracking)."""
    step_list = "\n".join(
        [f"{i + 1}. {step.label}" for i, step in enumerate(current_process.steps)]
    )

    return {
        "name": "tracking",
        "role_messages": [
            {
                "role": "system",
                "content": f"""You are a process tracking assistant.
                Your task is to monitor the conversation between a customer and an agent, and determine when the conversation has progressed to a new step in the current process.
                The conversation is recorded with a STT model. Therefore, the conversation may contain transcription errors.
                Use your judgment to interpret the conversation and identify the current process step.

                Conversation lines are tagged with speaker labels like [customer] or [agent].

                Process: {current_process.name}
                Steps:
                {step_list}

                Current step: {current_step + 1}

                Call update_step when you detect the conversation has moved to a new step.""",
            }
        ],
        "task_messages": [
            {
                "role": "user",
                "content": "\n".join(conversation_buffer[-5:]),  # Last 5 messages
            }
        ],
        "functions": [update_step_fn],
    }


# ============================================================================
# ProcessFlow
# ============================================================================


class ProcessFlow(FrameProcessor):
    """Process detection and step tracking flow.

    Responsibilities:
    - Detect customer process from conversation
    - Track progress through process steps
    - Emit ProcessIllustrationFrame for frontend

    Decoupled from SuggestionFlow - communicates only via frames.
    """

    def __init__(
        self,
        session_id: str,
        flow_manager: FlowManager,
        process_content_path: str,
        **kwargs,
    ):
        """Initialize process flow.

        Args:
            session_id: Session identifier
            flow_manager: FlowManager instance
            process_content_path: Path to process markdown files
        """
        super().__init__(**kwargs)
        self.session_id = session_id
        self.flow_manager = flow_manager
        self.process_path = Path(process_content_path)

        # Session-scoped logger
        self.logger = get_session_logger(__name__, session_id)

        # Create function schemas with handlers bound to this instance
        self.select_process_schema = FlowsFunctionSchema(
            name="select_process",
            description="Select the matching process based on customer intent",
            properties={
                "process_key": {
                    "type": "string",
                    "description": "Key of the selected process",
                },
                "confidence": {
                    "type": "number",
                    "description": "Confidence score (0-1)",
                },
                "rationale": {
                    "type": "string",
                    "description": "Why this process was selected",
                },
            },
            required=["process_key", "confidence"],
            handler=self._handle_select_process,
        )
        self.need_more_context_schema = FlowsFunctionSchema(
            name="need_more_context",
            description="Return to listening if no confident process match found",
            properties={
                "reason": {
                    "type": "string",
                    "description": "Why more context is needed",
                },
            },
            required=["reason"],
            handler=self._handle_need_more_context,
        )
        self.update_step_schema = FlowsFunctionSchema(
            name="update_step",
            description="Update current step based on conversation progress",
            properties={
                "step_number": {
                    "type": "number",
                    "description": "New step number (1-indexed)",
                },
                "rationale": {
                    "type": "string",
                    "description": "Why this step was selected",
                },
            },
            required=["step_number"],
            handler=self._handle_update_step,
        )

    async def start(self) -> None:
        """Start the flow."""
        self.logger.info("Starting ProcessFlow")

        # Load processes
        processes = await load_process_catalog(self.process_path, self.logger)

        # Initialize state
        self.flow_manager.state.update(
            {
                "processes": processes,
                "detected_process": None,
                "current_step": 0,
                "conversation_buffer": [],
                "utterance_count": 0,
            }
        )

        # Initialize to IDLE
        await self.flow_manager.initialize(create_idle_node())

        self.logger.info("ProcessFlow loaded %d processes", len(processes))

    async def stop(self) -> None:
        """Stop the flow."""
        self.logger.info("Stopping ProcessFlow")

    async def process_frame(self, frame: Frame, direction: FrameDirection) -> None:
        """Process transcription frames.

        Args:
            frame: The frame to process
            direction: Frame direction
        """
        await super().process_frame(frame, direction)

        if isinstance(frame, TranscriptionFrame) and frame.finalized:
            self.logger.debug("ProcessFlow processing: %s", frame.text)

            try:
                # Update conversation buffer with speaker tag
                speaker = getattr(frame, "user_id", "unknown")
                self.flow_manager.state["conversation_buffer"].append(f"[{speaker}]: {frame.text}")
                self.flow_manager.state["utterance_count"] += 1

                current_node = self.flow_manager.current_node
                current_process = self.flow_manager.state.get("detected_process")

                # State transitions
                if current_node == "idle":
                    # Wait for 3+ utterances before detecting
                    if self.flow_manager.state["utterance_count"] >= 3:
                        try:
                            node = create_detecting_node(
                                self.flow_manager.state["conversation_buffer"],
                                self.flow_manager.state["processes"],
                                self.select_process_schema,
                                self.need_more_context_schema,
                            )
                            await asyncio.wait_for(
                                self.flow_manager.set_node_from_config(node),
                                timeout=settings.llm_timeout,
                            )
                        except TimeoutError:
                            self.logger.error("ProcessFlow LLM timeout (detecting)")

                elif current_node == "tracking" and current_process:
                    # Update tracking node with new conversation
                    try:
                        node = create_tracking_node(
                            current_process,
                            self.flow_manager.state["conversation_buffer"],
                            self.flow_manager.state["current_step"],
                            self.update_step_schema,
                        )
                        await asyncio.wait_for(
                            self.flow_manager.set_node_from_config(node),
                            timeout=settings.llm_timeout,
                        )
                    except TimeoutError:
                        self.logger.error("ProcessFlow LLM timeout (tracking)")

            except Exception as e:
                self.logger.error("Error in ProcessFlow: %s", e)

        # Always push frame downstream
        await self.push_frame(frame, direction)

    # ========================================================================
    # Function Handlers
    # ========================================================================

    async def _handle_select_process(self, args: FlowArgs) -> tuple[FlowResult, NodeConfig]:
        """Handle process selection."""
        process_key = args["process_key"]
        confidence = args["confidence"]
        rationale = args.get("rationale", "")

        self.logger.info(
            "Selected %s (confidence: %.2f) - %s",
            process_key,
            confidence,
            rationale,
        )

        # Check confidence
        if confidence < 0.6:
            self.logger.debug("Confidence too low (%.2f)", confidence)
            next_node = create_idle_node()
            return {"status": "low_confidence"}, next_node

        # Get process
        process = self.flow_manager.state["processes"].get(process_key)
        if not process:
            self.logger.warning("Process not found: %s", process_key)
            next_node = create_idle_node()
            return {"status": "not_found"}, next_node

        # Update state
        self.flow_manager.state["detected_process"] = process
        self.flow_manager.state["current_step"] = 0

        # Emit ProcessIllustrationFrame
        illustration_frame = ProcessIllustrationFrame(
            process_key=process.process_key,
            process_name=process.name,
            steps=[
                {
                    "key": s.key,
                    "label": s.label,
                    "status": "pending",
                }
                for s in process.steps
            ],
            current_step=0,
            content=process.full_content,
        )

        await self.push_frame(illustration_frame)

        # Transition to tracking
        next_node = create_tracking_node(
            process,
            self.flow_manager.state["conversation_buffer"],
            0,
            self.update_step_schema,
        )

        return {"status": "selected", "process_key": process_key}, next_node

    async def _handle_need_more_context(self, args: FlowArgs) -> tuple[FlowResult, NodeConfig]:
        """Handle need more context."""
        reason = args.get("reason", "")
        self.logger.info("Need more context - %s", reason)

        # Stay in idle
        next_node = create_idle_node()

        return {"status": "need_more_context"}, next_node

    async def _handle_update_step(self, args: FlowArgs) -> tuple[FlowResult, NodeConfig]:
        """Handle step update."""
        step_number = args["step_number"]
        rationale = args.get("rationale", "")

        current_process = self.flow_manager.state.get("detected_process")
        if not current_process:
            self.logger.warning("No process detected, cannot update step")
            next_node = create_idle_node()
            return {"status": "no_process"}, next_node

        # Convert to 0-indexed
        step_index = step_number - 1

        if step_index < 0 or step_index >= len(current_process.steps):
            self.logger.warning("Invalid step number: %d", step_number)
            next_node = create_tracking_node(
                current_process,
                self.flow_manager.state["conversation_buffer"],
                self.flow_manager.state["current_step"],
                self.update_step_schema,
            )
            return {"status": "invalid_step"}, next_node

        # Update state
        self.flow_manager.state["current_step"] = step_index

        self.logger.info(
            "Updated to step %d: %s - %s",
            step_number,
            current_process.steps[step_index].label,
            rationale,
        )

        # Emit updated ProcessIllustrationFrame
        illustration_frame = ProcessIllustrationFrame(
            process_key=current_process.process_key,
            process_name=current_process.name,
            steps=[
                {
                    "key": s.key,
                    "label": s.label,
                    "status": (
                        "completed"
                        if i < step_index
                        else "in_progress"
                        if i == step_index
                        else "pending"
                    ),
                }
                for i, s in enumerate(current_process.steps)
            ],
            current_step=step_index,
            content=current_process.full_content,
        )

        await self.push_frame(illustration_frame)

        # Stay in tracking
        next_node = create_tracking_node(
            current_process,
            self.flow_manager.state["conversation_buffer"],
            step_index,
            self.update_step_schema,
        )

        return {
            "status": "updated",
            "step_number": step_number,
            "step_label": current_process.steps[step_index].label,
        }, next_node
