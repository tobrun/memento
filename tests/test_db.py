"""DB-1 through DB-7: Database storage tests."""

from pathlib import Path

import pytest

import memento.db as db_module
from memento.db import (
    datasource_exists,
    get_db,
    get_memory_stats,
    inbox_exists,
    init_datasource_db,
    store_memory,
)


# DB-1: Databases created in MEMORY_DB directory
def test_db_created_in_configured_dir(tmp_db_dir):
    """DB-1: get_db() creates the .db file inside MEMORY_DB_DIR."""
    db = get_db("testds")
    db.close()
    assert (tmp_db_dir / "testds.db").exists()


# DB-2: Default MEMORY_DB_DIR is ./databases
def test_default_memory_db_dir():
    """DB-2: The default MEMORY_DB_DIR ends with 'databases'."""
    # We can't use the live default (tests override it), so check the source
    import inspect
    src = inspect.getsource(db_module)
    assert '"./databases"' in src or "'./databases'" in src


# DB-3: Files named <datasource>.db
def test_db_file_naming(tmp_db_dir):
    """DB-3: Database files are named <datasource>.db."""
    get_db("myds").close()
    assert (tmp_db_dir / "myds.db").exists()
    assert not (tmp_db_dir / "myds").exists()  # not a directory


# DB-4: Schema tables exist
def test_schema_tables(tmp_db_dir):
    """DB-4: Schema includes memories, consolidations, processed_files tables."""
    db = get_db("schematest")
    tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    db.close()
    assert {"memories", "consolidations", "processed_files"} <= tables


# DB-5: Missing inbox warning
def test_missing_inbox_warning(tmp_db_dir, tmp_inbox):
    """DB-5: When inbox dir is deleted but DB remains, API returns warning."""
    # We test this via the watcher helper and API directly
    init_datasource_db("orphan")
    # Do NOT create the inbox subdirectory for "orphan"
    from memento.api import _inbox_warning
    warning = _inbox_warning("orphan", str(tmp_inbox))
    assert warning == "datasource inbox missing"


# DB-6: get_db(datasource) returns connection to correct DB
def test_get_db_correct_file(tmp_db_dir):
    """DB-6: get_db(datasource) connects to the correct datasource DB."""
    db_a = get_db("alpha")
    db_a.execute("INSERT INTO memories (source, raw_text, summary, entities, topics, importance, created_at) VALUES (?,?,?,?,?,?,?)",
                 ("src", "text", "summary", "[]", "[]", 0.5, "2024-01-01T00:00:00Z"))
    db_a.commit()
    db_a.close()

    # Beta DB should be empty
    db_b = get_db("beta")
    count = db_b.execute("SELECT COUNT(*) FROM memories").fetchone()[0]
    db_b.close()
    assert count == 0


# DB-7: databases/ directory auto-created
def test_db_dir_auto_created(tmp_path):
    """DB-7: The databases/ directory is created automatically if missing."""
    new_dir = tmp_path / "newdatabases"
    assert not new_dir.exists()
    old = db_module.MEMORY_DB_DIR
    db_module.MEMORY_DB_DIR = str(new_dir)
    try:
        db = get_db("autotest")
        db.close()
        assert new_dir.exists()
    finally:
        db_module.MEMORY_DB_DIR = old
