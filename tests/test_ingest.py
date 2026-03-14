"""Tests for inbox.ingest — file reading, markdown writing, and LLM ingestion pipeline."""

from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from inbox.config import load_config
from inbox.ingest import (
    SUPPORTED_TEXT_EXTENSIONS,
    ingest_file,
    is_supported_file,
    merge_frontmatter,
    parse_existing_frontmatter,
    read_file_content,
    write_markdown,
)
from inbox.manifest import Manifest


# ── Fixtures ─────────────────────────────────────────────────────


@pytest.fixture
def silo(tmp_path: Path) -> Path:
    d = tmp_path / "silo"
    d.mkdir()
    return d


@pytest.fixture
def config():
    return load_config(
        model="test-model",
        google_api_key="fake-key",
        max_file_size=5_242_880,
    )


LLM_RESPONSE = """\
---
title: Test Document
tags: [testing, unit]
category: testing
entities: [pytest]
importance: 5
content_type: notes
summary: A test document for unit tests.
---

This is the restructured body content."""


# ── read_file_content ────────────────────────────────────────────


def test_read_file_content_txt(tmp_path: Path):
    p = tmp_path / "hello.txt"
    p.write_text("hello world", encoding="utf-8")
    assert read_file_content(p) == "hello world"


def test_read_file_content_unsupported_binary(tmp_path: Path):
    p = tmp_path / "image.png"
    p.write_bytes(b"\x89PNG\r\n")
    with pytest.raises(ValueError, match="Unsupported file format"):
        read_file_content(p)


# ── write_markdown ───────────────────────────────────────────────


def test_write_markdown_format(tmp_path: Path):
    out = tmp_path / "output.md"
    fm = {"title": "Hello", "tags": ["a", "b"]}
    write_markdown(out, fm, "Body text here.")

    content = out.read_text(encoding="utf-8")
    assert content.startswith("---\n")
    assert content.endswith("Body text here.\n")

    # parse it back and verify frontmatter
    parts = content.split("---", 2)
    parsed_fm = yaml.safe_load(parts[1])
    assert parsed_fm["title"] == "Hello"
    assert parsed_fm["tags"] == ["a", "b"]

    body = parts[2].strip()
    assert body == "Body text here."


# ── merge_frontmatter ───────────────────────────────────────────


def test_merge_frontmatter_preserves_existing():
    existing = {"title": "My Title", "custom_field": "keep me"}
    generated = {"title": "LLM Title", "tags": ["new"], "category": "tech"}

    merged = merge_frontmatter(existing, generated)

    assert merged["title"] == "My Title"
    assert merged["custom_field"] == "keep me"
    assert merged["tags"] == ["new"]
    assert merged["category"] == "tech"


def test_merge_frontmatter_adds_new_fields():
    existing = {"title": "Original"}
    generated = {"importance": 7, "summary": "A summary."}

    merged = merge_frontmatter(existing, generated)

    assert merged["title"] == "Original"
    assert merged["importance"] == 7
    assert merged["summary"] == "A summary."


# ── parse_existing_frontmatter ───────────────────────────────────


def test_parse_existing_frontmatter_with_frontmatter():
    content = "---\ntitle: Hello\ntags: [a]\n---\n\nBody here."
    fm, body = parse_existing_frontmatter(content)

    assert fm is not None
    assert fm["title"] == "Hello"
    assert fm["tags"] == ["a"]
    assert body == "Body here."


def test_parse_existing_frontmatter_without_frontmatter():
    content = "Just plain text, no frontmatter."
    fm, body = parse_existing_frontmatter(content)

    assert fm is None
    assert body == content


def test_parse_existing_frontmatter_incomplete_delimiters():
    content = "---\ntitle: Broken\nNo closing delimiter."
    fm, body = parse_existing_frontmatter(content)

    assert fm is None
    assert body == content


# ── is_supported_file ────────────────────────────────────────────


