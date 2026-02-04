# VoiceBridge

Proactive guidance workspace for live human-human customer service calls.

## Architecture

- **Next.js UI** (`apps/web`) - 4-panel workspace interface
- **Python Pipecat Orchestrator** (`services/orchestrator`) - Voice pipeline with LLM
- **Supabase Postgres** - Database and realtime events
- **Shared Contracts** (`packages/contracts`) - TypeScript schemas with Zod

## Prerequisites

- Node.js v24+
- pnpm v10+
- Python 3.14+
- uv (Python package manager)
- Supabase CLI

## Quick Start

```bash
# Install dependencies
make install

# Set up environment variables
cp apps/web/.env.example apps/web/.env.local
cp services/orchestrator/.env.example services/orchestrator/.env

# Run database migrations
make db-migrate

# Start development servers
make dev
```

## Environment Variables

### Web App (`apps/web/.env.local`)

```bash
NEXT_PUBLIC_SUPABASE_URL=https://xxx.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=xxx
SUPABASE_SERVICE_ROLE_KEY=xxx
```

### Orchestrator (`services/orchestrator/.env`)

```bash
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_SERVICE_ROLE_KEY=xxx
DEEPGRAM_API_KEY=xxx
ANTHROPIC_API_KEY=xxx
DAILY_API_KEY=xxx
```

## Project Structure

```
voicebridge/
├── apps/web/                    # Next.js UI
├── services/orchestrator/       # Python Pipecat voice pipeline
├── packages/
│   ├── contracts/              # Shared TypeScript schemas
│   └── db/                     # Database helpers
└── supabase/migrations/        # Database migrations
```

## Development

```bash
# Run linting
make lint

# Run type checking
make typecheck

# Run tests
make test

# Format code
make format
```

## Services

| Service | Provider | Purpose |
|---------|----------|---------|
| STT | Deepgram | Streaming speech-to-text |
| LLM | Anthropic Claude | Process selection & suggestions |
| Audio | Daily.co | WebRTC voice transport |
| Database | Supabase | Postgres + Realtime |
