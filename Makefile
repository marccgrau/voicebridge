.PHONY: install dev build lint typecheck test clean db-migrate web-dev orchestrator-dev

# Install all dependencies
install:
	pnpm install
	cd services/orchestrator && uv sync

# Run all services in dev mode
dev:
	$(MAKE) -j2 web-dev orchestrator-dev

# Build all packages
build:
	pnpm -r build

# Lint all code
lint:
	pnpm -r lint
	cd services/orchestrator && uv run ruff check .

# Type check
typecheck:
	pnpm -r typecheck

# Run tests
test:
	pnpm -r test
	cd services/orchestrator && uv run pytest

# Clean build artifacts
clean:
	pnpm -r clean
	rm -rf node_modules
	cd services/orchestrator && rm -rf .venv __pycache__

# Database migrations
db-migrate:
	supabase db push

db-reset:
	supabase db reset

# Web app dev server
web-dev:
	pnpm --filter @voicebridge/web dev

# Orchestrator dev server
orchestrator-dev:
	cd services/orchestrator && uv run uvicorn src.main:app --reload --host 0.0.0.0 --port 8000

# Format code
format:
	pnpm -r format
	cd services/orchestrator && uv run ruff format .

# Pre-commit hooks
pre-commit-install:
	pre-commit install

pre-commit-run:
	pre-commit run --all-files
