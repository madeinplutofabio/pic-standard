# Changelog

All notable changes to this project will be documented in this file.

This project follows Semantic Versioning:
https://semver.org/

## [0.5.0] - 2026-02-09
### Added
- **OpenClaw integration**: Full plugin for OpenClaw AI agent platform
  - `pic-gate` hook — verifies PIC proposals before tool execution (fail-closed)
  - `pic-init` hook — injects PIC awareness at session start
  - `pic-audit` hook — structured audit logging for tool executions
  - HTTP bridge server (`pic-cli serve`) for TypeScript/Go/etc. consumers
  - Comprehensive TypeScript types and fail-closed HTTP client

### Security / Hardening
- HTTP bridge hardening:
  - Negative Content-Length rejection with logging
  - 5-second socket read timeout (DoS protection)
  - Incomplete body detection
  - JSON object type validation
  - 1MB request body limit (MAX_REQUEST_BYTES)
- TypeScript client hardening:
  - VALID_ERROR_CODES validation (rejects unknown error codes)
  - Strict toolName validation in pic-gate
  - HTTP status check before JSON parsing
- Added `PIC_INTERNAL_ERROR` to Python error codes enum for type safety

### Tests
- Python: 20 tests for HTTP bridge (Content-Length edge cases, non-dict JSON body, etc.)
- TypeScript: 9 tests for pic-client (fail-closed behavior, error code validation, eval_ms handling)

### Docs
- `docs/openclaw-integration.md` — comprehensive guide (architecture, setup, production deployment)
- `integrations/openclaw/README.md` — plugin-specific documentation

---

## [0.4.1] - 2026-02-02
### Added
- **Privacy is enforced as high-impact** in the reference verifier (same fail-closed gating class as `money` and `irreversible`).
- **Keyring expiry + revocation**:
  - `expires_at` (optional, per key) to enforce key expiration (UTC).
  - `revoked_keys` (optional list) to hard-disable signer key IDs.
  - Key status helpers for tooling/UX (`ok | missing | revoked | expired`).
- **CLI: `pic-cli keys`**:
  - Validates and prints the active keyring used for signature evidence (v0.4+).
  - `--write-example` now emits the recommended `trusted_keys + revoked_keys` structure and shows `expires_at`.

### Tests
- Keyring parsing tests for base64/hex/PEM + errors, plus expiry/revocation.
- CLI `keys` command tests.
- Tool binding mismatch tests (LangGraph + MCP guard).
- Mixed evidence proposal tests (hash + sig entries in the same proposal).

### Docs
- README updated to document:
  - privacy as high-impact,
  - key expiry/revocation,
  - `pic-cli keys` workflow,
  - mixed evidence behavior.

---

## [0.4.0] - 2026-01-30
### Added
- **Signature evidence (Ed25519)**: `evidence[].type="sig"` verifies an Ed25519 signature over `payload` bytes using a trusted key resolved from the keyring (`key_id`).
- Keyring support for trusted public keys (base64/hex/PEM) with env-based selection via `PIC_KEYS_PATH`.
- New examples:
  - `examples/financial_sig_ok.json` (passes)
  - `examples/failing/financial_sig_bad.json` (fails)
  - `examples/_gen_sig_example.py` (regenerates demo key + examples deterministically)
- New tests for signature evidence pass/fail using `pic_keys.example.json`.

### Security / Hardening
- Signature verification is offline and deterministic; no artifact shipping required.
- Payload size is capped in EvidenceSystem (`max_payload_bytes`) to reduce DoS risk.

---

## [0.3.2] - 2026-01-19
### Added
- **MCP integration (production-grade guard)**: `pic_standard.integrations.mcp_pic_guard.guard_mcp_tool(...)` to enforce PIC at the MCP tool boundary.
- MCP demos:
  - `examples/mcp_pic_server_demo.py` (FastMCP stdio server)
  - `examples/mcp_pic_client_demo.py` (stdio client that spawns the server)
- MCP hardening features:
  - **Debug-gated error details** via `PIC_DEBUG=1` (prevents leaking exception details by default)
  - **Request tracing**: `request_id` / `__pic_request_id` included in structured decision logs
  - **DoS limits**: proposal byte limit + item count limits + evaluation time budget
  - **Evidence sandbox**: `evidence_root_dir` + `max_file_bytes` (default 5MB) for file evidence

### Changed
- Evidence resolution hardened for servers: `file://` evidence can be sandboxed to an allowed root directory.
- README updated with an MCP integration section + enterprise guidance.

### Packaging
- Version bumped to `0.3.2`
- Added optional dependency extra: `mcp`

---

## [0.3.0] - 2026-01-14
### Added
- **Evidence verification (SHA-256)**: optional `evidence[]` objects can be resolved and verified deterministically.
- New module: `pic_standard.evidence` with:
  - `file://` resolver (paths resolved relative to the proposal JSON file)
  - SHA-256 verification
  - in-memory provenance upgrade: verified evidence IDs can upgrade `provenance[].trust` to `trusted`
- CLI additions:
  - `pic-cli evidence-verify <proposal.json>`
  - `pic-cli verify <proposal.json> --verify-evidence` (fail-closed evidence gate before verifier)
- New examples:
  - `examples/financial_hash_ok.json`
  - `examples/failing/financial_hash_bad.json`
  - `examples/artifacts/invoice_123.txt`
- Tests for evidence verification and provenance upgrade.

---

## [0.2.0] - 2026-01-12
### Added
- **LangGraph anchor integration**: `pic_standard.integrations.PICToolNode` for enforcing PIC at the tool boundary (schema + verifier + tool binding) and returning `ToolMessage` outputs.
- LangGraph demo: `examples/langgraph_pic_toolnode_demo.py` demonstrating a blocked (untrusted) vs allowed (trusted) money action.
- LangGraph requirements file: `sdk-python/requirements-langgraph.txt`.

### Changed
- Integration verification errors are now raised as clean `ValueError`s (no noisy Pydantic ValidationError formatting / links).
- README updated with a dedicated **Integrations** section documenting the LangGraph anchor integration and demo.

### Packaging
- Published updated package artifacts to PyPI so `pip install pic-standard` includes the LangGraph integration module and examples/docs updates.

---

## [0.1.0] - 2026-01-09
### Added
- PIC/1.0 proposal JSON Schema (`schemas/proposal_schema.json`)
- Reference Python verifier (`pic_standard.verifier`) with minimal causal contract checks
- CLI (`pic-cli`) with `schema` and `verify` commands
- Conformance tests validating examples against the schema and verifier
- GitHub Actions CI workflow
- Contribution guidelines and issue templates