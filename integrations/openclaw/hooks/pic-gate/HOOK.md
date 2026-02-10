---
name: pic-gate
description: PIC Standard pre-execution gate — verifies tool calls against the PIC bridge
metadata:
  openclaw:
    events: ["before_tool_call"]
    priority: 100
---

# pic-gate — PIC Standard Pre-Execution Gate

Intercepts every tool call via `before_tool_call` and verifies the agent's
PIC proposal against the PIC HTTP bridge before execution.

## Behavior

|
 Condition
|
 Result
|
|
-----------
|
--------
|
|
 Bridge returns
`allowed: true`
|
 Tool executes;
`__pic`
 stripped from params
|
|
 Bridge returns
`allowed: false`
|
 Tool blocked with
`blockReason`
|
|
 Bridge unreachable / timeout
|
 Tool blocked (fail-closed)
|

## Requirements

- OpenClaw ≥ v2026.2.1 (before_tool_call hook support)
- PIC HTTP bridge running (`pic-cli serve` or programmatic `start_bridge()`)
- Python 3.10+ with `pic-standard` installed (for the bridge, not the hook)
- Default bridge URL: `http://127.0.0.1:7580`

## Configuration

Set via `config/pic-plugin.example.json`:

```json
{
  "bridge_url": "http://127.0.0.1:7580",
  "bridge_timeout_ms": 500,
  "log_level": "info"
}
```