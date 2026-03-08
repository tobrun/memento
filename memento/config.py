"""Configuration — environment variable loading and argument parsing."""

import argparse
import os

from dotenv import load_dotenv

load_dotenv()

# ─── Environment variables ──────────────────────────────────────

MODEL_NAME: str = os.getenv("MODEL", "gemini-3.1-flash-lite-preview")
OPENAI_API_BASE: str | None = os.getenv("OPENAI_API_BASE")
OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "not-needed")
MEMORY_DB_DIR: str = os.getenv("MEMORY_DB", "./databases")
WATCH_DIR: str = os.getenv("WATCH_DIR", "./inbox")
PORT: int = int(os.getenv("PORT", "8888"))
MCP_PORT: int = int(os.getenv("MCP_PORT", "8889"))

# ─── Model initialisation ───────────────────────────────────────


def build_model():
    """Return a LiteLlm model object or a plain model name string.

    Uses LiteLlm when OPENAI_API_BASE is configured, otherwise returns the
    model name directly for use with Google ADK's native Gemini support.
    """
    if OPENAI_API_BASE:
        from google.adk.models.lite_llm import LiteLlm
        return LiteLlm(
            model=f"openai/{MODEL_NAME}",
            api_base=OPENAI_API_BASE,
            api_key=OPENAI_API_KEY,
        )
    return MODEL_NAME


# ─── Argument parsing ───────────────────────────────────────────


def parse_args(argv=None) -> argparse.Namespace:
    """Parse CLI arguments with environment variable defaults."""
    parser = argparse.ArgumentParser(description="Memento — Always-On Memory Agent")
    parser.add_argument(
        "--watch",
        default=WATCH_DIR,
        help=f"Root inbox directory to watch (default: {WATCH_DIR})",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=PORT,
        help=f"HTTP API port (default: {PORT})",
    )
    parser.add_argument(
        "--mcp-port",
        type=int,
        default=MCP_PORT,
        help=f"MCP server port (default: {MCP_PORT})",
    )
    parser.add_argument(
        "--consolidate-every",
        type=int,
        default=30,
        help="Consolidation interval in minutes (default: 30)",
    )
    parser.add_argument(
        "--db-dir",
        default=MEMORY_DB_DIR,
        help=f"Directory for datasource SQLite databases (default: {MEMORY_DB_DIR})",
    )
    return parser.parse_args(argv)
