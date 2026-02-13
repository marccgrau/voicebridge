# VoiceBridge Architecture

This document describes the system architecture, data flows, and design patterns of VoiceBridge.

## System Overview

VoiceBridge is a **proactive guidance workspace** for live human-human customer service calls. It listens to conversations over WebRTC, uses a voice processing pipeline to detect customer service processes, track step progress, and generate AI-powered suggestions — all delivered in real time to the agent's workspace.

The system does **not** replace the human agent. It augments them with contextual guidance while they handle the call.

### Components

| Component | Tech | Port | Purpose |
|-----------|------|------|---------|
| Agent Workspace | Next.js 16 | 3000 | Phase-based agent UI with real-time guidance |
| Customer App | Next.js 16 | 3001 | Customer-facing call interface |
| PCC Service | Python / Pipecat | 7860 | Stateless voice pipeline (listen-only bot) |
| Contracts | TypeScript / Zod | — | Shared schemas and types |
| DB Package | TypeScript | — | Supabase query helpers |
| Supabase | PostgreSQL | 54321 | Database + Realtime subscriptions |
| Daily.co | WebRTC | — | Audio transport (rooms + tokens) |
| Deepgram | API | — | Speech-to-text (STT) |
| OpenAI | API | — | LLM for suggestion generation + postcall summaries |

## High-Level Data Flow

```
┌─────────────┐     ┌─────────────┐     ┌──────────────────────────────────────┐
│  Customer    │     │  Daily.co   │     │  PCC Service (Pipecat Pipeline)      │
│  App         │────▶│  WebRTC     │────▶│                                      │
│  (audio in)  │     │  Room       │     │  Deepgram STT                        │
└─────────────┘     └─────────────┘     │    → TranscriptWriter                │
                          │              │    → ProcessDetectionProcessor        │
                          │              │    → ParallelPipeline                 │
                          │              │        ├─ passthrough                 │
                          │              │        └─ suggestion branch (LLM)     │
                          │              │    → VoiceBridgeRTVIObserver          │
                          │              └────────────────┬─────────────────────┘
                          │                               │
                          │                    RTVI (WebRTC data channel)
                          │                               │
                          ▼                               ▼
                    ┌─────────────┐              ┌─────────────────┐
                    │  Supabase   │              │  Agent           │
                    │  Realtime   │─────────────▶│  Workspace       │
                    │  (sessions) │              │  (Next.js)       │
                    └─────────────┘              └─────────────────┘
```

### Two Realtime Channels

VoiceBridge uses two complementary realtime channels optimized for different purposes:

**RTVI (WebRTC data channel)** — Sub-second latency for live call guidance:
- `transcript_segment` — Live transcription of customer/agent speech
- `process_illustration` — Detected process with step progress tracking
- `agent_guidance` — AI-generated suggestions for the agent

**Supabase Realtime** — Session lifecycle and notifications:
- Pending session inserts (incoming call notifications for agents)
- Session status changes (pending → active → completed)
- Used by both agent workspace and customer app

## Session Lifecycle

### Full Call Flow

```
1. Customer selects profile and clicks "Start Call"
       │
2. Customer App POST /api/sessions/create
       │
       ├─ Calls PCC /start → creates Daily room + bot instance
       ├─ Creates Daily tokens (customer + agent) via Daily REST API
       └─ Inserts 'pending' session into Supabase
       │
3. Customer joins Daily room with audio
       │
4. Agent Workspace sees pending session via Supabase Realtime
       │
5. Agent clicks "Accept"
       │
       ├─ Updates session status to 'active' in Supabase
       └─ Connects to Daily room via RTVI (@pipecat-ai/client-js)
       │
6. PCC bot processes audio and sends RTVI messages
       │
       ├─ transcript_segment → live transcript
       ├─ process_illustration → detected process + steps
       └─ agent_guidance → AI suggestions
       │
7. Agent ends call → status becomes 'completed'
       │
8. Postcall Summary phase
       │
       ├─ AI generates summary from transcript (OpenAI)
       ├─ Agent reviews/edits and saves
       └─ Workspace returns to idle
```

### Session Statuses

```
pending ──▶ active ──▶ completed
                  ├──▶ abandoned
                  ├──▶ escalated
                  └──▶ error
```

- `pending` — Customer has called, waiting for agent to accept
- `active` — Agent has accepted, call is in progress
- `completed` — Call ended normally
- `abandoned` — Call was abandoned (customer left before agent accepted)
- `escalated` — Call was escalated to a supervisor
- `error` — System error occurred during the call

## PCC Service Pipeline

The PCC (Pipecat Cloud) service is the core voice processing component. It is **stateless** and **listen-only** — it processes audio without speaking and delivers all guidance via RTVI.

### Pipeline Architecture

