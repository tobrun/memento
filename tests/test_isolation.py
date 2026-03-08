"""ISO-1 through ISO-5: Strict datasource isolation tests."""

import pytest
import pytest_asyncio

from memento.db import (
    clear_all_memories,
    get_db,
    get_memory_stats,
    init_datasource_db,
    read_all_memories,
    store_memory,
)


def _insert_memory(datasource: str, summary: str = "test"):
    store_memory(datasource, "raw", summary, [], [], 0.5, "test")


# ISO-1: Memory stored in news is NOT in company
def test_memory_isolation_between_datasources(tmp_db_dir):
    """ISO-1: Ingesting into news does not populate company DB."""
    init_datasource_db("news")
    init_datasource_db("company")
    _insert_memory("news", "news summary")

    result = read_all_memories("company")
    assert result["count"] == 0


# ISO-2: Querying news returns only news memories
def test_query_isolation(tmp_db_dir):
    """ISO-2: read_all_memories for news returns only news memories."""
    init_datasource_db("news")
    init_datasource_db("company")
    _insert_memory("news", "news item")
    _insert_memory("company", "company item")

    news_mems = read_all_memories("news")["memories"]
    assert all("news" in m["summary"] for m in news_mems)
    assert len(news_mems) == 1


# ISO-3: processed_files isolation
def test_processed_files_isolation(tmp_db_dir, tmp_inbox):
    """ISO-4: processed_files tracking is per-datasource."""
    init_datasource_db("news")
    init_datasource_db("company")

    # Mark a file processed in news
    db_news = get_db("news")
    db_news.execute(
        "INSERT INTO processed_files (path, processed_at) VALUES (?, ?)",
        ("/inbox/news/file.txt", "2024-01-01T00:00:00Z"),
    )
    db_news.commit()
    db_news.close()

    # Company should NOT have that file
    db_company = get_db("company")
    row = db_company.execute(
        "SELECT 1 FROM processed_files WHERE path = ?", ("/inbox/news/file.txt",)
    ).fetchone()
    db_company.close()
    assert row is None


# ISO-5: Clearing news does not affect company
def test_clear_does_not_affect_other_datasource(tmp_db_dir, tmp_inbox):
    """ISO-5: Clearing news leaves company untouched."""
    init_datasource_db("news")
    init_datasource_db("company")
    _insert_memory("news", "to be cleared")
    _insert_memory("company", "should survive")

    clear_all_memories("news")

    news_stats = get_memory_stats("news")
    company_stats = get_memory_stats("company")
    assert news_stats["total_memories"] == 0
    assert company_stats["total_memories"] == 1
