# VoiceBridge PCC Service

Unified Pipecat service for VoiceBridge.

## Pipeline

One transport + one STT pipeline, then fan-out via `ParallelPipeline`:

- transcript branch
- process branch (LLM via `PROCESS_MODEL`, default `gpt-4.1-nano`)
- suggestion branch (LLM via `SUGGESTION_MODEL`, default `gpt-4.1`)

Each branch emits RTVI bot-action messages:

- `transcript_segment`
- `process_illustration`
- `agent_guidance`

## Run locally

```bash
uv sync
uv run python bot.py -t daily --port 7860
```

## Required environment variables

- `DAILY_API_KEY`
- `DEEPGRAM_API_KEY`
- `OPENAI_API_KEY`

Optional:

- `PROCESS_MODEL` (default: `gpt-4.1-nano`)
- `SUGGESTION_MODEL` (default: `gpt-4.1`)
- `PROCESS_CONTENT_PATH` (override process markdown path, default is `services/pcc/process_content/`)

## Experiment process catalog

The repository ships four experiment-aligned process definitions (all in German) in `process_content/`:

- `bank_unauth_transaction` — Unautorisierte Bankbuchung
- `bank_credit_denial` — Kreditantrag abgelehnt
- `insurance_unauth_claim` — Unautorisierter Versicherungsanspruch
- `insurance_claim_denial` — Versicherungsantrag abgelehnt

## Knowledge base content

Supporting knowledge base articles are in `kb_content/` (all in German), one per process scenario:

- `bank_unauth_transaction.md`
- `bank_credit_denial.md`
- `insurance_unauth_claim.md`
- `insurance_claim_denial.md`

## Relation to Persona/Scenario Loading

- Persona and scenario definitions are authored in repository JSON files (German) and seeded into Supabase by `scripts/seed-experimental-data.mjs`.
- Customer app selects persona/scenario and creates sessions via `POST /api/sessions/create`.
- This PCC service does **not** query Supabase; it remains stateless and runs only on room/session context plus live audio.
- Process guidance is derived from markdown files in `services/pcc/process_content/` (not from DB rows).
- All LLM system prompts are in German.
