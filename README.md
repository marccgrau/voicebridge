# VoiceBridge

Proactive guidance workspace for live human-human customer service calls. VoiceBridge listens to conversations via WebRTC, uses LLMs to detect processes and track progress, and delivers real-time suggestions to agents.

## Architecture

- **Agent Workspace** (`apps/agent-workspace`) - Phase-based Next.js workspace with procedural UI adapting to call state
- **Customer App** (`apps/customer`) - Customer-facing call interface
- **Python Orchestrator** (`services/orchestrator`) - Pipecat voice pipeline with multi-provider LLM flows
- **Shared Contracts** (`packages/contracts`) - Zod schemas for events and DTOs
- **Database Package** (`packages/db`) - Supabase client and query helpers
- **Supabase Postgres** - Database, realtime events, and process catalog

## Prerequisites

- Node.js v24+
- pnpm v10+
- Python 3.13+
- uv (Python package manager)
- Supabase CLI

## Quick Start

```bash
# Install dependencies
make install

# Set up environment variables
cp apps/agent-workspace/.env.example apps/agent-workspace/.env.local
cp apps/customer/.env.example apps/customer/.env.local
cp services/orchestrator/.env.example services/orchestrator/.env

# Run database migrations
make db-migrate

# Start development servers
make dev
```

## Environment Variables

### Agent Workspace (`apps/agent-workspace/.env.local`)

```bash
NEXT_PUBLIC_SUPABASE_URL=https://xxx.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=xxx
SUPABASE_SERVICE_ROLE_KEY=xxx
NEXT_PUBLIC_ORCHESTRATOR_URL=http://localhost:8000
```

### Customer App (`apps/customer/.env.local`)

```bash
NEXT_PUBLIC_SUPABASE_URL=https://xxx.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=xxx
NEXT_PUBLIC_ORCHESTRATOR_URL=http://localhost:8000
```

### Orchestrator (`services/orchestrator/.env`)

```bash
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_SERVICE_ROLE_KEY=xxx
SPEECHMATICS_API_KEY=xxx

# LLM Provider API Keys (at least one required)
OPENAI_API_KEY=xxx          # Default provider
GOOGLE_API_KEY=xxx          # Optional: Gemini provider
ANTHROPIC_API_KEY=xxx       # Optional: Claude provider

DAILY_API_KEY=xxx
```

## Project Structure

```
voicebridge/
├── apps/
│   ├── agent-workspace/           # Next.js agent UI (port 3000)
│   └── customer/                  # Next.js customer call UI (port 3001)
├── services/
│   └── orchestrator/              # Python/FastAPI voice pipeline (port 8000)
│       ├── src/
│       │   ├── llm/               # Multi-provider LLM support (LLMServiceFactory)
│       │   ├── flows/             # ProcessFlow & SuggestionFlow (FlowManager)
│       │   ├── pipeline/          # Pipeline assembly & VoiceBridgePipeline
│       │   ├── processors/        # TranscriptWriter, VoiceBridgeRTVIObserver
│       │   ├── db/                # Supabase client
│       │   ├── utils/             # Logging, retry, cleanup utilities
│       │   ├── config.py          # Settings (API keys, timeouts, models)
│       │   └── main.py            # FastAPI app with session endpoints
│       ├── tests/                 # Pytest test suite (api, llm, pipeline, db)
│       └── process_content/       # Markdown process definitions
├── packages/
│   ├── contracts/                 # Shared Zod schemas (events & DTOs)
│   └── db/                        # Supabase query helpers
└── supabase/
    └── migrations/                # Database schema (001_initial_schema.sql)
```

## Development

```bash
make dev              # Run all services (agent-workspace, customer, orchestrator)
make web-dev          # Agent workspace only (port 3000)
make customer-dev     # Customer app only (port 3001)
make orchestrator-dev # Orchestrator only (port 8000)

make lint             # Lint TypeScript (eslint) + Python (ruff)
make typecheck        # TypeScript type checking
make test             # Run all tests (vitest + pytest)
make format           # Format code (prettier + ruff)
```

