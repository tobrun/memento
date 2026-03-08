.PHONY: install install-dev setup build dev run mcp test test-frontend lint clean

# ── Setup ────────────────────────────────────────────────────────

install:                          ## Install Python dependencies
	pip install -r requirements.txt

install-dev:                      ## Install Python + dev dependencies
	pip install -r requirements-dev.txt

setup: install build              ## Full setup: install deps + build frontend

# ── Frontend ─────────────────────────────────────────────────────

build:                            ## Build the frontend (required for web UI)
	cd frontend && bun install && bun run build

dev:                              ## Run frontend in dev mode (proxies API to :8888)
	cd frontend && bun run dev

test-frontend:                    ## Run frontend tests
	cd frontend && bun run test

# ── Run ──────────────────────────────────────────────────────────

run:                              ## Start the agent (watches ./inbox, serves on :8888)
	python -m memento

mcp:                              ## Start the MCP server (port 8889)
	python mcp_server.py

# ── Test & Lint ──────────────────────────────────────────────────

test:                             ## Run Python tests
	pytest

# ── Cleanup ──────────────────────────────────────────────────────

clean:                            ## Remove build artifacts and caches
	rm -rf frontend/dist frontend/node_modules/.vite
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true

# ── Help ─────────────────────────────────────────────────────────

help:                             ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*##' $(MAKEFILE_LIST) | awk -F ':.*## ' '{printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

.DEFAULT_GOAL := help
