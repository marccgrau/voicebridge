# VoiceBridge Flow Architecture

## Overview

VoiceBridge uses a **pipecat-native flow** architecture powered by the `pipecat-flows` library. Legacy implementations (`simple_turn` and `tool_agent`) have been removed in favor of this cleaner, more maintainable approach.

## Flow Agent Architecture

The `flow_agent` uses pipecat's native `FlowManager` for cleaner state management and conversation flow control.

### State Machine

```
[START] → [LISTENING] → [PROCESS_DETECTION] → [SUGGESTION_LOOP]
             ↓ (repeat)        ↓ (no match)           ↓ (repeat)
          [LISTENING]       [LISTENING]          [SUGGESTION_LOOP]
```

### Flow Nodes

#### 1. START
- Initial state when session begins
- Waits for first customer utterance
- No LLM calls

#### 2. LISTENING
- Buffers 3-5 customer utterances
- Accumulates conversation context
- Transitions to PROCESS_DETECTION when ready

#### 3. PROCESS_DETECTION
- LLM analyzes buffered conversation
- Selects matching process from markdown catalog
- Requires confidence > 0.6 to proceed
- Falls back to LISTENING if no confident match

#### 4. SUGGESTION_LOOP
- Generates suggestions after each customer utterance
- Tracks progress through process steps
- Updates process illustration in UI
- Repeats until call ends

### Function Handlers

Flow nodes use pipecat's function calling pattern:

| Function | Description | Next Node |
|----------|-------------|-----------|
| `ready_for_detection` | Signal enough context gathered | PROCESS_DETECTION |
| `select_process` | Choose process (confidence > 0.6) | SUGGESTION_LOOP |
| `need_more_context` | No confident match | LISTENING |
| `publish_suggestions` | Send suggestions to UI | SUGGESTION_LOOP |
| `update_process_step` | Track step progress | SUGGESTION_LOOP |

### State Management

All state is managed via `flow_manager.state` dict:

```python
{
    "session_id": str,
    "conversation_buffer": list[str],      # Recent utterances
    "detected_process": ProcessDefinition | None,
    "current_step": int,                    # 0-indexed
    "process_catalog": list[dict],          # Loaded from markdown files
    "utterance_count": int,
    "start_time": float,
}
```

## Usage

### API Request

```bash
curl -X POST http://localhost:8000/sessions/start \
  -H "Content-Type: application/json" \
  -d '{
    "process_illustration_enabled": true,
    "process_content_path": "process_content/"
  }'
```

### Configuration

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `process_illustration_enabled` | boolean | `true` | Enable process tracking |
| `process_content_path` | string | `"process_content/"` | Path to markdown process files |

### Model

Uses `claude-sonnet-4-20250514` for intelligent flow management with function calling.

## Benefits

- **Smart context buffering**: Accumulates 3-5 utterances before process detection
- **Automatic process tracking**: Detects and tracks process steps without manual coding
- **Clean state management**: Uses `flow_manager.state` instead of manual FSM flags
- **Native LLM integration**: Uses pipecat's LLM abstraction, not direct API calls
- **Flow-based control**: Automatic node transitions based on function calls

## Process Definition Format

Processes are defined in markdown files with frontmatter:

```markdown
---
process_key: order_cancellation
name: Order Cancellation
domain: orders
intents:
  - cancel order
  - refund request
---

# Order Cancellation Process

## Step 1: Verify Order

Check order status and eligibility for cancellation.

## Step 2: Process Cancellation

Submit cancellation and initiate refund.
```

## Testing

```bash
# Run flow tests
cd services/orchestrator
uv run pytest tests/flows/test_unified_flow.py -v

# Run all tests
uv run pytest -v
```

## Implementation Files

| File | Purpose |
|------|---------|
| `src/flows/unified_flow.py` | Main FlowManager implementation |
| `src/pipeline/pipeline.py` | Pipeline integration with FlowManager |
| `src/pipeline/processors.py` | TranscriptWriter processor |
| `tests/flows/test_unified_flow.py` | Comprehensive flow tests |

## Performance

Expected latency (from customer utterance to suggestion delivery): **~600-900ms** using Sonnet 4 with smart context buffering.

## Future Enhancements

- [ ] Add `end_call` function for cleanup
- [ ] Implement sub-process branching
- [ ] Add confidence thresholds to settings
- [ ] Support process switching mid-call
- [ ] Integrate with KB lookup tools (from tool_agent)
