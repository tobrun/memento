"""HTTP API — aiohttp application with all /api/ routes."""

import logging
from pathlib import Path

from aiohttp import web

from memento.agents import MemoryAgent
from memento.db import (
    ALL_SUPPORTED,
    clear_all_memories,
    datasource_exists,
    delete_memory,
    get_memory_stats,
    inbox_exists,
    init_datasource_db,
    read_memories_paginated,
    validate_datasource_name,
)
from memento.static import setup_static

log = logging.getLogger("memory-agent")

# Populated by __main__.py before build_http() is called
_watch_path: str = "./inbox"


def _inbox_warning(datasource: str, inbox_root: str) -> str | None:
    """Return a warning string if the datasource inbox directory is missing."""
    if datasource == "general":
        folder = Path(inbox_root)
    else:
        folder = Path(inbox_root) / datasource
    return "datasource inbox missing" if not folder.exists() else None


def _require_datasource(request: web.Request) -> str:
    """Extract and validate the datasource path parameter.

    Raises HTTPNotFound if the datasource DB does not exist.
    """
    ds = request.match_info["datasource"]
    if not datasource_exists(ds):
        raise web.HTTPNotFound(
            content_type="application/json",
            reason=f"Datasource '{ds}' not found",
        )
    return ds


def build_http(agent: MemoryAgent, watch_path: str = "./inbox") -> web.Application:
    """Build and return the aiohttp Application with all routes registered."""
    global _watch_path
    _watch_path = watch_path

    app = web.Application()

    # ─── Datasource management ──────────────────────────────────

    async def handle_list_datasources(request: web.Request) -> web.Response:
        """GET /api/datasources — list all known datasources with stats."""
        inbox_root = Path(watch_path)
        datasources: dict[str, dict] = {}

        # Discover from inbox subdirectories
        if inbox_root.exists():
            for sub in inbox_root.iterdir():
                if sub.is_dir() and validate_datasource_name(sub.name):
                    datasources[sub.name] = {"name": sub.name}

        # Always include general
        datasources["general"] = {"name": "general"}

        # Discover from existing DB files
        from memento.db import MEMORY_DB_DIR
        db_dir = Path(MEMORY_DB_DIR)
        if db_dir.exists():
            for db_file in db_dir.glob("*.db"):
                name = db_file.stem
                if validate_datasource_name(name):
                    datasources[name] = {"name": name}

        # Enrich each with stats
        result = []
        for name in sorted(datasources):
            entry: dict = {"name": name}
            if datasource_exists(name):
                stats = get_memory_stats(name)
                entry.update(stats)
            else:
                entry.update({"total_memories": 0, "unconsolidated": 0, "consolidations": 0})
            entry["inbox_exists"] = inbox_exists(name, watch_path)
            result.append(entry)

        return web.json_response(result)

    async def handle_create_datasource(request: web.Request) -> web.Response:
        """POST /api/datasources — create a new datasource."""
        try:
            data = await request.json()
        except Exception:
            return web.json_response({"error": "invalid JSON"}, status=400)

        name = data.get("name", "").strip()
        if not validate_datasource_name(name):
            return web.json_response({"error": "invalid name"}, status=400)

        if datasource_exists(name):
            return web.json_response({"error": "already exists"}, status=409)

        # Create inbox directory
        inbox_dir = Path(watch_path) / name
        inbox_dir.mkdir(parents=True, exist_ok=True)

        # Initialise DB with schema
        init_datasource_db(name)

        # Verify by reading stats
        stats = get_memory_stats(name)
        return web.json_response({"status": "created", "name": name, "stats": stats}, status=201)

    # ─── Health check ────────────────────────────────────────────

    async def handle_health(request: web.Request) -> web.Response:
        """GET /api/health — liveness probe for MCP server."""
        return web.json_response({"status": "ok"})

    # ─── Datasource-scoped endpoints ─────────────────────────────

    async def handle_query(request: web.Request) -> web.Response:
        """GET /api/query/{datasource}?q=..."""
        ds = _require_datasource(request)
        q = request.query.get("q", "").strip()
        if not q:
            return web.json_response({"error": "missing ?q= parameter"}, status=400)
        answer = await agent.query(q, datasource=ds)
        resp: dict = {"question": q, "answer": answer}
        warning = _inbox_warning(ds, watch_path)
        if warning:
            resp["warning"] = warning
        return web.json_response(resp)

    async def handle_ingest(request: web.Request) -> web.Response:
        """POST /api/ingest/{datasource}"""
        ds = _require_datasource(request)
        try:
            data = await request.json()
        except Exception:
            return web.json_response({"error": "invalid JSON"}, status=400)
        text = data.get("text", "").strip()
        if not text:
            return web.json_response({"error": "missing 'text' field"}, status=400)
        source = data.get("source", "api")
        result = await agent.ingest(text, source=source, datasource=ds)
        return web.json_response({"status": "ingested", "response": result})

    async def handle_upload(request: web.Request) -> web.Response:
        """POST /api/upload/{datasource} — multipart file upload."""
        ds = request.match_info["datasource"]
        if not datasource_exists(ds):
            return web.json_response({"error": "datasource not found"}, status=404)

        reader = await request.multipart()
        field = await reader.next()
        if field is None:
            return web.json_response({"error": "no file"}, status=400)

        filename = field.filename
        if filename:
            suffix = Path(filename).suffix.lower()
            if suffix not in ALL_SUPPORTED:
                return web.json_response(
                    {
                        "error": f"Unsupported file type: {suffix or '(none)'}",
                        "supported": sorted(ALL_SUPPORTED),
                    },
                    status=400,
                )
        if ds == "general":
            dest_dir = Path(watch_path)
        else:
            dest_dir = Path(watch_path) / ds
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / filename

        with open(dest, "wb") as f:
            while True:
                chunk = await field.read_chunk()
                if not chunk:
                    break
                f.write(chunk)

        return web.json_response({"status": "uploaded", "filename": filename, "path": str(dest)})

    async def handle_consolidate(request: web.Request) -> web.Response:
        """POST /api/consolidate/{datasource}"""
        ds = _require_datasource(request)
        result = await agent.consolidate(datasource=ds)
        return web.json_response({"status": "done", "response": result})

    async def handle_status(request: web.Request) -> web.Response:
        """GET /api/status/{datasource}"""
        ds = _require_datasource(request)
        stats = get_memory_stats(ds)
        warning = _inbox_warning(ds, watch_path)
        if warning:
            stats["warning"] = warning
        return web.json_response(stats)

    async def handle_memories(request: web.Request) -> web.Response:
        """GET /api/memories/{datasource}?cursor=&limit="""
        ds = _require_datasource(request)

        cursor_str = request.query.get("cursor")
        try:
            cursor = int(cursor_str) if cursor_str else None
        except ValueError:
            return web.json_response({"error": "invalid cursor"}, status=400)

        limit_str = request.query.get("limit", "20")
        try:
            limit = int(limit_str)
        except ValueError:
            limit = 20

        data = read_memories_paginated(ds, cursor, limit)
        warning = _inbox_warning(ds, watch_path)
        if warning:
            data["warning"] = warning
        return web.json_response(data)

    async def handle_delete(request: web.Request) -> web.Response:
        """POST /api/delete/{datasource}"""
        ds = _require_datasource(request)
        try:
            data = await request.json()
        except Exception:
            return web.json_response({"error": "invalid JSON"}, status=400)
        memory_id = data.get("memory_id")
        if not memory_id:
            return web.json_response({"error": "missing 'memory_id' field"}, status=400)
        result = delete_memory(ds, int(memory_id))
        return web.json_response(result)

    async def handle_clear(request: web.Request) -> web.Response:
        """POST /api/clear/{datasource}"""
        ds = _require_datasource(request)
        if ds == "general":
            inbox_path = watch_path
        else:
            inbox_path = str(Path(watch_path) / ds)
        result = clear_all_memories(ds, inbox_path=inbox_path)
        return web.json_response(result)

    async def handle_supported_formats(request: web.Request) -> web.Response:
        """GET /api/supported-formats — list accepted file extensions."""
        return web.json_response({"extensions": sorted(ALL_SUPPORTED)})

    async def handle_download(request: web.Request) -> web.Response:
        """GET /api/download/{datasource}/{filename} — serve a file from the inbox."""
        ds = request.match_info["datasource"]
        filename = request.match_info["filename"]

        if ds == "general":
            file_path = Path(watch_path) / filename
        else:
            file_path = Path(watch_path) / ds / filename

        file_path = file_path.resolve()
        inbox_root = Path(watch_path).resolve()
        if not str(file_path).startswith(str(inbox_root)):
            raise web.HTTPForbidden()

        if not file_path.is_file():
            raise web.HTTPNotFound()

        return web.FileResponse(file_path)

    # ─── Route registration ──────────────────────────────────────

    app.router.add_get("/api/datasources", handle_list_datasources)
    app.router.add_post("/api/datasources", handle_create_datasource)
    app.router.add_get("/api/health", handle_health)
    app.router.add_get("/api/supported-formats", handle_supported_formats)
    app.router.add_get("/api/query/{datasource}", handle_query)
    app.router.add_post("/api/ingest/{datasource}", handle_ingest)
    app.router.add_post("/api/upload/{datasource}", handle_upload)
    app.router.add_post("/api/consolidate/{datasource}", handle_consolidate)
    app.router.add_get("/api/status/{datasource}", handle_status)
    app.router.add_get("/api/memories/{datasource}", handle_memories)
    app.router.add_post("/api/delete/{datasource}", handle_delete)
    app.router.add_post("/api/clear/{datasource}", handle_clear)
    app.router.add_get("/api/download/{datasource}/{filename}", handle_download)

    # SPA static file serving — must be registered AFTER all /api/ routes
    setup_static(app)

    return app
