# VoiceBridge PCC Service

Unified Pipecat service for VoiceBridge.

## Pipeline

One transport + one STT pipeline, then fan-out via `ParallelPipeline`:

- transcript branch
- process branch (LLM via `PROCESS_MODEL`, default `gpt-4.1-nano`)
- suggestion branch (LLM via `SUGGESTION_MODEL`, default `gpt-4.1`)

Each branch emits RTVI bot-action messages:

- `transcript_segment`
- `process_illustration`
- `agent_guidance`

## Run locally

```bash
uv sync
uv run python bot.py -t daily --port 7860
```

## Required environment variables

- `DAILY_API_KEY`
- `DEEPGRAM_API_KEY`
- `OPENAI_API_KEY`

Optional:

- `PROCESS_MODEL` (default: `gpt-4.1-nano`)
- `SUGGESTION_MODEL` (default: `gpt-4.1`)
- `PROCESS_CONTENT_PATH` (override process markdown path, default fallback is `services/process-agent/process_content/`)