```
transport.input()
    │
    ▼
DeepgramSTTService (nova-3-general, streaming)
    │
    ▼
TranscriptWriter
    │ Converts STT output → TranscriptSegmentFrame
    │ Fields: session_id, speaker, text, timestamp, is_final
    ▼
ProcessDetectionProcessor
    │ Token-overlap matching against process catalog
    │ Emits ProcessIllustrationFrame when a process is detected
    │ Tracks step progress as conversation evolves
    ▼
ParallelPipeline
    ├─ Branch 1: passthrough
    │   Frames pass through immediately (no delay)
    │
    └─ Branch 2: suggestion generation
        SuggestionContextBuilder
            │ Aggregates transcript + process context
            ▼
        OpenAILLMService (gpt-4.1)
            │ Generates structured suggestions
            ▼
        SuggestionOutputProcessor
            │ Parses LLM output → SuggestionFrame
            ▼
VoiceBridgeRTVIObserver
    │ Intercepts custom frames
    │ Publishes as RTVI bot-action messages
    │ Includes retry logic (configurable max retries, 0.2s base delay)
    ▼
transport.output()
```

### Custom Frames

Three domain-specific frames flow through the pipeline:

| Frame | Fields | Purpose |
|-------|--------|---------|
| `TranscriptSegmentFrame` | session_id, speaker, text, timestamp, is_final | Live transcript |
| `ProcessIllustrationFrame` | process_key, process_name, steps[], current_step, content | Process tracking |
| `SuggestionFrame` | suggestions[], service_type, latency_ms, process_key, tools_used | Agent guidance |

### Process Detection

Process detection is **catalog-based** (no LLM calls required):

1. Process definitions are loaded from markdown files in `process_content/` on startup
2. Each file has YAML frontmatter with `process_key`, `name`, `domain`, and `intents`
3. Steps are extracted from `## Step N: Label` headings
4. `ProcessCatalogIndexService` indexes all processes
5. Customer speech is matched against intent keywords using token-overlap scoring
6. When a match is found, a `ProcessIllustrationFrame` is emitted with step tracking
7. Steps are tracked and updated as the conversation progresses

Currently includes 9 banking process definitions (lost/stolen card, e-banking locked, identity verification, legal guardianship, death reporting, large withdrawals, small estates, etc.).

## Agent Workspace UI

The agent workspace uses a **phase-based procedural UI** that adapts its layout based on the current call state.

### Phase State Machine

```
                    ┌───────────────────────────────────────────┐
                    │                                           │
                    ▼                                           │
                 ┌──────┐  pending session  ┌──────────┐       │
                 │ idle │────────────────▶│ incoming  │       │
                 └──────┘                  └──────────┘       │
                                                │              │
                                          accept │              │
                                                ▼              │
                                     ┌────────────────┐        │
                                     │ active         │        │
                                     │ (pre-process)  │        │
                                     └────────────────┘        │
                                                │              │
                                    process     │              │
                                    detected    │              │
                                                ▼              │
                                     ┌────────────────┐        │
                                     │ active         │        │
                                     │ (in-process)   │        │
                                     └────────────────┘        │
                                                │              │
                                          call  │              │
                                          ends  │              │
                                                ▼              │
                                     ┌────────────────┐        │
                                     │ postcall       │────────┘
                                     │ summary        │ (save/skip)
                                     └────────────────┘
```

### Phase Layouts

| Phase | Layout | Key Panels |
|-------|--------|------------|
| Idle | Centered message | Waiting indicator |
| Incoming | Full-width | Call notification, customer info (expanded) |
| Active (pre-process) | Two-column | Customer info, transcript, suggestions |
| Active (in-process) | Two-column | Customer info, transcript, suggestions, process steps |
| Postcall summary | Two-column | Transcript (read-only), summary editor |

### Panel Density

During active phases, panels support togglable density (`compact` / `expanded`) to let agents customize their workspace layout.

## Customer App

The customer app provides a minimal call interface:

### State Machine

```
idle → calling → connected → ended
```

### Session Creation Flow

The customer app's `POST /api/sessions/create` API route orchestrates session creation:

1. Calls PCC `/start` endpoint → PCC creates a Daily room and spawns a bot
2. Generates customer token (non-owner) and agent token (owner) via Daily REST API
3. Inserts a `pending` session into Supabase with room_url, agent_token, and customer_id
4. Returns `{ session_id, room_url, customer_token }` to the client
5. Client connects to Daily room with audio via `@daily-co/daily-js`
6. Subscribes to Supabase Realtime to detect agent acceptance (pending → active)

## Database Schema

### Entity Relationship

```
sessions
    │
    ├── 1:N ──▶ transcript_segments (session_id FK)
    │
    └── 1:N ──▶ customer_interactions (session_id FK)
                        │
                        └── N:1 ──▶ customers (customer_id FK)

process_catalog (standalone, seeded)
```

### Key Tables

**sessions**
- `id` (UUID, PK)
- `status` (enum: pending/active/completed/abandoned/escalated/error)
- `room_url`, `room_name` (Daily.co room info)
- `agent_token` (Daily.co owner token for agent)
- `state` (JSONB — flexible metadata, includes customer_id)
- `summary_text`, `summary_updated_at`, `summary_updated_by`
- `created_at`, `updated_at`

**transcript_segments**
- `id` (UUID, PK)
- `session_id` (FK → sessions)
- `speaker` (agent/customer)
- `text`, `is_final`
- `created_at`

