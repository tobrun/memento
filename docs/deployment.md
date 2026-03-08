# Deploying Memento as a systemd Service

This guide covers running Memento as a persistent background service on Linux using systemd.

## Prerequisites

- Linux with systemd (Ubuntu 20.04+, Debian 11+, or equivalent)
- Python 3.11+
- bun (for building the frontend)
- Git

## 1. Clone and install

```bash
git clone git@github.com:tobrun/memento.git
cd memento

python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 2. Build the frontend

```bash
cd frontend
bun install
bun run build
cd ..
```

This produces `frontend/dist/` which is served by the agent on port 8888.

## 3. Configure

```bash
cp .env.example .env
```

Edit `.env` for your LLM backend:

**Option A — Gemini (cloud)**
```env
GOOGLE_API_KEY=your-gemini-api-key
```

**Option B — Self-hosted / OpenAI-compatible**
```env
OPENAI_API_BASE=http://localhost:11434/v1
OPENAI_API_KEY=not-needed
MODEL=llama3
```

Verify the agent starts before setting up systemd:
```bash
source .venv/bin/activate
python -m memento
# Should print startup logs and listen on :8888
# Ctrl+C to stop
```

## 4. Create the systemd service

Replace `<your-user>` and `/path/to/memento` with your actual username and install path.

Create `/etc/systemd/system/memento.service`:

```ini
[Unit]
Description=Memento Memory Agent
Documentation=https://github.com/tobrun/memento
After=network.target

[Service]
Type=simple
User=<your-user>
WorkingDirectory=/path/to/memento
ExecStart=/path/to/memento/.venv/bin/python -m memento
Restart=on-failure
RestartSec=5
StandardOutput=journal
StandardError=journal
SyslogIdentifier=memento

# Load environment from .env file
EnvironmentFile=/path/to/memento/.env

[Install]
WantedBy=multi-user.target
```

Example with a real path (`/home/alice/memento`, user `alice`):

```ini
[Unit]
Description=Memento Memory Agent
After=network.target

[Service]
Type=simple
User=alice
WorkingDirectory=/home/alice/memento
ExecStart=/home/alice/memento/.venv/bin/python -m memento
Restart=on-failure
RestartSec=5
EnvironmentFile=/home/alice/memento/.env

[Install]
WantedBy=multi-user.target
```

## 5. Enable and start

```bash
# Reload systemd to pick up the new service file
sudo systemctl daemon-reload

# Enable the service to start on boot
sudo systemctl enable memento

# Start the service now
sudo systemctl start memento

# Verify it's running
sudo systemctl status memento
```

Expected output:
```
● memento.service - Memento Memory Agent
     Loaded: loaded (/etc/systemd/system/memento.service; enabled)
     Active: active (running) since ...
```

## 6. View logs

```bash
# Follow logs in real time
journalctl -u memento -f

# Show last 100 lines
journalctl -u memento -n 100

# Show logs since last boot
journalctl -u memento -b
```

## 7. Manage the service

```bash
sudo systemctl stop memento      # stop
sudo systemctl restart memento   # restart
sudo systemctl disable memento   # disable autostart
```

## 8. Verify

Once running, check the agent is accessible:

```bash
curl http://localhost:8888/api/datasources
# Expected: [{"name": "general", ...}]
```

Open the web interface: `http://localhost:8888`

## MCP server (optional)

The MCP server runs separately. To run it as a second service, create `/etc/systemd/system/memento-mcp.service`:

```ini
[Unit]
Description=Memento MCP Server
After=network.target memento.service

[Service]
Type=simple
User=<your-user>
WorkingDirectory=/path/to/memento
ExecStart=/path/to/memento/.venv/bin/python mcp_server.py
Restart=on-failure
RestartSec=5
EnvironmentFile=/path/to/memento/.env

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable memento-mcp
sudo systemctl start memento-mcp
```

The MCP server listens on port 8889 by default. Configure it in your MCP client:

```json
{
  "mcpServers": {
    "memento": {
      "url": "http://localhost:8889/mcp"
    }
  }
}
```

## Updating

```bash
cd /path/to/memento
git pull

# Reinstall Python dependencies if requirements.txt changed
source .venv/bin/activate
pip install -r requirements.txt

# Rebuild frontend if frontend/ changed
cd frontend && bun install && bun run build && cd ..

# Restart the service
sudo systemctl restart memento
```
