# PIC Standard Pack for Cordum

Provenance & Intent Contract (PIC) verification gate for Cordum workflows.
The pack adds a `job.pic-standard.verify` worker topic that checks proposed
tool calls against PIC contracts before execution.

> **Note:** This is an *optional Safety Kernel extension* delivered as a Pack.
> Packs do not hook into the kernel's internal PDP directly; instead they add
> governed job topics and workflows that Cordum evaluates and enforces like any
> other action.

## How it works

| Component                    | Role                                                    |
|------------------------------|---------------------------------------------------------|
| PIC bridge (`pic-cli serve`) | Evaluates provenance & intent contracts                 |
| Cordum Pack worker           | Calls the bridge and returns a workflow-friendly result  |
| Cordum workflow              | Composes the verify step as a gate before risky actions  |

**Workflow routing:**

| output.next         | Meaning                                |
|---------------------|----------------------------------------|
| `proceed`           | PIC verification passed — continue     |
| `fail`              | Verification failed — abort workflow   |
| `require_approval`  | Allowed, but impact requires review    |

## Prerequisites

- Cordum core with NATS + Redis
- Python >= 3.10 with `pic-standard` installed
- PIC bridge running (`pic-cli serve --port 3100`)

## Setup

### 1) Start the PIC bridge

```bash
pic-cli serve --port 3100
```

### 2) Install the pack

The pack source lives in the `cordum-io/cordum-packs` repository under
`packs/pic-standard/`.

```bash
go run ./cmd/cordumctl pack install path/to/cordum-packs/packs/pic-standard/pack
```

### 3) Run the worker

```bash
cd path/to/cordum-packs/packs/pic-standard
cp deploy/env.example .env
# Edit .env with your Cordum and bridge settings
go run ./cmd/cordum-pic-standard
```

## Configuration

See `deploy/env.example` in the pack for all environment variables. Key settings:

| Variable                                       | Default                 | Description                       |
|------------------------------------------------|-------------------------|-----------------------------------|
| `CORDUM_PIC_STANDARD_BRIDGE_URL`               | `http://localhost:3100` | PIC bridge endpoint               |
| `CORDUM_PIC_STANDARD_BRIDGE_TIMEOUT`           | `5s`                    | Bridge call timeout (Go duration) |
| `CORDUM_PIC_STANDARD_MAX_PARALLEL`             | `8`                     | Max concurrent verifications      |
| `CORDUM_PIC_STANDARD_REQUIRE_APPROVAL_IMPACTS` | _(empty)_               | Comma-separated impact types      |

## Fail-closed design

The pack **never fails open**. If the bridge is unreachable, times out,
or returns a malformed response, the worker returns a structured failure output:

```json
{
  "allowed": false,
  "eval_ms": 0,
  "next": "fail",
  "impact": null,
  "reason": "bridge call failed: ..."
}
```

This ensures the workflow always has a structured output to branch on.

## License

The Cordum pack is licensed under BUSL-1.1 (the `cordum-packs` repository license).
PIC Standard itself remains Apache-2.0.
