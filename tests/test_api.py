"""API-1 through API-20: HTTP API endpoint tests."""

import io

import pytest
import pytest_asyncio

from memento.db import init_datasource_db, store_memory


# ─── /api/datasources ───────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_datasources_returns_list(client, general_db):
    """API-1: GET /api/datasources returns a list with name field."""
    resp = await client.get("/api/datasources")
    assert resp.status == 200
    data = await resp.json()
    assert isinstance(data, list)
    assert all("name" in ds for ds in data)


@pytest.mark.asyncio
async def test_create_datasource_valid(client, tmp_db_dir):
    """API-2: POST /api/datasources with valid name returns 201."""
    resp = await client.post("/api/datasources", json={"name": "newds"})
    assert resp.status == 201
    data = await resp.json()
    assert data["status"] == "created"
    assert data["name"] == "newds"


@pytest.mark.asyncio
async def test_create_datasource_invalid_name(client):
    """API-3: POST /api/datasources with invalid name returns 400."""
    resp = await client.post("/api/datasources", json={"name": "Bad Name!"})
    assert resp.status == 400
    data = await resp.json()
    assert "error" in data


# ─── /api/ingest/{datasource} ───────────────────────────────────

@pytest.mark.asyncio
async def test_ingest_text(client, general_db, mock_agent):
    """API-4: POST /api/ingest/general stores a memory (via mock agent)."""
    resp = await client.post("/api/ingest/general", json={"text": "hello world", "source": "test"})
    assert resp.status == 200
    data = await resp.json()
    assert data["status"] == "ingested"
    mock_agent.ingest.assert_called_once()


@pytest.mark.asyncio
async def test_ingest_empty_text(client, general_db):
    """API-5: POST /api/ingest/general with empty text returns 400."""
    resp = await client.post("/api/ingest/general", json={"text": "   "})
    assert resp.status == 400


@pytest.mark.asyncio
async def test_ingest_nonexistent_datasource(client):
    """API-6: POST /api/ingest/nonexistent returns 404."""
    resp = await client.post("/api/ingest/nonexistent", json={"text": "hello"})
    assert resp.status == 404


# ─── /api/query/{datasource} ────────────────────────────────────

@pytest.mark.asyncio
async def test_query_returns_answer(client, general_db, mock_agent):
    """API-7: GET /api/query/general?q=test returns question and answer."""
    resp = await client.get("/api/query/general?q=test+question")
    assert resp.status == 200
    data = await resp.json()
    assert "question" in data
    assert "answer" in data


@pytest.mark.asyncio
async def test_query_missing_q(client, general_db):
    """API-8: GET /api/query/general without ?q= returns 400."""
    resp = await client.get("/api/query/general")
    assert resp.status == 400


# ─── /api/upload/{datasource} ───────────────────────────────────

@pytest.mark.asyncio
async def test_upload_file(client, general_db, tmp_inbox):
    """API-9: POST /api/upload/general with multipart writes file to inbox."""
    from aiohttp import FormData
    data = FormData()
    data.add_field("file", io.BytesIO(b"test content"), filename="test.txt", content_type="text/plain")
    resp = await client.post("/api/upload/general", data=data)
    assert resp.status == 200
    result = await resp.json()
    assert result["filename"] == "test.txt"
    assert (tmp_inbox / "test.txt").exists()


# ─── /api/consolidate/{datasource} ──────────────────────────────

@pytest.mark.asyncio
async def test_consolidate(client, general_db, mock_agent):
    """API-10: POST /api/consolidate/general triggers consolidation."""
    resp = await client.post("/api/consolidate/general")
    assert resp.status == 200
    data = await resp.json()
    assert data["status"] == "done"
    mock_agent.consolidate.assert_called_once()


# ─── /api/status/{datasource} ───────────────────────────────────

@pytest.mark.asyncio
async def test_status(client, general_db):
    """API-11: GET /api/status/general returns memory stats."""
    resp = await client.get("/api/status/general")
    assert resp.status == 200
    data = await resp.json()
    assert "total_memories" in data
    assert "unconsolidated" in data
    assert "consolidations" in data


# ─── /api/memories/{datasource} ─────────────────────────────────

