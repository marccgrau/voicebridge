# VoiceBridge Customer App

Next.js customer-facing call interface for initiating support calls with VoiceBridge agents. The entire UI is in **German**.

## Features

- **Simple Call Flow**: Idle → Calling → Connected → Ended
- **Cross-Combinable Setup**: Select any domain-compatible persona + scenario before calling
- **Briefing Step**: Actor reviews persona/scenario briefing before starting the call
- **Actor Script View**: After agent acceptance, the actor sees conversation steps and example utterances
- **Actor Guidance Reference**: Briefing and live view can show must-ask checkpoints and reveal-when-asked prompts
- **Template Rendering**: Scenario placeholders are resolved from selected persona data before and during the call
- **Daily.co Audio**: Connects to WebRTC rooms via `@daily-co/daily-js` for live audio
- **Real-time Status**: Monitors session status via Supabase Realtime to detect agent join/disconnect
- **PCC Integration**: Starts PCC bot instances via `/start` endpoint for each call

## Tech Stack

- Next.js 16 (App Router)
- React 19.2
- TypeScript 5.9
- Tailwind CSS v4
- Supabase (Database + Realtime)
- @daily-co/daily-js (WebRTC audio)

## Requirements

- Node.js 24+
- pnpm 10+

## Setup

```bash
# Install dependencies (from repo root)
make install

# Configure environment
cp .env.example .env.local
# Edit .env.local with your keys

# Run development server
pnpm dev --port 3001
```

Open http://localhost:3001

## Environment Variables

```bash
# Supabase
NEXT_PUBLIC_SUPABASE_URL=https://xxx.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=your_supabase_anon_key
SUPABASE_SERVICE_ROLE_KEY=your_supabase_service_role_key

# PCC Service URL
# Local dev: http://localhost:7860 (default port for local PCC dev server)
# Production: Your deployed PCC endpoint URL
PCC_AGENT_URL=http://localhost:7860

# Daily.co API key (for generating meeting tokens)
DAILY_API_KEY=your_daily_api_key

# Optional: Pipecat Cloud API key (for cloud-deployed PCC)
PIPECAT_CLOUD_API_KEY=your_pipecat_cloud_api_key
```

## Project Structure

```
apps/customer/
├── app/                        # Next.js App Router
│   ├── layout.tsx              # Root layout
│   ├── page.tsx                # Customer call interface
│   ├── globals.css             # Global styles + Tailwind
│   └── api/
│       └── sessions/
│           └── create/route.ts # Session creation endpoint
├── src/
│   └── lib/
│       ├── supabase.ts         # Supabase client
│       ├── customer-session.ts # Session lifecycle hook
│       ├── daily-audio.ts      # Daily.co audio connection hook
│       ├── scenario-render.ts   # Persona placeholder rendering for scenario text
│       ├── use-customers.ts     # Persona list fetching hook
│       └── use-scenarios.ts     # Scenario list fetching hook
└── package.json
```

## Call Flow

### 1. Idle / Preparation

Actor selects a persona and scenario (filtered by matching domain), reviews briefing, then clicks "Start Call".

### 2. Calling

The app:

1. Sends `POST /api/sessions/create` with required `customer_id` and `scenario_id`
2. API route validates both IDs against `customers` and active `scenarios`
3. API route calls PCC `/start` to create a Daily room and spawn a bot
4. API route generates customer + agent tokens via Daily REST API
5. API route inserts a `pending` session with persona/scenario metadata in row columns + `state`
6. Customer connects to the Daily room with audio
7. Subscribes to Supabase Realtime for session status changes

### 3. Connected

When an agent accepts the session (status changes to `active`), the actor script is shown with per-step guidance.

### 4. Ended

When the session status changes to `completed` or `abandoned`, or the customer clicks "End Call", the call ends.

## Persona and Scenario Definition + Loading

### 1) Definition in repository

- Personas: `personas/customer_profile_*.json`
- Scenarios: `scenarios/scenario_*.json`

### 2) Seeding into Supabase

- Script: `scripts/seed-experimental-data.mjs`
- Local: `make db-seed-experiment`
- Linked remote: `make db-seed-experiment-linked`
- Writes:
  - Persona profile + notes to `customers`
  - Persona history to `customer_interactions`
  - Scenario catalog to `scenarios`

### 3) Runtime loading in this app

- `useCustomers()` reads personas from `customers`
- `useScenarios()` reads active scenarios from `scenarios`, including `actor_guidance`
- `scenario-render.ts` resolves placeholders like `{{customer_name}}`, `{{customer_dob_human}}`, and address tokens for actor-facing script text
- Scenario scripts should use explicit issue wording in opening turns (for example, exactly which request was denied)

### 4) Session-time persistence

- `/api/sessions/create` stores selected scenario metadata on session columns (`scenario_id`, `scenario_family`, `civility_condition`) and mirrors it in `sessions.state`

## API Route

### `POST /api/sessions/create`

Creates a new customer-initiated session:

1. Validates selected `customer_id` and active `scenario_id`
2. Calls PCC service `/start` to create a Daily room and bot instance
3. Generates customer token (non-owner) and agent token (owner) via Daily REST API
4. Inserts a `pending` session row into Supabase with room URL, agent token, selected persona ID, and selected scenario metadata in both columns and `state`
5. Returns `{ session_id, room_url, customer_token }` to the client

## Key Hooks

### `useCustomerSession()`

Manages the customer call lifecycle:

- `startCall({ customerId, scenarioId })` — Initiates a call for the selected persona/scenario pair
- `endCall()` — Ends the current call
- State: `callState`, `sessionId`, `roomUrl`, `customerToken`, `isLoading`, `error`
- Subscribes to Supabase Realtime to detect agent join (pending → active)

### `useDailyAudio(roomUrl, customerToken)`

Connects to Daily.co room with audio:

- Returns `{ isConnected }` — Whether audio connection is established
- Automatically joins when roomUrl and token are provided
- Cleans up on unmount

### `useCustomers()`

Fetches available persona profiles from Supabase:

- Returns `{ customers, isLoading }` — List of customer profiles for dropdown + briefing

### `useScenarios()`

Fetches active experimental scenarios from Supabase:

- Returns `{ scenarios, isLoading, error }` — List used in scenario selection and briefing
- Maps DB shape (`scenario_id`, `conversation`, `civility_condition`, `behavior_instruction`, `actor_guidance`) into typed `Scenario` objects

## Development

```bash
pnpm dev --port 3001    # Start dev server with Turbopack
pnpm build              # Build for production
pnpm lint               # Lint code
pnpm typecheck          # Type check
```
