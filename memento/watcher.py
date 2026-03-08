"""File watcher and consolidation loop — multi-datasource aware."""

import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path

from memento.db import (
    ALL_SUPPORTED,
    MEDIA_EXTENSIONS,
    TEXT_EXTENSIONS,
    get_db,
    get_memory_stats,
    validate_datasource_name,
)

log = logging.getLogger("memory-agent")


async def discover_datasources(inbox_root: Path) -> list[str]:
    """Scan inbox_root for valid datasource subdirectories.

    Always includes 'general' for files in the root inbox directory.
    """
    datasources = ["general"]
    if inbox_root.exists():
        for sub in sorted(inbox_root.iterdir()):
            if sub.is_dir() and validate_datasource_name(sub.name):
                datasources.append(sub.name)
    return datasources


async def watch_datasource(
    datasource: str,
    folder: Path,
    agent,
    db_dir: str,
    poll_interval: int = 5,
) -> None:
    """Poll a single datasource inbox directory for new files every poll_interval seconds."""
    folder.mkdir(parents=True, exist_ok=True)
    log.info(f"Watching datasource '{datasource}': {folder}/")

    while True:
        try:
            db = get_db(datasource)
            for f in sorted(folder.iterdir()):
                if f.name.startswith("."):
                    continue
                suffix = f.suffix.lower()
                if suffix not in ALL_SUPPORTED:
                    continue

                mtime = f.stat().st_mtime
                row = db.execute(
                    "SELECT processed_at, file_mtime FROM processed_files WHERE path = ?",
                    (str(f),),
                ).fetchone()
                is_update = False
                if row:
                    stored_mtime = row[1]
                    if stored_mtime is not None and mtime <= stored_mtime:
                        continue
                    is_update = True
                    log.info(f"File modified since last ingestion [{datasource}]: {f.name}")

                source_file = str(f)

                if is_update:
                    db.execute("DELETE FROM processed_files WHERE path = ?", (str(f),))
                    deleted = db.execute(
                        "DELETE FROM memories WHERE source_file = ?", (source_file,)
                    ).rowcount
                    db.commit()
                    log.info(f"Replaced {deleted} old memory/memories for {f.name} [{datasource}]")

                stats_before = get_memory_stats(datasource)
                count_before = stats_before["total_memories"]

                try:
                    if suffix in TEXT_EXTENSIONS:
                        log.info(f"New text file [{datasource}]: {f.name}")
                        text = f.read_text(encoding="utf-8", errors="replace")[:10000]
                        if text.strip():
                            await agent.ingest(text, source=f.name, datasource=datasource)
                    else:
                        log.info(f"New media file [{datasource}]: {f.name}")
                        await agent.ingest_file(f, datasource=datasource)

                    stats_after = get_memory_stats(datasource)
                    if stats_after["total_memories"] <= count_before:
                        log.warning(
                            f"No memory stored after ingesting {f.name} [{datasource}], "
                            "will retry on next cycle"
                        )
                        continue

                    db.execute(
                        "INSERT INTO processed_files (path, processed_at, file_mtime) "
                        "VALUES (?, ?, ?)",
                        (str(f), datetime.now(timezone.utc).isoformat(), mtime),
                    )
                    db.execute(
                        "UPDATE memories SET source_file = ? "
                        "WHERE source = ? AND source_file IS NULL",
                        (source_file, f.name),
                    )
                    db.commit()
                except Exception as file_err:
                    log.error(f"Error ingesting {f.name} [{datasource}]: {file_err}")
            db.close()
        except Exception as e:
            log.error(f"Watch error [{datasource}]: {e}")

        await asyncio.sleep(poll_interval)


async def watcher_manager(
    agent,
    inbox_root: Path,
    db_dir: str,
    poll_interval: int = 30,
) -> None:
    """Re-scan datasources every poll_interval seconds and manage per-datasource watcher tasks.

    Cancels tasks for removed datasources and starts tasks for new ones.
    """
    active_tasks: dict[str, asyncio.Task] = {}

    while True:
        current = set(await discover_datasources(inbox_root))

        # Cancel tasks for datasources that no longer exist
        for ds in list(active_tasks):
            if ds not in current:
                active_tasks[ds].cancel()
                del active_tasks[ds]
                log.info(f"Stopped watcher for removed datasource '{ds}'")

        # Start tasks for new or dead datasources
        for ds in current:
            if ds not in active_tasks or active_tasks[ds].done():
                folder = inbox_root if ds == "general" else inbox_root / ds
                active_tasks[ds] = asyncio.create_task(
                    watch_datasource(ds, folder, agent, db_dir)
                )

        await asyncio.sleep(poll_interval)


async def consolidation_loop(
    agent,
    inbox_root: Path,
    interval_minutes: int = 30,
) -> None:
    """Run per-datasource consolidation on a timer."""
    log.info(f"Consolidation loop: every {interval_minutes} minutes")
    while True:
        await asyncio.sleep(interval_minutes * 60)
        try:
            for datasource in await discover_datasources(inbox_root):
                try:
                    stats = get_memory_stats(datasource)
                    count = stats["unconsolidated"]
                    if count >= 2:
                        log.info(f"Consolidating [{datasource}] ({count} unconsolidated memories)...")
                        result = await agent.consolidate(datasource=datasource)
                        log.info(f"Consolidation done [{datasource}]: {result[:100]}")
                    else:
                        log.info(f"Skipping consolidation [{datasource}] ({count} unconsolidated)")
                except Exception as e:
                    log.error(f"Consolidation error [{datasource}]: {e}")
        except Exception as e:
            log.error(f"Consolidation loop error: {e}")
