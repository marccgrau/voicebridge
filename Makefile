.PHONY: install dev build lint typecheck test clean db-migrate web-dev customer-dev pcc-dev

# Install all dependencies
install:
	pnpm install
	cd services/pcc && uv sync

# Run all services in dev mode
dev:
	@WEB_PID=""; CUSTOMER_PID=""; PCC_PID=""; CLEANED=0; \
	kill_tree() { \
		pid="$$1"; \
		signal="$$2"; \
		[ -z "$$pid" ] && return; \
		children=$$(pgrep -P "$$pid" 2>/dev/null || true); \
		for child in $$children; do \
			kill_tree "$$child" "$$signal"; \
		done; \
		kill -"$$signal" "$$pid" 2>/dev/null || true; \
	}; \
	force_kill_if_alive() { \
		pid="$$1"; \
		[ -z "$$pid" ] && return; \
		if kill -0 "$$pid" 2>/dev/null; then \
			kill_tree "$$pid" KILL; \
		fi; \
	}; \
	cleanup() { \
		if [ "$$CLEANED" -eq 1 ]; then \
			return; \
		fi; \
		CLEANED=1; \
		trap '' INT TERM; \
		echo ""; \
		echo "Stopping dev services..."; \
		kill_tree "$$WEB_PID" TERM; \
		kill_tree "$$CUSTOMER_PID" TERM; \
		kill_tree "$$PCC_PID" TERM; \
		sleep 1; \
		force_kill_if_alive "$$WEB_PID"; \
		force_kill_if_alive "$$CUSTOMER_PID"; \
		force_kill_if_alive "$$PCC_PID"; \
		wait "$$WEB_PID" "$$CUSTOMER_PID" "$$PCC_PID" 2>/dev/null || true; \
	}; \
	trap 'cleanup; exit 130' INT; \
	trap 'cleanup; exit 143' TERM; \
	trap 'cleanup' EXIT; \
	pnpm --filter @voicebridge/agent-workspace dev & WEB_PID=$$!; \
	pnpm --filter @voicebridge/customer dev --port 3001 & CUSTOMER_PID=$$!; \
	(cd services/pcc && uv run python bot.py -t daily --port 7860) & PCC_PID=$$!; \
	wait "$$WEB_PID" "$$CUSTOMER_PID" "$$PCC_PID"

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

# Unified PCC dev server (port 7860)
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
