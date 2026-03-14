"""Tests for inbox.watcher — file watching, debouncing, and batch processing."""

from __future__ import annotations

import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from inbox.config import Config
from inbox.manifest import Manifest, record_file
from inbox.watcher import (
    IGNORED_NAMES,
    DebouncedQueue,
    RetryQueue,
    SiloHandler,
    process_batch,
    scan_pending,
    should_ignore,
)


# ── Fixtures ─────────────────────────────────────────────────────


@pytest.fixture
def config() -> Config:
    return Config(
        model="test-model",
        google_api_key=None,
        anthropic_api_key=None,
        openai_api_base=None,
        openai_api_key="not-needed",
        max_file_size=5_242_880,
    )


@pytest.fixture
def silo(tmp_path: Path) -> Path:
    d = tmp_path / "silo"
    d.mkdir()
    return d


# ── should_ignore ────────────────────────────────────────────────


class TestShouldIgnore:

    def test_agents_md(self):
        assert should_ignore(Path("inbox/AGENTS.md"))

    def test_memento_state(self):
        assert should_ignore(Path("inbox/.memento-state.json"))

    def test_dotfile(self):
        assert should_ignore(Path("inbox/.hidden"))

    def test_dotdir_parent(self):
        assert should_ignore(Path(".git/config"))

    def test_nested_dotdir(self):
        assert should_ignore(Path("inbox/.obsidian/plugins.json"))

    def test_pycache(self):
        assert should_ignore(Path("inbox/__pycache__/module.pyc"))

    def test_normal_file_not_ignored(self):
        assert not should_ignore(Path("inbox/notes.txt"))

    def test_nested_normal_file(self):
        assert not should_ignore(Path("inbox/research/papers/review.md"))

    def test_ignored_names_contains_expected_entries(self):
        assert "AGENTS.md" in IGNORED_NAMES
        assert ".memento-state.json" in IGNORED_NAMES


# ── DebouncedQueue ───────────────────────────────────────────────


class TestDebouncedQueue:

    def test_empty_returns_none(self):
        q = DebouncedQueue(delay=0.1)
        assert q.get_batch() is None

    def test_returns_none_before_delay(self):
        q = DebouncedQueue(delay=10.0)
        q.add(Path("a.txt"))
        assert q.get_batch() is None

    def test_returns_batch_after_delay(self):
        q = DebouncedQueue(delay=0.05)
        q.add(Path("a.txt"))
        q.add(Path("b.txt"))
        time.sleep(0.1)
        batch = q.get_batch()
        assert batch == {Path("a.txt"), Path("b.txt")}

    def test_batch_clears_pending(self):
        q = DebouncedQueue(delay=0.05)
        q.add(Path("a.txt"))
        time.sleep(0.1)
        q.get_batch()
        assert q.get_batch() is None

    def test_deduplicates(self):
        q = DebouncedQueue(delay=0.05)
        q.add(Path("a.txt"))
        q.add(Path("a.txt"))
        time.sleep(0.1)
        batch = q.get_batch()
        assert batch == {Path("a.txt")}

    def test_add_resets_timer(self):
        q = DebouncedQueue(delay=0.1)
        q.add(Path("a.txt"))
        time.sleep(0.06)
        q.add(Path("b.txt"))
        # Only 0.06s since last add, should still be pending
        assert q.get_batch() is None


# ── RetryQueue ───────────────────────────────────────────────────


class TestRetryQueue:

    def test_initially_empty(self):
        rq = RetryQueue()
        assert rq.is_empty()

    def test_add_makes_non_empty(self):
        rq = RetryQueue()
        rq.add(Path("fail.txt"))
        assert not rq.is_empty()

    def test_get_pending_returns_and_clears(self):
        rq = RetryQueue()
        rq.add(Path("a.txt"))
        rq.add(Path("b.txt"))
        pending = rq.get_pending()
        assert pending == [Path("a.txt"), Path("b.txt")]
        assert rq.is_empty()

    def test_get_pending_empty(self):
        rq = RetryQueue()
        assert rq.get_pending() == []


# ── scan_pending ─────────────────────────────────────────────────


class TestScanPending:

    def test_finds_unprocessed_files(self, silo: Path):
        (silo / "notes.txt").write_text("content")
        (silo / "readme.md").write_text("content")
        manifest = Manifest()
        pending = scan_pending(silo, manifest)
        names = {p.name for p in pending}
        assert "notes.txt" in names
        assert "readme.md" in names

    def test_skips_processed_files(self, silo: Path):
        (silo / "done.md").write_text("content")
        manifest = Manifest()
        record_file(manifest, "done.md", source="done.txt", content_hash="sha256:abc")
        pending = scan_pending(silo, manifest)
        assert not any(p.name == "done.md" for p in pending)

    def test_skips_ignored_files(self, silo: Path):
        (silo / "AGENTS.md").write_text("index")
        (silo / ".hidden").write_text("secret")
        manifest = Manifest()
        assert scan_pending(silo, manifest) == []

    def test_skips_non_md_with_processed_md_counterpart(self, silo: Path):
        (silo / "report.pdf").write_bytes(b"%PDF-1.4")
        manifest = Manifest()
        record_file(manifest, "report.md", source="report.pdf", content_hash="sha256:abc")
        pending = scan_pending(silo, manifest)
        assert not any(p.name == "report.pdf" for p in pending)

    def test_recursive_scan(self, silo: Path):
        sub = silo / "sub"
        sub.mkdir()
        (sub / "deep.txt").write_text("deep content")
        manifest = Manifest()
        pending = scan_pending(silo, manifest)
        assert any(p.name == "deep.txt" for p in pending)

    def test_empty_directory(self, silo: Path):
        manifest = Manifest()
        assert scan_pending(silo, manifest) == []


