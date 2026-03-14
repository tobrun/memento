"""Tests for inbox.index — AGENTS.md generation, frontmatter collection, and silo naming."""

from pathlib import Path
from unittest.mock import patch

import pytest

from inbox.config import Config
from inbox.index import AGENTS_MD, collect_frontmatters, extract_silo_name, regenerate_index
from inbox.manifest import Manifest, record_file, save_manifest

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_CONFIG = Config(
    model="test-model",
    google_api_key=None,
    anthropic_api_key=None,
    openai_api_base="http://localhost:11434/v1",
    openai_api_key="test-key",
    max_file_size=5_242_880,
)

LLM_INDEX_RESPONSE = """\
# Knowledge Base: research

## How to use

Files in this directory have YAML frontmatter with `tags`, `category`, `importance`, and `summary` fields.

Available categories: infrastructure
Common tags: kubernetes, scheduling

## Contents

### Infrastructure
- k8s-scheduling.md — Pod scheduling strategies (7)
"""


def _make_md_file(directory: Path, filename: str, frontmatter: dict, body: str = "") -> Path:
    """Write a markdown file with YAML frontmatter to *directory*."""
    import yaml

    path = directory / filename
    fm_block = yaml.dump(frontmatter, default_flow_style=False, sort_keys=False)
    path.write_text(f"---\n{fm_block}---\n{body}", encoding="utf-8")
    return path


@pytest.fixture
def silo(tmp_path: Path) -> Path:
    d = tmp_path / "research"
    d.mkdir()
    return d


@pytest.fixture
def populated_silo(silo: Path) -> tuple[Path, Manifest]:
    """Silo with two markdown files and a matching manifest."""
    _make_md_file(
        silo,
        "k8s-scheduling.md",
        {
            "title": "Kubernetes Pod Scheduling Strategies",
            "tags": ["kubernetes", "scheduling"],
            "category": "infrastructure",
            "importance": 7,
            "summary": "Overview of pod scheduling strategies.",
        },
        body="## Scheduling\n\nContent about scheduling.",
    )
    _make_md_file(
        silo,
        "terraform-modules.md",
        {
            "title": "Terraform Module Patterns",
            "tags": ["terraform", "aws"],
            "category": "infrastructure",
            "importance": 6,
            "summary": "Reusable module patterns for AWS.",
        },
        body="## Modules\n\nContent about modules.",
    )

    manifest = Manifest()
    record_file(manifest, "k8s-scheduling.md", source="k8s-scheduling.pdf", content_hash="sha256:aaa")
    record_file(manifest, "terraform-modules.md", source="terraform-modules.txt", content_hash="sha256:bbb")
    return silo, manifest


# ---------------------------------------------------------------------------
# extract_silo_name
# ---------------------------------------------------------------------------


class TestExtractSiloName:
    def test_simple_directory(self):
        assert extract_silo_name(Path("/home/user/inbox/research")) == "research"

    def test_nested_directory(self):
        assert extract_silo_name(Path("/a/b/c/my-project")) == "my-project"

    def test_single_component(self):
        assert extract_silo_name(Path("notes")) == "notes"


# ---------------------------------------------------------------------------
# collect_frontmatters
# ---------------------------------------------------------------------------


class TestCollectFrontmatters:
    def test_multiple_files(self, populated_silo: tuple[Path, Manifest]):
        silo_dir, manifest = populated_silo
        result = collect_frontmatters(silo_dir, manifest)

        assert len(result) == 2

        filenames = {fm["filename"] for fm in result}
        assert filenames == {"k8s-scheduling.md", "terraform-modules.md"}

        k8s = next(fm for fm in result if fm["filename"] == "k8s-scheduling.md")
        assert k8s["title"] == "Kubernetes Pod Scheduling Strategies"
        assert k8s["importance"] == 7
        assert "kubernetes" in k8s["tags"]

    def test_skips_stale_manifest_entries(self, silo: Path):
        _make_md_file(
            silo,
            "exists.md",
            {"title": "Present", "tags": ["a"], "category": "test", "importance": 5, "summary": "Here."},
        )
        manifest = Manifest()
        record_file(manifest, "exists.md", source="exists.txt", content_hash="sha256:aaa")
        record_file(manifest, "deleted.md", source="deleted.txt", content_hash="sha256:bbb")

        result = collect_frontmatters(silo, manifest)
        assert len(result) == 1
        assert result[0]["filename"] == "exists.md"

    def test_empty_manifest_returns_empty_list(self, silo: Path):
        result = collect_frontmatters(silo, Manifest())
        assert result == []

    def test_skips_file_without_frontmatter(self, silo: Path):
        (silo / "no-fm.md").write_text("Just plain text, no frontmatter.", encoding="utf-8")
        manifest = Manifest()
        record_file(manifest, "no-fm.md", source="no-fm.txt", content_hash="sha256:ccc")

        result = collect_frontmatters(silo, manifest)
        assert result == []

    def test_skips_file_with_empty_frontmatter(self, silo: Path):
        (silo / "empty-fm.md").write_text("---\n---\nBody only.", encoding="utf-8")
        manifest = Manifest()
        record_file(manifest, "empty-fm.md", source="empty-fm.txt", content_hash="sha256:ddd")

        result = collect_frontmatters(silo, manifest)
        assert result == []


