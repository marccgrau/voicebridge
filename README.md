# VoiceBridge

VoiceBridge is a proactive guidance workspace for live human-human customer service calls. It listens to conversations over WebRTC, uses LLM flows to detect processes and track progress, and delivers real-time suggestions to agents.

## Monorepo Layout

- `apps/agent-workspace` - Next.js agent UI (port `3000`)
- `apps/customer` - Next.js customer UI (port `3001`)
- `services/pcc` - Pipecat Cloud voice pipeline (port `7860`)
- `packages/contracts` - shared Zod schemas and TypeScript types
- `packages/db` - Supabase query helpers
- `supabase/migrations` - database migrations

## High-Level Flow

```text
Daily.co WebRTC -> Deepgram STT -> Pipecat Pipeline -> RTVI + Supabase Realtime -> Next.js UIs
```

Realtime channels:

- RTVI (WebRTC data channel): `transcript_segment`, `process_illustration`, `agent_guidance`
- Supabase Realtime: session lifecycle + pending call notifications

The PCC bot is stateless and runs directly in Pipecat Cloud. Session management (pending → active) lives in Next.js API routes + Supabase.

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
cp services/pcc/.env.example services/pcc/.env

# 3) Apply migrations
make db-migrate

# 4) Start all services
make dev
```

## Common Commands

```bash
# Development
make dev                  # web + customer + pcc
make web-dev              # agent workspace only
make customer-dev         # customer app only
make pcc-dev              # pcc service only

# Quality
make test                 # pnpm workspace tests + pcc pytest
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
OPENAI_API_KEY  # For AI-generated call summaries
```

### Customer App (`apps/customer/.env.local`)

```bash
NEXT_PUBLIC_SUPABASE_URL
NEXT_PUBLIC_SUPABASE_ANON_KEY
SUPABASE_SERVICE_ROLE_KEY
PCC_AGENT_URL=http://localhost:7860
DAILY_API_KEY
PIPECAT_CLOUD_API_KEY  # Optional, for cloud deployment
```

### PCC Service (`services/pcc/.env`)

```bash
DAILY_API_KEY
DEEPGRAM_API_KEY
OPENAI_API_KEY

# Optional: Pipecat Cloud API key (for cloud deployment)
PIPECAT_CLOUD_API_KEY

# Optional: Override suggestion LLM model (default: gpt-4.1-mini)
SUGGESTION_MODEL=gpt-4.1-mini
```

## API Surface

### Customer App API Routes

- `POST /api/sessions/create` - Customer-initiated session (creates Daily room, starts PCC bot, stores pending session)

### Agent Workspace

- Reads session data directly from Supabase (room_url, agent_token)
- Updates session status via Supabase (pending → active, active → completed)

## PCC Service Architecture

`services/pcc/` is a stateless Pipecat Cloud bot:

- `bot.py` - Entry point with full pipeline wiring
- `src/frames.py` - Custom Pipecat frames
- `src/processors.py` - Pipeline processors
- `src/process_catalog.py` - Process loading and matching
- `process_content/` - Process markdown files

Pipeline processors emit these custom frames:

- `TranscriptSegmentFrame`
- `ProcessIllustrationFrame`
- `SuggestionFrame`

All frames are delivered via RTVI (WebRTC data channel) for sub-second latency.

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

Process definitions live in `services/pcc/process_content` (currently 9 markdown files).

- YAML frontmatter: `process_key`, `name`, `domain`, `intents`
- Steps parsed from `## Step N: ...` headings

## Testing

- Run full suite: `make test`
- PCC service only: `cd services/pcc && uv run pytest`
- Contracts only: `pnpm --filter @voicebridge/contracts test`

## Operational Gotchas

- Daily rooms are ephemeral (1-hour expiry at creation).
- PCC bot is listen-only (`audio_out_enabled=False`) and never speaks.
- PCC service is stateless — no DB persistence, all data flows through RTVI.
- Process detection uses token-overlap matching (no LLM calls).
- Suggestion generation uses OpenAI gpt-4.1-mini by default (configurable via `SUGGESTION_MODEL` env var).
