# Changelog

All notable changes to this project will be documented in this file.

This project follows Semantic Versioning:
https://semver.org/

## [0.8.0] - 2026-04-20

### Added
- **PIC Canonical JSON v1 spec** — `docs/canonicalization.md` normatively defines PIC-CJSON/1.0: RFC 8785 (JSON Canonicalization Scheme) as the baseline, plus PIC-specific rules for object key ordering, string escaping, number serialization, Unicode handling, boolean/null serialization, lone-surrogate rejection, and the digest-byte rules for `args_digest`, `claims_digest`, `intent_digest`, and attestation-object signed bytes (§8.1–§8.4). Frozen for PIC-CJSON/1.0; edge cases discovered after release are spec-level discussions, not patch-level fixes.
- **Reference canonicalization implementation** — `pic_standard.canonical` module with:
  - `canonicalize(value) -> bytes` — PIC-CJSON/1.0 serializer, pure Python stdlib (no runtime dependencies).
  - `sha256_hex(value) -> str` — convenience for §8.1 / §8.2 digests.
  - `intent_digest_hex(intent) -> str` — §8.3 path: hashes raw UTF-8 bytes of the intent string, explicitly distinct from `sha256_hex` to prevent the common trap of canonicalizing bare strings.
  - `CanonicalizationError` — PIC's own exception class, independent of the vendored dependency.
- **Conformance suite (`conformance/`)** — new top-level directory containing:
  - 9 canonicalization vectors under `conformance/canonicalization/` covering key ordering (including UTF-16 supplementary-plane trap), array preservation, string escaping (all RFC 8785 named escapes + representative unnamed controls + solidus), number serialization (11 cases across the ECMAScript `Number::toString` branch matrix), booleans/null, and attestation-object / claims-array shapes.
  - 4 core-verifier vectors under `conformance/core/` (2 allow, 2 block) pinning `PIC_VERIFIER_FAILED` and `PIC_TOOL_BINDING_MISMATCH` outcomes.
  - `conformance/manifest.json` — versioned (`conformance/v0.1`) index of all vectors.
  - Per-directory `README.md` files documenting vector format and seeding discipline.
- **Conformance runner** — `conformance/run.py` (`python -m conformance.run`) executes every vector, validates manifest schema strictly (rejects unknown fields and mode/expected mismatches), detects manifest/vector drift, and produces a pass/fail report with CI-friendly exit codes.
- **CI workflow** — `.github/workflows/conformance.yml` runs the conformance suite on every push and pull request as a `PIC Conformance` check, separate from the main CI job.
- **Unit tests** — `tests/test_canonical.py` adds 71 tests covering the conformance vector sweep, §10.1 implementation-local rejection cases (non-finite numbers, non-string keys including the pathological `.encode()`-bearing class, circular references, tuples, non-serializable host types, lone surrogates, integers outside the ±(2^53 − 1) safe range), and the `sha256_hex` ↔ `intent_digest_hex` distinction.
- **Refined attestation object draft** — `docs/attestation-object-draft.md` updated to cite the normative canonicalization spec directly, replace placeholder digests with real byte-verifiable hex values, document the §8.4 signer/verifier contract (both re-canonicalize from the parsed attestation object; raw payload bytes are never signed or verified directly), and link to the conformance vector that pins its worked example.

### Changed
- `docs/attestation-object-draft.md` Status banner no longer says the canonicalization spec "does not yet exist"; instead it separates what's frozen in v0.8.0 (canonicalization rules, digest inputs) from what remains DRAFT (field set, freshness semantics, audience semantics).

### Vendored
- **Trail of Bits `rfc8785.py`** (v0.1.4, commit `e7bbf8987c484950edfad6cc2a29f69a18920c8e`, Apache-2.0) — vendored at `sdk-python/pic_standard/_rfc8785.py` to provide RFC 8785 number and string serialization. Upstream raw blob SHA-256 `c25bc3a046528482d53bee3487b837f31dd9c05f33e8f13288c7aab320932cec` is pinned in the file header and in `THIRD_PARTY_NOTICES.md` at the repo root. PIC-specific behavior (tuple rejection, lone-surrogate-in-key validation, circular reference detection, `canonicalize`/`sha256_hex`/`intent_digest_hex` public API, exception normalization) lives in `pic_standard.canonical` which wraps the vendored module.

