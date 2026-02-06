# Repository Guidelines

## Project Structure & Module Organization
VoiceBridge is a pnpm workspace monorepo with two Next.js apps, a Python orchestrator, and shared TypeScript packages. The Agent Workspace lives in `apps/agent-workspace` (routes in `app/`, components in `src/components/workspace`, helpers in `src/lib`). The Customer App lives in `apps/customer` (routes in `app/`, helpers in `src/lib`). Voice pipeline automation lives in `services/orchestrator/src` (flows in `flows/`, processors in `pipeline/`, RTVI observer in `rtvi/`, custom frames in `frames/`, utilities in `utils/`); tests sit in `services/orchestrator/tests`. Shared TypeScript assets reside in `packages/contracts` (Zod schemas for RTVI messages and DTOs) and `packages/db` (Supabase helpers with Vitest tests). Database changes stay in `supabase/migrations` (single consolidated migration: `001_initial_schema.sql`), and the root `Makefile` keeps commands consistent.

## Build, Test, and Development Commands
Run `make install` to execute `pnpm install` and `uv sync`. `make dev` multiplexes the agent workspace (`make web-dev`, port 3000), customer app (`make customer-dev`, port 3001), and orchestrator (`make orchestrator-dev`, port 8000). `make build`, `make lint`, `make typecheck`, `make format`, and `make test` fan out to every package. `make db-migrate` (`supabase db push`) applies schema updates.

## Coding Style & Naming Conventions
TypeScript follows ESLint's Next.js rules, Tailwind CSS v4 utilities, and two-space indentation. Favor functional components, camelCase hooks, and PascalCase exports; name Zod schemas `{Domain}Schema` and keep shared utilities under `src/lib`. Database helpers should read like verbs (`fetchSessionById`). Python modules follow Ruff with 100-character lines, snake_case functions, and fully typed FastAPI endpoints. Run `make format` (prettier + `ruff format`); optional `pre-commit run --all-files` mirrors CI.

## Testing Guidelines
`make test` triggers Vitest across packages and Pytest for the orchestrator. Place new TS suites in `src/tests/{feature}.test.ts` and organize them by descriptive `describe` blocks. Python tests belong in `services/orchestrator/tests`, lean on pytest-asyncio, and mock HTTP with respx to avoid hitting Daily.co or Supabase. Use `vitest run --coverage` or `uv run pytest --cov src --cov-report=term-missing` whenever critical flows change.

## Commit & Pull Request Guidelines
Adopt Conventional Commits (`feat: add transcript timeline`, `fix: silence pipecat warnings`) and only push after lint/test/build succeed locally. Each PR should summarize scope, link issues, list validation commands (`make lint && make test && make build`), and highlight schema or env changes. Attach screenshots or Looms for UI tweaks, note Supabase migrations or orchestrator API impacts, and open the PR once everything is green.

## Environment & Security Notes
Copy `apps/agent-workspace/.env.example` to `.env.local`, `apps/customer/.env.example` to `.env.local`, and `services/orchestrator/.env.example` to `.env`. Secrets (Supabase keys, Speechmatics, Anthropic, Daily) stay in the team vault, not in Git or logs. Apply SQL updates with `make db-migrate`, reset local data with `make db-reset`, and prefer mock credentials so call audio and tokens remain local.
