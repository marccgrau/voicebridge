# Orchestrator Architecture

This document defines the modular-monolith structure for `services/orchestrator` and the boundaries we enforce.

## Goals

- Keep voice latency low while preserving clear module boundaries.
- Keep each module single-purpose and easy to test in isolation.
- Use Pipecat abstractions (`LLMContext`, frames, processors) as the core runtime contract.

## Module Map

- `src/api`
  - FastAPI route layer only (HTTP in/out, status codes, schema mapping).
  - No pipeline/flow orchestration logic.
- `src/services`
  - Application/domain logic for `session`, `process`, `summary`.
  - No imports from API/composition/pipeline/config.
- `src/ports`
  - Protocol interfaces for external dependencies (runtime registry, clock, repositories, LLM/daily factories).
- `src/adapters`
  - Concrete implementations of ports (Supabase, clock, Daily, LLM factory wrappers).
- `src/pipeline`
  - Pipecat runtime assembly (`VoiceBridgePipelineBuilder`, direct processors, transport wiring).
- `src/composition`
  - Dependency wiring only (container + runtime registry).

## Service Interfaces

- `SessionLifecycleService`
  - Inputs: `SessionStartParams`, `SessionCreateParams`, `SessionAcceptParams`, `session_id`.
  - Outputs: `SessionStartResult`, `SessionCreateResult`, `SessionAcceptResult`, `SessionStopResult`.
  - Depends on ports/callables, not framework internals.
- `ProcessService`
  - Owns process-catalog loading and markdown step parsing.
- `SessionSummaryService`
  - Owns postcall summary rules and persistence orchestration.

## Endpoint Ownership

- `src/api/routes/sessions.py`
  - Session lifecycle endpoints and summary endpoints.
  - Uses `SessionLifecycleService` + `SessionSummaryService`.
- `src/api/routes/health.py`
  - Liveness/readiness checks only.

## Latency-Critical Defaults

The following latency measures are part of the architecture baseline:

1. Async transcript writes in `TranscriptWriter` (queue + background worker) to keep the frame path non-blocking.
2. VAD `stop_secs=0.6` for faster end-of-turn detection while avoiding overly aggressive cutoffs.
3. Stale suggestion cancellation (`latest-turn-wins`) to drop obsolete LLM generations on new customer speech.

## Dependency Rules

Enforced by `tests/architecture/test_module_boundaries.py`:

- `src.api` cannot import `src.main`, `src.pipeline`.
- `src.services` cannot import `src.api`, `src.main`, `src.composition`, `src.pipeline`, `src.adapters`, `src.config`.
- `src.ports` cannot import `src.api`, `src.main`, `src.composition`, `src.adapters`, `src.services`, `src.pipeline`.
- `src.adapters` cannot import `src.api`, `src.main`, `src.composition`.

## Change Checklist

When adding new behavior:

1. Put business rules in `src/services/*/service.py`.
2. Expose external dependencies as port interfaces in `src/ports`.
3. Implement infrastructure in `src/adapters`.
4. Keep direct processor behavior in `src/pipeline/direct_processors.py` and business rules in services.
5. Add or update tests for service behavior and architecture boundaries.
