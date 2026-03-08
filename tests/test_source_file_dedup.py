"""Tests for source_file-based deduplication on file re-ingestion."""

from memento.db import (
    delete_memories_by_source_file,
    get_db,
    init_datasource_db,
    read_all_memories,
    store_memory,
    tag_memories_with_source_file,
)


DS = "dedup_test"


def test_tag_memories_with_source_file(tmp_db_dir):
    """tag_memories_with_source_file sets source_file on untagged memories matching source."""
    init_datasource_db(DS)
    store_memory(DS, "raw", "summary", ["e"], ["t"], 0.5, source="notes.txt")

    updated = tag_memories_with_source_file(DS, "notes.txt", "/inbox/notes.txt")
    assert updated == 1

    db = get_db(DS)
    row = db.execute("SELECT source_file FROM memories WHERE source = ?", ("notes.txt",)).fetchone()
    db.close()
    assert row["source_file"] == "/inbox/notes.txt"


def test_tag_does_not_overwrite_existing(tmp_db_dir):
    """tag_memories_with_source_file skips memories that already have a source_file."""
    init_datasource_db(DS)
    store_memory(DS, "raw", "summary", [], [], 0.5, source="a.txt", source_file="/old/a.txt")

    updated = tag_memories_with_source_file(DS, "a.txt", "/new/a.txt")
    assert updated == 0

    db = get_db(DS)
    row = db.execute("SELECT source_file FROM memories").fetchone()
    db.close()
    assert row["source_file"] == "/old/a.txt"


def test_delete_memories_by_source_file(tmp_db_dir):
    """delete_memories_by_source_file removes all memories with matching source_file."""
    init_datasource_db(DS)
    store_memory(DS, "v1", "first", [], [], 0.5, source="f.txt", source_file="/inbox/f.txt")
    store_memory(DS, "other", "other", [], [], 0.5, source="g.txt", source_file="/inbox/g.txt")

    deleted = delete_memories_by_source_file(DS, "/inbox/f.txt")
    assert deleted == 1

    memories = read_all_memories(DS)
    assert memories["count"] == 1
    assert memories["memories"][0]["source"] == "g.txt"


def test_delete_returns_zero_when_no_match(tmp_db_dir):
    """delete_memories_by_source_file returns 0 when no memories match."""
    init_datasource_db(DS)
    store_memory(DS, "raw", "summary", [], [], 0.5, source="x.txt", source_file="/inbox/x.txt")

    deleted = delete_memories_by_source_file(DS, "/nonexistent/path.txt")
    assert deleted == 0
    assert read_all_memories(DS)["count"] == 1


def test_full_reingestion_flow(tmp_db_dir):
    """Simulates the full watcher flow: ingest, tag, re-ingest replaces old memory."""
    init_datasource_db(DS)
    source_file = "/inbox/news/report.txt"

    # First ingestion
    store_memory(DS, "v1 content", "version 1", ["A"], ["news"], 0.7, source="report.txt")
    tag_memories_with_source_file(DS, "report.txt", source_file)

    memories = read_all_memories(DS)
    assert memories["count"] == 1
    assert memories["memories"][0]["summary"] == "version 1"

    # File modified — delete old, re-ingest
    deleted = delete_memories_by_source_file(DS, source_file)
    assert deleted == 1

    store_memory(DS, "v2 content", "version 2", ["A", "B"], ["news"], 0.8, source="report.txt")
    tag_memories_with_source_file(DS, "report.txt", source_file)

    memories = read_all_memories(DS)
    assert memories["count"] == 1
    assert memories["memories"][0]["summary"] == "version 2"
    assert memories["memories"][0]["source_file"] == source_file


def test_source_file_column_in_schema(tmp_db_dir):
    """The memories table includes the source_file column."""
    init_datasource_db(DS)
    db = get_db(DS)
    cols = {row[1] for row in db.execute("PRAGMA table_info(memories)").fetchall()}
    db.close()
    assert "source_file" in cols
