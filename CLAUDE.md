# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

VoiceBridge is a proactive guidance workspace for live human-human customer service calls. It listens to conversations via WebRTC, uses LLMs to detect processes, track step progress, and provide real-time suggestions to agents. The system consists of a Customer App, an Agent Workspace, and one unified Pipecat service with three parallel branches (transcript, process, suggestion). All user-facing UI, experiment content (personas, scenarios, process definitions, knowledge base), and LLM prompts are in **German**.

## Development Commands

### Setup

```bash
make install              # Install all dependencies (pnpm + uv for unified PCC)
make db-migrate          # Run Supabase migrations
```

### Development

```bash
make dev                 # Run all 3 services (agent-workspace + customer + unified PCC)
make web-dev             # Agent workspace only (port 3000)
make customer-dev        # Customer app only (port 3001)
make pcc-dev             # Unified PCC service only (port 7860)
```

### Testing & Quality

```bash
make test               # Run all tests (vitest + pytest for unified PCC)
make lint               # Lint TypeScript (eslint) and Python (ruff)
make typecheck          # TypeScript type checking
make format             # Format code (prettier + ruff)
```

### PCC-Specific Commands

```bash
# Unified PCC service
cd services/pcc && uv run pytest              # Run tests
cd services/pcc && uv run ruff check .        # Lint
```

### Database

```bash
make db-reset           # Reset database to clean state
make db-migrate         # Push migrations (supabase db push)
```

## Development Practices

### Testing Requirements

- Always implement new features, changes etc. in a new branch that we can later merge with main once accepted
- Commit regularly and often

**Always write tests and run them when implementing features.** This is non-negotiable for verifying that implementations work correctly.

- **TypeScript/React**: Write tests for new components and utilities, run with `make test` or `pnpm test`
- **Python**: Write pytest tests for PCC processors and utilities, run with `cd services/pcc && uv run pytest`
- **Contracts**: The `packages/contracts` package has vitest tests for schema validation - run these when modifying schemas

After implementing a feature:

1. Write appropriate tests (unit tests for utilities, integration tests for processors)
2. Run the relevant test suite to verify functionality
3. Run the full test suite (`make test`) to ensure no regressions
4. Only consider the feature complete after tests pass

For the PCC service, tests should cover:

- Pipeline processor logic (transcript, process LLM output parsing, suggestion LLM output parsing)
- RTVI bot-action payload shape and validation (`transcript_segment`, `process_illustration`, `agent_guidance`)
- Process catalog loading and prompt/catalog alignment for process identification

For the Next.js apps, tests should cover:

- Component rendering and state management
- RTVI message handling and Supabase Realtime subscription logic
- Schema validation with Zod

## Architecture

### High-Level Data Flow

```
                                  ┌─ Transcript branch → RTVI (transcript_segment)
Daily.co WebRTC → Unified PCC ───┼─ Process branch    → RTVI (process_illustration)
(same room)       (shared STT)   └─ Suggestion branch → RTVI (agent_guidance)

Supabase Realtime → Agent Workspace (session state only)
```

The system operates one **listen-only voice pipeline** with three parallel branches after shared STT. Real-time data is delivered via two channels:

- **RTVI (WebRTC data channel)**: Suggestions, process illustrations, and transcript segments (low latency)
- **Supabase Realtime**: Session state changes and pending session notifications (agent workspace only)

### Component Responsibilities

**Agent Workspace** (`apps/agent-workspace/`)

- **Phase-based procedural UI** that adapts to the current call state, showing only contextually relevant information:
  - **Idle**: Waiting screen for incoming calls
  - **Incoming**: Customer info + accept/reject interface
  - **Active (Pre-process)**: Customer info + transcript + suggestions (process detection in progress)
  - **Active (In-process)**: Full 4-panel workspace - customer info, transcript, suggestions, process visualization
  - **Postcall Summary**: Transcript review + AI-generated summary editor, auto-returns to idle after save
