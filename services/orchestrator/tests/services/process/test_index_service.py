"""Tests for process metadata index and lazy content loading."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.services.process.index_service import ProcessCatalogIndexService


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

## Step 1: Verify

Verify details.

## Step 2: Resolve

Resolve issue.
"""
    )


@pytest.mark.asyncio
async def test_shortlist_prefers_matching_intent(tmp_path: Path):
    service = ProcessCatalogIndexService(shortlist_k=3, cache_size=8)
    _write_process_file(
        tmp_path / "lost_stolen_card.md",
        "lost_stolen_card",
        "Lost or Stolen Card",
        ["lost card", "stolen card", "block card"],
    )
    _write_process_file(
        tmp_path / "small_estates.md",
        "small_estates",
        "Small Estates",
        ["estate", "deceased", "inheritance"],
    )
    logger = MagicMock()

    index = await service.load_index(tmp_path, logger)
    matches = service.shortlist(
        conversation_buffer=["[customer]: my card was stolen and I need to block it"],
        entries=index,
    )

    assert matches
    assert matches[0].entry.process_key == "lost_stolen_card"


@pytest.mark.asyncio
async def test_load_process_definition_uses_lru_cache(tmp_path: Path):
    service = ProcessCatalogIndexService(shortlist_k=3, cache_size=2)
    logger = MagicMock()
    process_file = tmp_path / "lost_stolen_card.md"
    _write_process_file(
        process_file,
        "lost_stolen_card",
        "Lost or Stolen Card",
        ["lost card", "stolen card"],
    )

    index = await service.load_index(tmp_path, logger)
    entry = index["lost_stolen_card"]
    definition_one = service.load_process_definition(entry, logger)
    definition_two = service.load_process_definition(entry, logger)

    assert definition_one is not None
    assert definition_two is definition_one
    assert definition_one.process_key == "lost_stolen_card"
