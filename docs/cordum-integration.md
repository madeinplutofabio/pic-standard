# Cordum Integration Guide

PIC Standard verification gate for [Cordum](https://cordum.io) workflows —
checks Provenance & Intent Contracts on tool calls before execution.

> **Requires:** Cordum core · NATS · Redis · Python >= 3.10

---

## Architecture

```text
┌─────────────────────────────────────────────────────────────┐
│  Cordum Control Plane                                       │
│                                                             │
│  ┌─────────────┐  workflow trigger  ┌────────────────────┐  │
│  │ Workflow    │ ────────────────→  │ Safety Kernel      │  │
│  │ Engine      │                    │ (evaluates policy) │  │
│  └─────────────┘                    └────────┬───────────┘  │
│                                              │ dispatch     │
│                                              ▼              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  NATS JetStream                                      │   │
│  │  topic: job.pic-standard.verify                      │   │
│  └──────────────────────────┬───────────────────────────┘   │
└─────────────────────────────┼───────────────────────────────┘
                              │
                              ▼
                ┌────────────────────────────┐
                │  PIC Standard Worker       │
                │  (Go, cordum-pic-standard) │
                │                            │
                │  1. Decode input           │
                │  2. Call bridge /verify    │
                │  3. Map → workflow output  │
                └────────────┬───────────────┘
                             │
               POST /verify  │  (localhost)
                             ▼
               ┌──────────────────────────┐
               │  PIC HTTP Bridge         │
               │  (Python, pic-cli serve) │
               │                          │
               │  evaluate_pic_for_       │
               │    tool_call()           │
               │                          │
               │  pic_policy.json         │
               └──────────────────────────┘
```

### Data flow

1. **Workflow dispatches** `job.pic-standard.verify` with `{tool_name, tool_args}`
2. **Worker** calls PIC bridge `POST /verify`
3. **Bridge** runs PIC verification (policy checks, tool binding, evidence, limits, time budget)
4. **Bridge responds** `{allowed, error, eval_ms}`
5. **Worker** maps to workflow output: `{allowed, eval_ms, next, impact, reason}`
6. **Workflow** branches on `output.next`: proceed, fail, or require_approval

> **Note:** The verify job itself is still governed by Cordum policy (via the
> pack's policy fragment + risk tags). This keeps the extension aligned with
> the Safety Kernel model.

### Fail-closed principle

Every error path — bridge unreachable, timeout, malformed response, internal
error — results in `{allowed: false, next: "fail"}`. The system never fails
open.

---

## Quick start

### 1) Start the PIC bridge

```bash
pic-cli serve --port 3100
```

### 2) Install and run the Cordum pack

```bash
# Install the pack manifest
go run ./cmd/cordumctl pack install path/to/cordum-packs/packs/pic-standard/pack

# Run the worker
cd path/to/cordum-packs/packs/pic-standard
cp deploy/env.example .env
go run ./cmd/cordum-pic-standard
```

### 3) Trigger a verification

```bash
curl -sS -X POST http://localhost:8081/api/v1/workflows/pic-standard.pic_verify/runs \
  -H "X-API-Key: ${CORDUM_API_KEY:-super-secret-key}" \
  -H "X-Tenant-ID: ${CORDUM_TENANT_ID:-default}" \
  -H "Content-Type: application/json" \
  -d '{"tool_name":"payments_send","tool_args":{"amount":500}}'
```

---

## Output semantics

| Field     | Type              | Description                                            |
|-----------|-------------------|--------------------------------------------------------|
| `allowed` | boolean           | Whether PIC verification succeeded                     |
| `eval_ms` | integer           | Bridge evaluation time in milliseconds                 |
| `next`    | enum string       | `proceed`, `fail`, or `require_approval`               |
| `impact`  | string \| null    | PIC impact classification (e.g. `money`, `privacy`)    |
| `reason`  | string \| null    | Human-readable explanation                             |

**Routing logic:**

- `allowed=false` → `next=fail` (always)
- `allowed=true` + impact in `REQUIRE_APPROVAL_IMPACTS` → `next=require_approval`
- `allowed=true` otherwise → `next=proceed`

`allowed=true` + `next=require_approval` is valid: PIC approved the action,
but its impact type is configured to require human sign-off.

---

## Configuration

All environment variables use the `CORDUM_PIC_STANDARD_` prefix. See
`deploy/env.example` in the pack for the full list.

Key settings:

| Variable                                       | Default                 | Description                       |
|------------------------------------------------|-------------------------|-----------------------------------|
| `CORDUM_PIC_STANDARD_BRIDGE_URL`               | `http://localhost:3100` | PIC bridge endpoint               |
| `CORDUM_PIC_STANDARD_BRIDGE_TIMEOUT`           | `5s`                    | Bridge call timeout (Go duration) |
| `CORDUM_PIC_STANDARD_MAX_PARALLEL`             | `8`                     | Max concurrent verifications      |
| `CORDUM_PIC_STANDARD_REQUIRE_APPROVAL_IMPACTS` | _(empty)_               | Comma-separated impact types      |

---

## Known limitations

- **Impact on allowed=true:** The PIC bridge currently surfaces impact
  primarily in error details (denial cases). Approval routing
  (`require_approval`) only triggers when impact is available. A future bridge
  enhancement can surface impact on allowed responses to enable approval
  routing for all classified actions.

- **Policy schema:** If/when a JSON Schema for policy config is published, it
  should be treated as permissive and best-effort. Runtime validation remains
  in the PIC SDK/bridge.

---

## Differences from OpenClaw integration

| Aspect      | OpenClaw                           | Cordum                                    |
|-------------|------------------------------------|-------------------------------------------|
| Integration | Plugin hooks (TypeScript)          | Pack worker (Go)                          |
| Gating      | `before_tool_call` hook            | Workflow step (`job.pic-standard.verify`) |
| Routing     | allow / block                      | `proceed` / `fail` / `require_approval`   |
| Audit       | PIC audit hook                     | Cordum job logs + workflow history         |
| License     | Apache-2.0 (PIC repo)             | BUSL-1.1 (cordum-packs repo)              |