## Services

| Service | Provider | Purpose |
|---------|----------|---------|
| STT | Speechmatics | Streaming speech-to-text with speaker diarization |
| LLM | OpenAI (default) | Process detection and suggestions (gpt-5-nano) |
| LLM | Gemini, Anthropic | Alternative providers (configurable per session) |
| Audio | Daily.co | WebRTC voice transport |
| Database | Supabase | Postgres + Realtime subscriptions |

---

## System Architecture

### Overview

VoiceBridge is a three-component system: a **Customer App**, an **Agent Workspace**, and a **Backend Orchestrator**. The customer and agent connect to the same Daily.co WebRTC room. The orchestrator joins as a listen-only bot, processes the audio through an LLM pipeline, and delivers real-time guidance back to the agent.

```
┌─────────────────┐         ┌──────────────────┐
│  Customer App   │         │ Agent Workspace   │
│  (Next.js)      │         │ (Next.js)         │
│                 │         │                   │
│  - Initiates    │         │  - 4-panel UI     │
│    call         │         │  - Live transcript│
│  - Audio via    │         │  - Suggestions    │
│    Daily.co     │         │  - Process steps  │
└────────┬────────┘         └────────┬──────────┘
         │                           │
         │   WebRTC Audio            │  RTVI (WebRTC data channel)
         │                           │  + Supabase Realtime
         ▼                           ▼
┌────────────────────────────────────────────────┐
│              Daily.co Room                      │
│         (WebRTC audio + data channels)          │
└────────────────────┬───────────────────────────┘
                     │
                     │  Audio (listen-only)
                     ▼
┌────────────────────────────────────────────────┐
│          Backend Orchestrator                   │
│          (Python / FastAPI / Pipecat)            │
│                                                 │
│  ┌─────────┐  ┌───────────┐  ┌──────────────┐  │
│  │Silero   │→ │Speechmatics│→ │Transcript    │  │
│  │VAD      │  │STT        │  │Writer        │  │
│  └─────────┘  └───────────┘  └──────┬───────┘  │
│                                      │          │
│                              ┌───────▼───────┐  │
│                              │ ProcessFlow   │  │
│                              │ (Multi-LLM)   │  │
│                              └───────┬───────┘  │
│                                      │          │
│                              ┌───────▼───────┐  │
│                              │SuggestionFlow │  │
│                              │ (Multi-LLM)   │  │
│                              └───────┬───────┘  │
│                                      │          │
│                              ┌───────▼───────┐  │
│                              │RTVI Observer  │  │
│                              └───────────────┘  │
│                                                 │
│  Supabase writes ─────────► Supabase Postgres   │
└─────────────────────────────────────────────────┘
```

### Component Interactions

**Customer App** (`apps/customer/`)
- Customer initiates a call via `POST /sessions/create`
- Receives a Daily.co room URL and customer token
- Connects to the room and sends audio via WebRTC
- Shows call status (idle, calling, connected, ended)

**Agent Workspace** (`apps/agent-workspace/`)
- **Phase-based UI** that adapts to the current call state, showing only contextually relevant information
- Subscribes to Supabase Realtime for pending sessions (incoming call notifications)
- Agent accepts a pending session via `POST /sessions/accept`, receives a Daily.co token
- Connects to the room via `@pipecat-ai/client-js` (RTVI client)
- Receives three types of RTVI messages through the WebRTC data channel:
  - `transcript_segment` - live transcript lines (speaker-tagged)
  - `agent_guidance` - suggested responses/actions for the agent
  - `process_illustration` - detected process with step progress
