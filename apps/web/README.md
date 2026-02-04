# VoiceBridge Web UI

Next.js workspace interface for real-time customer service call guidance.

## Features

- **4-Panel Workspace Layout**
  - Live transcript stream with speaker identification
  - AI-generated response suggestions
  - Process status tracking with step checklist
  - Session history browser

- **Real-time Updates**: Supabase Realtime subscriptions for instant UI updates
- **Session Management**: Start/stop voice sessions with one click
- **Suggestion Feedback**: Track which suggestions agents use or dismiss
- **Responsive Design**: Tailwind CSS v4 with custom theme

## Tech Stack

- Next.js 16 (App Router)
- React 19.2
- TypeScript 5.9
- Tailwind CSS v4
- Supabase (Database + Realtime)

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
apps/web/
├── app/                    # Next.js App Router
│   ├── layout.tsx         # Root layout
│   ├── page.tsx           # Main workspace page
│   └── globals.css        # Global styles
├── src/
│   ├── components/
│   │   └── workspace/     # 4 workspace panels
│   └── lib/
│       ├── supabase.ts    # Realtime subscriptions
│       └── session.ts     # Session management
└── package.json
```

## Workspace Panels

### 1. Interaction Panel (Top Left)
- Live transcript with customer/agent turns
- Auto-scroll to latest message
- Final transcripts only (no interim updates)

### 2. Suggestions Panel (Top Right)
- 3-6 AI-generated response suggestions
- Click to copy to clipboard
- Dismiss unwanted suggestions
- Feedback tracking (used/modified/dismissed)

### 3. Process Status Panel (Bottom Left)
- Current detected process
- Step-by-step checklist with status
- Extracted customer information (slots)

### 4. History Panel (Bottom Right)
- Recent session list
- Session status indicators
- Quick navigation to past sessions

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
```

## Real-time Event Flow

```
Customer speaks
    ↓
Orchestrator processes
    ↓
Events published to Supabase Realtime
    ↓
UI subscribes to session:{id}:events channel
    ↓
React state updates
    ↓
UI re-renders with new data
```

## Event Types

- `transcript_segment` - New transcript from STT
- `process_selection` - Process identified
- `slot_extraction` - Customer data extracted
- `suggestion` - New response suggestions
- `session_state` - Full session state update
