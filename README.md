# Memento

**Persistent memory layer for AI Agents: ingests files, consolidates knowledge, and answers queries.**

Built on top of [always-on-memory-agent](https://github.com/GoogleCloudPlatform/generative-ai/tree/main/gemini/agents/always-on-memory-agent). Runs 24/7 as a lightweight background process, continuously processing, consolidating, and connecting information across isolated datasources. Exposes data through MCP and CLI (TBA).

## Architecture

```
inbox/                  ← drop any file here
├── (root)              ← "general" datasource
├── news/               ← "news" datasource
└── company/            ← "company" datasource
```

Each datasource has its own inbox directory and SQLite database — fully isolated. The agent discovers datasources by scanning subdirectories, so creating a new datasource is as simple as `mkdir inbox/mydir`.

### Python Package: `memento/`

| Module | Purpose |
|---|---|
| `__main__.py` | Entry point: `python -m memento` |
| `config.py` | Env var loading + argparse |
| `db.py` | SQLite schema, CRUD, pagination, name validation |
| `agents.py` | Google ADK orchestrator + sub-agents, `MemoryAgent` class |
| `api.py` | aiohttp HTTP API (all routes under `/api/`) |
| `watcher.py` | Multi-datasource file watcher + consolidation loop |
| `static.py` | Serves the built frontend SPA |

### Agent Hierarchy

`memory_orchestrator` routes to three sub-agents per datasource:
- `ingest_agent` — extracts structured memory from any content type
- `consolidate_agent` — finds cross-memory patterns and connections
- `query_agent` — synthesises answers with citations

## Quick Start

### 1. Configure

```bash
git clone git@github.com:tobrun/memento.git && cd memento
cp .env.example .env
```

**Option A — Gemini (cloud)**
```env
GOOGLE_API_KEY=your-gemini-api-key
```

**Option B — Self-hosted / OpenAI-compatible**
```env
OPENAI_API_BASE=http://localhost:8080/v1
OPENAI_API_KEY=not-needed
MODEL=llama5
```

### 2. Install & build

```bash
python -m venv .venv
source .venv/bin/activate
make setup        # installs Python deps + builds the frontend
```

### 3. Start

```bash
make run          # watches ./inbox, serves API + web UI on :8888
```

Open `http://localhost:8888` in your browser.

### 4. Create a datasource

```bash
mkdir inbox/news
# Or via the web UI at http://localhost:8888/datasources
# Or via the API:
curl -X POST http://localhost:8888/api/datasources \
  -H "Content-Type: application/json" \
  -d '{"name": "news"}'
```

### 5. Feed it information

**Drop a file:**
```bash
echo "Breaking news: AI agents are taking over." > inbox/news/article.txt
# Ingested within 5 seconds
```

**HTTP API:**
```bash
curl -X POST http://localhost:8888/api/ingest/news \
  -H "Content-Type: application/json" \
  -d '{"text": "AI agents are the future", "source": "article"}'
```

### 6. Query

```bash
curl "http://localhost:8888/api/query/news?q=what+do+you+know+about+AI"
```

### Available Make targets

```
make setup          Full setup: install deps + build frontend
make install        Install Python dependencies
make install-dev    Install Python + dev dependencies
make build          Build the frontend
make run            Start the agent
make mcp            Start the MCP server (port 8889)
make dev            Run frontend in dev mode
make test           Run Python tests
make test-frontend  Run frontend tests
make clean          Remove build artifacts and caches
```

## API Reference

All routes are prefixed with `/api/`. The `{datasource}` parameter is the datasource name (e.g. `general`, `news`, `company`).

### Datasource management

| Endpoint | Method | Description |
|---|---|---|
| `/api/datasources` | GET | List all datasources with stats |
| `/api/datasources` | POST | Create a new datasource (`{"name": "news"}`) |
| `/api/health` | GET | Liveness check |

### Data endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/api/query/{ds}?q=...` | GET | Query memories with a question |
| `/api/ingest/{ds}` | POST | Ingest text (`{"text": "...", "source": "..."}`) |
| `/api/upload/{ds}` | POST | Upload a file (multipart) |
| `/api/consolidate/{ds}` | POST | Trigger manual consolidation |
| `/api/status/{ds}` | GET | Memory statistics |
| `/api/memories/{ds}` | GET | List memories (cursor-based pagination) |
| `/api/delete/{ds}` | POST | Delete a memory (`{"memory_id": 1}`) |
| `/api/clear/{ds}` | POST | Full reset — deletes all data + inbox files |

### Pagination

`GET /api/memories/{ds}?cursor=<id>&limit=<n>`

- `cursor`: return memories with ID less than this (for next page)
- `limit`: results per page (default 20, max 100)
- Response: `{"memories": [...], "next_cursor": <id|null>}`

## MCP Server

Memento exposes a [Model Context Protocol](https://modelcontextprotocol.io) server that allows AI coding agents (Claude Code, Cursor, etc.) to query memory directly. The server uses **Streamable HTTP transport** and binds to `0.0.0.0`, so it is accessible from any machine on your network.

```bash
make mcp              # starts on port 8889
```

| Tool | Parameters | Description |
|---|---|---|
| `list_datasources` | — | Returns all available datasource names |
| `query` | `question`, `datasource` | Queries the named datasource and returns an LLM-synthesised answer |

See [docs/mcp.md](docs/mcp.md) for CLI options, client configuration, and LAN setup.

## Web UI

The frontend is a React SPA built with TanStack Router, Tailwind CSS, and shadcn/ui.

**Development:**
```bash
make dev          # http://localhost:5173 (proxies /api to :8888)
```

**Production:** The built `frontend/dist/` is served automatically by `python -m memento` on the same port as the API.

### Pages

| Page | Route | Description |
|---|---|---|
| Dashboard | `/dashboard` | System metrics, per-datasource stats, 10s polling |
| Ingest | `/ingest` | Upload files or paste text into any datasource |
| Query | `/query` | Query a datasource, see LLM answer + source memories |
| Datasources | `/datasources` | Create datasources, view stats, clear data |

## CLI Options

```bash
python -m memento [options]
  --watch DIR              Root inbox directory (default: ./inbox)
  --port PORT              HTTP API + web UI port (default: 8888)
  --mcp-port PORT          MCP server port (default: 8889)
  --consolidate-every MIN  Consolidation interval (default: 30)
  --db-dir DIR             Database directory (default: ./databases)
```

## Configuration

All settings via `.env` or environment variables:

| Variable | Default | Description |
|---|---|---|
| `GOOGLE_API_KEY` | — | Required when using Gemini |
| `OPENAI_API_BASE` | — | OpenAI-compatible endpoint URL |
| `OPENAI_API_KEY` | `not-needed` | API key for self-hosted endpoint |
| `MODEL` | `gemini-3.1-flash-lite-preview` | Model name |
| `MEMORY_DB` | `./databases` | Directory for per-datasource SQLite databases |
| `WATCH_DIR` | `./inbox` | Root inbox directory |
| `PORT` | `8888` | HTTP API + web UI port |
| `MCP_PORT` | `8889` | MCP server port |

## Project Structure

```
memento/              # Python package
├── __main__.py       # Entry point
├── config.py         # Configuration
├── db.py             # Database layer
├── agents.py         # ADK agents
├── api.py            # HTTP API
├── watcher.py        # File watcher
└── static.py         # SPA serving

frontend/             # React SPA
├── src/
│   ├── pages/        # Dashboard, Ingest, Query, Datasources
│   ├── lib/api.ts    # API client
│   └── components/   # shadcn/ui components
└── dist/             # Built output (served by agent)

mcp_server.py         # MCP server (HTTP/SSE)
requirements.txt      # Python dependencies
.env.example          # Configuration template
inbox/                # Root inbox (general datasource)
databases/            # SQLite databases (auto-created)
docs/                 # Documentation
```

## Deployment

See [docs/deployment.md](docs/deployment.md) for running Memento as a systemd service on Linux.

## Roadmap
- [ ] CLI instead of MCP 
- [ ] Vector Database / Semantic Search 

## Prior Work Notice

Memento is a contiunation of the concept coined in [always-on-memory-agent](https://github.com/GoogleCloudPlatform/generative-ai/tree/main/gemini/agents/always-on-memory-agent). All credit for the baseline setup of this project goes to [Shubhamsaboo](https://github.com/Shubhamsaboo).

## License

MIT

---