# VoiceBridge Customer App

Next.js customer-facing call interface for initiating support calls with VoiceBridge agents.

## Features

- **Simple Call Flow**: Idle → Calling → Connected → Ended
- **Customer Profile Selection**: Dropdown to select a customer profile before calling
- **Routing Simulation Controls**: Select direct queue vs Voice AI transfer and provide handoff details
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
│       └── use-customers.ts    # Customer list fetching hook
└── package.json
```

## Call Flow

### 1. Idle

Customer selects a profile from the dropdown and clicks "Start Call".

### 2. Calling

The app:

1. Sends `POST /api/sessions/create` with optional `customer_id` and optional routing payload (`source`, `handoff_summary`, `transfer_reason`)
2. API route calls PCC `/start` to create a Daily room and spawn a bot
3. API route generates customer + agent tokens via Daily REST API
4. API route inserts a `pending` session into Supabase with customer/routing metadata in `state`
5. Customer connects to the Daily room with audio
6. Subscribes to Supabase Realtime for session status changes

### 3. Connected

When an agent accepts the session (status changes to `active`), the UI updates to show the connected state.

### 4. Ended

When the session status changes to `completed` or `abandoned`, or the customer clicks "End Call", the call ends.

## API Route

### `POST /api/sessions/create`

Creates a new customer-initiated session:

1. Calls PCC service `/start` to create a Daily room and bot instance
2. Generates customer token (non-owner) and agent token (owner) via Daily REST API
3. Inserts a `pending` session row into Supabase with room URL, agent token, optional customer ID, and routing context in `state`
4. Returns `{ session_id, room_url, customer_token }` to the client

## Key Hooks

### `useCustomerSession()`

Manages the customer call lifecycle:

- `startCall(customerId?, routing?)` — Initiates a call via API with optional routing context
- `endCall()` — Ends the current call
- State: `callState`, `sessionId`, `roomUrl`, `customerToken`, `isLoading`, `error`
- Subscribes to Supabase Realtime to detect agent join (pending → active)

### `useDailyAudio(roomUrl, customerToken)`

Connects to Daily.co room with audio:

- Returns `{ isConnected }` — Whether audio connection is established
- Automatically joins when roomUrl and token are provided
- Cleans up on unmount

### `useCustomers()`

Fetches available customer profiles from Supabase:

- Returns `{ customers, isLoading }` — List of customer profiles for the dropdown

## Development

```bash
pnpm dev --port 3001    # Start dev server with Turbopack
pnpm build              # Build for production
pnpm lint               # Lint code
pnpm typecheck          # Type check
```
