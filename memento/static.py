"""Static file serving — serves the frontend SPA from frontend/dist/."""

from pathlib import Path

from aiohttp import web

DIST_DIR = Path(__file__).parent.parent / "frontend" / "dist"


async def handle_static(request: web.Request) -> web.Response:
    """Serve static files from frontend/dist/ with SPA catch-all fallback."""
    if not DIST_DIR.exists():
        raise web.HTTPNotFound()

    path = request.match_info.get("path", "")
    file_path = DIST_DIR / path

    if file_path.is_file():
        return web.FileResponse(file_path)

    # SPA catch-all: serve index.html for any unmatched non-API route
    index = DIST_DIR / "index.html"
    if index.exists():
        return web.FileResponse(index)

    raise web.HTTPNotFound()


def setup_static(app: web.Application) -> None:
    """Register the SPA catch-all route on the aiohttp app.

    Must be called AFTER all /api/ routes are registered so the catch-all
    does not shadow API endpoints.
    """
    app.router.add_get("/{path:.*}", handle_static)
