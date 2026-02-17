# AGENTS.md

This file provides guidance to coding agents working in this repository.

## Overview

VoiceBridge is a proactive guidance workspace for live human-human customer service calls. It listens to conversations via WebRTC, uses LLMs to detect processes and track progress, and delivers real-time suggestions to agents.

The system consists of:

- `apps/agent-workspace` (Next.js, agent UI, port 3000)
- `apps/customer` (Next.js, customer UI, port 3001)
- `services/pcc` (Pipecat Cloud voice pipeline, port 7860)
- `packages/contracts` (shared Zod schemas/types)
- `packages/db` (Supabase query helpers)
- `services/orchestrator` (legacy, deprecated — superseded by PCC)

## Development Commands

### Setup

```bash
make install              # Install pnpm + uv deps
make db-migrate           # Push Supabase migrations
```

### Development

```bash
make dev                  # Run web + customer + pcc (all 3 in parallel)
make web-dev              # Agent workspace only (port 3000)
make customer-dev         # Customer app only (port 3001)
make pcc-dev              # PCC service only (port 7860)
```

### Testing & Quality

```bash
make test                 # pnpm workspace tests + PCC pytest
make lint                 # eslint + ruff
make typecheck            # TypeScript typecheck
make format               # prettier + ruff format
```

### PCC Service

```bash
cd services/pcc
uv run python bot.py -t daily --port 7860   # Run local dev server
uv run pytest                                # Run tests
uv run ruff check .                          # Lint
uv run ruff format .                         # Format
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
3. Commit regularly.
4. Fully test the feature with all relevant automated tests.
5. Prepare a pull request with a clear summary and test evidence.

### Testing Requirements

Always add tests for new behavior and run relevant suites before considering work complete.

- TypeScript/React changes: run workspace tests (`pnpm -r test`) or `make test`
- Python PCC changes: run `cd services/pcc && uv run pytest`
- Contract/schema changes: run `packages/contracts` vitest suite

For PCC service work, prioritize tests for:

- Pipeline processor logic (transcript, process LLM output parsing, suggestion LLM output parsing)
- RTVI bot-action payload shape and validation (`transcript_segment`, `process_illustration`, `agent_guidance`)
- Process catalog loading and prompt/catalog alignment for process identification

For Next.js apps, prioritize tests for:

- Component rendering and state management
- RTVI message handling and Supabase Realtime subscription logic
- Schema validation with Zod

## Architecture

### High-Level Flow

```text
Daily.co WebRTC → Deepgram STT → Pipecat Pipeline (PCC) → RTVI / Supabase Realtime → Next.js UIs
```

The PCC bot is listen-only (`audio_out_enabled=False`). It never speaks; it emits guidance events.

Realtime channels:

- RTVI (WebRTC data channel): transcript segments, process illustrations, suggestions
- Supabase Realtime: session lifecycle updates (pending/active/completed) and pending-call notifications

### Component Responsibilities

#### Agent Workspace (`apps/agent-workspace`)

- Phase-based UI:
  - `idle`
  - `incoming`
  - `active_preprocess`
  - `active_inprocess`
  - `postcall_summary`
- Accepts pending sessions via Supabase (updates status to active)
- Connects to Daily.co room via @pipecat-ai/client-js RTVI client
- Receives RTVI actions:
  - `transcript_segment`
  - `process_illustration`
  - `agent_guidance`
- Fetches customer profile/interactions from Supabase when `customer_id` exists
- API routes for postcall summary save and AI generation
- Includes `/admin` route with session list + session transcript/detail inspector

#### Customer App (`apps/customer`)

- Customer flow states: `idle → calling → connected → ended`
- Starts calls via `POST /api/sessions/create` (optional `customer_id`)
- API route creates PCC bot, Daily tokens, and pending session in Supabase
- Watches session status via Supabase Realtime to detect agent join/end
- Connects to Daily room audio using `@daily-co/daily-js`

#### PCC Service (`services/pcc`)

- Stateless Pipecat Cloud bot using standard runner pattern
- Entry point: `bot.py` with `RunnerArguments`
- Local dev: `python bot.py -t daily --port 7860` (HTTP server with `/start` endpoint)
- Production: `pipecat cloud deploy`
- Pipeline: `transport.input() -> DeepgramSTTService -> ParallelPipeline(...) -> transport.output()`
- Parallel branches:
  1. Transcript branch: `TranscriptWriter` emits `transcript_segment`
  2. Process branch: `LLMContextAggregatorPair.user()` -> `OpenAILLMService(PROCESS_MODEL)` -> `ProcessOutputProcessor` emits `process_illustration`
  3. Suggestion branch: `LLMContextAggregatorPair.user()` -> `OpenAILLMService(SUGGESTION_MODEL)` -> `SuggestionOutputProcessor` emits `agent_guidance`
- Shared STT + parallel branches keep transcript delivery low-latency while LLM branches run concurrently

## Database Schema

Migrations (in `supabase/migrations/`):

- `001_initial_schema.sql` — sessions, transcript_segments, process_catalog
- `002_customers.sql` — customers, customer_interactions
- `003_add_session_summary.sql` — summary fields on sessions
- `004_customers_rls.sql` — Row-level security for customers
- `005_update_suggestion_service_modes.sql` — Update service type column
- `006_add_agent_token.sql` — Add agent_token to sessions

Primary tables:

- `sessions` — status, room_url, room_name, agent_token, state (JSONB), timestamps
- `transcript_segments` — session_id, speaker, text, is_final, timestamps
- `process_catalog` — process_key, name, domain, status, version
- `customers` — id, name, classification, email
- `customer_interactions` — session_id, customer_id, interaction_type

Session statuses: `pending` → `active` → `completed` / `abandoned` / `escalated` / `error`

Supabase Realtime enabled on `sessions` and `transcript_segments`.

## Contracts and RTVI Actions

### Shared Contracts (`packages/contracts`)

- Zod schemas for RTVI events (`agent_guidance`, `process_illustration`, `transcript_segment`)
- DTO schemas for session lifecycle, summary updates, and customer data
- Cross-package TypeScript type source of truth

- Runtime payloads emitted by PCC are RTVI bot-action messages:
  - `transcript_segment`
  - `process_illustration`
  - `agent_guidance`

## Process Catalog

Process markdown content lives in `services/pcc/process_content/`.

- Files use YAML frontmatter (`process_key`, `name`, `domain`, `intents`)
- Steps are parsed from `## Step N: ...` headings
- Repository currently contains 9 process content markdown files
- Detection is catalog-informed and LLM-evaluated (`PROCESS_MODEL`, default `gpt-4.1-nano`)

