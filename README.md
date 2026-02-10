# VoiceBridge

VoiceBridge is a proactive guidance workspace for live human-human customer service calls. It listens to conversations over WebRTC, uses LLM flows to detect processes and track progress, and delivers real-time suggestions to agents.

## Monorepo Layout

- `apps/agent-workspace` - Next.js agent UI (port `3000`)
- `apps/customer` - Next.js customer UI (port `3001`)
- `services/orchestrator` - FastAPI + Pipecat voice pipeline (port `8000`)
- `packages/contracts` - shared Zod schemas and TypeScript types
- `packages/db` - Supabase query helpers
- `supabase/migrations` - database migrations

## High-Level Flow

```text
Daily.co WebRTC -> Silero VAD -> Speechmatics STT -> Pipecat Pipeline -> RTVI + Supabase Realtime -> Next.js UIs
```

Realtime channels:

- RTVI (WebRTC data channel): `transcript_segment`, `process_illustration`, `agent_guidance`
- Supabase Realtime: session lifecycle + pending call notifications

## Prerequisites

- Node.js `24+`
- pnpm `10+`
- Python `3.13+`
- `uv`
- Supabase CLI

## Quick Start

```bash
# 1) Install dependencies
make install

# 2) Configure env files
cp apps/agent-workspace/.env.example apps/agent-workspace/.env.local
cp apps/customer/.env.example apps/customer/.env.local
cp services/orchestrator/.env.example services/orchestrator/.env

# 3) Apply migrations
make db-migrate

# 4) Start all services
make dev
```

## Common Commands

```bash
# Development
make dev                  # web + customer + orchestrator
make web-dev              # agent workspace only
make customer-dev         # customer app only
make orchestrator-dev     # orchestrator only

# Quality
make test                 # pnpm workspace tests + orchestrator pytest
make lint                 # eslint + ruff
make typecheck            # TypeScript typecheck
make format               # prettier + ruff format

# Database
make db-migrate           # supabase db push
make db-reset             # supabase db reset
```

## Environment Variables

### Agent Workspace (`apps/agent-workspace/.env.local`)

```bash
NEXT_PUBLIC_SUPABASE_URL
NEXT_PUBLIC_SUPABASE_ANON_KEY
SUPABASE_SERVICE_ROLE_KEY
NEXT_PUBLIC_ORCHESTRATOR_URL=http://localhost:8000
```

### Customer App (`apps/customer/.env.local`)

```bash
NEXT_PUBLIC_SUPABASE_URL
NEXT_PUBLIC_SUPABASE_ANON_KEY
NEXT_PUBLIC_ORCHESTRATOR_URL=http://localhost:8000
```

### Orchestrator (`services/orchestrator/.env`)

```bash
SUPABASE_URL
SUPABASE_SERVICE_ROLE_KEY
SPEECHMATICS_API_KEY
DAILY_API_KEY

# Configure the provider keys you plan to use
# Defaults for process/suggestion flows use OpenAI unless overridden at session start/accept
OPENAI_API_KEY
GOOGLE_API_KEY
ANTHROPIC_API_KEY
```

Note: AI summary generation (`POST /sessions/{session_id}/generate-summary`) currently requires `ANTHROPIC_API_KEY`.

## API Surface (Orchestrator)

Session lifecycle:

- `POST /sessions/create`
- `POST /sessions/accept`
- `POST /sessions/start`
- `POST /sessions/stop`
- `GET /sessions/{session_id}/status`

Post-call:

- `POST /sessions/summary`
- `POST /sessions/{session_id}/generate-summary`

Health:

- `GET /healthz`

## Orchestrator Architecture

`services/orchestrator/src` follows modular boundaries:

- `api` - HTTP layer
- `services` - domain/business logic
- `ports` - dependency interfaces
- `adapters` - infrastructure implementations
- `flows` - Pipecat flow adapters
- `pipeline` - runtime assembly + processors
- `composition` - dependency wiring
- `frames` - custom Pipecat frames
- `rtvi` - RTVI observer/message publishing

Pipeline processors emit these custom frames:

- `TranscriptSegmentFrame`
- `ProcessIllustrationFrame`
- `SuggestionFrame`

## Database Notes

Current migrations:

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

Session statuses:

- `pending`
- `active`
- `completed`
- `abandoned`
- `escalated`
- `error`

Summary save/generate is allowed for terminal statuses only: `completed`, `abandoned`, `escalated`.

## Process Catalog

Process definitions live in `services/orchestrator/process_content` (currently 9 markdown files).

- YAML frontmatter: `process_key`, `name`, `domain`, `intents`
- Steps parsed from `## Step N: ...` headings

## Testing

- Run full suite: `make test`
- Orchestrator only: `cd services/orchestrator && uv run pytest`
- Contracts only: `pnpm --filter @voicebridge/contracts test`

## Operational Gotchas

- Daily rooms are ephemeral (1-hour expiry at creation).
- Orchestrator is listen-only (`audio_out_enabled=False`) and never speaks.
- VAD defaults in pipeline are `start_secs=0.2` and `stop_secs=0.8`.
- `GET /healthz` reports `llm: up` only when `ANTHROPIC_API_KEY` is configured.
