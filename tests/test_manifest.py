"""Tests for inbox.manifest — .memento-state.json read/write and helpers."""

import json
from pathlib import Path

import pytest

from inbox.manifest import (
    MANIFEST_FILENAME,
    Manifest,
    compute_hash,
    is_processed,
    load_manifest,
    record_file,
    remove_file,
    save_manifest,
    update_last_regen,
)


# ── Fixtures ─────────────────────────────────────────────────────


@pytest.fixture
def silo(tmp_path: Path) -> Path:
    """A temporary silo directory."""
    d = tmp_path / "silo"
    d.mkdir()
    return d


@pytest.fixture
def sample_file(tmp_path: Path) -> Path:
    """A small text file for hashing tests."""
    p = tmp_path / "sample.txt"
    p.write_text("hello world")
    return p


# ── Empty / missing manifest ────────────────────────────────────


def test_load_missing_returns_empty(silo: Path):
    m = load_manifest(silo)
    assert m.version == 1
    assert m.files == {}
    assert m.last_index_regen is None


# ── Round-trip read/write ────────────────────────────────────────


def test_round_trip(silo: Path):
    m = Manifest()
    record_file(m, "notes.md", source="notes.pdf", content_hash="sha256:aaa")
    save_manifest(silo, m)

    loaded = load_manifest(silo)
    assert loaded.version == 1
    assert "notes.md" in loaded.files
    entry = loaded.files["notes.md"]
    assert entry.source == "notes.pdf"
    assert entry.content_hash == "sha256:aaa"
    assert entry.ingested_at  # non-empty timestamp


def test_round_trip_preserves_last_regen(silo: Path):
    m = Manifest()
    update_last_regen(m)
    save_manifest(silo, m)

    loaded = load_manifest(silo)
    assert loaded.last_index_regen == m.last_index_regen


# ── Atomic save ──────────────────────────────────────────────────


def test_atomic_save_no_tmp_left(silo: Path):
    m = Manifest()
    save_manifest(silo, m)

    assert (silo / MANIFEST_FILENAME).exists()
    assert not (silo / f"{MANIFEST_FILENAME}.tmp").exists()


def test_atomic_save_produces_valid_json(silo: Path):
    m = Manifest()
    record_file(m, "a.txt", source="a.txt", content_hash="sha256:bbb")
    save_manifest(silo, m)

    raw = (silo / MANIFEST_FILENAME).read_text(encoding="utf-8")
    data = json.loads(raw)
    assert data["version"] == 1
    assert "a.txt" in data["files"]


# ── record / remove / is_processed ──────────────────────────────


def test_record_and_is_processed():
    m = Manifest()
    assert not is_processed(m, "file.md")

    record_file(m, "file.md", source="file.pdf", content_hash="sha256:ccc")
    assert is_processed(m, "file.md")
    assert m.files["file.md"].source == "file.pdf"


def test_remove_file():
    m = Manifest()
    record_file(m, "file.md", source="file.pdf", content_hash="sha256:ddd")
    assert is_processed(m, "file.md")

    remove_file(m, "file.md")
    assert not is_processed(m, "file.md")


def test_remove_nonexistent_is_noop():
    m = Manifest()
    remove_file(m, "ghost.md")
    assert m.files == {}


# ── update_last_regen ────────────────────────────────────────────


def test_update_last_regen():
    m = Manifest()
    assert m.last_index_regen is None

    update_last_regen(m)
    assert m.last_index_regen is not None
    assert m.last_index_regen.endswith("+00:00")


# ── compute_hash ─────────────────────────────────────────────────


def test_compute_hash_prefix(sample_file: Path):
    h = compute_hash(sample_file)
    assert h.startswith("sha256:")


def test_compute_hash_deterministic(sample_file: Path):
    assert compute_hash(sample_file) == compute_hash(sample_file)


def test_compute_hash_changes_with_content(tmp_path: Path):
    a = tmp_path / "a.txt"
    b = tmp_path / "b.txt"
    a.write_text("alpha")
    b.write_text("beta")
    assert compute_hash(a) != compute_hash(b)


def test_compute_hash_known_value(tmp_path: Path):
    """Verify against a known SHA-256 digest."""
    import hashlib
    p = tmp_path / "known.txt"
    content = b"deterministic"
    p.write_bytes(content)
    expected = f"sha256:{hashlib.sha256(content).hexdigest()}"
    assert compute_hash(p) == expected
