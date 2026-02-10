"""Tests for SuggestionFlow behavior."""

import asyncio
import time
from unittest.mock import AsyncMock

import pytest
from pipecat.frames.frames import TranscriptionFrame
from pipecat.processors.frame_processor import FrameDirection

from src.flows.suggestion_flow import SuggestionFlow


class FakeFlowManager:
    """Minimal FlowManager stub for SuggestionFlow tests."""

    def __init__(self):
        self.state: dict = {}
        self.current_node = "start"

    async def initialize(self, node):
        self.current_node = node["name"]

    async def set_node_from_config(self, node):
        self.current_node = node["name"]


@pytest.mark.asyncio
class TestSuggestionFlow:
    """SuggestionFlow tests."""

    async def test_schedules_generation_for_customer_turns(self):
        flow_manager = FakeFlowManager()
        flow = SuggestionFlow(session_id="test", flow_manager=flow_manager)
        await flow.start()
        flow._schedule_suggestion_task = AsyncMock()

        frame = TranscriptionFrame(
            text="I need help",
            user_id="customer",
            timestamp="2026-02-09T12:00:00Z",
            finalized=True,
        )

        await flow.process_frame(frame, FrameDirection.DOWNSTREAM)

        flow._schedule_suggestion_task.assert_awaited_once()

    async def test_skips_generation_for_agent_turns(self):
        flow_manager = FakeFlowManager()
        flow = SuggestionFlow(session_id="test", flow_manager=flow_manager)
        await flow.start()
        flow._schedule_suggestion_task = AsyncMock()

        frame = TranscriptionFrame(
            text="Let me check that",
            user_id="agent",
            timestamp="2026-02-09T12:00:00Z",
            finalized=True,
        )

        await flow.process_frame(frame, FrameDirection.DOWNSTREAM)

        flow._schedule_suggestion_task.assert_not_awaited()

    async def test_drops_stale_suggestions(self):
        flow_manager = FakeFlowManager()
        flow = SuggestionFlow(session_id="test", flow_manager=flow_manager)
        await flow.start()
        flow.push_frame = AsyncMock()

        flow._latest_turn_id = 2
        current_task = asyncio.current_task()
        assert current_task is not None
        flow._task_turn_map[current_task] = 1

        result, next_node = await flow._handle_publish_suggestions(
            {
                "suggestions": [
                    {"text": "s1", "type": "response"},
                    {"text": "s2", "type": "question"},
                    {"text": "s3", "type": "action"},
                ]
            }
        )

        assert result["status"] == "stale"
        assert next_node["name"] == "listening"
        flow.push_frame.assert_not_called()

    async def test_cancels_inflight_task_for_newer_turn(self):
        flow_manager = FakeFlowManager()
        flow = SuggestionFlow(session_id="test", flow_manager=flow_manager)
        await flow.start()

        old_task = asyncio.create_task(asyncio.sleep(60))
        flow._suggestion_task = old_task
        flow._latest_turn_id = 3

        flow._run_suggestion_turn = AsyncMock(return_value=None)

        await flow._schedule_suggestion_task()
        await flow._suggestion_task

        assert old_task.cancelled()
        flow._run_suggestion_turn.assert_awaited_once_with(3)

    async def test_publishes_fresh_suggestions(self):
        flow_manager = FakeFlowManager()
        flow = SuggestionFlow(session_id="test", flow_manager=flow_manager)
        await flow.start()
        flow.push_frame = AsyncMock()

        flow._latest_turn_id = 1
        flow._turn_start_times[1] = time.time() - 0.01
        current_task = asyncio.current_task()
        assert current_task is not None
        flow._task_turn_map[current_task] = 1

        result, next_node = await flow._handle_publish_suggestions(
            {
                "suggestions": [
                    {"text": "s1", "type": "response"},
                    {"text": "s2", "type": "question"},
                    {"text": "s3", "type": "action"},
                ]
            }
        )

        assert result["status"] == "published"
        assert result["count"] == 3
        assert next_node["name"] == "listening"
        flow.push_frame.assert_called_once()
