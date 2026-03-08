"""CS-1 through CS-8: Smoke tests for package structure and removed files."""

import importlib
from pathlib import Path

import pytest


# CS-1: python -m memento entry point
def test_entry_point_importable():
    """CS-1: The memento package entry point is importable."""
    import memento.__main__
    assert hasattr(memento.__main__, "main")


# CS-2 through CS-6: All submodules importable
@pytest.mark.parametrize("module,symbol", [
    ("memento.db", "get_db"),
    ("memento.agents", "MemoryAgent"),
    ("memento.api", "build_http"),
    ("memento.watcher", "watch_datasource"),
    ("memento.config", "parse_args"),
])
def test_submodule_importable(module, symbol):
    """CS-2 through CS-6: All memento submodules are importable."""
    mod = importlib.import_module(module)
    assert hasattr(mod, symbol)


# CS-7: dashboard.py removed
def test_dashboard_removed():
    """CS-7: dashboard.py does not exist at project root."""
    root = Path(__file__).parent.parent
    assert not (root / "dashboard.py").exists(), "dashboard.py should have been removed"


# CS-8: streamlit not in requirements.txt
def test_streamlit_not_in_requirements():
    """CS-8: streamlit is not listed as a dependency."""
    root = Path(__file__).parent.parent
    reqs = (root / "requirements.txt").read_text()
    assert "streamlit" not in reqs.lower(), "streamlit should be removed from requirements.txt"
