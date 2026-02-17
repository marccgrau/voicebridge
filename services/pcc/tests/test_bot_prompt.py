"""Tests for process prompt construction."""

from pathlib import Path

from bot import build_process_system_prompt
from src.process_catalog import ProcessCatalog


def test_build_process_system_prompt_includes_domain_intents_and_steps(tmp_path: Path):
    process_file = tmp_path / "bank_unauthorized_transaction_high_urgency.md"
    process_file.write_text(
        """---
process_key: bank_unauthorized_transaction_high_urgency
name: Bank Unauthorized Transaction (High Urgency)
domain: banking
intents:
  - unauthorized transaction
  - block card
---

# Bank Unauthorized Transaction (High Urgency)

## Step 1: Opening Alert

Start with urgency.

## Step 2: Identity Verification

Verify identity.
"""
    )

    catalog = ProcessCatalog(process_content_path=str(tmp_path))
    catalog.load()

    prompt = build_process_system_prompt(catalog)

    assert "domain: banking" in prompt
    assert "intents: unauthorized transaction, block card" in prompt
    assert "steps: 0:Opening Alert, 1:Identity Verification" in prompt
