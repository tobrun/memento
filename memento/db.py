"""Database layer — connection, schema, and all CRUD operations."""

import json
import logging
import re
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

log = logging.getLogger("memory-agent")

# ─── File type constants ────────────────────────────────────────

TEXT_EXTENSIONS = {".txt", ".md", ".mdx", ".json", ".csv", ".log", ".xml", ".yaml", ".yml"}
MEDIA_EXTENSIONS = {
    # Images
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".bmp": "image/bmp",
    ".svg": "image/svg+xml",
    # Audio
    ".mp3": "audio/mpeg",
    ".wav": "audio/wav",
    ".ogg": "audio/ogg",
    ".flac": "audio/flac",
    ".m4a": "audio/mp4",
    ".aac": "audio/aac",
    # Video
    ".mp4": "video/mp4",
    ".webm": "video/webm",
    ".mov": "video/quicktime",
    ".avi": "video/x-msvideo",
    ".mkv": "video/x-matroska",
    # Documents
    ".pdf": "application/pdf",
}
ALL_SUPPORTED = TEXT_EXTENSIONS | set(MEDIA_EXTENSIONS.keys())

# ─── Datasource name validation ─────────────────────────────────

_DS_NAME_RE = re.compile(r"^[a-z0-9_-]+$")


def validate_datasource_name(name: str) -> bool:
    """Validate a datasource name against the allowed pattern.

    Valid names match ^[a-z0-9_-]+$ and must not be empty, start with a dot,
    or contain path traversal sequences.
    """
    if not name:
        return False
    if ".." in name or name.startswith("."):
        return False
    return bool(_DS_NAME_RE.match(name))


# ─── DB path helpers ────────────────────────────────────────────

# Populated by config.py after argument parsing
MEMORY_DB_DIR: str = "./databases"


def _db_path(datasource: str) -> Path:
    db_dir = Path(MEMORY_DB_DIR)
    db_dir.mkdir(parents=True, exist_ok=True)
    return db_dir / f"{datasource}.db"


def datasource_exists(datasource: str) -> bool:
    """Return True if the datasource DB file exists."""
    return _db_path(datasource).exists()


def inbox_exists(datasource: str, inbox_root: str) -> bool:
    """Return True if the inbox directory for the datasource exists."""
    if datasource == "general":
        return Path(inbox_root).exists()
    return (Path(inbox_root) / datasource).exists()


def init_datasource_db(datasource: str) -> None:
    """Create the DB file and initialise the schema for a datasource."""
    db = get_db(datasource)
    db.close()


# ─── Database connection ────────────────────────────────────────

_SCHEMA = """
    CREATE TABLE IF NOT EXISTS memories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        source TEXT NOT NULL DEFAULT '',
        raw_text TEXT NOT NULL,
        summary TEXT NOT NULL,
        entities TEXT NOT NULL DEFAULT '[]',
        topics TEXT NOT NULL DEFAULT '[]',
        connections TEXT NOT NULL DEFAULT '[]',
        importance REAL NOT NULL DEFAULT 0.5,
        created_at TEXT NOT NULL,
        consolidated INTEGER NOT NULL DEFAULT 0
    );
    CREATE TABLE IF NOT EXISTS consolidations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        source_ids TEXT NOT NULL,
        summary TEXT NOT NULL,
        insight TEXT NOT NULL,
        created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS processed_files (
        path TEXT PRIMARY KEY,
        processed_at TEXT NOT NULL,
        file_mtime REAL
    );
"""


def get_db(datasource: str) -> sqlite3.Connection:
    """Open (and initialise) the SQLite database for a datasource."""
    db = sqlite3.connect(str(_db_path(datasource)))
    db.row_factory = sqlite3.Row
    db.executescript(_SCHEMA)
    # Migration: add file_mtime column if missing (pre-existing databases)
    cols = {row[1] for row in db.execute("PRAGMA table_info(processed_files)").fetchall()}
    if "file_mtime" not in cols:
        db.execute("ALTER TABLE processed_files ADD COLUMN file_mtime REAL")
    return db


# ─── Row helper ─────────────────────────────────────────────────


