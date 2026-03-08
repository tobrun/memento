#!/usr/bin/env python3
"""
Memento MCP Server — Streamable HTTP transport

Exposes all datasources via query and list_datasources tools.

    python mcp_server.py --port 8889

MCP client configuration:
    {
      "mcpServers": {
        "memento": { "url": "http://localhost:8889/mcp" }
      }
    }
"""

import argparse
import os

import httpx
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

load_dotenv()

# ─── Configuration ──────────────────────────────────────────────

_DEFAULT_AGENT_URL = f"http://localhost:{os.getenv('PORT', '8888')}"
_DEFAULT_MCP_PORT = int(os.getenv("MCP_PORT", "8889"))


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Memento MCP Server")
    parser.add_argument(
        "--agent-url",
        default=_DEFAULT_AGENT_URL,
        help=f"Base URL of the Memento agent API (default: {_DEFAULT_AGENT_URL})",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=_DEFAULT_MCP_PORT,
        help=f"Port to listen on (default: {_DEFAULT_MCP_PORT})",
    )
    return parser.parse_args()


args = _parse_args()
AGENT_URL = args.agent_url.rstrip("/")

# ─── MCP Server ─────────────────────────────────────────────────

mcp = FastMCP(
    "memento",
    stateless_http=True,
    json_response=True,
    host="0.0.0.0",
    port=args.port,
)


@mcp.tool()
async def list_datasources() -> list[str]:
    """Return the names of all available datasources."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(f"{AGENT_URL}/api/datasources")
            response.raise_for_status()
            return [ds["name"] for ds in response.json()]
        except httpx.HTTPStatusError as e:
            raise RuntimeError(f"Agent API error: {e.response.status_code}") from e
        except httpx.RequestError as e:
            raise RuntimeError(f"Agent API unreachable: {e}") from e


@mcp.tool()
async def query(question: str, datasource: str) -> str:
    """Query memories within a named datasource.

    Args:
        question: Natural-language question to ask against stored memories.
        datasource: Datasource to query (e.g. "general", "news", "company").
                    Call list_datasources first if you are unsure which names exist.

    Returns:
        Answer synthesised from memories in the requested datasource.
    """
    async with httpx.AsyncClient(timeout=120.0) as client:
        try:
            response = await client.get(
                f"{AGENT_URL}/api/query/{datasource}",
                params={"q": question},
            )
            if response.status_code == 404:
                raise RuntimeError(f"Datasource '{datasource}' not found")
            response.raise_for_status()
            return response.json().get("answer", "")
        except httpx.HTTPStatusError as e:
            raise RuntimeError(f"Agent API error: {e.response.status_code}") from e
        except httpx.RequestError as e:
            raise RuntimeError(f"Agent API unreachable: {e}") from e


# ─── Entry point ────────────────────────────────────────────────

if __name__ == "__main__":
    mcp.run(transport="streamable-http")
