# VoiceBridge Orchestrator

Python voice pipeline orchestrator using Pipecat for customer service guidance.

## Features

- **Pipecat Pipeline**: Voice processing with Deepgram STT and Daily.co transport
- **LLM Integration**: Claude-powered process selection and slot extraction
- **Real-time Events**: Publishes to Supabase Realtime for UI updates
- **Process Catalog**: Full-text search for customer service processes
- **Suggestion Engine**: Template-based with optional LLM rewriting

## Requirements

- Python 3.13+
- uv package manager

## Setup

```bash
# Install dependencies
uv sync

# Configure environment
cp .env.example .env
# Edit .env with your API keys

# Run server
uv run uvicorn src.main:app --reload
```

## API Endpoints

- `POST /sessions/start` - Start a new voice session
- `POST /sessions/stop` - Stop an active session
- `GET /healthz` - Health check
- `GET /sessions/{session_id}/status` - Get session status

## Development

```bash
# Run tests
uv run pytest

# Lint
uv run ruff check .

# Format
uv run ruff format .
```
