# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

VoiceBridge is a proactive guidance workspace for live human-human customer service calls. It listens to conversations via WebRTC, uses LLMs to detect processes, track step progress, and provide real-time suggestions to agents. The system consists of a Customer App, an Agent Workspace, and three independent Pipecat agents (Transcript, Process, Suggestion) connected through Daily.co WebRTC rooms.

## Development Commands

### Setup
```bash
make install              # Install all dependencies (pnpm + uv for all agents)
make db-migrate          # Run Supabase migrations
```

### Development
```bash
make dev                 # Run all 5 services (agent-workspace + customer + 3 agents)
make web-dev             # Agent workspace only (port 3000)
make customer-dev        # Customer app only (port 3001)
make transcript-agent-dev   # Transcript agent only (port 7860)
make process-agent-dev      # Process agent only (port 7861)
make suggestion-agent-dev   # Suggestion agent only (port 7862)
```

### Testing & Quality
```bash
make test               # Run all tests (vitest + pytest for all 3 agents)
make lint               # Lint TypeScript (eslint) and Python (ruff)
make typecheck          # TypeScript type checking
make format             # Format code (prettier + ruff)
```

### Agent-Specific Commands
```bash
# Transcript Agent
cd services/transcript-agent && uv run pytest           # Run tests
cd services/transcript-agent && uv run ruff check .     # Lint

# Process Agent
cd services/process-agent && uv run pytest              # Run tests
cd services/process-agent && uv run ruff check .        # Lint

# Suggestion Agent
cd services/suggestion-agent && uv run pytest           # Run tests
cd services/suggestion-agent && uv run ruff check .     # Lint
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
- **Python**: Write pytest tests for new processors and utilities, run with `cd services/<agent> && uv run pytest`
- **Contracts**: The `packages/contracts` package has vitest tests for schema validation - run these when modifying schemas

After implementing a feature:
1. Write appropriate tests (unit tests for utilities, integration tests for processors)
2. Run the relevant test suite to verify functionality
3. Run the full test suite (`make test`) to ensure no regressions
4. Only consider the feature complete after tests pass

For the agent services, tests should cover:
- Pipeline processor logic (transcript writing, process detection, suggestion generation)
- Custom frame emission and handling
- RTVI message delivery via agent-specific RTVI observers

For the Next.js apps, tests should cover:
- Component rendering and state management
- RTVI message handling and Supabase Realtime subscription logic
- Schema validation with Zod

## Architecture

### High-Level Data Flow

```
                                  ┌─ Transcript Agent → RTVI (transcript_segment)
Daily.co WebRTC → 3 Agents ──────┼─ Process Agent    → RTVI (process_illustration)
(same room)       (each w/ STT)  └─ Suggestion Agent → RTVI (agent_guidance)

Supabase Realtime → Agent Workspace (session state only)
```

The system operates three **independent listen-only voice pipelines** that process audio without responding verbally. All three agents join the same Daily.co room and run independent Deepgram STT. Real-time data is delivered via two channels:
- **RTVI (WebRTC data channel)**: Suggestions, process illustrations, and transcript segments (low latency) — each from a different agent
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
- Receives RTVI messages from all three agents: `agent_guidance`, `process_illustration`, `transcript_segment`
- Session management: accept pending sessions, stop active sessions

**Customer App** (`apps/customer/`)
- Customer-facing call interface (idle → calling → connected → ended)
- Creates bot sessions by starting all three agents sequentially/in parallel
- Connects to Daily.co room with audio via `@daily-co/daily-js`

**Transcript Agent** (`services/transcript-agent/`)
- Simplest agent — no LLM, no process catalog
- Pipeline: `transport.input() → DeepgramSTT → TranscriptWriter → TranscriptRTVIObserver → transport.output()`
- Creates the Daily.co room (called first with `createDailyRoom: true`)
- Emits `transcript_segment` RTVI messages
- Bot name: `VoiceBridge-Transcript`

**Process Agent** (`services/process-agent/`)
- LLM-based process detection with tool calling
- Pipeline: `transport.input() → DeepgramSTT → TranscriptWriter → ProcessContextBuilder → LLM (with tools) → ProcessOutputProcessor → ProcessRTVIObserver → transport.output()`
- Uses fast LLM (default: `gpt-4.1-nano`) with three tools: `list_processes`, `get_process_details`, `report_process_status`
- Emits `process_illustration` RTVI messages
- Bot name: `VoiceBridge-Process`

**Suggestion Agent** (`services/suggestion-agent/`)
- LLM-driven suggestion generation from transcript only (no process context)
- Pipeline: `transport.input() → DeepgramSTT → TranscriptWriter → SuggestionContextBuilder → OpenAILLMService → SuggestionOutputProcessor → SuggestionRTVIObserver → transport.output()`
- Generates 1 actionable suggestion per customer utterance
- Emits `agent_guidance` RTVI messages
- Bot name: `VoiceBridge-Suggestion`

**Shared Contracts** (`packages/contracts/`)
- Zod schemas for RTVI messages: `RTVISuggestionMessageSchema`, `RTVIProcessIllustrationMessageSchema`, `RTVITranscriptSegmentMessageSchema`
- Discriminated union: `RTVIMessageSchema` (on `action` field)
- Zod schemas for DTOs (session config, process lookup, etc.)
- Single source of truth for TypeScript types

**Database Package** (`packages/db/`)
- Supabase client wrapper
- Query helpers for sessions, transcripts, processes

### Session Creation Flow

```
POST /api/sessions/create
  → POST transcript-agent/start  { createDailyRoom: true, session_id }  ← creates room
  → POST process-agent/start     { dailyRoom: roomUrl, session_id }     ← joins room (parallel)
  → POST suggestion-agent/start  { dailyRoom: roomUrl, session_id }     ← joins room (parallel)
  → Create Daily tokens (customer + agent)
  → Insert pending session into Supabase
  ← { session_id, room_url, customer_token }
