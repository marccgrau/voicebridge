# VoiceBridge Agent Workspace

Next.js agent workspace with **phase-based procedural UI** for real-time customer service call guidance.

## Features

- **Phase-Based UI**: Adaptive layout that shows only contextually relevant information for the current call state
- **RTVI Integration**: Low-latency WebRTC data channel for real-time suggestions, transcripts, and process updates
- **Multi-Phase Workflow**:
  - **Idle**: Waiting screen for incoming calls
  - **Incoming**: Customer info preview + accept/reject interface
  - **Active (Pre-process)**: Customer info + transcript + suggestions (process detection in progress)
  - **Active (In-process)**: Full workspace with process visualization
  - **Postcall Summary**: Transcript review + AI-generated summary editor
- **Auto-Return to Idle**: After saving summary, workspace automatically returns to waiting state
- **Real-time Updates**: Supabase Realtime for session state + RTVI for live data
- **Incoming Queue Preview**: Pending calls can be selected before accept to preview the corresponding customer brief
- **Routing Context Briefing**: Customer panel surfaces direct vs Voice AI transfer context, including handoff summary and transfer reason when present
- **Admin Panel**: `/admin` route with session list and transcript inspector

## Tech Stack

- Next.js 16 (App Router)
- React 19.2
- TypeScript 5.9
- Tailwind CSS v4
- Supabase (Database + Realtime)
- @pipecat-ai/client-js (RTVI client)

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
pnpm dev
```

Open http://localhost:3000

## Environment Variables

```bash
# Supabase
NEXT_PUBLIC_SUPABASE_URL=https://xxx.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=your_supabase_anon_key
SUPABASE_SERVICE_ROLE_KEY=your_supabase_service_role_key
NEXT_PUBLIC_AGENT_MIC_ENABLED=true  # Set false for local dual-tab testing on one machine

# OpenAI (for AI-generated postcall summaries)
OPENAI_API_KEY=your_openai_api_key
```

## Project Structure

```
apps/agent-workspace/
├── app/                        # Next.js App Router
│   ├── layout.tsx              # Root layout with theme
│   ├── page.tsx                # Main workspace with phase logic
│   ├── globals.css             # Global styles + Tailwind
│   ├── admin/page.tsx          # Admin panel (session list + inspector)
│   └── api/
│       └── sessions/
│           ├── summary/route.ts               # Save postcall summary
│           └── [sessionId]/
│               └── generate-summary/route.ts  # AI summary generation
├── src/
│   ├── components/
│   │   └── workspace/          # Phase-based panels
│   │       ├── InteractionPanel.tsx          # Transcript display
│   │       ├── SuggestionsPanel.tsx          # Agent guidance
│   │       ├── ProcessLayer.tsx             # Process step visualization
│   │       ├── CustomerInfoPanel.tsx        # Customer profile
│   │       ├── IncomingCallNotification.tsx  # Call accept UI
│   │       └── SummaryEditor.tsx            # Postcall notes
│   └── lib/
│       ├── supabase.ts         # Supabase client
│       ├── session.ts          # Session management hook
│       ├── rtvi.ts             # RTVI message handling hook
│       ├── pending-sessions.ts # Incoming call subscription
│       ├── use-phase.ts        # Phase detection logic
│       └── use-summary.ts      # Summary editor state
└── package.json
```

## UI Phases

### 1. Idle Phase

**When**: No active session, no pending calls
**Shows**: Centered waiting message

### 2. Incoming Phase

**When**: Pending customer call waiting for agent acceptance
**Shows**:

- Incoming call notification (customer info preview)
- Accept button
- Customer info panel (expanded)

### 3. Active (Pre-Process) Phase

**When**: Call active, process not yet detected
**Shows**:

- Process layer (detecting state)
- Customer info (compact, toggleable)
- Live transcript (expanded)
- Suggestions panel

### 4. Active (In-Process) Phase

**When**: Call active, process detected
**Shows**:

- Process layer (steps + progress)
- Customer info (compact, toggleable)
- Live transcript (expanded)
- Suggestions panel (process-aware)

### 5. Postcall Summary Phase

**When**: Call ended, agent reviewing
**Shows**:

- Process layer (final state)
- Customer info (compact)
- Transcript (read-only)
- Summary editor with AI-generated summary
- Auto-saves and returns to idle after submission

## RTVI Message Types

The workspace receives real-time updates via RTVI (WebRTC data channel):

### `transcript_segment`

```typescript
{
  action: "transcript_segment",
  data: {
    speaker: "customer" | "agent",
    text: string,
    timestamp: string,
    isFinal: boolean
  }
}
```

### `agent_guidance`

```typescript
{
  action: "agent_guidance",
  data: {
    suggestions: Array<{
      text: string,
      type: "response" | "question" | "action" | "escalation"
    }>
  }
}
```

### `process_illustration`

```typescript
{
  action: "process_illustration",
  data: {
    processKey: string,
    processName: string,
    steps: Array<{
      key: string,
      label: string,
      status: "pending" | "in_progress" | "completed"
    }>,
    currentStep: number
  }
}
```

## Real-time Architecture

```
PCC Service (Pipecat Pipeline)
    ↓ RTVI (WebRTC data channel)
Agent Workspace (@pipecat-ai/client-js)
    ↓ useRTVI hook
React state updates
    ↓
Phase-based UI re-renders
```

**Supabase Realtime** is used only for:

- Incoming call notifications (pending session inserts)
- Session status changes (active → completed)

**RTVI (WebRTC data channel)** is used for:

- Live transcript updates
- Real-time suggestions
- Process detection and step tracking

## Key Hooks

### `useSession()`

Manages session lifecycle:

- `acceptSession(id)` — Accept pending call (updates status to active, connects RTVI)
- `stopSession()` — End active call (updates status to completed)
- `clearSession()` — Return to idle state

### `useRTVI(roomUrl, roomToken, callbacks, options)`

Connects to RTVI and handles messages:

- `onTranscript` — New transcript segment
- `onSuggestion` — New agent guidance
- `onProcessIllustration` — Process update
- Options: `{ audioEnabled }` — Enable agent microphone audio

### `usePendingSessions()`

Subscribes to incoming calls via Supabase Realtime:

- Returns array of pending sessions
- Auto-updates on insert/update/delete

### `usePhase({ sessionId, isConnected, processKey, pendingSessions, sessionStatus })`

Determines current UI phase:

- Returns: `"idle" | "incoming" | "active_preprocess" | "active_inprocess" | "postcall_summary"`

### `useSummary(sessionId, { autoGenerate, onSaveComplete })`

Manages postcall summary:

- Auto-generates summary when entering postcall phase
- Calls `onSaveComplete()` after successful save
- Triggers return to idle state

## Phase Transition Flow

```
idle
  → (pending session arrives) → incoming
  → (agent accepts) → active_preprocess
  → (process detected) → active_inprocess
  → (call ends) → postcall_summary
  → (summary saved) → idle
```

## Development

```bash
pnpm dev          # Start dev server with Turbopack
pnpm build        # Build for production
pnpm lint         # Lint code
pnpm typecheck    # Type check
pnpm test         # Run tests
```
