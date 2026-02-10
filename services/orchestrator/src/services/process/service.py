"""Domain logic for process detection and step tracking."""

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import frontmatter
from pipecat_flows import FlowResult, FlowsFunctionSchema, NodeConfig

from src.frames import ProcessIllustrationFrame


@dataclass
class ProcessStep:
    """Process step definition."""

    key: str
    label: str
    content: str
    order: int


@dataclass
class ProcessDefinition:
    """Process definition loaded from markdown."""

    process_key: str
    name: str
    domain: str | None
    intents: list[str]
    steps: list[ProcessStep]
    full_content: str


class ProcessService:
    """Encapsulates process-domain state and transition logic."""

    def __init__(
        self,
        min_utterances_before_detection: int = 3,
        detection_confidence_threshold: float = 0.6,
        conversation_window_size: int = 8,
    ):
        self._min_utterances_before_detection = min_utterances_before_detection
        self._detection_confidence_threshold = detection_confidence_threshold
        self._conversation_window_size = max(1, conversation_window_size)

    async def load_process_catalog(
        self,
        process_path: Path,
        logger: logging.Logger | logging.LoggerAdapter,
    ) -> dict[str, ProcessDefinition]:
        """Load process definitions from markdown files."""
        processes: dict[str, ProcessDefinition] = {}

        if not process_path.exists():
            logger.warning("Process content path does not exist: %s", process_path)
            return processes

        for md_file in process_path.glob("*.md"):
            try:
                content = md_file.read_text()
                post = frontmatter.loads(content)

                steps = self.extract_steps_from_markdown(post.content)

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

    @staticmethod
    def extract_steps_from_markdown(content: str) -> list[ProcessStep]:
        """Extract process steps from markdown content."""
        steps: list[ProcessStep] = []
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

    @staticmethod
    def initial_state(processes: dict[str, ProcessDefinition]) -> dict[str, Any]:
        """Return initial state map for ProcessFlow."""
        return {
            "processes": processes,
            "detected_process": None,
            "current_step": 0,
            "conversation_buffer": [],
            "utterance_count": 0,
        }

    @staticmethod
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

    @staticmethod
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

    @staticmethod
    def create_tracking_node(
        current_process: ProcessDefinition,
        conversation_buffer: list[str],
        current_step: int,
        update_step_fn: FlowsFunctionSchema,
        conversation_window_size: int = 8,
    ) -> NodeConfig:
        """Create TRACKING node (step progress tracking)."""
        step_list = "\n".join(
            [f"{i + 1}. {step.label}" for i, step in enumerate(current_process.steps)]
        )
        window_size = max(1, conversation_window_size)

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
                    "content": "\n".join(conversation_buffer[-window_size:]),
                }
            ],
            "functions": [update_step_fn],
        }

    def handle_transcription(
        self,
        state: dict[str, Any],
        speaker: str,
        text: str,
        current_node: str,
        select_process_schema: FlowsFunctionSchema,
        need_more_context_schema: FlowsFunctionSchema,
        update_step_schema: FlowsFunctionSchema,
    ) -> tuple[str | None, NodeConfig | None]:
        """Update process state from one transcription and return optional next node."""
        state["conversation_buffer"].append(f"[{speaker}]: {text}")
        state["utterance_count"] += 1

        if (
            current_node == "idle"
            and state["utterance_count"] >= self._min_utterances_before_detection
        ):
            return "detecting", self.create_detecting_node(
                state["conversation_buffer"],
                state["processes"],
                select_process_schema,
                need_more_context_schema,
            )

        current_process = state.get("detected_process")
        if current_node == "tracking" and current_process:
            return "tracking", self.create_tracking_node(
                current_process,
                state["conversation_buffer"],
                state["current_step"],
                update_step_schema,
                self._conversation_window_size,
            )

        return None, None

    def handle_select_process(
        self,
        args: dict[str, Any],
        state: dict[str, Any],
        update_step_schema: FlowsFunctionSchema,
        logger: logging.Logger | logging.LoggerAdapter,
    ) -> tuple[FlowResult, NodeConfig, ProcessIllustrationFrame | None]:
        """Handle process selection callback from LLM."""
        process_key = args["process_key"]
        confidence = args["confidence"]
        rationale = args.get("rationale", "")

        logger.info(
            "Selected %s (confidence: %.2f) - %s",
            process_key,
            confidence,
            rationale,
        )

        if confidence < self._detection_confidence_threshold:
            logger.debug("Confidence too low (%.2f)", confidence)
            return {"status": "low_confidence"}, self.create_idle_node(), None

        process = state["processes"].get(process_key)
        if not process:
            logger.warning("Process not found: %s", process_key)
            return {"status": "not_found"}, self.create_idle_node(), None

        state["detected_process"] = process
        state["current_step"] = 0

        illustration_frame = ProcessIllustrationFrame(
            process_key=process.process_key,
            process_name=process.name,
            steps=[
                {
                    "key": step.key,
                    "label": step.label,
                    "status": "pending",
                }
                for step in process.steps
            ],
            current_step=0,
            content=process.full_content,
        )

        next_node = self.create_tracking_node(
            process,
            state["conversation_buffer"],
            0,
            update_step_schema,
            self._conversation_window_size,
        )

        return {"status": "selected", "process_key": process_key}, next_node, illustration_frame

    def handle_need_more_context(
        self,
        args: dict[str, Any],
        logger: logging.Logger | logging.LoggerAdapter,
    ) -> tuple[FlowResult, NodeConfig]:
        """Handle need-more-context callback from LLM."""
        reason = args.get("reason", "")
        logger.info("Need more context - %s", reason)
        return {"status": "need_more_context"}, self.create_idle_node()

    def handle_update_step(
        self,
        args: dict[str, Any],
        state: dict[str, Any],
        update_step_schema: FlowsFunctionSchema,
        logger: logging.Logger | logging.LoggerAdapter,
    ) -> tuple[FlowResult, NodeConfig, ProcessIllustrationFrame | None]:
        """Handle step update callback from LLM."""
        step_number = args["step_number"]
        rationale = args.get("rationale", "")

        current_process = state.get("detected_process")
        if not current_process:
            logger.warning("No process detected, cannot update step")
            return {"status": "no_process"}, self.create_idle_node(), None

        step_index = step_number - 1
        if step_index < 0 or step_index >= len(current_process.steps):
            logger.warning("Invalid step number: %d", step_number)
            next_node = self.create_tracking_node(
                current_process,
                state["conversation_buffer"],
                state["current_step"],
                update_step_schema,
                self._conversation_window_size,
            )
            return {"status": "invalid_step"}, next_node, None

        state["current_step"] = step_index

        logger.info(
            "Updated to step %d: %s - %s",
            step_number,
            current_process.steps[step_index].label,
            rationale,
        )

        illustration_frame = ProcessIllustrationFrame(
            process_key=current_process.process_key,
            process_name=current_process.name,
            steps=[
                {
                    "key": step.key,
                    "label": step.label,
                    "status": (
                        "completed"
                        if i < step_index
                        else "in_progress"
                        if i == step_index
                        else "pending"
                    ),
                }
                for i, step in enumerate(current_process.steps)
            ],
            current_step=step_index,
            content=current_process.full_content,
        )

        next_node = self.create_tracking_node(
            current_process,
            state["conversation_buffer"],
            step_index,
            update_step_schema,
            self._conversation_window_size,
        )

        return (
            {
                "status": "updated",
                "step_number": step_number,
                "step_label": current_process.steps[step_index].label,
            },
            next_node,
            illustration_frame,
        )