```

### Database Schema

Single migration: `001_initial_schema.sql`

Key tables:
- `sessions`: Session state (JSONB), status, room URL/name, timestamps, error tracking
- `transcript_segments`: STT output segments by speaker (agent/customer)
- `process_catalog`: Process definitions with full-text search via `pg_trgm` (seeded with 5 processes)

Session statuses: `pending` → `active` → `completed` / `abandoned` / `escalated` / `error`

Supabase Realtime enabled on `sessions` and `transcript_segments`.

### Custom Frames

Each agent defines its own frames (not shared across agents):
- `TranscriptSegmentFrame`: session_id, speaker, text, timestamp, is_final (all agents use internally)
- `SuggestionFrame`: suggestions array, service_type, tools_used (suggestion agent only)
- `ProcessIllustrationFrame`: process_key, process_name, steps (with status), current_step, content (process agent only)

### Process Catalog

Process definitions are loaded from markdown files in `services/process-agent/process_content/`. Each file uses YAML frontmatter (`process_key`, `name`, `domain`, `intents`) and `## Step N: Label` headings for step extraction. The process agent's LLM accesses the catalog via tool calling.

## Key Design Patterns

### Three Independent Agents
Each agent runs in its own process with its own STT, eliminating latency coupling between transcript delivery, process detection, and suggestion generation. All join the same Daily.co room.

### Listen-Only Bots
All three agents are configured as listen-only (`audio_out_enabled=False`). They do not respond verbally — only publish events to guide human agents.

### LLM Tool Calling (Process Agent)
The process agent uses a fast LLM with three tools (`list_processes`, `get_process_details`, `report_process_status`) to identify processes from the catalog. The `report_process_status` tool handler emits a `ProcessIllustrationFrame` downstream.

### RTVI Over Supabase Realtime
Suggestions, process illustrations, and transcript segments are delivered via RTVI (WebRTC data channel) for sub-second latency. Supabase Realtime is used only for session state changes and pending session notifications.

### Type Safety Across Languages
TypeScript Zod schemas in `packages/contracts` define the contract. Python code maintains compatible JSON structures (validated at runtime, not type-checked).

### Monorepo Structure
- pnpm workspaces for TypeScript packages
- uv for Python dependency management (each agent has its own venv)
- Makefile coordinates cross-language operations

## Pipecat Framework Reference

### Core Concepts
- **Frames**: Units of data flowing through the pipeline (audio, text, custom). Custom frames carry domain-specific data.
- **FrameProcessors**: Transform or react to frames. Must call `super().__init__()`, `await super().process_frame()`, and always `push_frame()` to avoid blocking the pipeline.
- **Pipeline / PipelineTask / PipelineRunner**: Pipeline defines processor chain; PipelineTask wraps it for execution; PipelineRunner manages the event loop.

### RTVI
- `RTVIProcessor` + observer are registered on the PipelineTask.
- Custom messages are sent via `rtvi_processor.send_server_message()` as `bot-action` events.
- Each agent has its own RTVI observer that handles only its specific frame type.
- The agent workspace receives messages from all three bots in the room.

### Design Principle
Always prefer Pipecat abstractions (frames, processors, RTVI) over custom transport. Suggestions, process illustrations, and transcripts flow through the pipeline as custom frames and are sent to the client via RTVI — not written to Supabase for realtime pickup. Supabase Realtime is reserved for session state changes.

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
PCC_TRANSCRIPT_AGENT_URL              # default: http://localhost:7860
PCC_PROCESS_AGENT_URL                 # default: http://localhost:7861
PCC_SUGGESTION_AGENT_URL              # default: http://localhost:7862
DAILY_API_KEY
```

### Required for Transcript Agent
```
DAILY_API_KEY
DEEPGRAM_API_KEY
```

### Required for Process Agent
```
DAILY_API_KEY
DEEPGRAM_API_KEY
OPENAI_API_KEY
PROCESS_MODEL                         # default: gpt-4.1-nano
```

### Required for Suggestion Agent
```
DAILY_API_KEY
DEEPGRAM_API_KEY
OPENAI_API_KEY
SUGGESTION_MODEL                      # default: gpt-4.1
```

### Optional (all agents)
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
  - Each agent uses `RunnerArguments` (Pipecat runner pattern)
  - Local dev: `python bot.py -t daily --port <port>` starts HTTP server with `/start` endpoint
  - Transcript agent (7860) is started first with `createDailyRoom: true` to create the room
  - Process (7861) and suggestion (7862) agents join with `dailyRoom: roomUrl`
  - Production: `pipecat cloud deploy` for each agent separately
- **Session State Validation**:
  - Agent workspace checks localStorage on mount and validates against database
  - Terminal states (completed/abandoned/escalated/error) clear localStorage automatically
  - Stale sessions (>1 hour old) are cleared on restoration
  - Only truly active sessions with complete data (room_url, agent_token) are restored
- **Phase-based UI**: Agent workspace adapts its layout based on call state (idle → incoming → active-preprocess → active-inprocess → postcall), showing only relevant information for the current phase
- **Next.js 16 Async Params**: Route params are Promises and must be awaited before access in App Router API routes
- **Secondary agent failures**: Process and suggestion agent startup failures are logged as warnings but don't block session creation — the transcript agent is the critical path
