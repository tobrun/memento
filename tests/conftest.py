"""Shared pytest fixtures for the Memento test suite."""

import asyncio
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio

import memento.db as db_module
from memento.db import init_datasource_db


@pytest.fixture
def tmp_inbox(tmp_path: Path) -> Path:
    """Temporary inbox root directory."""
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    return inbox


@pytest.fixture
def tmp_db_dir(tmp_path: Path) -> Path:
    """Temporary database directory, wired into the db module."""
    db_dir = tmp_path / "databases"
    db_dir.mkdir()
    old_dir = db_module.MEMORY_DB_DIR
    db_module.MEMORY_DB_DIR = str(db_dir)
    yield db_dir
    db_module.MEMORY_DB_DIR = old_dir


@pytest.fixture
def general_db(tmp_db_dir: Path):
    """Initialise a general datasource DB and return the db_dir."""
    init_datasource_db("general")
    return tmp_db_dir


@pytest.fixture
def mock_agent():
    """A MemoryAgent whose async methods are no-ops."""
    agent = MagicMock()
    agent.ingest = AsyncMock(return_value="ingested")
    agent.ingest_file = AsyncMock(return_value="ingested file")
    agent.consolidate = AsyncMock(return_value="consolidated")
    agent.query = AsyncMock(return_value="answer")
    return agent


@pytest.fixture
def app(tmp_db_dir, tmp_inbox, mock_agent):
    """aiohttp Application wired to tmp directories with a mock agent."""
    from memento.api import build_http
    return build_http(mock_agent, watch_path=str(tmp_inbox))


@pytest_asyncio.fixture
async def client(aiohttp_client, app):
    """aiohttp test client."""
    return await aiohttp_client(app)
