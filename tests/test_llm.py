"""Tests for inbox.llm — prompt building, response parsing, and LLM calls."""

from unittest.mock import MagicMock, patch

import pytest

from inbox.config import Config
from inbox.llm import (
    build_index_prompt,
    build_ingestion_prompt,
    call_llm,
    parse_index_response,
    parse_ingestion_response,
)

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

SAMPLE_CONFIG_GEMINI = Config(
    model="gemini-2.0-flash-lite",
    google_api_key="gemini-key-123",
    anthropic_api_key=None,
    openai_api_base=None,
    openai_api_key="not-needed",
    max_file_size=5_242_880,
)

VALID_LLM_RESPONSE = """\
---
title: Project Architecture
tags:
  - architecture
  - design
category: engineering
entities:
  - Memento
  - SQLite
importance: 7
content_type: reference
summary: Overview of the project architecture and key components.
---

## Architecture

The system uses a modular design with three main layers.

### Database Layer

SQLite handles persistence with per-datasource isolation.
"""

FENCED_LLM_RESPONSE = """\
```markdown
---
title: Fenced Response
tags:
  - test
category: testing
entities: []
importance: 3
content_type: notes
summary: A response wrapped in code fences.
---

Some body content here.
```"""


# ---------------------------------------------------------------------------
# build_ingestion_prompt
# ---------------------------------------------------------------------------


class TestBuildIngestionPrompt:
    def test_contains_filename(self):
        prompt = build_ingestion_prompt("hello", "notes.txt", is_markdown=False)
        assert "notes.txt" in prompt

    def test_contains_source_content(self):
        prompt = build_ingestion_prompt("my unique content", "f.txt", is_markdown=False)
        assert "my unique content" in prompt

    def test_contains_required_frontmatter_fields(self):
        prompt = build_ingestion_prompt("x", "f.txt", is_markdown=False)
        for field in ("title", "tags", "category", "entities", "importance", "content_type", "summary"):
            assert field in prompt

    def test_excludes_code_injected_fields(self):
        prompt = build_ingestion_prompt("x", "f.txt", is_markdown=False)
        assert "Do NOT include date_ingested or source" in prompt

    def test_preserve_code_blocks_instruction(self):
        prompt = build_ingestion_prompt("x", "f.txt", is_markdown=False)
        assert "PRESERVE code blocks" in prompt

    def test_markdown_merge_instruction(self):
        prompt = build_ingestion_prompt("x", "readme.md", is_markdown=True)
        assert "existing frontmatter" in prompt
        assert "merge" in prompt.lower()

    def test_non_markdown_no_merge_instruction(self):
        prompt = build_ingestion_prompt("x", "notes.txt", is_markdown=False)
        assert "existing frontmatter" not in prompt

    def test_content_type_options(self):
        prompt = build_ingestion_prompt("x", "f.txt", is_markdown=False)
        for ct in ("reference", "tutorial", "guide", "notes", "log", "config", "spec", "report"):
            assert ct in prompt


# ---------------------------------------------------------------------------
# build_index_prompt
# ---------------------------------------------------------------------------


class TestBuildIndexPrompt:
    def test_contains_silo_name(self):
        prompt = build_index_prompt([], "my-project")
        assert "Knowledge Base: my-project" in prompt

    def test_contains_section_names(self):
        prompt = build_index_prompt([], "test")
        assert "How to use" in prompt
        assert "Contents" in prompt

    def test_budget_instruction(self):
        prompt = build_index_prompt([], "test")
        assert "150 lines" in prompt

    def test_consolidate_not_evict(self):
        prompt = build_index_prompt([], "test")
        assert "consolidate" in prompt.lower()
        assert "Never evict" in prompt

    def test_includes_frontmatter_data(self):
        entries = [{"title": "Unique Entry Alpha", "tags": ["alpha"], "importance": 5}]
        prompt = build_index_prompt(entries, "test")
        assert "Unique Entry Alpha" in prompt

    def test_no_code_fence_instruction(self):
        prompt = build_index_prompt([], "test")
        assert "Do NOT wrap the output in a markdown code fence" in prompt


# ---------------------------------------------------------------------------
# parse_ingestion_response
# ---------------------------------------------------------------------------


class TestParseIngestionResponse:
    def test_valid_response(self):
        fm, body = parse_ingestion_response(VALID_LLM_RESPONSE)
        assert fm["title"] == "Project Architecture"
        assert "architecture" in fm["tags"]
        assert fm["category"] == "engineering"
        assert fm["importance"] == 7
        assert fm["content_type"] == "reference"
        assert "SQLite" in fm["entities"]
        assert "summary" in fm
        assert "## Architecture" in body
        assert "SQLite handles persistence" in body

    def test_fenced_response(self):
        fm, body = parse_ingestion_response(FENCED_LLM_RESPONSE)
        assert fm["title"] == "Fenced Response"
        assert fm["category"] == "testing"
        assert "Some body content here." in body

    def test_no_frontmatter(self):
        fm, body = parse_ingestion_response("Just plain text without frontmatter.")
        assert fm == {}
        assert "plain text" in body

    def test_empty_frontmatter(self):
        fm, body = parse_ingestion_response("---\n---\nBody only.")
        assert fm == {}
        assert body == "Body only."

    def test_invalid_yaml_frontmatter(self):
        response = "---\n: [invalid yaml\n---\nBody here."
        fm, body = parse_ingestion_response(response)
        assert fm == {}
        assert "Body here." in body


# ---------------------------------------------------------------------------
# parse_index_response
# ---------------------------------------------------------------------------


class TestParseIndexResponse:
    def test_clean_response(self):
        raw = "# Knowledge Base: test\n\n## How to use\n\nQuery the base."
        result = parse_index_response(raw)
        assert result == raw

    def test_fenced_response(self):
        raw = "```markdown\n# Knowledge Base: test\n\nContent here.\n```"
        result = parse_index_response(raw)
        assert result == "# Knowledge Base: test\n\nContent here."

    def test_strips_whitespace(self):
        raw = "\n\n  # Title  \n\n"
        result = parse_index_response(raw)
        assert result == "# Title"


# ---------------------------------------------------------------------------
# call_llm
# ---------------------------------------------------------------------------


class TestCallLlm:
    @patch("inbox.llm.litellm")
    def test_openai_compatible_endpoint(self, mock_litellm):
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "LLM says hello"
        mock_litellm.completion.return_value = mock_response

        result = call_llm("test prompt", SAMPLE_CONFIG)

        assert result == "LLM says hello"
        mock_litellm.completion.assert_called_once_with(
            model="test-model",
            messages=[{"role": "user", "content": "test prompt"}],
            api_base="http://localhost:11434/v1",
            api_key="test-key",
        )

    @patch("inbox.llm.litellm")
    @patch.dict("os.environ", {}, clear=False)
    def test_gemini_sets_env_var(self, mock_litellm):
        import os

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "gemini response"
        mock_litellm.completion.return_value = mock_response

        result = call_llm("test prompt", SAMPLE_CONFIG_GEMINI)

        assert result == "gemini response"
        assert os.environ.get("GEMINI_API_KEY") == "gemini-key-123"
        mock_litellm.completion.assert_called_once_with(
            model="gemini-2.0-flash-lite",
            messages=[{"role": "user", "content": "test prompt"}],
        )

    @patch("inbox.llm.litellm")
    def test_raises_on_failure(self, mock_litellm):
        mock_litellm.completion.side_effect = RuntimeError("API down")

        with pytest.raises(RuntimeError, match="API down"):
            call_llm("test prompt", SAMPLE_CONFIG)
