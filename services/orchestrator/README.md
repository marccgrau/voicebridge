# VoiceBridge Orchestrator (Legacy)

> **Deprecated**: This service has been superseded by the [PCC Service](../pcc/README.md). The PCC service provides equivalent functionality using Pipecat Cloud's standard runner pattern, eliminating the need for a custom FastAPI orchestrator. This code remains in the repository for reference but is no longer actively developed.

Python voice pipeline orchestrator using Pipecat for real-time customer service guidance.

## What Changed

The orchestrator was the original backend that combined:
- FastAPI HTTP API for session management
- Pipecat pipeline for voice processing
- Supabase integration for persistence

The PCC service replaces this with:
- Stateless Pipecat Cloud bot (no custom API server)
- Session management moved to Next.js API routes + Supabase
- Simpler deployment via `pipecat cloud deploy`

## Original Features

- **Multi-Provider LLM Support**: OpenAI, Gemini, Anthropic — configurable per-session
- **Pipecat Pipeline**: Voice processing with Speechmatics STT, Silero VAD, and Daily.co transport
- **Process Detection**: LLM-driven process identification and step tracking (ProcessFlow)
- **Suggestion Generation**: Context-aware agent guidance with process awareness (SuggestionFlow)
- **RTVI Message Delivery**: Low-latency WebRTC data channel for real-time UI updates
- **Process Catalog**: Full-text search for customer service processes

## API Endpoints (No Longer Active)

- `POST /sessions/create` — Customer-initiated session
- `POST /sessions/accept` — Agent accepts pending session
- `POST /sessions/start` — Agent-initiated session
- `POST /sessions/stop` — Stop session
- `GET /sessions/{id}/status` — Get session status
- `POST /sessions/summary` — Save postcall summary
- `POST /sessions/{id}/generate-summary` — AI summary generation
- `GET /healthz` — Health check

## Development (Reference Only)

```bash
cd services/orchestrator
uv sync                           # Install dependencies
uv run uvicorn src.main:app --reload  # Run server
uv run pytest                     # Run tests
uv run ruff check .               # Lint
uv run ruff format .              # Format
```
