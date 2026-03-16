# VoiceBridge Architecture

This document describes the system architecture, data flows, and design patterns of VoiceBridge. All user-facing UI and experiment content (personas, scenarios, process definitions, knowledge base, LLM prompts) are in **German**.

## System Overview

VoiceBridge is a **proactive guidance workspace** for live human-human customer service calls. It listens to conversations over WebRTC, uses a voice processing pipeline to detect customer service processes, track step progress, and generate AI-powered Process-Pilot advice — all delivered in real time to the agent's workspace.

The system does **not** replace the human agent. It augments them with contextual guidance while they handle the call.

### Components

| Component       | Tech             | Port  | Purpose                                            |
| --------------- | ---------------- | ----- | -------------------------------------------------- |
| Agent Workspace | Next.js 16       | 3000  | Phase-based agent UI with real-time guidance       |
| Customer App    | Next.js 16       | 3001  | Customer-facing call interface                     |
| PCC Service     | Python / Pipecat | 7860  | Stateless voice pipeline (listen-only bot)         |
| Contracts       | TypeScript / Zod | —     | Shared schemas and types                           |
| DB Package      | TypeScript       | —     | Supabase query helpers                             |
| Supabase        | PostgreSQL       | 54321 | Database + Realtime subscriptions                  |
| Daily.co        | WebRTC           | —     | Audio transport (rooms + tokens)                   |
| Deepgram        | API              | —     | Speech-to-text (STT)                               |
| OpenAI          | API              | —     | LLM for advice generation + postcall summaries     |

## High-Level Data Flow

```
┌─────────────┐     ┌─────────────┐     ┌──────────────────────────────────────┐
│  Customer    │     │  Daily.co   │     │  PCC Service (Pipecat Pipeline)      │
│  App         │────▶│  WebRTC     │────▶│                                      │
│  (audio in)  │     │  Room       │     │  Deepgram STT                        │
└─────────────┘     └─────────────┘     │    → ParallelPipeline                 │
                          │              │        ├─ transcript branch           │
                          │              │        ├─ process branch (LLM)        │
                          │              │        └─ suggestion branch (LLM)     │
                          │              │    → RTVI bot-action messages         │
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

- `transcript_segment` — Live transcription segments
- `process_illustration` — Detected process with step progress tracking
- `agent_guidance` — Process-Pilot advice for the agent

**Supabase Realtime** — Session lifecycle and notifications:

- Pending session inserts (incoming call notifications for agents)
- Session status changes (pending → active → completed)
- Used by both agent workspace and customer app

## Session Lifecycle

### Full Call Flow

```
1. Actor selects a domain-compatible persona + scenario (and optional entry route: `direct` or `voice_ai`)
       │
2. Customer app loads and prepares briefing data
       │
       ├─ Personas loaded from `customers` (seeded from `personas/customer_profile_*.json`)
       ├─ Active scenarios loaded from `scenarios` (seeded from `scenarios/scenario_*.json`)
       ├─ Domain filtering keeps selections compatible (`customers.domain` ↔ `scenarios.domain`)
       └─ Scenario placeholders (for example `{{customer_name}}`) rendered with selected persona values
       │
3. Customer App POST /api/sessions/create with `customer_id` + `scenario_id`
       │
       ├─ Validates selected customer and scenario rows in Supabase
       ├─ Calls PCC /start → creates Daily room + bot instance
       │   metadata includes: scenario_id, scenario_family, domain, customer_id, customer_name
       ├─ Creates Daily tokens with user_name (customer="Kunde", agent="Berater") for speaker identification
       └─ Inserts `pending` session with customer/scenario metadata
           (`scenario_id`, `scenario_family`, `civility_condition`) and routing context in `state`
       │
4. Customer joins Daily room with audio
       │
5. Agent Workspace sees pending session via Supabase Realtime
       │
6. Agent clicks "Accept"
       │
       ├─ Updates session status to 'active' in Supabase
       └─ Connects to Daily room via RTVI (@pipecat-ai/client-js)
       │
7. PCC bot processes audio and sends RTVI messages
       │
       ├─ transcript_segment → live transcript
       ├─ process_illustration → detected process + steps
       └─ agent_guidance → Process-Pilot advice
       │
8. Agent ends call → status becomes 'completed'
       │
9. Postcall Summary phase
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
ParallelPipeline
    (only customer audio reaches STT — agent mic unsubscribed at transport level)
    ├─ Branch 1: transcript
    │   TranscriptWriter
    │   └─ Emits `transcript_segment` RTVI messages (always speaker "customer")
    │
    ├─ Branch 2: process identification
    │   LLMContextAggregatorPair.user()
    │   OpenAILLMService (PROCESS_MODEL, default gpt-4.1-nano)
    │   ProcessOutputProcessor
    │   └─ Parses strict JSON and emits `process_illustration` messages
    │       System prompt includes step descriptions + speaker awareness rules
    │
    └─ Branch 3: suggestion generation
        LLMContextAggregatorPair.user()
        OpenAILLMService (SUGGESTION_MODEL, default gpt-4.1)
        SuggestionOutputProcessor
        └─ Parses strict JSON and emits `agent_guidance` messages
            System prompt includes process definition + KB content (scenario-aware)
    ▼
