# VoiceBridge

VoiceBridge is a proactive guidance workspace for live human-human customer service calls. It listens to conversations over WebRTC, uses LLM flows to detect processes and track progress, and delivers real-time Process-Pilot advice to agents. The UI and all experiment content (personas, scenarios, process definitions, knowledge base) are in **German**.

## Monorepo Layout

```
voicebridge/
├── apps/
│   ├── agent-workspace/     # Next.js agent UI (port 3000)
│   └── customer/            # Next.js customer UI (port 3001)
├── services/
│   └── pcc/                 # Pipecat Cloud voice pipeline (port 7860)
├── packages/
│   ├── contracts/           # Shared Zod schemas and TypeScript types
│   └── db/                  # Supabase query helpers
└── supabase/
    └── migrations/          # Database migrations (001–009)
```

## High-Level Flow

```text
Daily.co WebRTC → Deepgram STT → Speaker Labeling → Pipecat Pipeline (PCC) → RTVI + Supabase Realtime → Next.js UIs
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
make db-seed-experiment   # seed personas + scenarios into local DB
make db-seed-experiment-linked  # seed personas + scenarios into linked remote DB
```

## Experimental Persona + Scenario Flow

Experiment data is file-defined in the repository, seeded into Supabase, then loaded by the customer and agent apps at runtime.

1. **Define personas** in `personas/customer_profile_*.json`.
   - Each file contains `customer_profile`, `case_context`, and `interaction_history`.
2. **Define scenarios** in `scenarios/scenario_*.json`.
   - Each file contains `scenario_id`, `background`, `customer_goal`, `conversation[]`, `behavioral_condition`, and optional `actor_guidance`.
   - Denial scenarios should name denied request(s) explicitly in opening turns to avoid ambiguity for participants.
3. **Seed to Supabase** via `make db-seed-experiment` (local) or `make db-seed-experiment-linked` (linked remote).
   - Seeder script: `scripts/seed-experimental-data.mjs`.
   - Writes to `customers`, `customer_interactions`, and `scenarios`.
4. **Load in customer app** from Supabase at runtime.
   - `apps/customer/src/lib/use-customers.ts` fetches persona rows from `customers`.
   - `apps/customer/src/lib/use-scenarios.ts` fetches active scenarios from `scenarios`, including behavioral cues and actor guidance.
   - `apps/customer/src/lib/scenario-render.ts` resolves placeholders (for example `{{customer_name}}`) in scenario script text.
   - Selection is domain-compatible (`customers.domain` ↔ `scenarios.domain`) so actors can mix personas/scenarios within the same domain.
5. **Create call session** with selected persona + scenario.
   - `apps/customer/app/api/sessions/create/route.ts` validates both IDs, inserts a `pending` session, and stores scenario metadata (`scenario_id`, `scenario_family`, `civility_condition`) on the session row and in `sessions.state`.

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

- `POST /api/sessions/create` — Customer-initiated session (requires `customer_id` + `scenario_id`, creates Daily room via PCC, passes `customer_id`/`customer_name` in bot metadata, generates Daily tokens with `user_name` for speaker identification, stores pending session in Supabase with routing handoff context and scenario metadata)

### Agent Workspace API Routes

- `POST /api/sessions/summary` — Save agent's postcall summary
- `POST /api/sessions/[sessionId]/generate-summary` — Generate AI summary from transcript via OpenAI

### Agent Workspace Data Access

- Reads session data directly from Supabase (room_url, agent_token, customer/routing metadata in `sessions.state`)
- Updates session status via Supabase (pending → active, active → completed)

## PCC Service Architecture

`services/pcc/` is a stateless Pipecat Cloud bot:

- `bot.py` — Entry point with full pipeline wiring
- `src/transcript_processors.py` — Speaker labeling (`SpeakerLabelingProcessor`) + transcript branch RTVI emission
- `src/process_processors.py` — Process branch LLM output parsing + RTVI emission (speaker-aware prompt)
- `src/suggestion_processors.py` — Process-Pilot advice branch: LLM output parsing + RTVI emission (scenario-aware prompt with process definition + KB)
- `src/process_catalog.py` — Process loading and matching

Pipeline branches emit RTVI bot-action messages:

- `transcript_segment` — Live transcript segment
- `process_illustration` — Detected process with step progress
- `agent_guidance` — Process-Pilot advice for the agent

All live guidance messages are delivered via RTVI (WebRTC data channel) for sub-second latency.

## Database

### Migrations

- `001_initial_schema.sql` — sessions, transcript_segments, process_catalog
- `002_customers.sql` — customers, customer_interactions tables
- `003_add_session_summary.sql` — summary fields on sessions
- `004_customers_rls.sql` — Row-level security for customers
- `005_update_suggestion_service_modes.sql` — Update service type column
- `006_add_agent_token.sql` — Add agent_token to sessions
- `007_experiment_schema.sql` — scenarios catalog, session_events, and experiment metadata columns
- `008_drop_legacy_process_catalog.sql` — remove DB-backed process_catalog in favor of markdown process definitions
- `009_cross_combinable_experiments.sql` — add `customers.domain` and `scenarios.actor_guidance` for cross-combinable experiment briefings

### Primary Tables

- `sessions` — Session state (JSONB), status, room URL/name, agent_token, selected `customer_id` + `scenario_id`, timestamps
- `transcript_segments` — STT output segments by speaker (agent/customer)
- `customers` — Persona-backed customer profiles shown in customer/agent UIs (includes `domain` for scenario filtering)
- `customer_interactions` — Historical interaction context used in pre-call briefing
- `scenarios` — Experiment scenario catalog (background, goal, conversation, civility condition, actor guidance)
- `session_events` — Experiment telemetry events (for example actor step toggles)

### Session Statuses

`pending` → `active` → `completed` / `abandoned` / `escalated` / `error`

Summary save/generate is allowed for terminal statuses only: `completed`, `abandoned`, `escalated`.

## Process Definitions

Process definitions live in `services/pcc/process_content/` and knowledge base articles in `services/pcc/kb_content/` (all in German).

Current process definitions:

- `bank_unauth_transaction` — Unautorisierte Bankbuchung
- `bank_credit_denial` — Kreditantrag abgelehnt
- `insurance_unauth_claim` — Unautorisierter Versicherungsanspruch
- `insurance_claim_denial` — Versicherungsantrag abgelehnt

Each file uses YAML frontmatter (`process_key`, `name`, `domain`, `intents`) and `## Step N: ...` headings.
Catalog content is embedded into the process-LLM system prompt (`PROCESS_MODEL`).
`PROCESS_CONTENT_PATH` can override the default markdown directory.

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
- Speaker diarization uses Daily participant tracking (`on_participant_joined`) + `user_name` tokens ("Kunde"/"Berater") to map `TranscriptionFrame.user_id` to roles. Transcript entries are prefixed `[Kunde]`/`[Berater]` for both LLM branches.
- Process identification uses an OpenAI model (`PROCESS_MODEL`, default `gpt-4.1-nano`).
- Advice generation (Process-Pilot) uses OpenAI `gpt-4.1` by default (configurable via `SUGGESTION_MODEL`).
- Node must be 24+, Python must be 3.13+, pnpm must be 10+.

## Further Reading

- [Architecture Guide](./ARCHITECTURE.md) — Detailed system architecture, data flows, and design patterns
- [Agent Workspace](./apps/agent-workspace/README.md) — Phase-based agent UI documentation
- [Customer App](./apps/customer/README.md) — Customer call interface documentation
- [PCC Service](./services/pcc/README.md) — Voice pipeline service documentation
