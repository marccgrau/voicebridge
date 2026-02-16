.PHONY: install dev build lint typecheck test clean db-migrate web-dev customer-dev transcript-agent-dev process-agent-dev suggestion-agent-dev

# Install all dependencies
install:
	pnpm install
	cd services/transcript-agent && uv sync
	cd services/process-agent && uv sync
	cd services/suggestion-agent && uv sync

# Run all services in dev mode
dev:
	$(MAKE) -j5 web-dev customer-dev transcript-agent-dev process-agent-dev suggestion-agent-dev

# Build all packages
build:
	pnpm -r build

# Lint all code
lint:
	pnpm -r lint
	cd services/transcript-agent && uv run ruff check .
	cd services/process-agent && uv run ruff check .
	cd services/suggestion-agent && uv run ruff check .

# Type check
typecheck:
	pnpm -r typecheck

# Run tests
test:
	pnpm -r test
	cd services/transcript-agent && uv run pytest
	cd services/process-agent && uv run pytest
	cd services/suggestion-agent && uv run pytest

# Clean build artifacts
clean:
	pnpm -r clean
	rm -rf node_modules
	cd services/transcript-agent && rm -rf .venv __pycache__
	cd services/process-agent && rm -rf .venv __pycache__
	cd services/suggestion-agent && rm -rf .venv __pycache__

# Database migrations
db-migrate:
	supabase db push

db-reset:
	supabase db reset

# Agent workspace dev server
web-dev:
	pnpm --filter @voicebridge/agent-workspace dev

# Customer app dev server
customer-dev:
	pnpm --filter @voicebridge/customer dev --port 3001

# Transcript agent dev server (port 7860)
transcript-agent-dev:
	cd services/transcript-agent && uv run python bot.py -t daily --port 7860

# Process agent dev server (port 7861)
process-agent-dev:
	cd services/process-agent && uv run python bot.py -t daily --port 7861

# Suggestion agent dev server (port 7862)
suggestion-agent-dev:
	cd services/suggestion-agent && uv run python bot.py -t daily --port 7862

# Format code
format:
	pnpm -r format
	cd services/transcript-agent && uv run ruff format .
	cd services/process-agent && uv run ruff format .
	cd services/suggestion-agent && uv run ruff format .

# Pre-commit hooks
pre-commit-install:
	pre-commit install

pre-commit-run:
	pre-commit run --all-files
