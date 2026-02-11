"""Tests for ProcessService catalog parsing."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.services.process.service import ProcessService


def _write_process_file(path: Path, process_key: str, name: str, intents: list[str]) -> None:
    intents_yaml = "\n".join(f"  - {intent}" for intent in intents)
    path.write_text(
        f"""---
process_key: {process_key}
name: {name}
domain: card_services
intents:
{intents_yaml}
---

# {name}

## Step 1: Verify Identity

Verify the caller identity.

## Step 2: Resolve Request

Complete the customer request.
"""
    )


class TestProcessService:
    """ProcessService behavior tests."""

    @pytest.mark.asyncio
    async def test_load_process_catalog_reads_markdown(self, tmp_path: Path):
        service = ProcessService()
        logger = MagicMock()
        _write_process_file(
            tmp_path / "lost_stolen_card.md",
            "lost_stolen_card",
            "Lost or Stolen Card",
            ["lost card", "stolen card", "block card"],
        )

        processes = await service.load_process_catalog(tmp_path, logger)

        assert "lost_stolen_card" in processes
        process = processes["lost_stolen_card"]
        assert process.name == "Lost or Stolen Card"
        assert len(process.steps) == 2
        assert process.steps[0].label == "Verify Identity"

    def test_extract_steps_from_markdown_parses_step_headers(self):
        content = """
# Test Process

## Step 1: First Step
Collect account details.

## Step 2: Second Step
Resolve issue.
"""
        steps = ProcessService.extract_steps_from_markdown(content)

        assert len(steps) == 2
        assert steps[0].key == "step_1"
        assert steps[0].label == "First Step"
        assert "Collect account details." in steps[0].content
        assert steps[1].key == "step_2"
        assert steps[1].label == "Second Step"