- Incoming call notification via Supabase Realtime subscription on `sessions` table (pending status)
- Connects to Daily.co room via `@pipecat-ai/client-js` RTVI client
- Receives RTVI messages from unified PCC branches: `agent_guidance`, `process_illustration`, `transcript_segment`
- Session management: accept pending sessions, stop active sessions

**Customer App** (`apps/customer/`)

- Customer-facing call interface (idle → calling → connected → ended)
- Selection/briefing flow with domain-compatible persona+scenario pairing and actor guidance references
- Creates bot sessions by starting the unified PCC service
- Connects to Daily.co room with audio via `@daily-co/daily-js`

**Unified PCC Service** (`services/pcc/`)

- Single listen-only bot with one Daily transport and one Deepgram STT stream
- Pipeline: `transport.input() → DeepgramSTT → ParallelPipeline(...) → transport.output()`
- Parallel branches:
  - Transcript branch emits `transcript_segment`
  - Process branch emits `process_illustration`
  - Suggestion branch emits `agent_guidance`
- Bot name: `VoiceBridge`

**Shared Contracts** (`packages/contracts/`)

- Zod schemas for RTVI messages: `RTVISuggestionMessageSchema`, `RTVIProcessIllustrationMessageSchema`, `RTVITranscriptSegmentMessageSchema`
- Discriminated union: `RTVIMessageSchema` (on `action` field)
- Zod schemas for DTOs (session config, process lookup, etc.)
- Single source of truth for TypeScript types

**Database Package** (`packages/db/`)

- Supabase client wrapper
- Query helpers for sessions, customers, and interactions

### Session Creation Flow

```
POST /api/sessions/create
  → Validate selected customer_id + scenario_id
  → POST pcc/start  { createDailyRoom: true, body: { session_id, metadata } }  ← creates room + starts branches
  → Create Daily tokens (customer + agent)
  → Insert pending session into Supabase with scenario metadata
  ← { session_id, room_url, customer_token }
```

### Database Schema

Migrations (in `supabase/migrations/`):

- `001_initial_schema.sql` — sessions, transcript_segments, process_catalog
- `002_customers.sql` — customers, customer_interactions
- `003_add_session_summary.sql` — summary fields on sessions
- `004_customers_rls.sql` — Row-level security for customers
- `005_update_suggestion_service_modes.sql` — Update service type column
- `006_add_agent_token.sql` — Add agent_token to sessions
- `007_experiment_schema.sql` — scenarios, session_events, and experiment metadata columns
- `008_drop_legacy_process_catalog.sql` — remove DB-backed process_catalog table
- `009_cross_combinable_experiments.sql` — add `customers.domain` and `scenarios.actor_guidance`

Key tables:

- `sessions`: Session state (JSONB), status, room URL/name, `customer_id`, `scenario_id`, scenario metadata, timestamps
- `transcript_segments`: STT output segments by speaker (agent/customer)
- `customers`: Persona-backed customer profiles (includes `domain`)
- `customer_interactions`: Historical interaction context linked to customers
- `scenarios`: Scenario catalog for experiment selection (includes optional `actor_guidance`)
- `session_events`: Experiment telemetry events

Session statuses: `pending` → `active` → `completed` / `abandoned` / `escalated` / `error`

Supabase Realtime enabled on `sessions` and `transcript_segments`.

### RTVI Actions

The unified service emits three RTVI action payloads:

- `transcript_segment`
- `process_illustration`
- `agent_guidance`

### Process Catalog

Process definitions (in German) are loaded from markdown files under `services/pcc/process_content/`. Each file uses YAML frontmatter (`process_key`, `name`, `domain`, `intents`) and `## Step N: Label` headings for step extraction. Current definitions: `bank_unauth_transaction`, `bank_credit_denial`, `insurance_unauth_claim`, `insurance_claim_denial`.

Supporting knowledge base articles (in German) are in `services/pcc/kb_content/`, one per process scenario.

## Key Design Patterns

### Parallel Branches In One Agent

Transcript, process detection, and suggestion generation run as parallel branches in one bot process after a shared STT stage. This removes room orchestration complexity and duplicate STT connections.

### Listen-Only Bot

