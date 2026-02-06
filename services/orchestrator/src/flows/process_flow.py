"""Process detection and step tracking flow.

Handles:
- Process detection from markdown catalog
- Step progress tracking
- Process illustration frame emission

Communicates via ProcessIllustrationFrame (decoupled from SuggestionFlow).
"""

import logging
import re
from dataclasses import dataclass
from pathlib import Path

import frontmatter
from pipecat.frames.frames import Frame, TranscriptionFrame
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor
from pipecat_flows import FlowArgs, FlowManager, FlowResult, NodeConfig

from src.frames import ProcessIllustrationFrame

logger = logging.getLogger(__name__)


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


async def load_process_catalog(process_path: Path) -> dict[str, ProcessDefinition]:
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
# Flow Function Schemas
# ============================================================================


select_process_schema = {
    "type": "function",
    "function": {
        "name": "select_process",
        "description": "Select the matching process based on customer intent",
        "parameters": {
            "type": "object",
            "properties": {
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
            "required": ["process_key", "confidence"],
        },
    },
}


update_step_schema = {
    "type": "function",
    "function": {
        "name": "update_step",
        "description": "Update current step based on conversation progress",
        "parameters": {
            "type": "object",
            "properties": {
                "step_number": {
                    "type": "number",
                    "description": "New step number (1-indexed)",
                },
                "rationale": {
                    "type": "string",
                    "description": "Why this step was selected",
                },
            },
            "required": ["step_number"],
        },
    },
}


need_more_context_schema = {
    "type": "function",
    "function": {
        "name": "need_more_context",
        "description": "Return to listening if no confident process match found",
        "parameters": {
            "type": "object",
            "properties": {
                "reason": {
                    "type": "string",
                    "description": "Why more context is needed",
                }
            },
            "required": ["reason"],
        },
    },
}


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
Analyze the customer conversation and identify which process matches their needs.

NOTE: Conversation lines are tagged with speaker labels like [customer] or [agent].

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
        "functions": [select_process_schema, need_more_context_schema],
    }


def create_tracking_node(
    current_process: ProcessDefinition,
    conversation_buffer: list[str],
    current_step: int,
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
                "content": f"""Track conversation progress through process steps.

NOTE: Conversation lines are tagged with speaker labels like [customer] or [agent].

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
        "functions": [update_step_schema],
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

        # Register function handlers
        self.flow_manager.register_function("select_process", self._handle_select_process)
        self.flow_manager.register_function("need_more_context", self._handle_need_more_context)
        self.flow_manager.register_function("update_step", self._handle_update_step)

    async def start(self) -> None:
        """Start the flow."""
        logger.info("Starting ProcessFlow for session %s", self.session_id)

        # Load processes
        processes = await load_process_catalog(self.process_path)

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

        logger.info("ProcessFlow loaded %d processes", len(processes))

    async def stop(self) -> None:
        """Stop the flow."""
        logger.info("Stopping ProcessFlow for session %s", self.session_id)

    async def process_frame(self, frame: Frame, direction: FrameDirection) -> None:
        """Process transcription frames.

        Args:
            frame: The frame to process
            direction: Frame direction
        """
        if isinstance(frame, TranscriptionFrame) and frame.finalized:
            logger.debug("ProcessFlow processing: %s", frame.text)

            try:
                # Update conversation buffer with speaker tag
                speaker = getattr(frame, "user_id", "unknown")
                self.flow_manager.state["conversation_buffer"].append(f"[{speaker}]: {frame.text}")
                self.flow_manager.state["utterance_count"] += 1

                current_node = self.flow_manager.current_node
                current_process = self.flow_manager.state.get("detected_process")

                # State transitions
                if current_node["name"] == "idle":
                    # Wait for 3+ utterances before detecting
                    if self.flow_manager.state["utterance_count"] >= 3:
                        await self.flow_manager.set_node(
                            create_detecting_node(
                                self.flow_manager.state["conversation_buffer"],
                                self.flow_manager.state["processes"],
                            )
                        )

                elif current_node["name"] == "tracking" and current_process:
                    # Update tracking node with new conversation
                    await self.flow_manager.set_node(
                        create_tracking_node(
                            current_process,
                            self.flow_manager.state["conversation_buffer"],
                            self.flow_manager.state["current_step"],
                        )
                    )

            except Exception as e:
                logger.error("Error in ProcessFlow: %s", e)

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

        logger.info(
            "ProcessFlow: Selected %s (confidence: %.2f) - %s",
            process_key,
            confidence,
            rationale,
        )

        # Check confidence
        if confidence < 0.6:
            logger.debug("ProcessFlow: Confidence too low (%.2f)", confidence)
            next_node = create_idle_node()
            return {"status": "low_confidence"}, next_node

        # Get process
        process = self.flow_manager.state["processes"].get(process_key)
        if not process:
            logger.warning("ProcessFlow: Process not found: %s", process_key)
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
        )

        return {"status": "selected", "process_key": process_key}, next_node

    async def _handle_need_more_context(self, args: FlowArgs) -> tuple[FlowResult, NodeConfig]:
        """Handle need more context."""
        reason = args.get("reason", "")
        logger.info("ProcessFlow: Need more context - %s", reason)

        # Stay in idle
        next_node = create_idle_node()

        return {"status": "need_more_context"}, next_node

    async def _handle_update_step(self, args: FlowArgs) -> tuple[FlowResult, NodeConfig]:
        """Handle step update."""
        step_number = args["step_number"]
        rationale = args.get("rationale", "")

        current_process = self.flow_manager.state.get("detected_process")
        if not current_process:
            logger.warning("ProcessFlow: No process detected, cannot update step")
            next_node = create_idle_node()
            return {"status": "no_process"}, next_node

        # Convert to 0-indexed
        step_index = step_number - 1

        if step_index < 0 or step_index >= len(current_process.steps):
            logger.warning("ProcessFlow: Invalid step number: %d", step_number)
            next_node = create_tracking_node(
                current_process,
                self.flow_manager.state["conversation_buffer"],
                self.flow_manager.state["current_step"],
            )
            return {"status": "invalid_step"}, next_node

        # Update state
        self.flow_manager.state["current_step"] = step_index

        logger.info(
            "ProcessFlow: Updated to step %d: %s - %s",
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
        )

        return {
            "status": "updated",
            "step_number": step_number,
            "step_label": current_process.steps[step_index].label,
        }, next_node
