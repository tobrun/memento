# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install Python dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env   # then edit .env

# Build the frontend (required for web UI)
cd frontend && bun install && bun run build && cd ..

# Run the agent (watches ./inbox, serves API + web UI on :8888)
python -m memento

# Run with custom options
python -m memento --watch ./docs --port 9000 --consolidate-every 15

# Run the MCP server (separate process, port 8889)
python mcp_server.py

# Run frontend in dev mode (proxies API to :8888)
cd frontend && bun run dev

# Run Python tests
pytest tests/

# Run frontend tests
cd frontend && bun run test

# Query via curl (all routes under /api/)
curl "http://localhost:8888/api/query/general?q=what+do+you+know"
curl -X POST http://localhost:8888/api/ingest/general \
  -H "Content-Type: application/json" \
  -d '{"text": "some info", "source": "test"}'
curl http://localhost:8888/api/datasources
```

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `GOOGLE_API_KEY` | — | Required when using Gemini. |
| `MODEL` | `gemini-3.1-flash-lite-preview` | Model name. When using an OpenAI-compatible endpoint, use the model name on that server (e.g. `llama3`). |
| `OPENAI_API_BASE` | — | If set, switches to an OpenAI-compatible endpoint via LiteLLM (e.g. `http://localhost:11434/v1`). `GOOGLE_API_KEY` is then not required. |
| `OPENAI_API_KEY` | `not-needed` | API key for the OpenAI-compatible endpoint. |
| `MEMORY_DB` | `./databases` | Directory for per-datasource SQLite databases. |
| `WATCH_DIR` | `./inbox` | Root inbox directory. Subdirectories become named datasources. |
| `PORT` | `8888` | HTTP API + web UI port. |
| `MCP_PORT` | `8889` | MCP server port (separate from main API). |

## Architecture

The system is structured as a Python package (`memento/`) plus a React frontend (`frontend/`):

### Python Package: `memento/`

| Module | Purpose |
|---|---|
| `__main__.py` | Entry point — wires all modules, starts asyncio tasks |
| `config.py` | Env var loading, argparse, model initialization |
| `db.py` | SQLite schema, CRUD functions, name validation, pagination |
| `agents.py` | ADK agent definitions (`build_agents()`), `MemoryAgent` class |
| `api.py` | aiohttp HTTP API routes (all under `/api/`) |
| `watcher.py` | Multi-datasource file watcher, watcher manager, consolidation loop |
| `static.py` | Static file serving for the built SPA + SPA catch-all |

### Frontend: `frontend/`

React SPA built with Vite, TanStack Router, Tailwind CSS, and shadcn/ui. Built output served by the agent at `/`.

### MCP Server: `mcp_server.py`

Thin wrapper exposing `query` and `list_datasources` MCP tools via HTTP/SSE. No direct DB access — delegates to the agent HTTP API.

### Multi-Datasource Model

- Root `inbox/` → `general` datasource → `databases/general.db`
- `inbox/news/` → `news` datasource → `databases/news.db`
- Each datasource is fully isolated (separate DB, separate watcher task, separate consolidation)
- Datasources are discovered by scanning `inbox/` subdirectories on each poll cycle

### Agent Hierarchy (Google ADK)

`memory_orchestrator` (root) routes to three sub-agents per datasource:
- `ingest_agent` — processes new content into structured memories via `store_memory`
- `consolidate_agent` — reads unconsolidated memories and finds connections via `store_consolidation`
- `query_agent` — answers questions by reading all memories and consolidation history

Agents are built per-datasource with closures binding the `datasource` parameter to each tool function.

### SQLite Schema (per datasource)

Three tables in `databases/<name>.db`:
- `memories` — stores each ingested item with summary, entities (JSON), topics (JSON), connections (JSON), importance score, and a `consolidated` flag
- `consolidations` — stores cross-memory insights with source_ids (JSON) pointing back to memories
- `processed_files` — tracks which inbox files have already been ingested (by path)

### Async Concurrency

`main_async` runs two top-level tasks via `asyncio.gather`:
1. `watcher_manager` — every 30s, rescans datasources and manages per-datasource watcher tasks
2. `consolidation_loop` — on each interval, consolidates per-datasource if ≥2 unconsolidated memories exist

Plus the aiohttp web server.

### Multimodal Ingestion

Text files are read as strings. Media files (images, audio, video, PDF) are sent as raw bytes with MIME type using `types.Part.from_bytes`. Files >20MB are skipped. The web UI uploads files via `POST /api/upload/<datasource>`, which writes them to the inbox directory for the watcher to pick up.