The unified PCC service is configured as listen-only (`audio_out_enabled=False`). It does not respond verbally — it only publishes events to guide human agents.

### LLM Branches For Process + Suggestion

The process and suggestion branches each use their own LLM context aggregator and model invocation chain downstream of shared STT.

### RTVI Over Supabase Realtime

Suggestions, process illustrations, and transcript segments are delivered via RTVI (WebRTC data channel) for sub-second latency. Supabase Realtime is used only for session state changes and pending session notifications.

### Type Safety Across Languages

TypeScript Zod schemas in `packages/contracts` define the contract. Python code maintains compatible JSON structures (validated at runtime, not type-checked).

### Monorepo Structure

- pnpm workspaces for TypeScript packages
- uv for Python dependency management (unified PCC venv)
- Makefile coordinates cross-language operations

## Pipecat Framework Reference

### Core Concepts

- **Frames**: Units of data flowing through the pipeline (audio, text, control).
- **FrameProcessors**: Transform or react to frames. Must call `super().__init__()`, `await super().process_frame()`, and always `push_frame()` to avoid blocking the pipeline.
- **Pipeline / PipelineTask / PipelineRunner**: Pipeline defines processor chain; PipelineTask wraps it for execution; PipelineRunner manages the event loop.

### RTVI

- Branch processors emit `RTVIServerMessageFrame` payloads as `bot-action` events.
- The agent workspace receives transcript, process, and suggestion actions from one bot.

### Design Principle

Always prefer Pipecat abstractions (processors, pipeline, RTVI) over custom transport. Suggestions, process illustrations, and transcripts are sent to the client via RTVI — not written to Supabase for realtime pickup. Supabase Realtime is reserved for session state changes.

## Environment Variables

### Required for Agent Workspace

```
NEXT_PUBLIC_SUPABASE_URL
NEXT_PUBLIC_SUPABASE_ANON_KEY
SUPABASE_SERVICE_ROLE_KEY
```

### Required for Customer App

```
NEXT_PUBLIC_SUPABASE_URL
NEXT_PUBLIC_SUPABASE_ANON_KEY
PCC_AGENT_URL                         # default: http://localhost:7860
DAILY_API_KEY
```

### Required for Unified PCC Service

```
DAILY_API_KEY
DEEPGRAM_API_KEY
OPENAI_API_KEY
PROCESS_MODEL                         # default: gpt-4.1-nano
SUGGESTION_MODEL                      # default: gpt-4.1
```

### Optional (unified PCC)

```
PIPECAT_CLOUD_API_KEY                 # Required for production deployment
```

## Common Gotchas

- **Python version**: Must use Python 3.13+ (specified in pyproject.toml)
- **Node version**: Must use Node 24+ (see .nvmrc)
- **Supabase CLI**: Database migrations require Supabase CLI to be installed
- **Daily.co rooms**: Sessions create ephemeral rooms with 1-hour expiry
- **VAD tuning**: Silero VAD parameters (`start_secs`, `stop_secs`) affect responsiveness vs. false positives
- **Agent Invocation**:
  - Unified PCC service uses `RunnerArguments` (Pipecat runner pattern)
  - Local dev: `python bot.py -t daily --port 7860` starts HTTP server with `/start` endpoint
  - Customer app starts one bot with `createDailyRoom: true`
  - Production: `pipecat cloud deploy` for the unified service
- **Session State Validation**:
  - Agent workspace checks localStorage on mount and validates against database
  - Terminal states (completed/abandoned/escalated/error) clear localStorage automatically
  - Stale sessions (>1 hour old) are cleared on restoration
  - Only truly active sessions with complete data (room_url, agent_token) are restored
- **Phase-based UI**: Agent workspace adapts its layout based on call state (idle → incoming → active-preprocess → active-inprocess → postcall), showing only relevant information for the current phase
- **Next.js 16 Async Params**: Route params are Promises and must be awaited before access in App Router API routes
- **PCC startup failures**: Session creation fails fast if the unified PCC `/start` call cannot return `dailyRoom` and `dailyToken`
