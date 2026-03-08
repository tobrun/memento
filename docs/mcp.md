# MCP Server

The Memento MCP server exposes your datasources to any MCP-compatible client (Claude Code, Claude Desktop, etc.) over Streamable HTTP.

## Prerequisites

The main Memento agent must be running — the MCP server delegates all requests to its HTTP API.

```bash
python -m memento
```

## Starting the MCP Server

```bash
python mcp_server.py --port 8889
```

The server binds to `0.0.0.0`, making it accessible from other machines on your local network.

### Command-Line Options

| Flag | Default | Description |
|---|---|---|
| `--port` | `8889` (or `MCP_PORT` env var) | Port to listen on |
| `--agent-url` | `http://localhost:8888` (or `PORT` env var) | Base URL of the Memento agent API |

## Exposed Tools

### `list_datasources`

Returns the names of all available datasources (e.g. `["general", "news", "company"]`).

### `query`

Queries memories within a named datasource.

| Parameter | Type | Description |
|---|---|---|
| `question` | `str` | Natural-language question to ask against stored memories |
| `datasource` | `str` | Datasource to query (use `list_datasources` to discover names) |

## Client Configuration

### Local

Add to your MCP client settings (e.g. `~/.claude/settings.json` or project `.mcp.json`):

```json
{
  "mcpServers": {
    "memento": {
      "url": "http://localhost:8889/mcp"
    }
  }
}
```

### Remote (LAN)

Find the server machine's IP (`hostname -I | awk '{print $1}'`) and point the client at it:

```json
{
  "mcpServers": {
    "memento": {
      "url": "http://<SERVER_IP>:8889/mcp"
    }
  }
}
```

Make sure ports `8888` (agent API) and `8889` (MCP) are not blocked by a firewall on the server machine.

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `MCP_PORT` | `8889` | Default port (overridden by `--port`) |
| `PORT` | `8888` | Used to derive the default `--agent-url` |
