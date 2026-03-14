"""Shared pytest fixtures for the agent-inbox-memory-layer test suite."""

from pathlib import Path

import pytest


@pytest.fixture
def tmp_inbox(tmp_path: Path) -> Path:
    """Temporary inbox/silo directory."""
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    return inbox
