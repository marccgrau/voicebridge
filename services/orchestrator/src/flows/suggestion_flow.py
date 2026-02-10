"""Pipecat adapter for suggestion generation service."""

import asyncio
import time
from contextlib import suppress

from pipecat.frames.frames import Frame, TranscriptionFrame
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor
from pipecat_flows import FlowArgs, FlowManager, FlowResult, FlowsFunctionSchema, NodeConfig

from src.config import settings
from src.frames import ProcessIllustrationFrame
from src.services.suggestion import SuggestionService
from src.utils.logging import get_session_logger


class SuggestionFlow(FrameProcessor):
    """Suggestion generation flow adapter."""

    def __init__(
        self,
        session_id: str,
        flow_manager: FlowManager,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.session_id = session_id
        self.flow_manager = flow_manager
        self.service = SuggestionService(conversation_window_size=settings.conversation_window_size)
        self._turn_start_time: float | None = None
        self._latest_turn_id = 0
        self._suggestion_task: asyncio.Task | None = None
        self._task_turn_map: dict[asyncio.Task, int] = {}
        self._turn_start_times: dict[int, float] = {}

        self.logger = get_session_logger(__name__, session_id)

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

        self.flow_manager.state.update(self.service.initial_state())
        await self.flow_manager.initialize(self.service.create_start_node())

        self.logger.info("SuggestionFlow initialized")

    async def stop(self) -> None:
        """Stop the flow."""
        self.logger.info("Stopping SuggestionFlow")
        if self._suggestion_task and not self._suggestion_task.done():
            self._suggestion_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._suggestion_task

    async def _schedule_suggestion_task(self) -> None:
        """Start suggestion generation for latest turn and cancel stale work."""
        if self._suggestion_task and not self._suggestion_task.done():
            self.logger.debug("Cancelling stale suggestion task for newer customer turn")
            self._suggestion_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._suggestion_task

        turn_id = self._latest_turn_id
        task = asyncio.create_task(self._run_suggestion_turn(turn_id))
        self._task_turn_map[task] = turn_id
        task.add_done_callback(lambda t: self._task_turn_map.pop(t, None))
        self._suggestion_task = task

    async def _run_suggestion_turn(self, turn_id: int) -> None:
        """Run suggestion generation for one turn id."""
        try:
            await asyncio.wait_for(
                self.flow_manager.set_node_from_config(
                    self.service.create_suggesting_node(
                        self.flow_manager.state["conversation_buffer"],
                        self.flow_manager.state.get("process_context"),
                        self.publish_suggestions_schema,
                    )
                ),
                timeout=settings.llm_timeout,
            )
        except TimeoutError:
            self.logger.error("LLM timeout (suggesting)")
            await self.flow_manager.set_node_from_config(self.service.create_listening_node())
        except asyncio.CancelledError:
            self.logger.debug("Suggestion task cancelled for turn %d", turn_id)
            raise
        except Exception as e:
            self.logger.error("Suggestion task failed for turn %d: %s", turn_id, e)
            await self.flow_manager.set_node_from_config(self.service.create_listening_node())

    async def process_frame(self, frame: Frame, direction: FrameDirection) -> None:
        """Process frames and drive suggestion generation."""
        await super().process_frame(frame, direction)

        if isinstance(frame, ProcessIllustrationFrame):
            self.logger.debug("Received process context: %s", frame.process_name)
            self.service.update_process_context(self.flow_manager.state, frame)

        elif isinstance(frame, TranscriptionFrame) and frame.finalized:
            self.logger.debug("Processing: %s", frame.text)

            try:
                speaker = getattr(frame, "user_id", "unknown")
                self.service.add_conversation_line(self.flow_manager.state, speaker, frame.text)

                if self.flow_manager.current_node == "start":
                    await self.flow_manager.set_node_from_config(
                        self.service.create_listening_node()
                    )

                if self.service.should_generate_for_speaker(speaker):
                    self._latest_turn_id += 1
                    self._turn_start_time = time.time()
                    self._turn_start_times[self._latest_turn_id] = self._turn_start_time
                    await self._schedule_suggestion_task()

            except Exception as e:
                self.logger.error("Error in SuggestionFlow: %s", e)

        await self.push_frame(frame, direction)

    async def _handle_publish_suggestions(self, args: FlowArgs) -> tuple[FlowResult, NodeConfig]:
        """Handle publish suggestions callback."""
        current_task = asyncio.current_task()
        turn_id = self._task_turn_map.get(current_task) if current_task else None
        if self.service.is_stale_turn(turn_id, self._latest_turn_id):
            self.logger.debug(
                "Dropping stale suggestions for turn %d (latest=%d)",
                turn_id,
                self._latest_turn_id,
            )
            return {"status": "stale", "count": 0}, self.service.create_listening_node()

        suggestions = args["suggestions"]
        start_time = self._turn_start_times.pop(turn_id, self._turn_start_time)
        latency_ms = (time.time() - start_time) * 1000 if start_time else 0

        self.logger.info(
            "Generated %d suggestions (latency: %.1fms)",
            len(suggestions),
            latency_ms,
        )

        process_context = self.flow_manager.state.get("process_context")
        suggestion_frame = self.service.build_suggestion_frame(
            suggestions=suggestions,
            process_context=process_context,
            latency_ms=latency_ms,
        )

        await self.push_frame(suggestion_frame)
        return {
            "status": "published",
            "count": len(suggestions),
        }, self.service.create_listening_node()
