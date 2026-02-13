.PHONY: install dev build lint typecheck test clean db-migrate web-dev customer-dev pcc-dev

# Install all dependencies
install:
	pnpm install
	cd services/pcc && uv sync

# Run all services in dev mode
dev:
	$(MAKE) -j3 web-dev customer-dev pcc-dev

# Build all packages
build:
	pnpm -r build

# Lint all code
lint:
	pnpm -r lint
	cd services/pcc && uv run ruff check .

# Type check
typecheck:
	pnpm -r typecheck

# Run tests
test:
	pnpm -r test
	cd services/pcc && uv run pytest

# Clean build artifacts
clean:
	pnpm -r clean
	rm -rf node_modules
	cd services/pcc && rm -rf .venv __pycache__

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

# PCC service dev server
pcc-dev:
	cd services/pcc && uv run python bot.py -t daily --port 7860

# Format code
format:
	pnpm -r format
	cd services/pcc && uv run ruff format .

# Pre-commit hooks
pre-commit-install:
	pre-commit install

pre-commit-run:
	pre-commit run --all-files
