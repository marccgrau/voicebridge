# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

VoiceBridge is a proactive guidance workspace for live human-human customer service calls. It listens to conversations via WebRTC, uses LLMs to detect processes, track step progress, and provide real-time suggestions to agents. The system consists of a Customer App, an Agent Workspace, and a Pipecat Cloud (PCC) Service connected through Daily.co WebRTC rooms.

## Development Commands

### Setup
```bash
make install              # Install all dependencies (pnpm + uv)
make db-migrate          # Run Supabase migrations
```

### Development
```bash
make dev                 # Run all services (agent-workspace + customer + pcc)
make web-dev             # Agent workspace only (port 3000)
make customer-dev        # Customer app only (port 3001)
make pcc-dev             # PCC service only (port 7860)
```

### Testing & Quality
```bash
make test               # Run all tests (vitest + pytest)
make lint               # Lint TypeScript (eslint) and Python (ruff)
make typecheck          # TypeScript type checking
make format             # Format code (prettier + ruff)
```

### PCC Service Specific
```bash
cd services/pcc
uv run python bot.py -t daily --port 7860      # Run PCC local dev server (port 7860)
uv run pytest                                  # Run Python tests
uv run ruff check .                            # Lint Python code
uv run ruff format .                           # Format Python code
```

### Database
```bash
make db-reset           # Reset database to clean state
make db-migrate         # Push migrations (supabase db push)
```

## Development Practices

### Testing Requirements

**Always write tests and run them when implementing features.** This is non-negotiable for verifying that implementations work correctly.

- **TypeScript/React**: Write tests for new components and utilities, run with `make test` or `pnpm test`
- **Python**: Write pytest tests for new processors and utilities, run with `cd services/pcc && uv run pytest`
- **Contracts**: The `packages/contracts` package has vitest tests for schema validation - run these when modifying schemas

After implementing a feature:
1. Write appropriate tests (unit tests for utilities, integration tests for processors)
2. Run the relevant test suite to verify functionality
3. Run the full test suite (`make test`) to ensure no regressions
4. Only consider the feature complete after tests pass

For the PCC service, tests should cover:
- Pipeline processor logic (transcript writing, process detection, suggestion generation)
- Custom frame emission and handling
- RTVI message delivery via VoiceBridgeRTVIObserver

For the Next.js apps, tests should cover:
- Component rendering and state management
- RTVI message handling and Supabase Realtime subscription logic
- Schema validation with Zod

## Architecture

### High-Level Data Flow

```
Daily.co WebRTC → Deepgram STT → Pipecat Pipeline (PCC) → RTVI / Supabase Realtime → Next.js UI
```

The system operates as a **listen-only voice pipeline** that processes audio without responding verbally. All real-time data is delivered to the agent workspace via two channels:
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
- Receives RTVI messages: `agent_guidance`, `process_illustration`, `transcript_segment`
- Session management: accept pending sessions, stop active sessions

**Customer App** (`apps/customer/`)
- Customer-facing call interface (idle → calling → connected → ended)
- Creates bot sessions via `POST ${PCC_AGENT_URL}/start` with session metadata
- Connects to Daily.co room with audio via `@daily-co/daily-js`

**PCC Service** (`services/pcc/`)
- Pipecat service handling multi-session voice processing
- **Standard invocation**: Uses `RunnerArguments` (Pipecat runner pattern)
- **Local dev**: `python bot.py -t daily --port 7860` runs HTTP server on port 7860 with `/start` endpoint
- **Production**: `pipecat cloud deploy` deploys to Pipecat Cloud infrastructure
- **Multi-session support**: Each `/start` call creates a new bot instance
- Pipecat pipeline with custom FrameProcessors:
  1. **TranscriptWriter**: Emits `TranscriptSegmentFrame` with live STT output
  2. **ProcessDetectionProcessor**: Catalog-based process matching; emits `ProcessIllustrationFrame`
  3. **SuggestionContextBuilder**: Builds context for LLM suggestion generation
  4. **SuggestionOutputProcessor**: LLM-driven suggestion generation; emits `SuggestionFrame`
  5. **VoiceBridgeRTVIObserver**: Intercepts custom frames and publishes them to the frontend via RTVI `bot-action` messages with retry logic

**Shared Contracts** (`packages/contracts/`)
- Zod schemas for RTVI messages: `RTVISuggestionMessageSchema`, `RTVIProcessIllustrationMessageSchema`, `RTVITranscriptSegmentMessageSchema`
- Discriminated union: `RTVIMessageSchema` (on `action` field)
- Zod schemas for DTOs (session config, process lookup, etc.)
- Single source of truth for TypeScript types

**Database Package** (`packages/db/`)
- Supabase client wrapper
- Query helpers for sessions, transcripts, processes

### Database Schema

Single migration: `001_initial_schema.sql`

Key tables:
- `sessions`: Session state (JSONB), status, room URL/name, timestamps, error tracking
- `transcript_segments`: STT output segments by speaker (agent/customer)
- `process_catalog`: Process definitions with full-text search via `pg_trgm` (seeded with 5 processes)

Session statuses: `pending` → `active` → `completed` / `abandoned` / `escalated` / `error`

Supabase Realtime enabled on `sessions` and `transcript_segments`.

### Custom Frames

Three custom Pipecat frames carry domain data through the pipeline:
- `SuggestionFrame`: suggestions array, service_type, latency_ms, process_key, tools_used
- `ProcessIllustrationFrame`: process_key, process_name, steps (with status), current_step, content
- `TranscriptSegmentFrame`: session_id, speaker, text, timestamp, is_final

### Process Catalog

