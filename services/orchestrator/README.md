# VoiceBridge Orchestrator

Python voice pipeline orchestrator using Pipecat for real-time customer service guidance.

Architecture reference: see `ARCHITECTURE.md` for module boundaries and service ownership.

## Features

- **Multi-Provider LLM Support**: OpenAI (default), Gemini, Anthropic - configurable per-session
- **Pipecat Pipeline**: Voice processing with Pipecat Smart Turn V3, Speechmatics STT, and Daily.co transport
- **Process Detection**: Direct process-context resolver with metadata shortlist + optional LLM disambiguation
- **Suggestion Generation**: Direct per-turn suggestion generation with process awareness and stale-turn cancellation
- **RTVI Message Delivery**: Low-latency WebRTC data channel for real-time UI updates
- **Process Catalog**: Full-text search for customer service processes loaded from markdown files
- **Listen-Only Bot**: Processes audio without speaking, delivers guidance to human agents

## Requirements

- Python 3.13+
- uv package manager
- At least one LLM provider API key (OpenAI, Google, or Anthropic)

## Setup

```bash
# Install dependencies
uv sync

# Configure environment
cp .env.example .env
# Edit .env with your API keys (at least OPENAI_API_KEY required)

# Run server
uv run uvicorn src.main:app --reload
```

## Environment Variables

```bash
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_SERVICE_ROLE_KEY=xxx
SPEECHMATICS_API_KEY=xxx
DAILY_API_KEY=xxx

# STT / turn detection tuning
STT_LANGUAGE=en
STT_INCLUDE_PARTIALS=false
STT_ENABLE_DIARIZATION=true
STT_MAX_SPEAKERS=2
STT_PREFER_CURRENT_SPEAKER=true
SMART_TURN_CPU_COUNT=1
SMART_TURN_MODEL_PATH=

# LLM Provider API Keys (at least one required)
OPENAI_API_KEY=xxx          # Default provider
GOOGLE_API_KEY=xxx          # Optional: Gemini
ANTHROPIC_API_KEY=xxx       # Optional: Claude
```

## API Endpoints

### Session Management
- `POST /sessions/create` - Customer-initiated session (creates room, bot joins, status=pending)
- `POST /sessions/accept` - Agent accepts pending session (atomic status update, returns agent token)
- `POST /sessions/start` - Agent-initiated session (creates room, bot joins, status=active)
- `POST /sessions/stop` - Stop session (stops pipeline, status=completed)
- `GET /sessions/{id}/status` - Get session status

### Postcall
- `POST /sessions/summary` - Save agent's postcall summary
- `POST /sessions/{id}/generate-summary` - Generate AI summary from transcript

### Health
- `GET /healthz` - Health check (validates DB, Daily.co, STT, LLM connectivity)

## Multi-Provider LLM Configuration

Process context resolution and suggestion generation support independent provider configuration:

```bash
# Default (OpenAI gpt-5-nano for both)
POST /sessions/start
{}

# Custom providers
POST /sessions/start
{
  "processFlowProvider": "anthropic",
  "processFlowModel": "claude-haiku-4-5-20251001",
  "suggestionFlowProvider": "openai",
  "suggestionFlowModel": "gpt-4"
}
```

Provider options: `"openai"`, `"gemini"`, `"anthropic"`

## Pipeline Architecture

```
Daily.co WebRTC (audio in)
  → Pipecat Smart Turn V3 (LocalSmartTurnAnalyzerV3 + user turn strategies)
    → Speechmatics STT (EXTERNAL turn mode, explicit InputParams)
      → TranscriptWriter (saves to Supabase, emits TranscriptSegmentFrame)
        → ProcessContextResolverProcessor (detects process, tracks steps)
          → DirectSuggestionProcessor (generates suggestions per customer turn)
            → VoiceBridgeRTVIObserver (sends frames via RTVI)
              → Daily.co WebRTC (data channel out)
```

### Custom Frames

Three custom Pipecat frames carry domain data:
- `TranscriptSegmentFrame`: Live transcript with speaker role
- `ProcessIllustrationFrame`: Detected process with step progress
- `SuggestionFrame`: Agent guidance suggestions

### RTVI Messages

All frames are delivered to the agent workspace via RTVI (WebRTC data channel):
- `transcript_segment`: Live transcript updates
- `process_illustration`: Process detection and step tracking
- `agent_guidance`: Contextual agent suggestions

## Project Structure

```
services/orchestrator/
├── src/
│   ├── main.py              # FastAPI app, session endpoints
│   ├── config.py            # Settings (Supabase, LLM keys, etc.)
│   ├── llm/                 # Multi-provider LLM support
│   │   ├── factory.py       # LLMServiceFactory for provider creation
│   │   └── __init__.py
│   ├── pipeline/
│   │   ├── pipeline.py      # VoiceBridgePipeline (main audio pipeline)
│   │   ├── builder.py       # Runtime assembly for transport/STT/processors
│   │   ├── direct_processors.py # Direct process/suggestion processors
│   │   └── __init__.py
│   ├── processors/          # Custom FrameProcessors
│   │   ├── transcript_writer.py   # Saves transcripts, emits frames
│   │   ├── rtvi_observer.py       # Sends custom frames via RTVI
│   │   └── __init__.py
│   ├── db/
│   │   ├── client.py        # Supabase client wrapper
│   │   └── __init__.py
│   └── utils/
│       ├── retry.py         # Retry decorator
│       └── __init__.py
├── tests/
│   ├── api/                 # FastAPI endpoint tests
│   ├── pipeline/            # Pipeline processor tests
│   ├── llm/                 # LLM factory tests
│   ├── db/                  # Database client tests
│   └── conftest.py          # Shared fixtures
├── process_content/         # Process markdown definitions
├── pyproject.toml           # Dependencies and project config
└── uv.lock                  # Lockfile
```

## Development

```bash
# Run tests
uv run pytest

# Run specific test file
uv run pytest tests/llm/test_factory.py

# Lint
uv run ruff check .

# Format
uv run ruff format .

# Type hints check (via pyright if installed)
pyright src/
```

## Testing

Tests use:
- `pytest` for test runner
- `respx` for mocking HTTP calls (Daily.co API)
- `pytest-asyncio` for async test support
- Fixtures in `conftest.py`: `mock_supabase_client`, `mock_anthropic_client`, `mock_event_publisher`

Test structure:
- `tests/api/` - FastAPI endpoint tests
- `tests/pipeline/` - Pipeline processor tests
- `tests/llm/` - LLM factory tests
- `tests/db/` - Database client tests

## Process Definitions

Process definitions are markdown files in `process_content/`:

```markdown
---
process_key: billing_dispute
name: Billing Dispute Resolution
domain: billing
intents:
  - charge dispute
  - incorrect bill
---

## Step 1: Verify Account
Confirm customer identity...

## Step 2: Review Charges
Investigate disputed charges...
```

YAML frontmatter defines metadata, `## Step N:` headings define steps.