def _convert_row(r: sqlite3.Row) -> dict:
    return {
        "id": r["id"],
        "source": r["source"],
        "summary": r["summary"],
        "raw_text": r["raw_text"],
        "entities": json.loads(r["entities"]),
        "topics": json.loads(r["topics"]),
        "importance": r["importance"],
        "connections": json.loads(r["connections"]),
        "created_at": r["created_at"],
        "consolidated": bool(r["consolidated"]),
    }


# ─── CRUD operations ────────────────────────────────────────────


def store_memory(
    datasource: str,
    raw_text: str,
    summary: str,
    entities: list[str],
    topics: list[str],
    importance: float,
    source: str = "",
) -> dict:
    """Store a processed memory in the database.

    Args:
        datasource: The datasource name (e.g. "general", "news").
        raw_text: The original input text.
        summary: A concise 1-2 sentence summary.
        entities: Key people, companies, products, or concepts.
        topics: 2-4 topic tags.
        importance: Float 0.0 to 1.0 indicating importance.
        source: Where this memory came from (filename, URL, etc).

    Returns:
        dict with memory_id and confirmation.
    """
    db = get_db(datasource)
    now = datetime.now(timezone.utc).isoformat()
    cursor = db.execute(
        """INSERT INTO memories (source, raw_text, summary, entities, topics, importance, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (source, raw_text, summary, json.dumps(entities), json.dumps(topics), importance, now),
    )
    db.commit()
    mid = cursor.lastrowid
    db.close()
    log.info(f"Stored memory #{mid} [{datasource}]: {summary[:60]}...")
    return {"memory_id": mid, "status": "stored", "summary": summary}


def read_all_memories(datasource: str) -> dict:
    """Read all stored memories from the database, most recent first.

    Args:
        datasource: The datasource name.

    Returns:
        dict with list of memories and count.
    """
    db = get_db(datasource)
    rows = db.execute("SELECT * FROM memories ORDER BY created_at DESC LIMIT 50").fetchall()
    memories = [_convert_row(r) for r in rows]
    db.close()
    return {"memories": memories, "count": len(memories)}


def read_unconsolidated_memories(datasource: str) -> dict:
    """Read memories that haven't been consolidated yet.

    Args:
        datasource: The datasource name.

    Returns:
        dict with list of unconsolidated memories and count.
    """
    db = get_db(datasource)
    rows = db.execute(
        "SELECT * FROM memories WHERE consolidated = 0 ORDER BY created_at DESC LIMIT 10"
    ).fetchall()
    memories = []
    for r in rows:
        memories.append({
            "id": r["id"], "summary": r["summary"],
            "entities": json.loads(r["entities"]), "topics": json.loads(r["topics"]),
            "importance": r["importance"], "created_at": r["created_at"],
        })
    db.close()
    return {"memories": memories, "count": len(memories)}


def store_consolidation(
    datasource: str,
    source_ids: list[int],
    summary: str,
    insight: str,
    connections: list[dict],
) -> dict:
    """Store a consolidation result and mark source memories as consolidated.

    Args:
        datasource: The datasource name.
        source_ids: List of memory IDs that were consolidated.
        summary: A synthesized summary across all source memories.
        insight: One key pattern or insight discovered.
        connections: List of dicts with 'from_id', 'to_id', 'relationship'.

    Returns:
        dict with confirmation.
    """
    db = get_db(datasource)
    now = datetime.now(timezone.utc).isoformat()
    db.execute(
        "INSERT INTO consolidations (source_ids, summary, insight, created_at) VALUES (?, ?, ?, ?)",
        (json.dumps(source_ids), summary, insight, now),
    )
    for conn in connections:
        from_id, to_id = conn.get("from_id"), conn.get("to_id")
        rel = conn.get("relationship", "")
        if from_id and to_id:
            for mid in [from_id, to_id]:
                row = db.execute("SELECT connections FROM memories WHERE id = ?", (mid,)).fetchone()
                if row:
                    existing = json.loads(row["connections"])
                    existing.append({"linked_to": to_id if mid == from_id else from_id, "relationship": rel})
                    db.execute("UPDATE memories SET connections = ? WHERE id = ?", (json.dumps(existing), mid))
    placeholders = ",".join("?" * len(source_ids))
    db.execute(f"UPDATE memories SET consolidated = 1 WHERE id IN ({placeholders})", source_ids)
    db.commit()
    db.close()
    log.info(f"Consolidated {len(source_ids)} memories [{datasource}]. Insight: {insight[:80]}...")
    return {"status": "consolidated", "memories_processed": len(source_ids), "insight": insight}


def read_consolidation_history(datasource: str) -> dict:
    """Read past consolidation insights.

    Args:
        datasource: The datasource name.

    Returns:
        dict with list of consolidation records.
    """
    db = get_db(datasource)
    rows = db.execute("SELECT * FROM consolidations ORDER BY created_at DESC LIMIT 10").fetchall()
    result = [{"summary": r["summary"], "insight": r["insight"], "source_ids": r["source_ids"]} for r in rows]
    db.close()
    return {"consolidations": result, "count": len(result)}


def get_memory_stats(datasource: str) -> dict:
    """Get current memory statistics for a datasource.

    Args:
        datasource: The datasource name.

    Returns:
        dict with counts of memories, consolidations, etc.
    """
    db = get_db(datasource)
    total = db.execute("SELECT COUNT(*) as c FROM memories").fetchone()["c"]
    unconsolidated = db.execute("SELECT COUNT(*) as c FROM memories WHERE consolidated = 0").fetchone()["c"]
    consolidations = db.execute("SELECT COUNT(*) as c FROM consolidations").fetchone()["c"]
    db.close()
    return {
        "total_memories": total,
        "unconsolidated": unconsolidated,
        "consolidations": consolidations,
    }


def delete_memory(datasource: str, memory_id: int) -> dict:
    """Delete a memory by ID.

    Args:
        datasource: The datasource name.
        memory_id: The ID of the memory to delete.

    Returns:
        dict with status.
    """
    db = get_db(datasource)
    row = db.execute("SELECT 1 FROM memories WHERE id = ?", (memory_id,)).fetchone()
    if not row:
        db.close()
        return {"status": "not_found", "memory_id": memory_id}
    db.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
    db.commit()
    db.close()
    log.info(f"Deleted memory #{memory_id} [{datasource}]")
    return {"status": "deleted", "memory_id": memory_id}


def clear_all_memories(datasource: str, inbox_path: str | None = None) -> dict:
    """Delete all memories, consolidations, and inbox files for a datasource.

    Args:
        datasource: The datasource name.
        inbox_path: If provided, also delete files in this directory.

    Returns:
        dict with counts of deleted items.
    """
    db = get_db(datasource)
    mem_count = db.execute("SELECT COUNT(*) as c FROM memories").fetchone()["c"]
    db.execute("DELETE FROM memories")
    db.execute("DELETE FROM consolidations")
    db.execute("DELETE FROM processed_files")
    db.commit()
    db.close()

    files_deleted = 0
    if inbox_path:
        folder = Path(inbox_path)
        if folder.is_dir():
            for f in folder.iterdir():
                if f.name.startswith("."):
                    continue  # keep hidden files like .gitkeep
                try:
                    if f.is_file():
                        f.unlink()
                        files_deleted += 1
                    elif f.is_dir():
                        shutil.rmtree(f)
                        files_deleted += 1
                except OSError as e:
                    log.error(f"Failed to delete {f.name}: {e}")

    log.info(f"Cleared all {mem_count} memories [{datasource}], deleted {files_deleted} inbox files")
    return {"status": "cleared", "memories_deleted": mem_count, "files_deleted": files_deleted}


def read_memories_paginated(datasource: str, cursor: int | None = None, limit: int = 20) -> dict:
    """Read memories with cursor-based pagination.

    Args:
        datasource: The datasource name.
        cursor: If provided, return memories with id < cursor (older than cursor).
        limit: Number of results per page (1-100, default 20).

    Returns:
        dict with memories list and next_cursor (None if no more results).
    """
    limit = max(1, min(limit, 100)) if limit > 0 else 20
    db = get_db(datasource)
    if cursor is not None:
        rows = db.execute(
            "SELECT * FROM memories WHERE id < ? ORDER BY id DESC LIMIT ?",
            (cursor, limit + 1),
        ).fetchall()
    else:
        rows = db.execute(
            "SELECT * FROM memories ORDER BY id DESC LIMIT ?",
            (limit + 1,),
        ).fetchall()
    has_more = len(rows) > limit
    rows = rows[:limit]
    next_cursor = rows[-1]["id"] if has_more and rows else None
    memories = [_convert_row(r) for r in rows]
    db.close()
    return {"memories": memories, "next_cursor": next_cursor}