def test_is_supported_file_text():
    assert is_supported_file(Path("notes.txt"))
    assert is_supported_file(Path("code.py"))
    assert is_supported_file(Path("data.json"))
    assert is_supported_file(Path("readme.md"))


def test_is_supported_file_pdf():
    assert is_supported_file(Path("doc.pdf"))
    assert is_supported_file(Path("DOC.PDF"))


def test_is_supported_file_unsupported():
    assert not is_supported_file(Path("photo.png"))
    assert not is_supported_file(Path("video.mp4"))
    assert not is_supported_file(Path("archive.zip"))


# ── ingest_file — end to end ─────────────────────────────────────


def test_ingest_file_success(silo: Path, config):
    src = silo / "notes.txt"
    src.write_text("Some raw notes about testing.", encoding="utf-8")
    manifest = Manifest()

    with patch("inbox.ingest.llm.call_llm", return_value=LLM_RESPONSE):
        result = ingest_file(src, silo, manifest, config)

    assert result is True

    # original .txt should be deleted, .md should exist
    assert not src.exists()
    md_path = silo / "notes.md"
    assert md_path.exists()

    # manifest should record the .md file
    assert "notes.md" in manifest.files
    assert manifest.files["notes.md"].source == "notes.txt"

    # verify written content
    content = md_path.read_text(encoding="utf-8")
    parts = content.split("---", 2)
    fm = yaml.safe_load(parts[1])
    assert fm["title"] == "Test Document"
    assert fm["source"] == "notes.txt"
    assert "date_ingested" in fm


def test_ingest_file_skips_large_files(silo: Path):
    src = silo / "big.txt"
    src.write_text("x" * 100, encoding="utf-8")

    small_config = load_config(
        model="test-model",
        google_api_key="fake-key",
        max_file_size=10,
    )
    manifest = Manifest()

    result = ingest_file(src, silo, manifest, small_config)

    assert result is False
    assert src.exists()
    assert "big.txt" not in manifest.files


def test_ingest_file_non_md_deleted_and_md_created(silo: Path, config):
    src = silo / "data.csv"
    src.write_text("col1,col2\n1,2\n", encoding="utf-8")
    manifest = Manifest()

    with patch("inbox.ingest.llm.call_llm", return_value=LLM_RESPONSE):
        result = ingest_file(src, silo, manifest, config)

    assert result is True
    assert not src.exists()
    assert (silo / "data.md").exists()
    assert "data.md" in manifest.files
    assert manifest.files["data.md"].source == "data.csv"


def test_ingest_file_md_preserves_existing_frontmatter(silo: Path, config):
    original_content = "---\ntitle: My Custom Title\ncustom: preserve_me\n---\n\nOriginal body."
    src = silo / "notes.md"
    src.write_text(original_content, encoding="utf-8")
    manifest = Manifest()

    with patch("inbox.ingest.llm.call_llm", return_value=LLM_RESPONSE):
        result = ingest_file(src, silo, manifest, config)

    assert result is True
    assert src.exists()

    content = src.read_text(encoding="utf-8")
    parts = content.split("---", 2)
    fm = yaml.safe_load(parts[1])

    # existing fields preserved
    assert fm["title"] == "My Custom Title"
    assert fm["custom"] == "preserve_me"
    # generated fields added
    assert fm["tags"] == ["testing", "unit"]
    assert fm["category"] == "testing"


def test_ingest_file_md_without_frontmatter(silo: Path, config):
    src = silo / "plain.md"
    src.write_text("Just plain markdown, no frontmatter.", encoding="utf-8")
    manifest = Manifest()

    with patch("inbox.ingest.llm.call_llm", return_value=LLM_RESPONSE):
        result = ingest_file(src, silo, manifest, config)

    assert result is True
    content = src.read_text(encoding="utf-8")
    parts = content.split("---", 2)
    fm = yaml.safe_load(parts[1])

    assert fm["title"] == "Test Document"
    assert fm["source"] == "plain.md"