### Notes
- **Runtime behavior of existing proposals is unchanged in v0.8.0.** Canonicalization is a new capability exposed through `pic_standard.canonical`; it is not wired into `verify_proposal()` or evidence signing paths. Existing payload-string signatures continue to verify as v0 legacy mode.
- **Wire-up of canonicalization into evidence signing** (attestation-object-backed signatures using `canonicalize(attestation_object)` as the signed bytes per §8.4) is deferred to a future release.
- **Evidence-mode and trust-sanitization-mode conformance vectors** are deferred to v0.8.1+ per the Out of Scope section of the v0.8.0 plan. v0.8.0's conformance suite covers canonicalization mode and core verifier mode only.
- **Cross-implementation conformance** (TypeScript/Go) arrives alongside those reference implementations in Phase 3+; the v0.8.0 conformance suite is deliberately language-neutral (JSON vectors + hex expectations + SHA-256 expectations) so any future language binding consumes the same vectors.

---

## [0.7.5] - 2026-04-03

### Added
- **`strict_trust` pipeline option**: new `PipelineOptions.strict_trust` (default `False`).
  When enabled, all inbound `provenance[].trust` values are sanitized to `"untrusted"`
  before verification. Evidence verification is the only path to trusted status.
- **Trust deprecation warning**: when a proposal declares `trust:"trusted"` but
  effective evidence verification will not run for that proposal, a
  `PICTrustFutureWarning` is emitted with migration guidance. In PIC/1.0,
  non-sanitizing mode will be legacy and non-conformant.
- **Attestation Object v1 draft**: `docs/attestation-object-draft.md` — non-normative
  design document for the canonical minimal signing target (community feedback welcome).
- **Migration guide**: `docs/migration-trust-sanitization.md` — step-by-step guide for
  migrating from self-asserted trust to evidence-backed trust.
- `strict_trust` and `key_resolver` parameters in `guard_mcp_tool()`,
  `guard_mcp_tool_async()`, and `PICToolNode` for integration-level opt-in.

### Changed
- **Pipeline refactor**: `verify_proposal()` now finalizes trust state (sanitization +
  evidence verification + trust upgrade) before `ActionProposal` instantiation. This
  removes duplicate instantiation/binding and ensures `strict_trust=True` works correctly
  with evidence-backed proposals.
- `PICToolNode` constructor now accepts `verify_evidence`, `strict_trust`, `key_resolver`,
  `policy`, `proposal_base_dir`, and `evidence_root_dir` for full pipeline configuration.

---

## [0.7.1] - 2026-03-18

### Fixed
- **Import crash on base install**: `import pic_standard.cli` no longer fails
  when optional dependencies (`langchain-core`, `mcp`) are not installed.
  `integrations/__init__.py` now uses lazy `__getattr__` loading so importing
  one integration does not pull in another's dependencies.
- CLI `serve` command import moved inside the handler — `pic-cli verify`,
  `pic-cli keys`, etc. no longer trigger any integration imports.

### Added
- `docs/spec-status.md` — companion status note for RFC-0001, explaining that
  the defensive publication is intentionally preserved with its original SHA-256
  fingerprint while the implementation has evolved through v0.7.x.
- `TYPE_CHECKING` imports and `__dir__()` in `integrations/__init__.py` for
  IDE/type-checker support.

---

## [0.7.0] - 2026-03-12

### Added
- **`KeyResolver` protocol** — injectable, sync-only interface for trust key resolution.
  `get_key(key_id) -> Optional[bytes]` and `key_status(key_id) -> KeyStatus`.
