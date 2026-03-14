"""Tests for inbox.__main__ — CLI entry point."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from inbox.__main__ import cli
from inbox.manifest import FileEntry, Manifest, save_manifest


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def silo(tmp_path: Path) -> Path:
    d = tmp_path / "silo"
    d.mkdir()
    return d


# ── Help output ──────────────────────────────────────────────────


class TestHelp:

    def test_main_help_shows_subcommands(self, runner: CliRunner):
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "watch" in result.output
        assert "ingest" in result.output
        assert "status" in result.output
        assert "reindex" in result.output

    def test_watch_help_shows_dirs_argument(self, runner: CliRunner):
        result = runner.invoke(cli, ["watch", "--help"])
        assert result.exit_code == 0
        assert "DIRS" in result.output


# ── status ───────────────────────────────────────────────────────


class TestStatus:

    def test_empty_directory_shows_zeros(self, runner: CliRunner, silo: Path):
        result = runner.invoke(cli, ["status", str(silo)])
        assert result.exit_code == 0
        assert "Processed files: 0" in result.output
        assert "Pending files:   0" in result.output
        assert "AGENTS.md lines: 0" in result.output
        assert "Last index regen: never" in result.output

    def test_shows_correct_counts_with_manifest(self, runner: CliRunner, silo: Path):
        manifest = Manifest()
        manifest.files["doc-a.md"] = FileEntry(
            source="doc-a.txt", ingested_at="2026-03-14T00:00:00Z", content_hash="sha256:aaa",
        )
        manifest.files["doc-b.md"] = FileEntry(
            source="doc-b.txt", ingested_at="2026-03-14T00:00:01Z", content_hash="sha256:bbb",
        )
        manifest.last_index_regen = "2026-03-14T00:00:02Z"
        save_manifest(silo, manifest)

        # Create the tracked files so they are not considered pending
        (silo / "doc-a.md").write_text("---\ntitle: A\n---\nbody")
        (silo / "doc-b.md").write_text("---\ntitle: B\n---\nbody")

        # Create AGENTS.md with known line count
        (silo / "AGENTS.md").write_text("line1\nline2\nline3\n")

        result = runner.invoke(cli, ["status", str(silo)])
        assert result.exit_code == 0
        assert "Processed files: 2" in result.output
        assert "Pending files:   0" in result.output
        assert "AGENTS.md lines: 3" in result.output
        assert "2026-03-14T00:00:02Z" in result.output

    def test_counts_pending_files(self, runner: CliRunner, silo: Path):
        (silo / "unprocessed.txt").write_text("new content")

        result = runner.invoke(cli, ["status", str(silo)])
        assert result.exit_code == 0
        assert "Pending files:   1" in result.output


# ── ingest ───────────────────────────────────────────────────────


class TestIngest:

    @patch("inbox.__main__.save_manifest")
    @patch("inbox.index.regenerate_index")
    @patch("inbox.ingest.ingest_file", return_value=True)
    def test_ingests_pending_files(
        self, mock_ingest: MagicMock, mock_regen: MagicMock, mock_save: MagicMock,
        runner: CliRunner, silo: Path,
    ):
        (silo / "notes.txt").write_text("some notes")
        (silo / "readme.md").write_text("readme content")

        result = runner.invoke(cli, ["ingest", str(silo)])
        assert result.exit_code == 0
        assert mock_ingest.call_count == 2
        mock_regen.assert_called_once()
        assert "2 files ingested" in result.output

    @patch("inbox.__main__.save_manifest")
    @patch("inbox.index.regenerate_index")
    @patch("inbox.ingest.ingest_file", return_value=True)
    def test_singular_file_message(
        self, mock_ingest: MagicMock, mock_regen: MagicMock, mock_save: MagicMock,
        runner: CliRunner, silo: Path,
    ):
        (silo / "only.txt").write_text("solo")

        result = runner.invoke(cli, ["ingest", str(silo)])
        assert result.exit_code == 0
        assert "1 file ingested" in result.output

    @patch("inbox.__main__.save_manifest")
    @patch("inbox.index.regenerate_index")
    def test_no_pending_files(
        self, mock_regen: MagicMock, mock_save: MagicMock,
        runner: CliRunner, silo: Path,
    ):
        result = runner.invoke(cli, ["ingest", str(silo)])
        assert result.exit_code == 0
        assert "0 files ingested" in result.output


# ── reindex ──────────────────────────────────────────────────────


class TestReindex:

    @patch("inbox.index.regenerate_index")
    def test_calls_regenerate_index(self, mock_regen: MagicMock, runner: CliRunner, silo: Path):
        result = runner.invoke(cli, ["reindex", str(silo)])
        assert result.exit_code == 0
        mock_regen.assert_called_once()
        assert "AGENTS.md regenerated" in result.output

    @patch("inbox.index.regenerate_index")
    def test_passes_config_and_manifest(self, mock_regen: MagicMock, runner: CliRunner, silo: Path):
        result = runner.invoke(cli, ["--model", "custom-model", "reindex", str(silo)])
        assert result.exit_code == 0

        call_args = mock_regen.call_args
        config = call_args[0][2]
        assert config.model == "custom-model"