# ── process_batch ────────────────────────────────────────────────


class TestProcessBatch:

    @patch("inbox.watcher.index.regenerate_index")
    @patch("inbox.watcher.ingest.ingest_file")
    def test_calls_ingest_and_regenerate(self, mock_ingest, mock_regen, silo: Path, config: Config):
        files = {silo / "a.txt", silo / "b.txt"}
        manifest = Manifest()
        retry_queue = RetryQueue()

        process_batch(files, silo, manifest, config, retry_queue)

        assert mock_ingest.call_count == 2
        mock_regen.assert_called_once_with(silo, manifest, config)
        assert retry_queue.is_empty()

    @patch("inbox.watcher.index.regenerate_index")
    @patch("inbox.watcher.ingest.ingest_file", side_effect=RuntimeError("LLM down"))
    def test_failed_files_go_to_retry_queue(self, mock_ingest, mock_regen, silo: Path, config: Config):
        files = {silo / "fail.txt"}
        manifest = Manifest()
        retry_queue = RetryQueue()

        process_batch(files, silo, manifest, config, retry_queue)

        assert not retry_queue.is_empty()
        pending = retry_queue.get_pending()
        assert len(pending) == 1
        assert pending[0].name == "fail.txt"
        # regenerate_index is still called after all attempts
        mock_regen.assert_called_once()

    @patch("inbox.watcher.index.regenerate_index")
    @patch("inbox.watcher.ingest.ingest_file")
    def test_partial_failure(self, mock_ingest, mock_regen, silo: Path, config: Config):
        ok_file = silo / "ok.txt"
        bad_file = silo / "bad.txt"
        mock_ingest.side_effect = lambda fp, *a, **kw: (
            (_ for _ in ()).throw(RuntimeError("boom")) if fp == bad_file else True
        )

        manifest = Manifest()
        retry_queue = RetryQueue()
        process_batch({ok_file, bad_file}, silo, manifest, config, retry_queue)

        retry_names = [p.name for p in retry_queue.get_pending()]
        assert "bad.txt" in retry_names
        mock_regen.assert_called_once()


# ── SiloHandler ──────────────────────────────────────────────────


class TestSiloHandler:

    def _make_handler(self, silo: Path, config: Config, manifest: Manifest | None = None) -> SiloHandler:
        manifest = manifest or Manifest()
        queue = DebouncedQueue()
        return SiloHandler(silo, queue, manifest, config)

    def test_on_created_adds_to_queue(self, silo: Path, config: Config):
        handler = self._make_handler(silo, config)
        event = MagicMock()
        event.is_directory = False
        event.src_path = str(silo / "new.txt")

        handler.on_created(event)

        # Wait for debounce
        time.sleep(0.01)
        # Verify file was added (force batch)
        handler.debounced_queue._delay = 0
        batch = handler.debounced_queue.get_batch()
        assert batch is not None
        assert Path(str(silo / "new.txt")) in batch

    def test_on_created_ignores_directories(self, silo: Path, config: Config):
        handler = self._make_handler(silo, config)
        event = MagicMock()
        event.is_directory = True
        event.src_path = str(silo / "subdir")

        handler.on_created(event)

        handler.debounced_queue._delay = 0
        assert handler.debounced_queue.get_batch() is None

    def test_on_created_ignores_dotfiles(self, silo: Path, config: Config):
        handler = self._make_handler(silo, config)
        event = MagicMock()
        event.is_directory = False
        event.src_path = str(silo / ".hidden")

        handler.on_created(event)

        handler.debounced_queue._delay = 0
        assert handler.debounced_queue.get_batch() is None

    def test_on_modified_skips_processed(self, silo: Path, config: Config):
        manifest = Manifest()
        record_file(manifest, "existing.md", source="existing.txt", content_hash="sha256:abc")
        handler = self._make_handler(silo, config, manifest)

        event = MagicMock()
        event.is_directory = False
        event.src_path = str(silo / "existing.md")

        handler.on_modified(event)

        handler.debounced_queue._delay = 0
        assert handler.debounced_queue.get_batch() is None

    def test_on_modified_adds_unprocessed(self, silo: Path, config: Config):
        handler = self._make_handler(silo, config)
        event = MagicMock()
        event.is_directory = False
        event.src_path = str(silo / "new.txt")

        handler.on_modified(event)

        handler.debounced_queue._delay = 0
        batch = handler.debounced_queue.get_batch()
        assert batch is not None

    def test_on_deleted_removes_from_manifest(self, silo: Path, config: Config):
        manifest = Manifest()
        record_file(manifest, "gone.md", source="gone.txt", content_hash="sha256:abc")
        handler = self._make_handler(silo, config, manifest)

        event = MagicMock()
        event.is_directory = False
        event.src_path = str(silo / "gone.md")

        with patch("inbox.watcher.save_manifest") as mock_save:
            handler.on_deleted(event)

        assert "gone.md" not in manifest.files
        assert handler.needs_regen
        mock_save.assert_called_once_with(silo, manifest)

    def test_on_deleted_ignores_untracked(self, silo: Path, config: Config):
        handler = self._make_handler(silo, config)
        event = MagicMock()
        event.is_directory = False
        event.src_path = str(silo / "unknown.txt")

        handler.on_deleted(event)

        assert not handler.needs_regen

    def test_on_deleted_ignores_directories(self, silo: Path, config: Config):
        handler = self._make_handler(silo, config)
        event = MagicMock()
        event.is_directory = True
        event.src_path = str(silo / "subdir")

        handler.on_deleted(event)

        assert not handler.needs_regen