- **`StaticKeyRingResolver`** — zero-I/O resolver backed by a pre-loaded `TrustedKeyRing`.
- `PipelineOptions.key_resolver` — threads custom resolver through the shared pipeline
  into `EvidenceSystem`.
- `KeyResolver` and `StaticKeyRingResolver` exported from `pic_standard` public API.
- `tests/test_key_resolver.py` — 7 tests covering resolver protocol, injection,
  lazy default semantics, and pipeline threading.

### Changed
- **Evidence hot path fix:** `EvidenceSystem` no longer reloads the keyring per signature
  item. Default trust resolution is lazy (loaded on first signature verification only).
- `EvidenceSystem.__init__` accepts optional `key_resolver` parameter. When omitted,
  the default resolver is constructed lazily via `TrustedKeyRing.load_default()` on
  first use — hash-only evidence never triggers keyring loading.
- Deleted `_load_public_key_from_keyring()` module-level function; replaced by
  `EvidenceSystem._resolve_public_key()` instance method using the resolver protocol.

### Fixed
- Hash-only evidence verification no longer triggers unnecessary keyring file I/O.

---

## [0.6.1] - 2026-02-26

### Changed
- **Shared verification pipeline**: Extracted duplicated verification logic from
  MCP guard, LangGraph, and CLI into a single `pipeline.py` module with
  `verify_proposal()` as the one function all consumers delegate to.
- All three consumers (MCP guard, LangGraph ToolNode, CLI) now delegate to
  `pipeline.verify_proposal()` instead of reimplementing the verification chain.
- **Error code semantics**: `ActionProposal` instantiation / verifier-rule failures
  are now reported as `PIC_VERIFIER_FAILED` (instead of `PIC_POLICY_VIOLATION` in
  some MCP paths).
- `pic-cli verify` now uses the shared pipeline (`verify_proposal()`), aligning CLI
  behavior with MCP/LangGraph verification flow.
- `_debug_enabled()` moved to `errors.py` (shared location).
- `PICEvaluateLimits` canonical home moved to `pipeline.py`.
- `integrations/__init__.py` exports `PipelineOptions`, `PipelineResult`,
  `verify_proposal`, and `guard_mcp_tool_async`.

### Fixed
- Catch-all in MCP guard wrappers changed from `POLICY_VIOLATION` to
  `INTERNAL_ERROR`.
- Evidence imports narrowed from `except Exception` to `except ImportError`.
- Impact resolution now falls back to `expected_tool` when `tool_name` is None.
- Impact enum values normalized to strings before comparison.

### Added
- `pipeline.py` — shared verification pipeline with `PipelineOptions`,
  `PipelineResult`, and `verify_proposal()`.
- `tests/test_pipeline.py` — 26 tests covering schema, verifier rules, tool
  binding, limits, impact resolution, evidence gating, time budget, and result shape.
- `tests/conftest.py` — `make_proposal()` helper and reusable pytest fixtures.
- `_b64decode()` now supports a `strict` mode (default remains permissive for
  backward compatibility; strict mode will be used in future canonicalization
  tightening).
- Cross-ref comments on `VERIFIER_FAILED` and `POLICY_VIOLATION` in `errors.py`.

---

## [0.6.0] - 2026-02-19

### Added
- **Cordum integration**: Pack for workflow-level PIC verification gating
  - Worker topic: `job.pic-standard.verify`
  - Workflow routing: `proceed` / `fail` / `require_approval`
  - Fail-closed HTTP bridge client (Go)
  - Pack source: `cordum-io/cordum-packs` → `packs/pic-standard/`
- `integrations/cordum/` — README, example policy config
- `docs/cordum-integration.md` — full integration guide with architecture diagram

---

## [0.5.5] - 2026-02-18

### Fixed (OpenClaw Plugin — PR #14704 Review)
- **CRITICAL: pic-init hook API**: Changed from mutating `event.messages.push()` to returning
  `{ prependContext: string }` — the correct `before_agent_start` return type
