# Changelog

All notable changes to this project will be documented in this file.

This project follows Semantic Versioning:
https://semver.org/

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

