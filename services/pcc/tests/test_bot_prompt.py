"""Tests for process prompt construction."""

from pathlib import Path

from bot import LiveOptions, build_process_system_prompt
from src.process_catalog import ProcessCatalog
from src.process_processors import PROCESS_SYSTEM_PROMPT


def test_build_process_system_prompt_includes_domain_and_intents(tmp_path: Path):
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


def test_build_process_system_prompt_includes_step_descriptions(tmp_path: Path):
    process_file = tmp_path / "bank_credit_denial.md"
    process_file.write_text(
        """---
process_key: bank_credit_denial
name: Kreditablehnung
domain: banking
intents:
  - kredit abgelehnt
---

# Kreditablehnung

## Step 0: Begrüssung

Kunden freundlich begrüssen und Anliegen aufnehmen.

## Step 1: Prüfung

Kreditantrag prüfen und Gründe erläutern.
"""
    )

    catalog = ProcessCatalog(process_content_path=str(tmp_path))
    catalog.load()

    prompt = build_process_system_prompt(catalog)

    assert "Step 0 – Begrüssung: Kunden freundlich begrüssen und Anliegen aufnehmen." in prompt
    assert "Step 1 – Prüfung: Kreditantrag prüfen und Gründe erläutern." in prompt


def test_build_process_system_prompt_step_without_content(tmp_path: Path):
    process_file = tmp_path / "test_process.md"
    process_file.write_text(
        """---
process_key: test_process
name: Test Process
domain: test
intents:
  - test
---

# Test Process

## Step 0: Empty Step

"""
    )

    catalog = ProcessCatalog(process_content_path=str(tmp_path))
    catalog.load()

    prompt = build_process_system_prompt(catalog)

    # Step with empty content should just show label
    assert "Step 0 – Empty Step" in prompt


def test_process_system_prompt_has_speaker_awareness_rules():
    assert "[Kunde]" in PROCESS_SYSTEM_PROMPT
    assert "[Berater]" in PROCESS_SYSTEM_PROMPT
    assert "Fokussiere auf Kundenäusserungen" in PROCESS_SYSTEM_PROMPT


def test_bot_uses_stable_deepgram_live_options_import():
    assert LiveOptions.__module__ == "deepgram.clients.listen.v1.websocket.options"