- **CRITICAL: pic-audit event shape**: Fixed to match real `tool_result_persist` event
  `{ toolName?, toolCallId?, message, isSynthetic? }` instead of fictional
  `{ toolName, params, result, error, durationMs }`
- **CRITICAL: Config loading**: All 3 handlers now receive `pluginConfig` via closure
  from `register()` instead of reading `ctx.pluginConfig` (which doesn't exist in
  hook contexts). Config was silently falling back to defaults.
- **Type-only imports**: Split `import type` from value imports in `pic-client.ts`
- **Test exclusion**: Added `**/*.test.ts` to tsconfig `exclude` (both repos)
- **package-lock.json**: Removed from OpenClaw repo (pnpm workspace uses pnpm-lock.yaml)

### Changed
- All handlers refactored from `export default function handler()` to factory pattern:
  `export function createPicXxxHandler(pluginConfig)` returning a closure handler

---

## [0.5.4] - 2026-02-11

### Fixed (OpenClaw Plugin)
- **CRITICAL: Hook registration**: Changed from `api.registerHook()` to `api.on()` to use
  OpenClaw's typed hook system. The old method registered to the internal hooks system
  which requires a config flag and uses different trigger paths. The `api.on()` method
  registers to `typedHooks` which the hook runner actually uses for `before_tool_call`.
- **Type stub**: Added `api.on()` method and `PluginHookName` type union
- **Package name**: Changed from `@pic-standard/openclaw-plugin` to `pic-guard`

### Changed
- Hook handlers now use typed hook registration instead of internal hook system
- Removed `name` from hook options (not required for `api.on()`)

---

## [0.5.3] - 2026-02-10

### Fixed (OpenClaw Plugin)
- **Docs**: Removed fictional `openclaw plugins configure` command from integration guide
- **Import path**: Changed `openclaw` → `openclaw/plugin-sdk` for correct module resolution
- **Plugin discovery**: Added `openclaw.extensions` field to `package.json` for `openclaw plugins install`
- **HOOK.md frontmatter**: Added required `name` and `description` fields to all three hooks
  - `pic-gate`, `pic-init`, `pic-audit` now display properly in OpenClaw UI/CLI

---

## [0.5.2] - 2026-02-10

### Fixed (OpenClaw Plugin)
- **Hook discovery path**: Fixed `index.ts` to point to source `hooks/` directory
  (was loading from `dist/hooks/` which lacks `HOOK.md` files)
- **PIC_AWARENESS_MESSAGE**: Fixed schema description to match actual PIC/1.0
  - `impact`: string (not array)
  - `provenance`: array of `{ id, trust }` (not `{ source, trust_level }`)
  - `action`: `{ tool, args }` (not `{ tool, params_hash }`)
  - Added concrete JSON example for agents
- **PICVerifyResponse type**: Changed to discriminated union matching wire format
  - `allowed: true` → `error: null`
  - `allowed: false` → `error: PICError`
- **log_level type**: Removed `"error"` option (not in manifest, not used)
- **pic-audit HOOK.md**: Fixed logging description (JSON at debug, summary at info)
- **Policy docs**: Fixed example to match actual `pic_policy.example.json` schema
  - `impact_by_tool` (not `tool_impact`)
  - lowercase strings (not uppercase arrays)

### Added
- Debug logging for malformed bridge responses in `pic-client.ts`
- Debug logging for injected awareness message in `pic-init`
- TODO comments for future telemetry and i18n enhancements

---

## [0.5.1] - 2026-02-09

### Fixed (OpenClaw Conformance)
- Added required `configSchema` to plugin manifest
- Added `uiHints` for OpenClaw Control UI form rendering
- Made `pic-audit` handler synchronous (required for `tool_result_persist`)
- Updated HOOK.md frontmatter to use `metadata.openclaw.events` format
- Fixed installation paths: `~/.openclaw/plugins/` → `~/.openclaw/extensions/`
- Added `openclaw.plugin.json` to npm package files array
- Removed non-standard `hooks` array from manifest (auto-discovered)

---

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
