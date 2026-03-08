"""SPA-1 through SPA-6: Static file serving and SPA catch-all tests."""

import pytest
import pytest_asyncio
from pathlib import Path

from memento.db import init_datasource_db


@pytest.fixture
def app_with_dist(tmp_db_dir, tmp_inbox, mock_agent, tmp_path):
    """App wired to a temporary frontend/dist directory."""
    # Create a fake dist directory
    dist = tmp_path / "frontend" / "dist"
    dist.mkdir(parents=True)
    (dist / "index.html").write_text("<html><body>Memento</body></html>")
    assets = dist / "assets"
    assets.mkdir()
    (assets / "main.js").write_text("console.log('ok')")

    # Patch the static module to use tmp dist
    import memento.static as static_module
    old = static_module.DIST_DIR
    static_module.DIST_DIR = dist

    from memento.api import build_http
    init_datasource_db("general")
    app = build_http(mock_agent, watch_path=str(tmp_inbox))

    yield app

    static_module.DIST_DIR = old


@pytest_asyncio.fixture
async def spa_client(aiohttp_client, app_with_dist):
    return await aiohttp_client(app_with_dist)


# SPA-1: GET / serves index.html
@pytest.mark.asyncio
async def test_root_serves_index(spa_client):
    """SPA-1: GET / serves frontend/dist/index.html."""
    resp = await spa_client.get("/")
    assert resp.status == 200
    text = await resp.text()
    assert "Memento" in text


# SPA-2: GET /ingest serves index.html (catch-all)
@pytest.mark.asyncio
async def test_spa_route_served(spa_client):
    """SPA-2: GET /ingest serves index.html via SPA catch-all."""
    resp = await spa_client.get("/ingest")
    assert resp.status == 200
    text = await resp.text()
    assert "Memento" in text


# SPA-3: Nested SPA route
@pytest.mark.asyncio
async def test_nested_spa_route(spa_client):
    """SPA-3: GET /query/news serves index.html for nested SPA routes."""
    resp = await spa_client.get("/query/news")
    assert resp.status == 200
    text = await resp.text()
    assert "Memento" in text


# SPA-4: Static assets served
@pytest.mark.asyncio
async def test_static_asset_served(spa_client):
    """SPA-4: GET /assets/main.js serves the actual static file."""
    resp = await spa_client.get("/assets/main.js")
    assert resp.status == 200
    text = await resp.text()
    assert "console.log" in text


# SPA-5: /api/* routes NOT caught by SPA
@pytest.mark.asyncio
async def test_api_route_not_caught_by_spa(spa_client):
    """SPA-5: GET /api/status/general hits the API handler, not the SPA."""
    resp = await spa_client.get("/api/status/general")
    assert resp.status == 200
    data = await resp.json()
    assert "total_memories" in data


# SPA-6: Missing dist directory returns 404
@pytest.mark.asyncio
async def test_missing_dist_returns_404(client):
    """SPA-6: When frontend/dist/ does not exist, non-API routes return 404."""
    import memento.static as static_module
    from pathlib import Path
    old = static_module.DIST_DIR
    static_module.DIST_DIR = Path("/nonexistent/path/dist")
    try:
        resp = await client.get("/some-page")
        assert resp.status == 404
    finally:
        static_module.DIST_DIR = old
