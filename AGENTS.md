# Repository Guidelines

## Project Structure & Module Organization
VoiceBridge is a pnpm workspace combining a Next.js UI and a Python Pipecat orchestrator. UI code lives in `apps/web` (routes in `app/`, components in `src/components`, helpers in `src/lib`). Voice automation lives in `services/orchestrator/src`; tests sit in `services/orchestrator/tests`. Shared TypeScript assets reside in `packages/contracts` (Zod schemas) and `packages/db` (Supabase helpers with Vitest in `src/tests`). Database changes stay in `supabase/migrations`, and the root `Makefile` keeps commands consistent.

## Build, Test, and Development Commands
Run `make install` to execute `pnpm install` and `uv sync`. `make dev` multiplexes the UI (`make web-dev` / `pnpm --filter @voicebridge/web dev`) and orchestrator (`make orchestrator-dev`, a `uv run uvicorn src.main:app --reload`). `make build`, `make lint`, `make typecheck`, `make format`, and `make test` fan out to every package, while `make db-migrate` (`supabase db push`) applies schema updates.

## Coding Style & Naming Conventions
TypeScript follows ESLint’s Next.js rules, Tailwind utilities, and two-space indentation. Favor functional components, camelCase hooks, and PascalCase exports; name Zod schemas `{Domain}Schema` and keep shared utilities under `src/lib`. Database helpers should read like verbs (`fetchSessionById`). Python modules follow Ruff with 100-character lines, snake_case functions, and fully typed FastAPI endpoints. Run `make format` (pnpm formatters + `ruff format`); optional `pre-commit run --all-files` mirrors CI.

## Testing Guidelines
`make test` triggers Vitest across packages and Pytest for the orchestrator. Place new TS suites in `src/tests/{feature}.test.ts` and organize them by descriptive `describe` blocks. Python tests belong in `services/orchestrator/tests`, lean on pytest-asyncio, and mock HTTP with respx to avoid hitting Deepgram or Supabase. Use `vitest run --coverage` or `uv run pytest --cov src --cov-report=term-missing` whenever critical flows change.

## Commit & Pull Request Guidelines
With no public history yet, adopt Conventional Commits (`feat: add transcript timeline`, `fix: silence pipecat warnings`) and only push after lint/test/build succeed locally so every change is verified. Each PR should summarize scope, link issues, list validation commands (`make lint && make test && make build`), and highlight schema or env changes. Attach screenshots or Looms for UI tweaks, note Supabase migrations or orchestrator API impacts, and open the PR once everything is green.

## Environment & Security Notes
Copy `apps/web/.env.example` to `.env.local` and `services/orchestrator/.env.example` to `.env`. Secrets (Supabase keys, Deepgram, Anthropic, Daily) stay in the team vault, not in Git or logs. Apply SQL updates with `make db-migrate`, reset local data with `make db-reset`, and prefer mock credentials so call audio and tokens remain local.
