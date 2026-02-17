# VoiceBridge

VoiceBridge is a proactive guidance workspace for live human-human customer service calls. It listens to conversations over WebRTC, uses LLM flows to detect processes and track progress, and delivers real-time suggestions to agents.

## Monorepo Layout

```
voicebridge/
├── apps/
│   ├── agent-workspace/     # Next.js agent UI (port 3000)
│   └── customer/            # Next.js customer UI (port 3001)
├── services/
│   ├── pcc/                 # Pipecat Cloud voice pipeline (port 7860)
│   └── orchestrator/        # Legacy orchestrator (deprecated, superseded by PCC)
├── packages/
│   ├── contracts/           # Shared Zod schemas and TypeScript types
│   └── db/                  # Supabase query helpers
└── supabase/
    └── migrations/          # Database migrations (001–006)
```

## High-Level Flow

```text
Daily.co WebRTC → Deepgram STT → Pipecat Pipeline (PCC) → RTVI + Supabase Realtime → Next.js UIs
```

Realtime channels:

- **RTVI** (WebRTC data channel): `transcript_segment`, `process_illustration`, `agent_guidance`
- **Supabase Realtime**: session lifecycle + pending call notifications

The PCC bot is stateless and runs in Pipecat Cloud (or locally). Session management (pending → active) lives in Next.js API routes + Supabase.

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
make dev                  # web + customer + pcc (all 3 in parallel)
make web-dev              # agent workspace only (port 3000)
make customer-dev         # customer app only (port 3001)
make pcc-dev              # PCC service only (port 7860)

# Quality
make test                 # pnpm workspace tests + PCC pytest
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
NEXT_PUBLIC_SUPABASE_URL=https://xxx.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=your_supabase_anon_key
SUPABASE_SERVICE_ROLE_KEY=your_supabase_service_role_key
NEXT_PUBLIC_AGENT_MIC_ENABLED=true  # Set false for local dual-tab testing on one machine
OPENAI_API_KEY=your_openai_api_key  # For AI-generated call summaries
```

### Customer App (`apps/customer/.env.local`)

```bash
NEXT_PUBLIC_SUPABASE_URL=https://xxx.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=your_supabase_anon_key
SUPABASE_SERVICE_ROLE_KEY=your_supabase_service_role_key
PCC_AGENT_URL=http://localhost:7860  # PCC local dev server
DAILY_API_KEY=your_daily_api_key
PIPECAT_CLOUD_API_KEY=your_pipecat_cloud_api_key  # Optional, for cloud deployment
```

### PCC Service (`services/pcc/.env`)

```bash
DAILY_API_KEY=your_daily_api_key
DEEPGRAM_API_KEY=your_deepgram_api_key
OPENAI_API_KEY=your_openai_api_key

# Optional
PIPECAT_CLOUD_API_KEY=your_pipecat_cloud_api_key  # For cloud deployment
PROCESS_MODEL=gpt-4.1-nano                         # Process identification model
SUGGESTION_MODEL=gpt-4.1                           # Override suggestion LLM model (default: gpt-4.1)
```

## API Surface

### Customer App API Routes

- `POST /api/sessions/create` — Customer-initiated session (creates Daily room via PCC, generates tokens, stores pending session in Supabase with optional `customer_id` + routing handoff context)

### Agent Workspace API Routes

- `POST /api/sessions/summary` — Save agent's postcall summary
- `POST /api/sessions/[sessionId]/generate-summary` — Generate AI summary from transcript via OpenAI

### Agent Workspace Data Access

- Reads session data directly from Supabase (room_url, agent_token, customer/routing metadata in `sessions.state`)
- Updates session status via Supabase (pending → active, active → completed)

## PCC Service Architecture

`services/pcc/` is a stateless Pipecat Cloud bot:

- `bot.py` — Entry point with full pipeline wiring
- `src/transcript_processors.py` — Transcript branch RTVI emission
- `src/process_processors.py` — Process branch LLM output parsing + RTVI emission
- `src/suggestion_processors.py` — Suggestion branch LLM output parsing + RTVI emission
- `src/process_catalog.py` — Process loading and matching

Pipeline branches emit RTVI bot-action messages:

- `transcript_segment` — Live transcript segment
- `process_illustration` — Detected process with step progress
- `agent_guidance` — Agent guidance suggestions

All live guidance messages are delivered via RTVI (WebRTC data channel) for sub-second latency.

## Database

### Migrations

- `001_initial_schema.sql` — sessions, transcript_segments, process_catalog
- `002_customers.sql` — customers, customer_interactions tables
- `003_add_session_summary.sql` — summary fields on sessions
- `004_customers_rls.sql` — Row-level security for customers
- `005_update_suggestion_service_modes.sql` — Update service type column
- `006_add_agent_token.sql` — Add agent_token to sessions

### Primary Tables

- `sessions` — Session state (JSONB), status, room URL/name, agent_token, timestamps
- `transcript_segments` — STT output segments by speaker (agent/customer)
- `process_catalog` — Process definitions with full-text search
- `customers` — Customer profiles with classification
- `customer_interactions` — Links sessions to customers

### Session Statuses

`pending` → `active` → `completed` / `abandoned` / `escalated` / `error`

Summary save/generate is allowed for terminal statuses only: `completed`, `abandoned`, `escalated`.

## Process Catalog

Process definitions currently live in `services/pcc/process_content/` (9 markdown files).

- YAML frontmatter: `process_key`, `name`, `domain`, `intents`
- Steps parsed from `## Step N: ...` headings
- Catalog content is embedded into the process-LLM system prompt (`PROCESS_MODEL`)
- `PROCESS_CONTENT_PATH` can override the default markdown directory

## Testing

```bash
make test                                        # Full suite (vitest + pytest)
cd services/pcc && uv run pytest                 # PCC service only
pnpm --filter @voicebridge/contracts test        # Contracts only
pnpm --filter @voicebridge/db test               # DB package only
```

## Operational Gotchas

- Daily rooms are ephemeral (1-hour expiry at creation).
- PCC bot is listen-only (`audio_out_enabled=False`) and never speaks.
- PCC service is stateless — no DB persistence, all data flows through RTVI.
- Process identification uses an OpenAI model (`PROCESS_MODEL`, default `gpt-4.1-nano`).
- Suggestion generation uses OpenAI `gpt-4.1` by default (configurable via `SUGGESTION_MODEL`).
- Node must be 24+, Python must be 3.13+, pnpm must be 10+.

## Further Reading

- [Architecture Guide](./ARCHITECTURE.md) — Detailed system architecture, data flows, and design patterns
- [Agent Workspace](./apps/agent-workspace/README.md) — Phase-based agent UI documentation
- [Customer App](./apps/customer/README.md) — Customer call interface documentation
- [PCC Service](./services/pcc/README.md) — Voice pipeline service documentation
