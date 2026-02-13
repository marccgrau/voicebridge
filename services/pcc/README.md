# VoiceBridge PCC Service

Independent Pipecat Cloud service for VoiceBridge — provides real-time call guidance without requiring the orchestrator.

## Features

- **Listen-only bot**: Joins Daily.co rooms, processes customer audio without responding verbally
- **Real-time transcription**: Uses Deepgram STT for live transcription
- **Process detection**: Catalog-based process matching from customer speech
- **AI suggestions**: OpenAI LLM generates contextual guidance for agents
- **RTVI delivery**: Sends transcript, process illustrations, and suggestions via WebRTC data channel

## Architecture

```
Daily.co WebRTC → Deepgram STT → ParallelPipeline → RTVI → Agent Workspace
                                   ├─ passthrough (transcript + process)
                                   └─ suggestion branch (LLM)
```

The service uses a `ParallelPipeline` to process suggestions in a separate branch while passing through transcripts and process detections immediately for low latency.

## Setup

### 1. Install dependencies

```bash
uv sync
```

### 2. Configure environment variables

Copy `.env.example` to `.env` and fill in your API keys:

```bash
cp .env.example .env
```

Required variables:
- `DAILY_API_KEY` - Daily.co API key (for creating rooms in local dev)
- `DEEPGRAM_API_KEY` - Deepgram API key for STT
- `OPENAI_API_KEY` - OpenAI API key for LLM suggestions

Optional variables:
- `DAILY_ROOM_URL` - Use an existing Daily.co room instead of creating one
- `SUGGESTION_MODEL` - Override default LLM model (default: `gpt-4.1-mini`)

### 3. Run locally

**Using Pipecat runner** (recommended):

```bash
# Option 1: Using make (from repo root)
make pcc-dev

# Option 2: Direct execution from services/pcc
uv run python bot.py -t daily --port 7860
```

This starts a local HTTP server on port 7860 (configurable via `--port` flag) that:
- Exposes a `/start` endpoint for session creation (compatible with customer app)
- Handles multiple concurrent sessions automatically
- Each `/start` call creates a new bot instance
- Uses the standard Pipecat runner with `RunnerArguments`

### 4. How it works

When a customer initiates a call:
1. Customer app sends `POST http://localhost:7860/start` with `{"session_id": "..."}`
2. PCC local server creates a Daily.co room and spawns a bot instance
3. Bot joins the room and starts processing audio
4. Bot sends RTVI messages to the agent workspace
5. Multiple sessions work independently — each gets its own bot instance

## Cloud Deployment

Deploy to Pipecat Cloud (requires `PIPECAT_CLOUD_API_KEY`):

```bash
# Set your Pipecat Cloud API key in .env
PIPECAT_CLOUD_API_KEY=your_key_here

# Deploy
pipecat cloud deploy
```

Configuration is in `pcc-deploy.toml`. Make sure to:
1. Update the Docker image path
2. Create a secret set named `voicebridge-secrets` with your API keys
3. Adjust agent profile and scaling as needed
4. Production deployment exposes a public `/start` endpoint for session creation

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

The `ProcessDetectionProcessor` loads these on startup and matches them against customer speech using intent keywords.

## Project Structure

```
services/pcc/
├── bot.py                    # Main entry point
├── src/
│   ├── processors.py         # Pipeline processors
│   ├── frames.py            # Custom frame definitions
│   └── process_catalog.py   # Process loading and matching
├── process_content/         # Process definition markdown files
├── pyproject.toml           # Dependencies and config
├── pcc-deploy.toml          # Pipecat Cloud deployment config
└── .env.example             # Environment variable template
```

## Development Notes

- **Python version**: Requires Python 3.13+
- **Local testing**: The bot creates a temporary Daily.co room (1-hour expiry by default)
- **RTVI protocol**: Custom messages follow the RTVI spec with `bot-action` events
- **Parallel processing**: Suggestions run in parallel to avoid blocking transcript/process delivery
- **No database**: This service is stateless — transcript persistence happens in the agent workspace or other services

## RTVI Message Types

The service sends three types of RTVI messages:

1. **transcript_segment** - Live transcript segments
   ```json
   {
     "action": "transcript_segment",
     "session_id": "...",
     "speaker": "customer",
     "text": "I lost my credit card",
     "timestamp": "2024-01-15T10:30:00Z",
     "is_final": true
   }
   ```

2. **process_illustration** - Process detection/tracking
   ```json
   {
     "action": "process_illustration",
     "process_key": "lost_stolen_card",
     "process_name": "Lost or Stolen Card",
     "steps": [...],
     "current_step": 0
   }
   ```

3. **agent_guidance** - AI suggestions
   ```json
   {
     "action": "agent_guidance",
     "suggestions": [
       {
         "type": "response",
         "content": "Ask for the card's last 4 digits",
         "priority": "high"
       }
     ],
     "process_key": "lost_stolen_card"
   }
   ```

## Troubleshooting

**Import errors**: Make sure you've run `uv sync` to install all dependencies.

**Room creation fails**: Verify your `DAILY_API_KEY` is set correctly.

**No transcription**: Check that `DEEPGRAM_API_KEY` is valid and the room has audio input.

**No suggestions**: Verify `OPENAI_API_KEY` is set and the model is available.
