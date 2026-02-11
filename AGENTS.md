# AGENTS.md

This file provides guidance to coding agents working in this repository.

## Overview

VoiceBridge is a proactive guidance workspace for live human-human customer service calls. It listens to conversations via WebRTC, uses LLMs to detect processes and track progress, and delivers real-time suggestions to agents.

The system consists of:

- `apps/agent-workspace` (Next.js, agent UI)
- `apps/customer` (Next.js, customer UI)
- `services/orchestrator` (FastAPI + Pipecat voice pipeline)
- `packages/contracts` (shared Zod schemas/types)
- `packages/db` (Supabase query helpers)

## Development Commands

### Setup

```bash
make install              # Install pnpm + uv deps
make db-migrate           # Push Supabase migrations
```

### Development

```bash
make dev                  # Run web + customer + orchestrator
make web-dev              # Agent workspace only (3000)
make customer-dev         # Customer app only (3001)
make orchestrator-dev     # Orchestrator only (8000)
```

### Testing & Quality

```bash
make test                 # pnpm workspace tests + orchestrator pytest
make lint                 # eslint + ruff
make typecheck            # TypeScript typecheck
make format               # prettier + ruff format
```

### Python Orchestrator

```bash
cd services/orchestrator
uv run uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
uv run pytest
uv run ruff check .
uv run ruff format .
```

### Database

```bash
make db-migrate           # supabase db push
make db-reset             # supabase db reset
```

## Development Practices

### Branching and PR Workflow

For every new feature:

1. Create a new git branch before making code changes.
2. Implement the feature on that branch only.
3. Fully test the feature with all relevant automated tests.
4. Prepare a pull request with a clear summary and test evidence.

### Testing Requirements

Always add tests for new behavior and run relevant suites before considering work complete.

- TypeScript/React changes: run workspace tests (`pnpm -r test`) or `make test`
- Python orchestrator changes: run `cd services/orchestrator && uv run pytest`
- Contract/schema changes: run `packages/contracts` vitest suite

For orchestrator work, prioritize tests for:

- service-level business logic in `src/services`
- API route behavior in `tests/api`
- pipeline/flow processors in `tests/pipeline` and `tests/flows`
- architecture boundaries in `tests/architecture/test_module_boundaries.py`

## Architecture

### High-Level Flow

```text
Daily.co WebRTC -> Silero VAD -> Speechmatics STT -> Pipecat Pipeline -> RTVI / Supabase Realtime -> Next.js UIs
```

The orchestrator is listen-only (`audio_out_enabled=False`). It never speaks; it emits guidance events.

Realtime channels:

- RTVI (WebRTC data channel): transcript segments, process illustrations, suggestions
- Supabase Realtime: session lifecycle updates (pending/active/completed...) and pending-call notifications

### Component Responsibilities

#### Agent Workspace (`apps/agent-workspace`)

- Phase-based UI:
  - `idle`
  - `incoming`
  - `active_preprocess`
  - `active_inprocess`
  - `postcall_summary`
- Accepts pending sessions and stops active ones via orchestrator API
- Receives RTVI actions:
  - `transcript_segment`
  - `process_illustration`
  - `agent_guidance`
- Fetches customer profile/interactions from Supabase when `customer_id` exists
- Includes `/admin` route with session list + session transcript/detail inspector

#### Customer App (`apps/customer`)

- Customer flow states: `idle -> calling -> connected -> ended`
- Starts calls via `POST /sessions/create` (optional `customer_id`)
- Watches session status via Supabase Realtime to detect agent join/end
- Connects to Daily room audio using `@daily-co/daily-js`

#### Orchestrator (`services/orchestrator`)

- FastAPI API with session lifecycle + summary endpoints:
  - `POST /sessions/create`
  - `POST /sessions/accept`
  - `POST /sessions/start`
  - `POST /sessions/stop`
  - `GET /sessions/{session_id}/status`
  - `POST /sessions/summary`
  - `POST /sessions/{session_id}/generate-summary`
  - `GET /healthz`
- Pipecat pipeline processors:
  1. `TranscriptWriter` (speaker mapping + async DB writes + emits `TranscriptSegmentFrame`)
  2. `ProcessFlow` (LLM process detection/tracking + emits `ProcessIllustrationFrame`)
  3. `SuggestionFlow` (LLM suggestions; consumes process context; emits `SuggestionFrame`)
  4. `VoiceBridgeRTVIObserver` (publishes custom frames as RTVI bot-action messages with retries)

