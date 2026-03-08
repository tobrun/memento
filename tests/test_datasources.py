"""DS-1 through DS-8: Datasource discovery, creation, and naming tests."""

import asyncio
from pathlib import Path

import pytest
import pytest_asyncio

from memento.db import validate_datasource_name, init_datasource_db, datasource_exists


# ─── DS-4, DS-5: Name validation ────────────────────────────────

@pytest.mark.parametrize("name", ["news", "my-feed", "company_docs", "x1", "a", "abc-123_def"])
def test_valid_datasource_names(name):
    """DS-4: Valid names are accepted."""
    assert validate_datasource_name(name) is True


@pytest.mark.parametrize("name", [
    "My News",      # uppercase + space
    "../etc",       # path traversal
    ".hidden",      # dot prefix
    "",             # empty
    "a!b",          # special char
    "A",            # uppercase
    "has space",    # space
    "../../etc",    # deep traversal
    None,           # None
])
def test_invalid_datasource_names(name):
    """DS-5: Invalid names are rejected."""
    assert validate_datasource_name(name or "") is False


# ─── DS-6: Creation flow ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_datasource_via_api(client, tmp_inbox, tmp_db_dir):
    """DS-6: POST /api/datasources creates inbox dir, initialises DB, returns 201."""
    resp = await client.post("/api/datasources", json={"name": "news"})
    assert resp.status == 201
    data = await resp.json()
    assert data["status"] == "created"
    assert data["name"] == "news"
    # Inbox directory was created
    assert (tmp_inbox / "news").is_dir()
    # DB was created
    assert (tmp_db_dir / "news.db").exists()


# ─── DS-7: Duplicate creation ────────────────────────────────────

@pytest.mark.asyncio
async def test_create_duplicate_datasource(client, tmp_db_dir):
    """DS-7: Creating a datasource that already exists returns 409."""
    init_datasource_db("news")
    resp = await client.post("/api/datasources", json={"name": "news"})
    assert resp.status == 409
    data = await resp.json()
    assert "already exists" in data["error"]


# ─── DS-5 via API: Invalid name rejection ────────────────────────

@pytest.mark.asyncio
async def test_create_datasource_invalid_name(client):
    """DS-5 (API): Invalid name returns 400."""
    resp = await client.post("/api/datasources", json={"name": "My News!"})
    assert resp.status == 400
    data = await resp.json()
    assert "error" in data


# ─── DS-1, DS-2: Datasource listing ─────────────────────────────

@pytest.mark.asyncio
async def test_list_datasources_includes_general(client, tmp_db_dir):
    """DS-2: GET /api/datasources always includes general."""
    init_datasource_db("general")
    resp = await client.get("/api/datasources")
    assert resp.status == 200
    data = await resp.json()
    names = [d["name"] for d in data]
    assert "general" in names


@pytest.mark.asyncio
async def test_list_datasources_includes_subdirs(client, tmp_inbox, tmp_db_dir):
    """DS-1: Subdirectory in inbox appears in GET /api/datasources."""
    (tmp_inbox / "news").mkdir()
    init_datasource_db("general")
    resp = await client.get("/api/datasources")
    assert resp.status == 200
    data = await resp.json()
    names = [d["name"] for d in data]
    assert "news" in names