- Subscribes to Supabase Realtime for session state changes
- **UI Phases**:
  - **Idle**: Waiting screen for incoming calls
  - **Incoming**: Customer info + accept/reject interface
  - **Active (Pre-process)**: Customer info + transcript + suggestions (process detection in progress)
  - **Active (In-process)**: Full 4-panel workspace - customer info, transcript, suggestions, process visualization
  - **Postcall Summary**: Transcript review + AI-generated summary editor, auto-returns to idle after save

**Backend Orchestrator** (`services/orchestrator/`)
- FastAPI service managing session lifecycle
- Creates Daily.co rooms and generates participant tokens
- Spawns a Pipecat pipeline per session as a background task
- Pipeline joins the Daily.co room as a listen-only bot
- Processes audio through VAD, STT, and LLM flows
- Writes transcripts to Supabase (persisted + Realtime)
- Sends suggestions and process illustrations via RTVI (low-latency WebRTC data channel)

### Session Lifecycle

**Customer-initiated flow:**
1. Customer calls `POST /sessions/create` → session created with status `pending`, Daily.co room created, pipeline bot starts listening
2. Agent sees incoming call notification via Supabase Realtime subscription
3. Agent calls `POST /sessions/accept` → session status updated to `active`, agent token returned
4. Both customer and agent are in the room; pipeline processes audio
5. Either party calls `POST /sessions/stop` → session status updated to `completed`, pipeline stopped

**Agent-initiated flow:**
1. Agent calls `POST /sessions/start` → session created with status `active`, Daily.co room and pipeline started
2. Agent and customer join the room
3. Session proceeds and is stopped via `POST /sessions/stop`

---

## Backend Pipeline Flows

### Audio Flow

```
Microphone → Daily.co WebRTC → Silero VAD → Speechmatics STT → TranscriptionFrame
```

1. **Daily.co Transport**: Receives audio from all room participants via WebRTC. Configured as listen-only (`audio_out_enabled=False`) - the bot never speaks.
2. **Silero VAD**: Voice Activity Detection filters silence. Tuned with `start_secs=0.2` (quick speech detection) and `stop_secs=0.8` (waits before marking speech end).
3. **Speechmatics STT**: Streaming speech-to-text with external turn detection. Produces `TranscriptionFrame` objects with `finalized=True` for completed utterances. Speaker diarization provides raw speaker IDs (e.g., "S1", "S2").

### Transcript Processing

```
TranscriptionFrame → TranscriptWriter → Supabase + TranscriptSegmentFrame → RTVI
```

1. **TranscriptWriter** receives finalized `TranscriptionFrame` objects
2. Maps raw Speechmatics speaker IDs to roles (`customer`/`agent`) using first-speaker heuristic (first speaker = customer by default)
3. Stamps the resolved role back onto the frame's `user_id` for downstream processors
4. Writes the segment to the `transcript_segments` table in Supabase (with retry logic)
5. Emits a `TranscriptSegmentFrame` that the RTVI Observer picks up and sends to the frontend

### Process Detection Flow (ProcessFlow)

```
TranscriptionFrame → ProcessFlow (FlowManager + Multi-Provider LLM) → ProcessIllustrationFrame
```

**Multi-Provider LLM Support**: ProcessFlow can use OpenAI (default: gpt-5-nano), Gemini, or Anthropic models. Provider and model are configurable per-session via API request.

ProcessFlow uses a `pipecat_flows.FlowManager` with three node states:

1. **IDLE**: Waits until 3+ utterances have been collected before attempting detection
2. **DETECTING**: Sends the conversation buffer to the configured LLM (default: OpenAI gpt-5-nano) along with the available process catalog. The LLM calls either:
   - `select_process(process_key, confidence, rationale)` → transitions to TRACKING
   - `need_more_context(reason)` → returns to IDLE
3. **TRACKING**: On each new utterance, sends the last 5 messages to the LLM with the current process steps. The LLM calls:
   - `update_step(step_number, rationale)` → emits an updated `ProcessIllustrationFrame`

**Process Catalog**: Process definitions are loaded from markdown files in `process_content/`. Each file uses YAML frontmatter (`process_key`, `name`, `domain`, `intents`) and `## Step N: Label` headings for step definitions.