### Orchestrator Module Boundaries

`services/orchestrator` follows a modular-monolith structure:

- `src/api` for HTTP layer only
- `src/services` for business rules (`session`, `process`, `suggestion`, `summary`)
- `src/ports` for dependency interfaces
- `src/adapters` for concrete infrastructure integrations
- `src/flows` for Pipecat frame adapters around services
- `src/pipeline` for runtime assembly
- `src/composition` for dependency wiring

See `services/orchestrator/ARCHITECTURE.md` for details and constraints.

## Database Schema

Migrations currently present:

- `001_initial_schema.sql`
- `002_customers.sql`
- `003_add_session_summary.sql`
- `004_customers_rls.sql`

Primary tables:

- `sessions`
- `transcript_segments`
- `process_catalog`
- `customers`
- `customer_interactions`

Notable additions after initial schema:

- `sessions.customer_id` links sessions to customers
- summary fields on sessions:
  - `summary_text`
  - `summary_updated_at`
  - `summary_updated_by`

Session statuses:

- `pending`
- `active`
- `completed`
- `abandoned`
- `escalated`
- `error`

Supabase Realtime publications are enabled for `sessions` and `transcript_segments`.

## Contracts and Frames

### Shared Contracts (`packages/contracts`)

- Zod schemas for RTVI events (`agent_guidance`, `process_illustration`, `transcript_segment`)
- DTO schemas for session lifecycle, summary updates, and customer data
- Cross-package TypeScript type source of truth

### Custom Pipecat Frames (`services/orchestrator/src/frames`)

- `SuggestionFrame`
- `ProcessIllustrationFrame`
- `TranscriptSegmentFrame`

## Process Catalog

Process markdown content lives in `services/orchestrator/process_content`.

- Files use YAML frontmatter (`process_key`, `name`, `domain`, `intents`)
- Steps are parsed from `## Step N: ...` headings
- Repository currently contains 9 process content markdown files

## Key Design Patterns

- Listen-only bot: no audio output from orchestrator.
- Decoupled flows: `SuggestionFlow` gets process context through frames, not direct coupling.
- Isolated LLM tasks: each flow uses its own FlowManager/LLM pipeline.
- Non-blocking transcript persistence: `TranscriptWriter` writes via background queue/worker.
- Latest-turn-wins suggestions: stale suggestion tasks are canceled on newer customer turns.
- RTVI-first for live guidance: low-latency messages over WebRTC data channel.

## Environment Variables

### Agent Workspace (`apps/agent-workspace/.env.local`)

```bash
NEXT_PUBLIC_SUPABASE_URL
NEXT_PUBLIC_SUPABASE_ANON_KEY
SUPABASE_SERVICE_ROLE_KEY
NEXT_PUBLIC_ORCHESTRATOR_URL   # default http://localhost:8000
```

### Customer App (`apps/customer/.env.local`)

```bash
NEXT_PUBLIC_SUPABASE_URL
NEXT_PUBLIC_SUPABASE_ANON_KEY
NEXT_PUBLIC_ORCHESTRATOR_URL   # default http://localhost:8000
```

### Orchestrator (`services/orchestrator/.env`)

```bash
SUPABASE_URL
SUPABASE_SERVICE_ROLE_KEY
SPEECHMATICS_API_KEY
DAILY_API_KEY

# LLM provider keys (configure based on selected providers)
OPENAI_API_KEY
GOOGLE_API_KEY
ANTHROPIC_API_KEY
```

Notes:

- At least one provider key is required for session flows, depending on configured provider (`openai`, `gemini`, or `anthropic`).
- AI summary generation currently uses Anthropic `SummaryService`; `ANTHROPIC_API_KEY` is required for `POST /sessions/{id}/generate-summary`.

## Common Gotchas

- Python must be 3.13+; Node must be 24+; pnpm must be 10+.
- Supabase CLI is required for migration/reset commands.
- Daily rooms are ephemeral (1-hour expiry on room creation).
- VAD defaults are tuned in config (`start_secs=0.2`, `stop_secs=0.6`) and strongly affect responsiveness.
- `SessionSummaryService` allows save/generate only for terminal statuses (`completed`, `abandoned`, `escalated`).
- First detected speaker defaults to `customer` (`first_speaker_role`) and affects downstream suggestion/process behavior.
- Current `GET /healthz` implementation reports LLM as `up` only when `ANTHROPIC_API_KEY` is configured.