## Key Design Patterns

- **Listen-only bot**: No audio output from PCC service.
- **Async transcript persistence**: Transcript rows are written to Supabase in background batches so live guidance remains low-latency.
- **Decoupled flows**: Transcript, process identification, and suggestion generation run as independent branches after shared STT.
- **Parallel processing**: Suggestions run in a ParallelPipeline branch to avoid blocking transcript delivery.
- **RTVI-first for live guidance**: Low-latency messages over WebRTC data channel.
- **Session management in Next.js**: API routes in customer app handle room creation and session insertion.

## Environment Variables

### Agent Workspace (`apps/agent-workspace/.env.local`)

```bash
NEXT_PUBLIC_SUPABASE_URL
NEXT_PUBLIC_SUPABASE_ANON_KEY
SUPABASE_SERVICE_ROLE_KEY
OPENAI_API_KEY              # For AI-generated postcall summaries
```

### Customer App (`apps/customer/.env.local`)

```bash
NEXT_PUBLIC_SUPABASE_URL
NEXT_PUBLIC_SUPABASE_ANON_KEY
SUPABASE_SERVICE_ROLE_KEY
PCC_AGENT_URL=http://localhost:7860
DAILY_API_KEY
PIPECAT_CLOUD_API_KEY       # Optional, for cloud deployment
```

### PCC Service (`services/pcc/.env`)

```bash
DAILY_API_KEY
DEEPGRAM_API_KEY
OPENAI_API_KEY
SUPABASE_URL
SUPABASE_SERVICE_ROLE_KEY
PIPECAT_CLOUD_API_KEY       # Optional, for cloud deployment
SUGGESTION_MODEL            # Optional, default: gpt-4.1
```

## Common Gotchas

- Python must be 3.13+; Node must be 24+; pnpm must be 10+.
- Supabase CLI is required for migration/reset commands.
- Daily rooms are ephemeral (1-hour expiry on room creation).
- PCC bot is listen-only (`audio_out_enabled=False`) and never speaks.
- PCC persists transcript segments asynchronously to Supabase while guidance flows via RTVI.
- Process identification uses OpenAI (`PROCESS_MODEL`, default `gpt-4.1-nano`) against the loaded process catalog.
- Summary save/generate is allowed for terminal statuses only (`completed`, `abandoned`, `escalated`).
- Next.js 16 async params: Route params are Promises and must be awaited in App Router API routes.