**ProcessIllustrationFrame** contains: `process_key`, `process_name`, `steps` (with status: pending/in_progress/completed), `current_step`, and full process `content`.

### Suggestion Generation Flow (SuggestionFlow)

```
TranscriptionFrame + ProcessIllustrationFrame → SuggestionFlow (FlowManager + Multi-Provider LLM) → SuggestionFrame
```

**Multi-Provider LLM Support**: SuggestionFlow can use OpenAI (default: gpt-5-nano), Gemini, or Anthropic models. Provider and model are independently configurable from ProcessFlow.

SuggestionFlow uses a `pipecat_flows.FlowManager` with three node states:

1. **START**: Initial state, transitions to LISTENING on first utterance
2. **LISTENING**: Accumulates conversation. On each customer utterance, transitions to SUGGESTING
3. **SUGGESTING**: Sends the conversation and optional process context to the configured LLM (default: OpenAI gpt-5-nano). The LLM calls:
   - `publish_suggestions(suggestions)` → emits a `SuggestionFrame` with exactly 3 suggestions, each typed as `response`, `question`, `action`, or `escalation`

**Process context injection**: SuggestionFlow listens for `ProcessIllustrationFrame` objects from ProcessFlow (decoupled communication via the pipeline). When present, the LLM prompt includes the current process name, steps, and progress so suggestions are contextually relevant.

**SuggestionFrame** contains: `suggestions` (array of `{text, type}`), `service_type`, `latency_ms`, `process_key`, and `tools_used`.

### RTVI Message Delivery

```
SuggestionFrame / ProcessIllustrationFrame / TranscriptSegmentFrame → VoiceBridgeRTVIObserver → RTVI → Agent Workspace
```

The `VoiceBridgeRTVIObserver` is a `FrameProcessor` at the end of the pipeline that intercepts custom frames and sends them to the frontend via the RTVI protocol (WebRTC data channel):

| Frame | RTVI Action | Purpose |
|-------|-------------|---------|
| `SuggestionFrame` | `agent_guidance` | Suggested responses/actions for the agent |
| `ProcessIllustrationFrame` | `process_illustration` | Detected process with step progress |
| `TranscriptSegmentFrame` | `transcript_segment` | Live transcript with speaker role |

All RTVI messages include retry logic (configurable max retries with 0.2s base delay). Messages are sent via `rtvi_processor.send_server_message()` as `bot-action` events.

The agent workspace parses these messages using the Zod schemas from `@voicebridge/contracts` (`RTVIMessageSchema` discriminated union on the `action` field).

### Pipeline Assembly

The full Pipecat pipeline is assembled in `VoiceBridgePipeline` and runs as a background asyncio task per session:

```
Daily Transport Input
  → Speechmatics STT
    → TranscriptWriter (writes to Supabase, emits TranscriptSegmentFrame)
      → ProcessFlow (optional, detects process + tracks steps)
        → SuggestionFlow (optional, generates suggestions with process context)
          → VoiceBridgeRTVIObserver (sends frames via RTVI)
            → Daily Transport Output (WebRTC data channel for RTVI)
```

Each FlowManager (ProcessFlow and SuggestionFlow) has its own isolated LLM pipeline running in a background `asyncio.Task`. This allows LLM calls to happen independently without blocking the main audio pipeline.

### Database Schema

Key tables (single migration: `001_initial_schema.sql`):

| Table | Purpose |
|-------|---------|
| `sessions` | Session state, status, room info, timestamps, error tracking |
| `transcript_segments` | Persisted STT output with speaker role and timestamps |
| `process_catalog` | Process definitions with full-text search (seeded with 5 processes) |

Session statuses: `pending` → `active` → `completed` / `abandoned` / `escalated` / `error`

Supabase Realtime is enabled on `sessions` and `transcript_segments` for live UI updates.
