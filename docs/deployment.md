# Deploying agent-inbox-memory-layer as a systemd Service

This guide covers running the `inbox watch` daemon as a persistent background service on Linux using systemd.

## Prerequisites

- Linux with systemd (Ubuntu 20.04+, Debian 11+, or equivalent)
- Python 3.10+
- Git

## 1. Clone and install

```bash
git clone git@github.com:tobrun/memento.git
cd memento

python -m venv .venv
source .venv/bin/activate
pip install -e .
```

## 2. Configure

```bash
cp .env.example .env
```

Edit `.env` for your LLM backend:

**Option A — Gemini (cloud)**
```env
GOOGLE_API_KEY=your-gemini-api-key
```

**Option B — Anthropic (cloud)**
```env
ANTHROPIC_API_KEY=your-anthropic-api-key
MODEL=claude-sonnet-4-20250514
```

**Option C — Self-hosted / OpenAI-compatible**
```env
OPENAI_API_BASE=http://localhost:11434/v1
OPENAI_API_KEY=not-needed
MODEL=llama3
```

Verify the tool starts before setting up systemd:
```bash
source .venv/bin/activate
inbox watch ./inbox
# Should print startup logs and begin watching
# Ctrl+C to stop
```

## 3. Create the systemd service

Replace `<your-user>`, `/path/to/memento`, and the watched directories with your actual values.

Create `/etc/systemd/system/inbox.service`:

```ini
[Unit]
Description=agent-inbox-memory-layer
Documentation=https://github.com/tobrun/memento
After=network.target

[Service]
Type=simple
User=<your-user>
WorkingDirectory=/path/to/memento
ExecStart=/path/to/memento/.venv/bin/inbox watch /path/to/inbox /path/to/research
Restart=on-failure
RestartSec=5
StandardOutput=journal
StandardError=journal
SyslogIdentifier=inbox

# Load environment from .env file
EnvironmentFile=/path/to/memento/.env

[Install]
WantedBy=multi-user.target
```

Example with a real path (`/home/alice/memento`, user `alice`):

```ini
[Unit]
Description=agent-inbox-memory-layer
After=network.target

[Service]
Type=simple
User=alice
WorkingDirectory=/home/alice/memento
ExecStart=/home/alice/memento/.venv/bin/inbox watch /home/alice/inbox
Restart=on-failure
RestartSec=5
EnvironmentFile=/home/alice/memento/.env

[Install]
WantedBy=multi-user.target
```

## 4. Enable and start

```bash
# Reload systemd to pick up the new service file
sudo systemctl daemon-reload

# Enable the service to start on boot
sudo systemctl enable inbox

# Start the service now
sudo systemctl start inbox

# Verify it's running
sudo systemctl status inbox
```

Expected output:
```
● inbox.service - agent-inbox-memory-layer
     Loaded: loaded (/etc/systemd/system/inbox.service; enabled)
     Active: active (running) since ...
```

## 5. View logs

```bash
# Follow logs in real time
journalctl -u inbox -f

# Show last 100 lines
journalctl -u inbox -n 100

# Show logs since last boot
journalctl -u inbox -b
```

## 6. Manage the service

```bash
sudo systemctl stop inbox      # stop
sudo systemctl restart inbox   # restart
sudo systemctl disable inbox   # disable autostart
```

## 7. Verify

Once running, check the watched directories for `AGENTS.md` and `.memento-state.json` files:

```bash
ls /path/to/inbox/AGENTS.md
cat /path/to/inbox/.memento-state.json
```

Drop a test file and watch the logs to confirm ingestion:

```bash
echo "Test content for ingestion" > /path/to/inbox/test-note.txt
journalctl -u inbox -f
```

## Updating

```bash
cd /path/to/memento
git pull

# Reinstall if dependencies changed
source .venv/bin/activate
pip install -e .

# Restart the service
sudo systemctl restart inbox
```
