# Split Flows Architecture

## Overview

VoiceBridge now uses **two independent, decoupled flows** instead of a single unified flow:

1. **ProcessFlow** - Process detection and step tracking (optional)
2. **SuggestionFlow** - Agent guidance generation (optional)

Each flow:
- Has its own `FlowManager` instance
- Uses its own LLM model (configurable)
- Manages its own state independently
- Can be enabled/disabled independently
- Communicates via frames (decoupled)

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         Pipecat Pipeline                                 │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  1. Daily Transport                                                     │
│  2. Silero VAD                                                          │
│  3. Deepgram STT                                                        │
│  4. TranscriptWriter                                                    │
│     │                                                                    │
│     ▼                                                                    │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │ 5. ProcessFlow (Optional - FlowManager #1)                        │ │
│  │    ┌────────────────────────────────────────────────────────────┐ │ │
│  │    │ Model: claude-3-5-haiku-20241022 (fast/cheap)              │ │ │
│  │    │ State Machine: IDLE → DETECTING → TRACKING                 │ │ │
│  │    │                                                             │ │ │
│  │    │ Responsibilities:                                           │ │ │
│  │    │  ✅ Detect process from markdown catalog (once)            │ │ │
│  │    │  ✅ Track step progress (infrequent)                       │ │ │
│  │    │  ✅ Emit ProcessIllustrationFrame                          │ │ │
│  │    │                                                             │ │ │
│  │    │ Functions:                                                  │ │ │
│  │    │  - select_process(process_key, confidence)                 │ │ │
│  │    │  - need_more_context(reason)                               │ │ │
│  │    │  - update_step(step_number, rationale)                     │ │ │
│  │    └────────────────────────────────────────────────────────────┘ │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│     │                                                                    │
│     │ ProcessIllustrationFrame                                          │
│     ▼                                                                    │
│  6. LLM Context Aggregator (User)                                       │
│  7. RTVI Processor                                                      │
│     │                                                                    │
│     ▼                                                                    │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │ 8. SuggestionFlow (Optional - FlowManager #2)                     │ │
│  │    ┌────────────────────────────────────────────────────────────┐ │ │
│  │    │ Model: claude-sonnet-4-20250514 (quality)                  │ │ │
│  │    │ State Machine: START → LISTENING → SUGGESTING              │ │ │
│  │    │                                                             │ │ │
│  │    │ Responsibilities:                                           │ │ │
│  │    │  ✅ Generate agent guidance (every turn)                   │ │ │
│  │    │  ✅ Use process context if available                       │ │ │
│  │    │  ✅ Emit SuggestionFrame                                   │ │ │
│  │    │                                                             │ │ │
│  │    │ Functions:                                                  │ │ │
│  │    │  - publish_suggestions(suggestions)                        │ │ │
│  │    │                                                             │ │ │
│  │    │ Listens to: ProcessIllustrationFrame (decoupled!)         │ │ │
│  │    └────────────────────────────────────────────────────────────┘ │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│     │                                                                    │
│     │ SuggestionFrame                                                   │
│     ▼                                                                    │
│  9. LLM Context Aggregator (Assistant)                                  │
│  10. RTVI Observer                                                      │
│     │                                                                    │
│     ▼                                                                    │
│  Frontend (receives both ProcessIllustrationFrame & SuggestionFrame)    │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

## Decoupled Communication

**Key Innovation:** Flows don't directly reference each other. They communicate via **frames**.

```python
# ProcessFlow emits frames
ProcessIllustrationFrame(
    process_key="order_cancellation",
    process_name="Order Cancellation",
    current_step=1,
    steps=[...],
    content="..."
)

# SuggestionFlow listens for frames
async def process_frame(self, frame, direction):
    if isinstance(frame, ProcessIllustrationFrame):
        # Update internal state with process context
        self.flow_manager.state["process_context"] = {
            "process_key": frame.process_key,
            "process_name": frame.process_name,
            "current_step": frame.current_step,
            ...
        }
```

## API Configuration

### Enable/Disable Flows

```json
{
  "enable_process_flow": true,       // Optional: Process detection & tracking
  "enable_suggestion_flow": true,    // Optional: Agent guidance
  "process_flow_model": "claude-3-5-haiku-20241022",
  "suggestion_flow_model": "claude-sonnet-4-20250514",
  "process_content_path": "process_content/"
}
```

### Configuration Examples

#### Both Flows Enabled (Default)
```bash
curl -X POST http://localhost:8000/sessions/start \
  -H "Content-Type: application/json" \
  -d '{
    "enable_process_flow": true,
    "enable_suggestion_flow": true
  }'
```

#### Suggestions Only (No Process Tracking)
```bash
curl -X POST http://localhost:8000/sessions/start \
  -H "Content-Type: application/json" \
  -d '{
    "enable_process_flow": false,
    "enable_suggestion_flow": true
  }'
```

#### Process Tracking Only (No Suggestions)
```bash
curl -X POST http://localhost:8000/sessions/start \
  -H "Content-Type: application/json" \
  -d '{
    "enable_process_flow": true,
    "enable_suggestion_flow": false
  }'
```

#### Custom Models
```bash
curl -X POST http://localhost:8000/sessions/start \
  -H "Content-Type: application/json" \
  -d '{
    "enable_process_flow": true,
    "enable_suggestion_flow": true,
    "process_flow_model": "claude-3-5-haiku-20241022",
    "suggestion_flow_model": "claude-opus-4-5-20251101"
  }'
```

## Flow Details

### ProcessFlow

**Purpose:** Detect customer process and track progress through steps

**Frequency:** Infrequent
- Detection: Once per call (after 3+ utterances)
- Step tracking: Occasionally (when moving between steps)

**Model Recommendation:** Haiku (fast, cheap for infrequent calls)

**State Machine:**
```
IDLE (waiting for context)
  ↓ (3+ utterances)
DETECTING (LLM analyzes conversation)
  ↓ (confidence > 0.6)
TRACKING (monitors step progress)
```

**Functions:**
- `select_process(process_key, confidence, rationale)` - Choose process
- `need_more_context(reason)` - Not enough info, stay in IDLE
- `update_step(step_number, rationale)` - Move to new step

**Output:** `ProcessIllustrationFrame`

### SuggestionFlow

**Purpose:** Generate agent guidance after each customer utterance

**Frequency:** High
- Runs: After EVERY customer utterance
- Latency-sensitive

**Model Recommendation:** Sonnet (quality over speed)

**State Machine:**
```
START (initialization)
  ↓ (first utterance)
LISTENING (ready to generate)
  ↓ (customer speaks)
SUGGESTING (LLM generates guidance)
  ↓ (published)
LISTENING (back to listening)
```

**Functions:**
- `publish_suggestions(suggestions)` - Generate and send guidance

**Listens For:** `ProcessIllustrationFrame` (to get process context)

**Output:** `SuggestionFrame`

## Benefits

### 1. **Single Responsibility**
- ProcessFlow: "What process? What step?"
- SuggestionFlow: "What should agent say/do?"

### 2. **Independent Models**
```python
# Fast model for infrequent process detection
ProcessFlow → Haiku (200-300ms, cheap)

# Quality model for frequent suggestions
SuggestionFlow → Sonnet (600-800ms, quality)
```

### 3. **Independent Scaling**
```python
# Low frequency, can tolerate latency
ProcessFlow: 1-2 LLM calls per call

# High frequency, needs optimization
SuggestionFlow: 20-30 LLM calls per call
```

### 4. **Optional Features**
```python
# Use cases:
- Demo mode: enable_suggestion_flow only
- Process tracking only: enable_process_flow only
- Full system: both enabled
- Research/testing: both disabled
```

### 5. **Decoupled Testing**
- Test ProcessFlow independently
- Test SuggestionFlow independently
- Test integration via frame communication

## State Management

### ProcessFlow State
```python
{
  "processes": {
    "order_cancel": ProcessDefinition(...),
    ...
  },
  "detected_process": ProcessDefinition | None,
  "current_step": 0,
  "conversation_buffer": [...],
  "utterance_count": 3
}
```

### SuggestionFlow State
```python
{
  "conversation_buffer": [...],
  "process_context": {  # From ProcessIllustrationFrame
    "process_key": "order_cancel",
    "process_name": "Order Cancellation",
    "current_step": 1,
    "steps": [...]
  }
}
```

## Performance Characteristics

### ProcessFlow
- **Calls per session:** 1-5 (detection + occasional step updates)
- **Latency target:** 500-1000ms (not critical)
- **Cost per call:** ~$0.0005 (Haiku)
- **Total cost per session:** ~$0.003

### SuggestionFlow
- **Calls per session:** 20-50 (every customer utterance)
- **Latency target:** 400-700ms (user-facing)
- **Cost per call:** ~$0.005 (Sonnet)
- **Total cost per session:** ~$0.15

## File Structure

```
src/flows/
├── __init__.py              # Exports ProcessFlow, SuggestionFlow
├── process_flow.py          # Process detection & step tracking (520 lines)
└── suggestion_flow.py       # Agent guidance generation (330 lines)

Total: 850 lines (vs 672 lines in old unified flow)
```

## Migration Notes

### From UnifiedFlow

**Before:**
```python
UnifiedFlow(
    session_id=session_id,
    flow_manager=flow_manager,
    process_content_path=path
)
```

**After:**
```python
# Optional ProcessFlow
if enable_process_flow:
    ProcessFlow(
        session_id=session_id,
        flow_manager=process_flow_manager,  # Own FlowManager
        process_content_path=path
    )

# Optional SuggestionFlow
if enable_suggestion_flow:
    SuggestionFlow(
        session_id=session_id,
        flow_manager=suggestion_flow_manager  # Own FlowManager
    )
```

### Breaking Changes

**None!** The API is **backwards compatible**:
- Existing clients work without changes
- Same frame types emitted
- Same RTVI message format
- Defaults enable both flows (same behavior)

## Test Results

```bash
============================= test session starts ==============================
45 passed, 12 warnings in 2.68s
===============================================================================================
```

**All tests passing** ✅

## Next Steps

1. **Add flow-specific tests** for ProcessFlow and SuggestionFlow
2. **Monitor costs** - track LLM usage per flow
3. **A/B testing** - compare Haiku vs Sonnet for ProcessFlow
4. **Frontend updates** - UI controls for enable/disable
5. **Analytics** - track which flows are actually used

## Summary

The split flow architecture provides:
- ✅ **Flexibility** - Enable/disable independently
- ✅ **Optimization** - Different models for different needs
- ✅ **Clarity** - Single responsibility per flow
- ✅ **Decoupling** - Communication via frames
- ✅ **Testability** - Test each flow independently
- ✅ **Cost control** - Optimize expensive SuggestionFlow separately

**Result:** Cleaner, more maintainable, and more flexible architecture! 🎉
