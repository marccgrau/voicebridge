# VoiceBridge Agent Workspace

Next.js agent workspace with **phase-based procedural UI** for real-time customer service call guidance.

## Features

- **Phase-Based UI**: Adaptive layout that shows only contextually relevant information for the current call state
- **RTVI Integration**: Low-latency WebRTC data channel for real-time suggestions, transcripts, and process updates
- **Multi-Phase Workflow**:
  - **Idle**: Waiting screen for incoming calls
  - **Incoming**: Customer info preview + accept/reject interface
  - **Active (Pre-process)**: Customer info + transcript + suggestions (process detection in progress)
  - **Active (In-process)**: Full 4-panel workspace with process visualization
  - **Postcall Summary**: Transcript review + AI-generated summary editor
- **Auto-Return to Idle**: After saving summary, workspace automatically returns to waiting state
- **Real-time Updates**: Supabase Realtime for session state + RTVI for live data
- **Incoming Call Notifications**: Toast-style notifications for pending customer calls

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
# Install dependencies
pnpm install

# Configure environment
cp .env.example .env.local
# Edit .env.local with your Supabase keys

# Run development server
pnpm dev
```

Open http://localhost:3000

## Environment Variables

```bash
# Supabase
NEXT_PUBLIC_SUPABASE_URL=https://xxx.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=eyJhbGc...
SUPABASE_SERVICE_ROLE_KEY=eyJhbGc...

# Orchestrator API
NEXT_PUBLIC_ORCHESTRATOR_URL=http://localhost:8000
```

## Project Structure

```
apps/agent-workspace/
├── app/                    # Next.js App Router
│   ├── layout.tsx         # Root layout with theme
│   ├── page.tsx           # Main workspace with phase logic
│   └── globals.css        # Global styles + Tailwind
├── src/
│   ├── components/
│   │   └── workspace/     # Phase-based panels
│   │       ├── InteractionPanel.tsx       # Transcript
│   │       ├── SuggestionsPanel.tsx       # Agent guidance
│   │       ├── ProcessLayer.tsx           # Process visualization layer
│   │       ├── CustomerInfoPanel.tsx      # Customer profile
│   │       ├── IncomingCallNotification.tsx  # Call accept UI
│   │       └── SummaryEditor.tsx          # Postcall notes
│   └── lib/
│       ├── supabase.ts    # Supabase client
│       ├── session.ts     # Session management hook
│       ├── rtvi.ts        # RTVI message handling hook
│       ├── pending-sessions.ts  # Incoming call subscription
│       ├── use-phase.ts   # Phase detection logic
│       └── use-summary.ts # Summary editor state
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
- Accept/Reject buttons
- Process layer (waiting state)
- Customer info panel (expanded)

### 3. Active (Pre-Process) Phase

**When**: Call active, process not yet detected
**Shows**:

- Process layer (detecting state)
- Customer info (compact)
- Live transcript (expanded)
- Suggestions panel

### 4. Active (In-Process) Phase

**When**: Call active, process detected
**Shows**:

- Process layer (steps + progress)
- Customer info (compact)
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
Backend Orchestrator (Pipecat Pipeline)
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

## Development

```bash
# Start dev server with Turbopack
pnpm dev

# Build for production
pnpm build

# Lint code
pnpm lint

# Type check
pnpm typecheck

# Run tests
pnpm test
```

## Key Hooks

### `useSession()`

Manages session lifecycle:

- `acceptSession(id)` - Accept pending call
- `stopSession()` - End active call
- `clearSession()` - Return to idle state

### `useRTVI(roomUrl, roomToken, callbacks)`

Connects to RTVI and handles messages:

- `onTranscript` - New transcript segment
- `onSuggestion` - New agent guidance
- `onProcessIllustration` - Process update

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