# ---------------------------------------------------------------------------
# regenerate_index
# ---------------------------------------------------------------------------


class TestRegenerateIndex:
    @patch("inbox.index.llm")
    def test_end_to_end(self, mock_llm, populated_silo: tuple[Path, Manifest]):
        silo_dir, manifest = populated_silo
        mock_llm.call_llm.return_value = LLM_INDEX_RESPONSE
        mock_llm.build_index_prompt.return_value = "prompt"
        mock_llm.parse_index_response.return_value = LLM_INDEX_RESPONSE.strip()

        regenerate_index(silo_dir, manifest, SAMPLE_CONFIG)

        agents_path = silo_dir / AGENTS_MD
        assert agents_path.exists()
        content = agents_path.read_text(encoding="utf-8")
        assert "Knowledge Base: research" in content
        assert "k8s-scheduling.md" in content

    @patch("inbox.index.llm")
    def test_agents_md_written_correctly(self, mock_llm, populated_silo: tuple[Path, Manifest]):
        silo_dir, manifest = populated_silo
        expected_content = "# Knowledge Base: research\n\n## Contents\n\n- file.md"
        mock_llm.call_llm.return_value = expected_content
        mock_llm.build_index_prompt.return_value = "prompt"
        mock_llm.parse_index_response.return_value = expected_content

        regenerate_index(silo_dir, manifest, SAMPLE_CONFIG)

        written = (silo_dir / AGENTS_MD).read_text(encoding="utf-8")
        assert written == expected_content

    @patch("inbox.index.llm")
    def test_manifest_last_regen_updated(self, mock_llm, populated_silo: tuple[Path, Manifest]):
        silo_dir, manifest = populated_silo
        assert manifest.last_index_regen is None

        mock_llm.call_llm.return_value = "index content"
        mock_llm.build_index_prompt.return_value = "prompt"
        mock_llm.parse_index_response.return_value = "index content"

        regenerate_index(silo_dir, manifest, SAMPLE_CONFIG)

        assert manifest.last_index_regen is not None
        assert manifest.last_index_regen.endswith("+00:00")

    @patch("inbox.index.llm")
    def test_manifest_saved_after_regen(self, mock_llm, populated_silo: tuple[Path, Manifest]):
        silo_dir, manifest = populated_silo
        mock_llm.call_llm.return_value = "content"
        mock_llm.build_index_prompt.return_value = "prompt"
        mock_llm.parse_index_response.return_value = "content"

        regenerate_index(silo_dir, manifest, SAMPLE_CONFIG)

        from inbox.manifest import load_manifest

        loaded = load_manifest(silo_dir)
        assert loaded.last_index_regen is not None

    def test_empty_manifest_deletes_agents_md(self, silo: Path):
        agents_path = silo / AGENTS_MD
        agents_path.write_text("old index content", encoding="utf-8")
        assert agents_path.exists()

        regenerate_index(silo, Manifest(), SAMPLE_CONFIG)

        assert not agents_path.exists()

    def test_empty_manifest_no_agents_md_is_noop(self, silo: Path):
        agents_path = silo / AGENTS_MD
        assert not agents_path.exists()

        regenerate_index(silo, Manifest(), SAMPLE_CONFIG)

        assert not agents_path.exists()

    @patch("inbox.index.llm")
    def test_calls_llm_with_correct_args(self, mock_llm, populated_silo: tuple[Path, Manifest]):
        silo_dir, manifest = populated_silo
        mock_llm.call_llm.return_value = "resp"
        mock_llm.build_index_prompt.return_value = "the-prompt"
        mock_llm.parse_index_response.return_value = "resp"

        regenerate_index(silo_dir, manifest, SAMPLE_CONFIG)

        mock_llm.build_index_prompt.assert_called_once()
        call_args = mock_llm.build_index_prompt.call_args
        frontmatters_arg = call_args[0][0]
        silo_name_arg = call_args[0][1]

        assert len(frontmatters_arg) == 2
        assert silo_name_arg == "research"

        mock_llm.call_llm.assert_called_once_with("the-prompt", SAMPLE_CONFIG)
        mock_llm.parse_index_response.assert_called_once_with("resp")