transport.output()
```

### RTVI Messages

The PCC service emits three bot-action messages over RTVI:

| Action                 | Key fields                                             | Purpose          |
| ---------------------- | ------------------------------------------------------ | ---------------- |
| `transcript_segment`   | sessionId, speaker, text, timestamp, isFinal           | Live transcript  |
| `process_illustration` | processKey, processName, steps[], currentStep, content | Process tracking |
| `agent_guidance`       | advice[], serviceType, toolsUsed                       | Agent guidance   |

### Process Detection

Process identification is **catalog-informed + LLM-evaluated**:

1. Process definitions are loaded from markdown files in `process_content/` on startup
2. Each file has YAML frontmatter with `process_key`, `name`, `domain`, and `intents`
3. Steps are extracted from `## Step N: Label` headings (with descriptions from step body text)
4. Catalog summaries with step descriptions are embedded into the process system prompt
5. All transcript entries are customer speech (agent mic is unsubscribed at the transport level)
6. `OpenAILLMService` returns strict JSON (`processKey`, `currentStep`)
7. `ProcessOutputProcessor` validates output and maps step statuses
8. Valid output is emitted as `process_illustration` with step progress

By default, PCC resolves process markdown from `services/pcc/process_content/` (or `PROCESS_CONTENT_PATH` when set). The repository currently includes four experiment-aligned process definitions (all in German):

- `bank_unauth_transaction` — Unautorisierte Bankbuchung
- `bank_credit_denial` — Kreditantrag abgelehnt
- `insurance_unauth_claim` — Unautorisierter Versicherungsanspruch
- `insurance_claim_denial` — Versicherungsantrag abgelehnt

Supporting knowledge base articles are in `services/pcc/kb_content/` (one per process).

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

| Phase                | Layout           | Key Panels                                             |
| -------------------- | ---------------- | ------------------------------------------------------ |
| Idle                 | Centered message | Waiting indicator                                      |
| Incoming             | Full-width       | Queue selector + accept action, customer brief preview |
| Active (pre-process) | Two-column       | Customer info, transcript, Process-Pilot advice        |
| Active (in-process)  | Two-column       | Customer info, transcript, Process-Pilot advice, process steps |
| Postcall summary     | Two-column       | Transcript (read-only), summary editor                 |

### Panel Density

During active phases, panels support togglable density (`compact` / `expanded`) to let agents customize their workspace layout.

## Customer App

The customer app provides a prep-first call interface:

### State Machine

```
idle → calling → connected → ended
```

- Before `calling`, actors complete a selection + briefing step that includes scenario context, civility instruction, escalation/de-escalation cues, and actor guidance (`mustAskCheckpoints`, `revealWhenAsked`) when present.

### Session Creation Flow

The customer app's `POST /api/sessions/create` API route orchestrates session creation:

1. Validates selected `customer_id` and `scenario_id` against `customers` + active `scenarios`
2. Calls PCC `/start` endpoint → PCC creates a Daily room and spawns a bot
3. Generates customer token (non-owner) and agent token (owner) via Daily REST API
4. Inserts a `pending` session into Supabase with room data, selected persona/scenario metadata (`customer_id`, `scenario_id`, `scenario_family`, `civility_condition`), and routing context in `state`
5. Returns `{ session_id, room_url, customer_token }` to the client
6. Client connects to Daily room with audio via `@daily-co/daily-js`
7. Subscribes to Supabase Realtime to detect agent acceptance (pending → active)

## Experiment Persona and Scenario Definition + Loading

Experiment data follows a file-to-database-to-runtime loading model:

1. **File definitions**
   - Personas are authored in `personas/customer_profile_*.json`
   - Scenarios are authored in `scenarios/scenario_*.json`
   - Scenario scripts may include `actor_guidance` plus escalation/de-escalation cues inside `behavioral_condition`
2. **Seeding to Supabase**
   - `scripts/seed-experimental-data.mjs` parses and validates both directories
   - Personas are written to `customers` and `customer_interactions`
   - Scenarios are written to `scenarios`
   - `scenario_family` is derived from `scenario_id` by stripping `_civil` / `_uncivil`
3. **Runtime loading (customer app)**
   - `apps/customer/src/lib/use-customers.ts` reads personas from `customers`
   - `apps/customer/src/lib/use-scenarios.ts` reads active scenarios from `scenarios` (including `actor_guidance`)
   - `apps/customer/src/lib/scenario-render.ts` resolves placeholders (for example `{{customer_name}}`, `{{customer_dob_human}}`) into actor-facing script text
   - Selection UI keeps persona/scenario combinations domain-compatible
4. **Runtime propagation (session + agent workspace)**
   - `apps/customer/app/api/sessions/create/route.ts` persists selected scenario metadata on `sessions` and in `sessions.state`
   - Agent workspace reads `sessions.customer_id` and loads the full customer context from `customers` + `customer_interactions`

## Database Schema

### Entity Relationship