Process definitions are loaded from markdown files in `process_content/`. Each file uses YAML frontmatter (`process_key`, `name`, `domain`, `intents`) and `## Step N: Label` headings for step extraction.

## Key Design Patterns

### Listen-Only Bot
The Pipecat pipeline is configured as listen-only (`audio_out_enabled=False`). It does not respond verbally — only publishes events to guide human agents.

### Decoupled Flows
ProcessFlow and SuggestionFlow communicate only via frames in the pipeline. SuggestionFlow listens for `ProcessIllustrationFrame` to get process context, but has no direct reference to ProcessFlow.

### Isolated LLM Pipelines
Each FlowManager (ProcessFlow and SuggestionFlow) has its own LLM pipeline running in a background `asyncio.Task` via `PipelineRunner`. This prevents LLM calls from blocking the main audio pipeline.

### RTVI Over Supabase Realtime
Suggestions, process illustrations, and transcript segments are delivered via RTVI (WebRTC data channel) for sub-second latency. Supabase Realtime is used only for session state changes and pending session notifications.

### Type Safety Across Languages
TypeScript Zod schemas in `packages/contracts` define the contract. Python code maintains compatible JSON structures (validated at runtime, not type-checked).

### Monorepo Structure
- pnpm workspaces for TypeScript packages
- uv for Python dependency management
- Makefile coordinates cross-language operations

## Pipecat Framework Reference

### Core Concepts
- **Frames**: Units of data flowing through the pipeline (audio, text, custom). Custom frames carry domain-specific data.
- **FrameProcessors**: Transform or react to frames. Must call `super().__init__()`, `await super().process_frame()`, and always `push_frame()` to avoid blocking the pipeline.
- **Pipeline / PipelineTask / PipelineRunner**: Pipeline defines processor chain; PipelineTask wraps it for execution; PipelineRunner manages the event loop.

### Pipecat Flows (FlowManager)
- `FlowManager` manages node-based conversation state for LLM-driven processors.
- Nodes have `role_messages`, `task_messages`, `functions`, `pre_actions`, and `post_actions`.
- Function handlers return `(result, next_node)` to drive state transitions.
- Shared state is available via `flow_manager.state` — used to pass context between nodes.
- Both `ProcessFlow` and `SuggestionFlow` use this pattern.

### RTVI
- `RTVIProcessor` + `RTVIObserver` are registered on the PipelineTask.
- Custom messages are sent via `rtvi_processor.send_server_message()` as `bot-action` events.
- `VoiceBridgeRTVIObserver` intercepts `SuggestionFrame` (action=`agent_guidance`), `ProcessIllustrationFrame` (action=`process_illustration`), and `TranscriptSegmentFrame` (action=`transcript_segment`) and delivers them to the frontend.
- Messages include retry logic (configurable max retries, 0.2s base delay).

### Design Principle
Always prefer Pipecat abstractions (frames, processors, RTVI) over custom transport. Suggestions, process illustrations, and transcripts flow through the pipeline as custom frames and are sent to the client via RTVI — not written to Supabase for realtime pickup. Supabase Realtime is reserved for session state changes.

## Environment Variables

### Required for Agent Workspace
```
NEXT_PUBLIC_SUPABASE_URL
NEXT_PUBLIC_SUPABASE_ANON_KEY
SUPABASE_SERVICE_ROLE_KEY
NEXT_PUBLIC_ORCHESTRATOR_URL          # default: http://localhost:8000
```

### Required for Customer App
```
NEXT_PUBLIC_SUPABASE_URL
NEXT_PUBLIC_SUPABASE_ANON_KEY
PCC_AGENT_URL                         # default: http://localhost:7860 (PCC local dev)
```

### Required for PCC Service
```
DAILY_API_KEY                         # Daily.co API key for room creation
DEEPGRAM_API_KEY                      # Deepgram STT API key
OPENAI_API_KEY                        # OpenAI API key for LLM suggestions

# Optional: Pipecat Cloud configuration
PIPECAT_CLOUD_API_KEY                 # Required for production deployment (pipecat cloud deploy)
PORT                                  # Local dev server port (default: 7860)
SUGGESTION_MODEL                      # Override LLM model (default: gpt-4.1)
```

## Common Gotchas

- **Python version**: Must use Python 3.13+ (specified in pyproject.toml)
- **Node version**: Must use Node 24+ (see .nvmrc)
- **Supabase CLI**: Database migrations require Supabase CLI to be installed
- **Daily.co rooms**: Sessions create ephemeral rooms with 1-hour expiry
- **VAD tuning**: Silero VAD parameters (`start_secs`, `stop_secs`) affect responsiveness vs. false positives
- **PCC Standard Invocation**:
  - Bot entry point uses `RunnerArguments` (Pipecat runner pattern)
  - Local dev: `python bot.py -t daily --port 7860` starts HTTP server on port 7860 with `/start` endpoint
  - Production: `pipecat cloud deploy` requires `PIPECAT_CLOUD_API_KEY`
  - Multi-session support: Each `/start` call creates a new bot instance
  - The Pipecat runner automatically creates a FastAPI server with `/start` endpoint
- **Session State Validation**:
  - Agent workspace checks localStorage on mount and validates against database
  - Terminal states (completed/abandoned/escalated/error) clear localStorage automatically
  - Stale sessions (>1 hour old) are cleared on restoration
  - Only truly active sessions with complete data (room_url, agent_token) are restored
- **Phase-based UI**: Agent workspace adapts its layout based on call state (idle → incoming → active-preprocess → active-inprocess → postcall), showing only relevant information for the current phase
- **Next.js 16 Async Params**: Route params are Promises and must be awaited before access in App Router API routes