**process_catalog**
- `process_key` (PK)
- `name`, `domain`, `status`, `version`, `locale`
- Full-text search via `pg_trgm` extension

**customers**
- `id` (UUID, PK)
- `name`, `classification` (high/medium/low value), `email`
- Row-level security enabled

**customer_interactions**
- `session_id` (FK → sessions)
- `customer_id` (FK → customers)
- `interaction_type`

### Realtime

Supabase Realtime publications are enabled on:
- `sessions` — For pending call notifications and status changes
- `transcript_segments` — For live transcript updates (currently unused in favor of RTVI)

## Shared Contracts

The `packages/contracts` package is the **single source of truth** for TypeScript types across the monorepo.

### RTVI Message Schemas (Zod)

```typescript
// Discriminated union on 'action' field
RTVIMessageSchema = z.discriminatedUnion("action", [
  RTVISuggestionMessageSchema,         // action: "agent_guidance"
  RTVIProcessIllustrationMessageSchema, // action: "process_illustration"
  RTVITranscriptSegmentMessageSchema,   // action: "transcript_segment"
])
```

### DTO Schemas

- Session config, state, and status
- Process definition and step schemas
- Customer and interaction schemas
- Summary update schema
- LLM provider schema (`"openai" | "gemini" | "anthropic"`)

Python code in the PCC service maintains compatible JSON structures (validated at runtime, not type-checked).

## Design Patterns

### Listen-Only Bot

The Pipecat pipeline is configured with `audio_out_enabled=False`. The bot never speaks — it only processes incoming audio and emits guidance events. This is fundamental to the system design: VoiceBridge augments human agents rather than replacing them.

### Stateless PCC Service

The PCC service has no database connection. All data flows through the pipeline as frames and exits via RTVI. This makes it:
- Easy to scale horizontally (each bot instance is independent)
- Simple to deploy (no database migrations or connection pooling)
- Resilient (bot crashes don't corrupt persistent state)

### Parallel Processing

The `ParallelPipeline` is critical for latency:
- **Branch 1 (passthrough)**: Transcript segments and process detections flow through immediately
- **Branch 2 (LLM)**: Suggestion generation runs asynchronously without blocking

This ensures agents see transcript updates in real time even while the LLM is generating suggestions.

### RTVI Over Supabase Realtime

Live call data (transcripts, suggestions, process updates) is delivered via RTVI (WebRTC data channel) for sub-second latency. Supabase Realtime is reserved for:
- Session lifecycle events (pending/active/completed)
- Pending call notifications to agents

This separation ensures the highest-frequency, most latency-sensitive data takes the fastest path.

### Decoupled Flows

The process detection and suggestion generation flows communicate only through frames in the pipeline. The `SuggestionContextBuilder` reads `ProcessIllustrationFrame` to incorporate process context, but has no direct reference to `ProcessDetectionProcessor`. This keeps the processors independently testable and replaceable.

### Session Management in Next.js

Session creation and management is handled entirely by Next.js API routes and Supabase, not the PCC service. The customer app's `/api/sessions/create` route orchestrates:
1. PCC bot creation
2. Daily token generation
3. Supabase session insertion

This keeps the PCC service focused on audio processing and makes session logic easy to modify without redeploying the voice pipeline.

### Type Safety Across Languages

TypeScript Zod schemas in `packages/contracts` define the contract for all RTVI messages and DTOs. Both Next.js apps import these directly. The Python PCC service maintains compatible JSON structures validated at runtime.

## Technology Choices

| Concern | Choice | Rationale |
|---------|--------|-----------|
| Audio transport | Daily.co WebRTC | Managed rooms, ephemeral rooms, token-based auth |
| Speech-to-text | Deepgram (nova-3-general) | Low-latency streaming, smart formatting |
| Voice pipeline | Pipecat | Frame-based processing, built-in RTVI support, cloud deployment |
| LLM (suggestions) | OpenAI (gpt-4.1) | Fast, cost-effective for structured suggestions |
| LLM (summaries) | OpenAI | Used in agent workspace API route for postcall summaries |
| Frontend | Next.js 16 + React 19.2 | App Router, server components, API routes |
| Database | Supabase (PostgreSQL) | Realtime subscriptions, RLS, managed hosting |
| Schema validation | Zod | TypeScript-native, runtime validation, type inference |
| Styling | Tailwind CSS v4 | Utility-first, fast iteration |
| Python packaging | uv | Fast dependency resolution, Python 3.13+ |
| Monorepo | pnpm workspaces | Efficient, supports workspace protocol |

## Deployment

### Local Development

```bash
make install    # Install all dependencies
make dev        # Start all 3 services in parallel
```

### Production (PCC)

```bash
pipecat cloud deploy    # Deploy PCC to Pipecat Cloud
```

The Next.js apps can be deployed to any hosting platform that supports Next.js (Vercel, Cloudflare, self-hosted).

### Environment Configuration

Each component has its own `.env` file with the minimum required variables. See the root [README.md](./README.md) for the full list.
