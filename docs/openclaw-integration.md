# OpenClaw Integration Guide

PIC Standard plugin for [OpenClaw](https://github.com/openclaw/openclaw) —
verifies Provenance & Intent Contracts on every tool call before execution.

> **Requires:** OpenClaw ≥ v2026.2.1 · Python ≥ 3.10 · Node ≥ 18

---

## Architecture

```
┌──────────────────────────────────────────────────────────┐
│  OpenClaw Agent Runtime (TypeScript)                     │
│                                                          │
│  ┌──────────┐  before_tool_call   ┌───────────────────┐  │
│  │ Agent/LLM│ ────────────────→   │  pic-gate hook    │  │
│  │ tool call│                     └────────┬──────────┘  │
│  └──────────┘                              │ HTTP        │
│                                            │             │
│  ┌───────────────────┐  tool_result_persist│             │
│  │  pic-audit hook   │ ←─ (after exec)     │             │
│  └───────────────────┘                     │             │
│                                            │             │
│  ┌───────────────────┐  before_agent_start │             │
│  │  pic-init hook    │ ── (session start)  │             │
│  └───────────────────┘                     │             │
└────────────────────────────────────────────┼─────────────┘
                                             │
                               POST /verify  │  (localhost)
                                             ▼
                               ┌──────────────────────────┐
                               │  PIC HTTP Bridge         │
                               │  (Python stdlib)         │
                               │                          │
                               │  evaluate_pic_for_       │
                               │    tool_call()           │
                               │                          │
                               │  pic_policy.json         │
                               └──────────────────────────┘
```

### Data Flow

1. **Agent proposes a tool call** with `__pic` metadata in params
2. **pic-gate** (`before_tool_call`) sends `{tool_name, tool_args}` to the bridge
3. **Bridge** runs the full PIC verification pipeline (limits → schema → verifier → tool-binding → evidence → time-budget)
4. **Bridge responds** `{allowed: true/false, error, eval_ms}`
5. **pic-gate** blocks or strips `__pic` and allows execution
6. **pic-audit** (`tool_result_persist`) logs the outcome

### Fail-Closed Principle

Every error path — bridge unreachable, timeout, malformed response, internal
error — results in the tool call being **blocked**. The system never fails
open.

---

## Quick Start

### 1. Start the PIC Bridge

```bash
# Option A: CLI
pip install pic-standard
pic-cli serve --port 7580

# Option B: Programmatic
python -c "
from pic_standard.integrations import start_bridge
start_bridge(port=7580)
"
```

Verify it's running:

```bash
curl http://127.0.0.1:7580/health
# → {"status": "ok"}
```

### 2. Install the Plugin

```bash
# Option A: OpenClaw CLI (recommended)
cd integrations/openclaw
npm install && npm run build
openclaw plugins install .

# Option B: Manual installation
cd integrations/openclaw
npm install && npm run build
cp -r . ~/.openclaw/extensions/pic-guard/
```

### 3. Configure

Plugin config is stored in `~/.openclaw/openclaw.json` under `plugins.entries.pic-guard.config`.

You can configure via CLI:

```bash
openclaw plugins configure pic-guard --set bridge_url=http://127.0.0.1:7580
```

Or copy the example config file:

```bash
cp integrations/openclaw/config/pic-plugin.example.json \
   ~/.openclaw/extensions/pic-guard/config/pic-plugin.json
```

Edit `pic-plugin.json` if you need to change the bridge URL or timeout:

```json
{
  "bridge_url": "http://127.0.0.1:7580",
  "bridge_timeout_ms": 500,
  "log_level": "info"
}
```

### 4. Run

Start OpenClaw as usual. The plugin registers three hooks automatically:

- **pic-init** — injects PIC awareness at session start
- **pic-gate** — verifies every tool call before execution
- **pic-audit** — logs verification outcomes after execution

---

## Hooks

### pic-gate (`before_tool_call`, priority 100)

The primary enforcement point. Intercepts every tool call and verifies the
agent's `__pic` proposal against the bridge.

| Bridge Response | Hook Action |
|----------------|-------------|
| `allowed: true` | Strips `__pic` from params, tool proceeds |
| `allowed: false` | Returns `{ block: true, blockReason }` |
| Unreachable/timeout | Returns `{ block: true, blockReason }` (fail-closed) |

### pic-init (`before_agent_start`, priority 50)

Fires once at session start. Pushes a PIC awareness message into the session
so the agent knows to include `__pic` proposals in high-impact tool calls.
Also performs an early health check against the bridge.

### pic-audit (`tool_result_persist`, priority 200)

Fires after every tool execution. Logs a structured audit record with tool
name, PIC presence, trust level, and execution duration. Read-only — never
modifies tool results.

---

## Configuration Reference

### Plugin Config

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `bridge_url` | string | `http://127.0.0.1:7580` | PIC bridge endpoint |
| `bridge_timeout_ms` | number | `500` | HTTP timeout for bridge calls |
| `log_level` | string | `info` | `debug`, `info`, or `warn` |

### Bridge CLI Options

```
pic-cli serve [--host HOST] [--port PORT] [--repo-root PATH] [--verify-evidence]
```

| Flag | Default | Description |
|------|---------|-------------|
| `--host` | `127.0.0.1` | Bind address |
| `--port` | `7580` | Listen port |
| `--repo-root` | `.` | Repository root for policy/evidence lookup |
| `--verify-evidence` | off | Enable evidence file verification |

---

## Policy Setup

The bridge loads policy from `pic_policy.json` in the repo root (see
`pic_policy.example.json` for the full schema). This maps tool names to
impact classifications:

```json
{
  "impact_by_tool": {
    "payments_send": "money",
    "customer_export": "privacy",
    "delete_account": "irreversible"
  },
  "require_pic_for_impacts": ["money", "privacy", "irreversible"],
  "require_evidence_for_impacts": ["money", "privacy", "irreversible"]
}
```

- `impact_by_tool`: maps tool names to impact class strings (lowercase)
- `require_pic_for_impacts`: which impact classes require a valid `__pic` proposal
- `require_evidence_for_impacts`: which impact classes require verified evidence

Tools not in `impact_by_tool` or mapped to unlisted impacts pass through
without PIC verification.

---

## Alternative: MCP Sidecar Pattern

For **operator-controlled tools** (where the tool server is under your
control), the MCP sidecar pattern provides tighter integration without HTTP:

```python
from pic_standard.integrations import guard_mcp_tool

payments_send = guard_mcp_tool("payments_send", _payments_send, policy=policy)
```

This wraps the tool function directly in Python — no bridge needed. Use the
OpenClaw plugin for **agent-controlled tools** where you need to intercept
at the platform level.

---

## Troubleshooting

### Bridge unreachable — all tool calls blocked

Check that the bridge is running:

```bash
curl http://127.0.0.1:7580/health
```

If using a custom port, ensure `bridge_url` in your plugin config matches.

### "PIC contract violation" on every call

The agent likely isn't including `__pic` in tool params. Check that:
- pic-init fired at session start (look for `[pic-init] PIC awareness injected`)
- The agent model supports structured tool parameters

### Slow tool calls

Check `eval_ms` in bridge logs. Typical verification takes <10ms. If
evidence verification is enabled (`--verify-evidence`), file I/O may add
latency. Consider disabling it for development.

### Debug mode

Set `PIC_DEBUG=1` to get detailed error information from the bridge:

```bash
PIC_DEBUG=1 pic-cli serve --port 7580
```

Set `log_level: "debug"` in plugin config for verbose TypeScript-side logs.

---

## Production Deployment

### Security: Authentication & TLS

The bridge binds to `127.0.0.1` by default (localhost-only). For network exposure
or multi-host deployments, use a reverse proxy with TLS and authentication:

**Nginx example:**

```nginx
server {
    listen 443 ssl;
    server_name pic-bridge.internal;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    location /pic/ {
        proxy_pass http://127.0.0.1:7580/;
        proxy_read_timeout 1s;

        # API key authentication
        if ($http_x_pic_api_key != "your-secret-key") {
            return 403;
        }
    }
}
```

**Plugin config for proxy:**

```json
{
  "bridge_url": "https://pic-bridge.internal/pic",
  "bridge_timeout_ms": 1000
}
```

> **Note:** The TypeScript client does not currently send auth headers. If you
> need authenticated bridge calls, implement header injection in `pic-client.ts`
> or handle auth at the proxy layer (IP allowlist, mTLS, etc.).

### Concurrency: Single-Threaded Limitation

The stdlib HTTP server is **single-threaded**. Under concurrent load, requests
queue and may timeout. Options for production:

**Option 1: Multiple bridge instances**

Run N instances behind a load balancer:

```bash
# Start 4 bridge instances on different ports
for port in 7580 7581 7582 7583; do
  pic-cli serve --port $port &
done
```

**Option 2: Process manager (systemd, supervisord)**

```ini
# /etc/supervisor/conf.d/pic-bridge.conf
[program:pic-bridge]
command=pic-cli serve --port 758%(process_num)d
process_name=%(program_name)s_%(process_num)d
numprocs=4
```

### Monitoring

**Health check:**

```bash
curl -f http://127.0.0.1:7580/health || alert "PIC bridge down"
```

**Watch for BLOCK events:**

```bash
# Bridge logs (Python logging)
tail -f /var/log/pic-bridge.log | grep BLOCK

# Or set log_level: "debug" in plugin config for TypeScript-side logs
```

**Metrics to track:**
- `eval_ms` — verification latency (typical <10ms)
- BLOCK rate — high rate may indicate misconfigured policy or agent issues
- Bridge error rate — should be near-zero

---

## Limitations

1. **No bridge authentication** — binds to localhost by default. Production
   deployments with network exposure need a reverse proxy with auth/TLS.
2. **OpenClaw ≥ v2026.2.1 required** — older versions don't fire
   `before_tool_call`.
3. **Evidence verification** requires the bridge to have filesystem access
   to evidence files referenced by `file://` URIs.
4. **Single bridge instance** — the stdlib HTTP server is single-threaded.
   For high-concurrency deployments, run behind a process manager or
   replace with an async server.
5. **pic-audit `__pic` visibility** — The `pic-gate` hook strips `__pic` from
   params before tool execution. Depending on OpenClaw's event propagation,
   `pic-audit` may see `pic_in_params: false` even for verified calls. The trust
   level logged is from the original proposal (if captured before stripping).
