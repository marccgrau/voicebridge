# VoiceBridge PCC Service

Pipecat Cloud service for VoiceBridge — provides real-time call guidance by listening to customer service calls and delivering AI-powered suggestions to agents.

## Features

- **Listen-only bot**: Joins Daily.co rooms, processes audio without responding verbally
- **Real-time transcription**: Deepgram STT (`nova-3-general`) for live transcription
- **Process detection**: Catalog-based token-overlap matching from customer speech (no LLM)
- **AI suggestions**: OpenAI LLM generates contextual guidance for agents (default: `gpt-4.1`)
- **RTVI delivery**: Sends transcript, process illustrations, and suggestions via WebRTC data channel
- **Parallel processing**: Suggestions run in a parallel branch to avoid blocking transcript/process delivery

## Architecture

```
Daily.co WebRTC (audio in)
    → Deepgram STT (nova-3-general, streaming)
        → TranscriptWriter (emits TranscriptSegmentFrame)
            → ProcessDetectionProcessor (emits ProcessIllustrationFrame)
                → ParallelPipeline
                    ├─ passthrough (frames reach RTVI immediately)
                    └─ suggestion branch (context builder → LLM → output processor)
                        → VoiceBridgeRTVIObserver (sends via RTVI)
                            → Daily.co WebRTC (data channel out)
```

The `ParallelPipeline` ensures transcript segments and process detections are delivered immediately while suggestions are generated asynchronously in a separate branch.

## Setup

### 1. Install dependencies

```bash
uv sync
```

### 2. Configure environment variables

```bash
cp .env.example .env
```

Required variables:
- `DAILY_API_KEY` — Daily.co API key (for creating rooms in local dev)
- `DEEPGRAM_API_KEY` — Deepgram API key for STT
- `OPENAI_API_KEY` — OpenAI API key for LLM suggestions

Optional variables:
- `SUGGESTION_MODEL` — Override default LLM model (default: `gpt-4.1`)
- `PIPECAT_CLOUD_API_KEY` — Required for cloud deployment

### 3. Run locally

```bash
# From repo root
make pcc-dev

# Or directly from services/pcc
uv run python bot.py -t daily --port 7860
```

This starts a local HTTP server on port 7860 that:
- Exposes a `/start` endpoint for session creation (compatible with customer app)
- Handles multiple concurrent sessions automatically
- Each `/start` call creates a new bot instance
- Uses the standard Pipecat runner with `RunnerArguments`

### 4. How it works

When a customer initiates a call:
1. Customer app sends `POST /api/sessions/create` to its own Next.js API route
2. That route calls `POST http://localhost:7860/start` with `{"createDailyRoom": true}`
3. PCC creates a Daily.co room and spawns a bot instance
4. Bot joins the room and starts processing audio
5. Bot sends RTVI messages to the agent workspace via the WebRTC data channel
6. Multiple sessions run independently — each gets its own bot instance

## Cloud Deployment

Deploy to Pipecat Cloud (requires `PIPECAT_CLOUD_API_KEY`):

```bash
# Set your Pipecat Cloud API key
export PIPECAT_CLOUD_API_KEY=your_key_here

# Deploy
pipecat cloud deploy
```

Configuration is in `pcc-deploy.toml`. Steps:
1. Update the Docker image path
2. Create a secret set named `voicebridge-secrets` with your API keys
3. Adjust agent profile and scaling as needed
4. Production deployment exposes a public `/start` endpoint

## Process Definitions

Process definitions are stored in `process_content/` as markdown files with YAML frontmatter:

```markdown
---
process_key: lost_stolen_card
name: Lost or Stolen Card
domain: banking
intents:
  - lost card
  - stolen card
---

## Step 1: Verify Identity
[content]

## Step 2: Block Card
[content]
```

The `ProcessDetectionProcessor` loads these on startup and matches them against customer speech using intent keyword token-overlap (no LLM calls required).

Currently includes 9 process definitions covering banking scenarios (lost cards, e-banking, identity verification, estates, etc.).

## Project Structure

```
services/pcc/
├── bot.py                    # Main entry point (Pipecat runner pattern)
├── src/
│   ├── processors.py         # Pipeline processors (5 processors + RTVI observer)
│   ├── frames.py             # Custom frame definitions (3 frames)
│   └── process_catalog.py    # Process loading, indexing, and matching
├── process_content/          # Process definition markdown files (9 files)
├── tests/                    # Pytest test suite
├── pyproject.toml            # Dependencies and config (Python 3.13+)
├── pcc-deploy.toml           # Pipecat Cloud deployment config
└── .env.example              # Environment variable template
```

## Pipeline Processors

1. **TranscriptWriter** — Converts Deepgram STT output into `TranscriptSegmentFrame` with speaker, text, and timestamp
2. **ProcessDetectionProcessor** — Loads process catalog on startup, matches customer speech against intent keywords, emits `ProcessIllustrationFrame` with step tracking
3. **SuggestionContextBuilder** — Aggregates transcript and process context for LLM input
4. **SuggestionOutputProcessor** — Processes LLM response into structured `SuggestionFrame`
5. **VoiceBridgeRTVIObserver** — Intercepts custom frames and publishes them as RTVI `bot-action` messages with retry logic

## RTVI Message Types

The service sends three types of RTVI messages:

### `transcript_segment`

```json
{
  "action": "transcript_segment",
  "data": {
    "session_id": "...",
    "speaker": "customer",
    "text": "I lost my credit card",
    "timestamp": "2025-01-15T10:30:00Z",
    "is_final": true
  }
}
```

### `process_illustration`

```json
{
  "action": "process_illustration",
  "data": {
    "process_key": "lost_stolen_card",
    "process_name": "Lost or Stolen Card",
    "steps": [
      { "key": "step_1", "label": "Verify Identity", "status": "completed" },
      { "key": "step_2", "label": "Block Card", "status": "in_progress" }
    ],
    "current_step": 1
  }
}
```

### `agent_guidance`

```json
{
  "action": "agent_guidance",
  "data": {
    "suggestions": [
      {
        "type": "response",
        "text": "Ask for the card's last 4 digits"
      }
    ],
    "process_key": "lost_stolen_card"
  }
}
```

## Development

```bash
uv run pytest              # Run tests
uv run ruff check .        # Lint
uv run ruff format .       # Format
```

## Troubleshooting

**Import errors**: Make sure you've run `uv sync` to install all dependencies.

**Room creation fails**: Verify your `DAILY_API_KEY` is set correctly.

**No transcription**: Check that `DEEPGRAM_API_KEY` is valid and the room has audio input.

**No suggestions**: Verify `OPENAI_API_KEY` is set and the model is available.

**Bot doesn't join room**: Ensure the PCC service is running and reachable at the configured `PCC_AGENT_URL`.
