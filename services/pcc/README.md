# VoiceBridge PCC Service

Unified Pipecat service for VoiceBridge.

## Pipeline

One transport + one STT pipeline, then fan-out via `ParallelPipeline`:

```
transport.input() → DeepgramSTT → ParallelPipeline(…) → transport.output()
```

Only customer audio reaches STT — agent microphone is unsubscribed at the Daily transport level when the agent joins.

- **Transcript branch**: `TranscriptWriter` emits `transcript_segment` (always speaker `"customer"`)
- **Process branch**: LLM via `PROCESS_MODEL` (default `gpt-4.1-nano`), prompt includes step descriptions
- **Suggestion branch (Process-Pilot)**: LLM via `SUGGESTION_MODEL` (default `gpt-4.1`), prompt is scenario-aware with matching process definition + KB content; emits 2–4 advice items as German imperatives

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
- Session metadata (`scenario_family`, `customer_id`, `customer_name`) is passed via the `/start` request body and used to select the matching process definition and KB content for scenario-aware prompts.
- Daily tokens include `user_name` ("Kunde"/"Berater") for participant identification; agent mic is unsubscribed at the transport level so only customer audio reaches STT.
- All LLM system prompts are in German.
