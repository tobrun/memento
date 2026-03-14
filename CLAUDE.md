# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install Python dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env   # then edit .env

# Watch directories for new files (long-running daemon)
inbox watch ./inbox

# Watch multiple directories
inbox watch ./inbox ./research ./notes

# One-shot: process all pending files, then exit
inbox ingest ./inbox

# Show manifest stats (total files, pending, last ingestion time)
inbox status ./inbox

# Force-regenerate AGENTS.md from all files' frontmatter
inbox reindex ./inbox

# Run tests
pytest tests/
```

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `MODEL` | `gemini-2.0-flash-lite` | LiteLLM model string. Any LiteLLM-compatible model works (Gemini, OpenAI, Anthropic, local via Ollama). |
| `GOOGLE_API_KEY` | -- | Required when using Gemini models. |
| `ANTHROPIC_API_KEY` | -- | Required when using Anthropic/Claude models. |
| `OPENAI_API_BASE` | -- | If set, uses an OpenAI-compatible endpoint via LiteLLM (e.g. `http://localhost:11434/v1`). `GOOGLE_API_KEY` is then not required. |
| `OPENAI_API_KEY` | `not-needed` | API key for the OpenAI-compatible endpoint. |
| `MAX_FILE_SIZE` | `5242880` (5 MB) | Skip files larger than this (bytes). |

CLI flags (`--model`, `--openai-api-base`, `--max-file-size`) override env vars. No config file.

## Architecture

The system is a Python package (`inbox/`) providing a CLI tool (`inbox`) that watches directories, ingests files through an LLM, and maintains an `AGENTS.md` index for consumption by AI coding tools.

### Modules

| Module | Purpose |
|---|---|
| `__main__.py` | Entry point, Click CLI group with `watch`, `ingest`, `status`, `reindex` subcommands |
| `config.py` | Env var loading, defaults, immutable `Config` dataclass. Resolution order: CLI override > env var > default |
| `llm.py` | LiteLLM wrapper, prompt templates (`build_ingestion_prompt`, `build_index_prompt`), response parsing |
| `ingest.py` | File reading (text + PDF via pymupdf4llm), LLM ingestion call, frontmatter merging, markdown output writing |
| `index.py` | AGENTS.md generation -- collects frontmatter from all processed files, sends to LLM, writes index |
| `manifest.py` | `.memento-state.json` read/write/update, file entry tracking, SHA-256 content hashing |
| `watcher.py` | Watchdog-based file watcher with debounced queue, batch processing, retry queue, deletion detection |

### How It Works

1. **File watching** -- uses the `watchdog` library with native OS event backends (inotify on Linux, FSEvents on macOS) and automatic polling fallback. The `watch` command starts a long-running observer.

2. **Debounced queue** -- file events are collected into a `DebouncedQueue`. After 2 seconds of inactivity (no new events), the batch is processed. This handles both single-file drops and bulk drops efficiently.

3. **Ingestion pipeline** (`ingest.py`) -- for each new file:
   - Size guard: skip files exceeding `MAX_FILE_SIZE`
   - Read content: text files read as UTF-8, PDFs converted via `pymupdf4llm`
   - Existing frontmatter: if the file is already markdown with YAML frontmatter, existing fields are preserved and merged
   - LLM call: restructures content into clean markdown with rich YAML frontmatter (title, tags, category, entities, importance, content_type, summary)
   - Deterministic fields (`date_ingested`, `source`) are injected by code, not the LLM
   - Output: original file is replaced with `.md` version; non-markdown originals are deleted
   - Manifest updated with file entry and content hash

4. **AGENTS.md generation** (`index.py`) -- after each ingestion batch, `regenerate_index` collects frontmatter from all processed files and sends it to the LLM to produce a categorized index. Capped at ~150 lines; the LLM consolidates by merging related entries when over budget.

5. **State tracking** -- each watched directory (silo) has a `.memento-state.json` manifest tracking all processed files, content hashes, and last index regeneration time. Files in the manifest are never re-ingested, even if edited (user edits are sacred).

6. **Deletion detection** -- when a file is removed, the watcher updates the manifest and triggers AGENTS.md regeneration.

7. **Retry logic** -- LLM failures place files in an in-memory retry queue. The daemon retries periodically. On restart, unprocessed files are re-detected since they were never added to the manifest.

### Inbox Silos

Each watched directory is an independent silo with its own `AGENTS.md` and `.memento-state.json`. Subdirectories within a silo are **not** separate silos -- they belong to the parent. When watching multiple directories, each is processed independently with no cross-pollination.

### Supported File Types

- **Text files**: `.txt`, `.md`, `.csv`, `.json`, `.html`, `.xml`, `.yaml`, `.yml`, `.toml`, `.rst`, `.log`, plus common source code extensions (`.py`, `.js`, `.ts`, `.go`, `.rs`, `.java`, `.c`, `.cpp`, `.sh`, `.sql`, etc.)
- **PDF files**: text extracted via pymupdf4llm
- All other binary formats are skipped

### Dependencies

| Package | Purpose |
|---|---|
| `litellm` | Multi-provider LLM completion calls |
| `watchdog` | Filesystem event monitoring |
| `pymupdf` / `pymupdf4llm` | PDF text extraction |
| `pyyaml` | YAML frontmatter parsing and writing |
| `click` | CLI framework |
