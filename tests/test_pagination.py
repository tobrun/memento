"""PG-1 through PG-9: Cursor-based pagination tests."""

import pytest

from memento.db import get_db, init_datasource_db, read_memories_paginated, store_memory


def _populate(datasource: str, n: int):
    """Insert n memories into a datasource, return their IDs in insertion order."""
    ids = []
    for i in range(n):
        result = store_memory(datasource, f"raw {i}", f"summary {i}", [], [], 0.5, "test")
        ids.append(result["memory_id"])
    return ids


# PG-1: First page returns most recent N memories
def test_first_page_most_recent(tmp_db_dir):
    """PG-1: Without cursor, returns the most recent N memories (descending by id)."""
    init_datasource_db("pgtest")
    ids = _populate("pgtest", 5)
    result = read_memories_paginated("pgtest", cursor=None, limit=3)
    returned_ids = [m["id"] for m in result["memories"]]
    assert returned_ids == sorted(ids, reverse=True)[:3]


# PG-2: cursor returns memories older than cursor id
def test_cursor_returns_older(tmp_db_dir):
    """PG-2: cursor=<id> returns memories with id < cursor."""
    init_datasource_db("pgtest2")
    ids = _populate("pgtest2", 5)  # ids[0] < ids[4]
    cursor = ids[3]  # 4th memory
    result = read_memories_paginated("pgtest2", cursor=cursor, limit=10)
    returned_ids = [m["id"] for m in result["memories"]]
    assert all(mid < cursor for mid in returned_ids)


# PG-3: next_cursor is None when no more results
def test_next_cursor_null_on_last_page(tmp_db_dir):
    """PG-3: next_cursor is None when all results fit in one page."""
    init_datasource_db("pg3")
    _populate("pg3", 3)
    result = read_memories_paginated("pg3", cursor=None, limit=10)
    assert result["next_cursor"] is None


# PG-4: next_cursor set when more results exist
def test_next_cursor_set_when_more(tmp_db_dir):
    """PG-4: next_cursor contains ID of last returned item when more results exist."""
    init_datasource_db("pg4")
    _populate("pg4", 5)
    result = read_memories_paginated("pg4", cursor=None, limit=3)
    assert result["next_cursor"] is not None
    assert result["next_cursor"] == result["memories"][-1]["id"]


# PG-5: Default limit is 20
def test_default_limit(tmp_db_dir):
    """PG-5: Without limit parameter, default is 20."""
    init_datasource_db("pg5")
    _populate("pg5", 25)
    result = read_memories_paginated("pg5")
    assert len(result["memories"]) == 20


# PG-6: limit=0 falls back to default 20
def test_zero_limit_falls_back(tmp_db_dir):
    """PG-6: limit=0 falls back to default 20."""
    init_datasource_db("pg6")
    _populate("pg6", 25)
    result = read_memories_paginated("pg6", limit=0)
    assert len(result["memories"]) == 20


# PG-7: limit=200 clamped to 100
def test_limit_clamped_to_100(tmp_db_dir):
    """PG-7: limit=200 is clamped to 100."""
    init_datasource_db("pg7")
    _populate("pg7", 150)
    result = read_memories_paginated("pg7", limit=200)
    assert len(result["memories"]) <= 100


# PG-8: Invalid cursor returns 400 via API
@pytest.mark.asyncio
async def test_invalid_cursor_returns_400(client, general_db):
    """PG-8: Invalid cursor (non-integer) returns 400."""
    resp = await client.get("/api/memories/general?cursor=notanint")
    assert resp.status == 400


# PG-9: Paginating through all memories visits each exactly once
def test_full_pagination_no_duplicates(tmp_db_dir):
    """PG-9: Paginating through all memories with small limit visits each exactly once."""
    init_datasource_db("pg9")
    ids = set(_populate("pg9", 10))

    seen = set()
    cursor = None
    while True:
        result = read_memories_paginated("pg9", cursor=cursor, limit=3)
        for m in result["memories"]:
            assert m["id"] not in seen, f"Memory {m['id']} seen twice"
            seen.add(m["id"])
        cursor = result["next_cursor"]
        if cursor is None:
            break

    assert seen == ids