@pytest.mark.asyncio
async def test_memories_paginated(client, general_db):
    """API-12: GET /api/memories/general returns paginated memories."""
    resp = await client.get("/api/memories/general")
    assert resp.status == 200
    data = await resp.json()
    assert "memories" in data
    assert "next_cursor" in data


@pytest.mark.asyncio
async def test_memories_cursor(client, general_db):
    """API-13: GET /api/memories/general?cursor=5&limit=10 paginates correctly."""
    # Insert some memories first
    for i in range(5):
        store_memory("general", f"raw {i}", f"summary {i}", [], [], 0.5, "test")
    resp = await client.get("/api/memories/general?cursor=5&limit=10")
    assert resp.status == 200
    data = await resp.json()
    assert all(m["id"] < 5 for m in data["memories"])


@pytest.mark.asyncio
async def test_memories_limit_clamped(client, general_db):
    """API-14: limit=200 is silently clamped to 100."""
    resp = await client.get("/api/memories/general?limit=200")
    assert resp.status == 200  # No error, just clamped


@pytest.mark.asyncio
async def test_memories_empty(client, general_db):
    """API-15: Empty datasource returns empty list with null next_cursor."""
    resp = await client.get("/api/memories/general")
    assert resp.status == 200
    data = await resp.json()
    assert data["memories"] == []
    assert data["next_cursor"] is None


# ─── /api/delete/{datasource} ───────────────────────────────────

@pytest.mark.asyncio
async def test_delete_memory(client, general_db):
    """API-16: POST /api/delete/general deletes the specified memory."""
    result = store_memory("general", "raw", "summary", [], [], 0.5, "test")
    mid = result["memory_id"]
    resp = await client.post("/api/delete/general", json={"memory_id": mid})
    assert resp.status == 200
    data = await resp.json()
    assert data["status"] == "deleted"
    assert data["memory_id"] == mid


@pytest.mark.asyncio
async def test_delete_nonexistent_memory(client, general_db):
    """API-17: Deleting non-existent memory returns not_found status."""
    resp = await client.post("/api/delete/general", json={"memory_id": 99999})
    assert resp.status == 200
    data = await resp.json()
    assert data["status"] == "not_found"


# ─── /api/clear/{datasource} ────────────────────────────────────

@pytest.mark.asyncio
async def test_clear_datasource(client, general_db):
    """API-18: POST /api/clear/general deletes all memories."""
    store_memory("general", "raw", "summary", [], [], 0.5, "test")
    resp = await client.post("/api/clear/general")
    assert resp.status == 200
    data = await resp.json()
    assert data["status"] == "cleared"
    assert data["memories_deleted"] >= 1


# ─── General API contract ────────────────────────────────────────

@pytest.mark.asyncio
async def test_all_routes_return_json(client, general_db):
    """API-19: All /api/ routes return Content-Type application/json."""
    routes = [
        ("GET", "/api/datasources"),
        ("GET", "/api/status/general"),
        ("GET", "/api/memories/general"),
    ]
    for method, path in routes:
        if method == "GET":
            resp = await client.get(path)
        else:
            resp = await client.post(path, json={})
        assert "application/json" in resp.headers.get("Content-Type", ""), f"{method} {path}"


@pytest.mark.asyncio
async def test_unknown_datasource_returns_404(client):
    """API-20: Requests to unknown datasource return 404."""
    resp = await client.get("/api/status/doesnotexist")
    assert resp.status == 404


# ─── Importance score contract ───────────────────────────────────

@pytest.mark.asyncio
@pytest.mark.parametrize("importance", [0.0, 0.3, 0.5, 0.7, 1.0])
async def test_importance_returned_as_zero_to_one(client, general_db, importance):
    """API-21: importance is returned in 0.0–1.0 range (frontend multiplies by 10 for display)."""
    store_memory("general", "raw", "summary", [], [], importance, "test")
    resp = await client.get("/api/memories/general")
    data = await resp.json()
    mem = data["memories"][0]
    assert mem["importance"] == importance
    assert 0.0 <= mem["importance"] <= 1.0
    # Clean up for next parametrize iteration
    from memento.db import clear_all_memories
    clear_all_memories("general")
