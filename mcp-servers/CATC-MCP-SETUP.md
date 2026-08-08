# Catalyst Center MCP Server Setup

Connect VS Code + GitHub Copilot to Cisco Catalyst Center via MCP.
Runs on a privileged-zone Linux box; VS Code connects from a Windows instance in the same zone.

## Architecture

```
Privileged Zone
├── Linux box  →  MCP server (port 7001)  →  Catalyst Center (HTTPS 443)
└── Windows instance  →  VS Code + Copilot  →  http://linux-box-ip:7001/v1/mcp
```

---

## Part 1 — Linux Box: Clone and Run the MCP Server

### 1. Clone the repo and check out the matching release

```bash
cd ~/
git clone https://github.com/cisco-en-programmability/catc-mcp-oss
cd catc-mcp-oss
git checkout release/2.3.7.11
```

> Match the release branch to your Catalyst Center version.
> This guide uses `2.3.7.11` for CatC `2.3.7.11.71047.100`.

### 2. Create a virtual environment and install dependencies

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

### 3. Set credentials as environment variables

```bash
export CATALYST_CENTER_HOST="https://your-catc-ip-or-hostname"
export CATALYST_CENTER_USERNAME="your-username"
export CATALYST_CENTER_PASSWORD="your-password"
export CATALYST_CENTER_VERIFY_SSL=false
```

> Use a dedicated least-privilege CatC account.
> Set `VERIFY_SSL=true` if your CatC has a trusted certificate.

### 4. Start the MCP server

```bash
python3 -m uvicorn catalyst_center_mcp.main:app --host 0.0.0.0 --port 7001
```

> `--host 0.0.0.0` makes it reachable from other machines in the zone.
> For localhost-only use `--host 127.0.0.1`.

### 5. Verify it is running

```bash
curl http://localhost:7001/v1/health
curl http://localhost:7001/v1/readiness
```

Both should return `200 OK`. Health confirms the process is up; readiness confirms credentials are configured.

### 6. (Optional) Run as a persistent background service

To keep the server running after you log out, use `nohup`:

```bash
nohup python3 -m uvicorn catalyst_center_mcp.main:app --host 0.0.0.0 --port 7001 > mcp.log 2>&1 &
echo $! > mcp.pid
```

To stop it later:
```bash
kill $(cat mcp.pid)
```

---

## Part 2 — Windows Instance (Privileged Zone): VS Code + Copilot

### 1. Install VS Code

Download from https://code.visualstudio.com and install.

### 2. Install GitHub Copilot extensions

- Open VS Code
- Click the Extensions icon in the left sidebar (four squares)
- Search and install:
  - **GitHub Copilot**
  - **GitHub Copilot Chat**
- Sign in with the GitHub account that has your Copilot license

### 3. Enable MCP in VS Code settings

Open the Command Palette (`Ctrl+Shift+P`) → **Preferences: Open User Settings (JSON)**

Add this line inside the curly braces:

```json
{
    "chat.mcp.enabled": true
}
```

Save the file.

### 4. Add the MCP server

Command Palette → **MCP: Open User Configuration**

Paste this, replacing `LINUX_BOX_IP` with your Linux box's IP address:

```json
{
  "servers": {
    "catalyst-center": {
      "type": "http",
      "url": "http://LINUX_BOX_IP:7001/v1/mcp"
    }
  }
}
```

Save the file.

### 5. Reload VS Code

Command Palette → **Developer: Reload Window**

### 6. Verify the MCP server is connected

Command Palette → **MCP: List Servers**

`catalyst-center` should appear with a connected status.

### 7. Open Copilot Chat and test

- Menu bar → **View → GitHub Copilot Chat**
- Switch to **Agent** mode (dropdown at top of chat panel)
- Click the **Tools** (wrench) button — catalyst-center tools should be listed

**Test prompt:**
> "Show me device inventory from Catalyst Center"

---

## Example Prompts

```
Summarize device inventory and health for the Global site.
Identify devices with POOR health and group them by device role.
```

```
Investigate wireless client experience at HQ over the last 24 hours.
Identify access points or SSIDs with the most degraded experience.
```

```
Review the network for software and compliance risk.
List devices with compliance issues and prioritize by operational impact.
Do not make any changes.
```

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `readiness` returns error | Missing env vars | Re-export credentials and restart server |
| Tools not listed in VS Code | `chat.mcp.enabled` not set | Add to `settings.json`, reload window |
| Connection refused from Windows | Server bound to `127.0.0.1` | Restart with `--host 0.0.0.0` |
| SSL errors connecting to CatC | Self-signed cert | Set `CATALYST_CENTER_VERIFY_SSL=false` |
| Firewall blocking port 7001 | Zone firewall rules | Open port 7001 TCP between Windows instance and Linux box |