```
customers
    │
    ├── 1:N ──▶ customer_interactions (customer_id FK)
    │
    └── 1:N ──▶ sessions (customer_id FK)

scenarios
    │
    └── 1:N ──▶ sessions (scenario_id FK)

sessions
    │
    ├── 1:N ──▶ transcript_segments (session_id FK)
    │
    └── 1:N ──▶ session_events (session_id FK)
```

### Key Tables

**sessions**

- `id` (UUID, PK)
- `status` (enum: pending/active/completed/abandoned/escalated/error)
- `room_url`, `room_name` (Daily.co room info)
- `agent_token` (Daily.co owner token for agent)
- `customer_id` (FK → customers)
- `scenario_id` (FK → scenarios)
- `scenario_family`, `civility_condition`
- `state` (JSONB — flexible metadata, includes scenario + routing handoff context)
- `summary_text`, `summary_updated_at`, `summary_updated_by`
- `created_at`, `updated_at`

**transcript_segments**

- `id` (UUID, PK)
- `session_id` (FK → sessions)
- `speaker` (agent/customer)
- `text`, `is_final`
- `created_at`

**customers**

- `id` (UUID, PK)
- `customer_code`, `name`, `classification`, `email`, `date_of_birth`
- `address_*`, `preferred_contact_channel`, `quick_internal_note`, `domain`
- Row-level security enabled

**customer_interactions**

- `customer_id` (FK → customers)
- `type`, `date`, `summary`, `outcome`
- `direction`, `topic`, `subtopic`, `sentiment`, `priority`

**scenarios**

- `scenario_id` (PK)
- `scenario_family`, `title`, `domain`
- `civility_condition`, `behavior_instruction`
- `background`, `customer_goal`, `guidelines`, `conversation`, `actor_guidance`, `status`

**session_events**

- `id` (UUID, PK)
- `session_id` (FK → sessions)
- `event_type`, `source`, `payload`, `ts`

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
  RTVISuggestionMessageSchema, // action: "agent_guidance"
  RTVIProcessIllustrationMessageSchema, // action: "process_illustration"
  RTVITranscriptSegmentMessageSchema, // action: "transcript_segment"
]);
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

- **Customer-only audio**: Agent mic is unsubscribed at the transport level, so only customer speech reaches STT and the LLM branches
- **Branch 1 (transcript)**: emits transcript updates with correct `speaker` field, stripping label prefixes
- **Branch 2 (process LLM)**: identifies process + current step using speaker-aware, step-description-enriched prompts
- **Branch 3 (suggestion LLM)**: acts as "Process-Pilot", generating 2–4 advice items (German imperatives) using scenario-aware prompts (process definition + KB content)

This ensures transcript updates are delivered in real time while process and advice LLM work runs in parallel. The `on_participant_joined` handler identifies the agent by token ownership and unsubscribes from their microphone, so only customer audio reaches STT.

### RTVI Over Supabase Realtime

Live call data (transcripts, advice, process updates) is delivered via RTVI (WebRTC data channel) for sub-second latency. Supabase Realtime is reserved for:

- Session lifecycle events (pending/active/completed)
- Pending call notifications to agents

This separation ensures the highest-frequency, most latency-sensitive data takes the fastest path.

### Session Management in Next.js

Session creation and management is handled entirely by Next.js API routes and Supabase, not the PCC service. The customer app's `/api/sessions/create` route orchestrates:

1. PCC bot creation
2. Daily token generation
3. Supabase session insertion

This keeps the PCC service focused on audio processing and makes session logic easy to modify without redeploying the voice pipeline.

### Type Safety Across Languages

TypeScript Zod schemas in `packages/contracts` define the contract for all RTVI messages and DTOs. Both Next.js apps import these directly. The Python PCC service maintains compatible JSON structures validated at runtime.

## Technology Choices

| Concern                      | Choice                        | Rationale                                                       |
| ---------------------------- | ----------------------------- | --------------------------------------------------------------- |
| Audio transport              | Daily.co WebRTC               | Managed rooms, ephemeral rooms, token-based auth                |
| Speech-to-text               | Deepgram (nova-3-general)     | Low-latency streaming, smart formatting                         |
| Voice pipeline               | Pipecat                       | Frame-based processing, built-in RTVI support, cloud deployment |
| LLM (process identification) | OpenAI (gpt-4.1-nano default) | Structured JSON classification against process catalog          |
| LLM (advice / Process-Pilot) | OpenAI (gpt-4.1 default)      | Fast, cost-effective structured next-action guidance            |
| LLM (summaries)              | OpenAI                        | Used in agent workspace API route for postcall summaries        |
| Frontend                     | Next.js 16 + React 19.2       | App Router, server components, API routes                       |
| Database                     | Supabase (PostgreSQL)         | Realtime subscriptions, RLS, managed hosting                    |
| Schema validation            | Zod                           | TypeScript-native, runtime validation, type inference           |
| Styling                      | Tailwind CSS v4               | Utility-first, fast iteration                                   |
| Python packaging             | uv                            | Fast dependency resolution, Python 3.13+                        |
| Monorepo                     | pnpm workspaces               | Efficient, supports workspace protocol                          |

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
