# RFC-0001: PIC/1.0 — Provenance & Intent Contracts for AI Agent Action Safety

| Field | Value |
|-------|-------|
| **RFC** | 0001 |
| **Title** | PIC/1.0 — Provenance & Intent Contracts for AI Agent Action Safety |
| **Author** | Fabio Marcello Salvadori |
| **Status** | Living Draft |
| **Created** | 2026-01-08 (initial commit [`436cc2a`](https://github.com/madeinplutofabio/pic-standard/commit/436cc2a6e97da2a9ee6b3ff717ddab88144a06bd)) |
| **First Public Release** | 2026-01-09 ([PyPI v0.1.0](https://pypi.org/project/pic-standard/0.1.0/)) |
| **RFC Drafted** | 2026-02-21 |
| **Versions Covered** | v0.1.0 through v0.5.5 (as of this RFC) |
| **Repository** | https://github.com/madeinplutofabio/pic-standard |
| **PyPI** | https://pypi.org/project/pic-standard/ |
| **License** | Apache-2.0 |

---

## Defensive Publication & IP Notice

This document is published as a **defensive publication** under the Apache License 2.0. Its purpose is to establish verifiable prior art for the techniques, protocols, and architectural patterns described herein.

By publishing this RFC in a public Git repository with cryptographic commit hashes and timestamps, the author establishes a publicly auditable chain of disclosure dating to 2026-01-08 (initial commit) and continuing through the version history documented below. The first public release on PyPI (v0.1.0, 2026-01-09) provides an independently timestamped disclosure record outside of Git.

**Intent:** To prevent any third party from obtaining patent claims over the core concepts described in this document — including but not limited to: action-level provenance gating, causal taint logic for AI agent tool calls, fail-closed evidence verification at the action boundary, and impact-classified proposal contracts.

The Apache-2.0 license grants perpetual, worldwide, royalty-free rights to use, reproduce, and distribute this work. The Git commit history, PyPI publication records, and (optionally) a Zenodo DOI serve as independent, timestamped evidence of public disclosure.

### Core Claims

The novel contributions disclosed and timestamped by this publication are:

1. **Action-boundary tool-call interception** with a machine-validated proposal envelope (the PIC/1.0 Action Proposal).
2. **Impact-class taxonomy with fail-closed gating semantics**: tool calls are classified by risk and high-impact actions are blocked unless justified.
3. **Provenance → claim → evidence ID binding** enabling "trusted bridge" enforcement: untrusted data can be bridged to trusted status through cryptographic verification.
4. **Deterministic offline evidence verification** via SHA-256 hash artifacts and Ed25519 digital signatures, with no external service dependency.
5. **Policy-controlled enforcement boundary**: operators configure which tools and impact classes require PIC proposals, enabling incremental adoption.
6. **Causal taint semantics**: formal rules for how untrusted-data taint propagates through agent reasoning and how trusted evidence bridges it.
7. **Local-first verification architecture** that can run with zero external dependencies, with sandboxed evidence resolution and key lifecycle management.

---

## Abstract

PIC (Provenance & Intent Contracts) is a lightweight, local-first, fail-closed protocol that forces AI agents to declare **intent**, **impact class**, **data provenance**, **claims**, and **cryptographic evidence** before any tool call is executed. The PIC verifier intercepts proposed actions at the **action boundary** — after the agent reasons but before any side effect occurs — and blocks any action that lacks sufficient justification.

PIC complements output guardrails (which constrain what a model *says*) by constraining what an agent is *allowed to do*. It introduces **causal taint semantics**: plans derived from untrusted data carry taint, and tainted plans cannot trigger high-impact actions (financial transfers, data deletion, PII exposure) without trusted evidence to bridge the taint. The reference verifier implements the **minimal enforcement rule**: high-impact actions require at least one claim referencing evidence from trusted provenance.

---

## Problem Statement

1. **Unverified side effects.** LLM-based agents can execute high-impact actions — payments, data exports, resource deletion — based on hallucinated reasoning or injected prompts, with no mechanism to verify the justification before execution.

2. **Guardrails gap.** Existing guardrail frameworks (NeMo Guardrails, Guardrails AI) constrain model *output* (what the model says). They do not constrain agent *actions* (what tools the agent calls and why). A model can pass all output filters and still trigger an unauthorized wire transfer.

3. **No provenance standard.** No existing protocol requires AI agents to declare the provenance of data influencing their decisions, nor to provide cryptographic evidence supporting their claims, before a tool call is dispatched.

4. **Blind tool-call patterns.** Frameworks such as LangGraph, MCP, OpenAI function calling, and CrewAI dispatch tool calls without causal accountability — there is no structured record of *why* the agent chose the action or *where* the decision data came from.

---

## Scope

PIC/1.0 covers:

- **Action-level governance**: Pre-execution interception of AI agent tool calls via structured Action Proposals.
- **Structured Action Proposals**: JSON envelopes containing `protocol`, `intent`, `impact`, `provenance`, `claims`, `evidence`, and `action` fields.
- **Impact classification taxonomy**: Seven impact classes — `read`, `write`, `external`, `compute`, `money`, `privacy`, `irreversible` — each with defined evidence requirements.
- **Causal taint semantics**: Formal rules for how untrusted data propagates taint through agent reasoning and how trusted evidence bridges it. The reference verifier enforces the minimal bridging rule: high-impact requires trusted evidence.
- **Provenance bridging**: The mechanism by which trusted data validates claims made from untrusted sources.
- **Evidence verification**: Deterministic, offline verification of SHA-256 hash artifacts (v0.3) and Ed25519 digital signatures (v0.4).
- **Trusted keyring management**: Public key storage with expiry timestamps and revocation lists (v0.4.1).
- **Policy-driven tool-to-impact mapping**: Configurable mapping of tool names to impact classes, controlling which tools require PIC proposals.
- **Reference implementations** (as of v0.5.5):
  - Python SDK with CLI (`pic-cli`)
  - LangGraph integration (`PICToolNode`)
  - MCP guard (`mcp_pic_guard.py`)
  - OpenClaw plugin (TypeScript, 3 hooks)
  - HTTP bridge (Python, language-agnostic)

---

## Threat Model

| ID | Threat | Description | PIC Mitigation |
|----|--------|-------------|----------------|
| T1 | Prompt injection to side effect | Malicious input in user message, email, or webhook causes agent to execute a harmful tool call | Causal taint: if the only provenance for a high-impact action is untrusted, the action is blocked |
| T2 | Hallucination to financial loss | LLM fabricates an invoice number, recipient, or amount and triggers a payment | High-impact actions (`money`) require evidence from trusted provenance; hallucinated claims have no evidence |
| T3 | Privilege escalation via tool chaining | Agent chains low-risk reads to achieve a high-impact write | Each tool call is independently gated by its impact class; a `money` action requires its own trusted evidence regardless of prior `read` actions |
| T4 | Untrusted data laundering | Agent treats user/email/webhook input as authoritative without verification | Provenance tracking with explicit trust levels (as defined in the PIC/1.0 schema); high-impact gating enforces the distinction |
| T5 | Evidence forgery | Attacker provides fake SHA-256 hashes or forged signatures to bypass gates | Cryptographic verification: SHA-256 is recomputed from sandboxed files; Ed25519 signatures are verified against a managed keyring of trusted public keys |
| T6 | Verification bypass | Agent omits `__pic` metadata or submits a malformed proposal to skip verification | Fail-closed design: missing metadata, schema violations, or any verification error results in the action being blocked |
| T7 | Denial of service via proposals | Attacker floods the verifier with oversized or numerous proposals | Reference hardening defaults: 64 KB max proposal size, 500 ms evaluation time budget, 5 MB max evidence file, 64-item caps on provenance/claims/evidence arrays. Deployments SHOULD tune these to their environment |

---

## Security Properties

The key words "MUST", "MUST NOT", "SHOULD", "SHOULD NOT", and "MAY" in this document are to be interpreted as described in [RFC 2119](https://www.rfc-editor.org/rfc/rfc2119).

A conforming PIC/1.0 implementation provides the following guarantees:

1. **Fail-closed execution.** Every error path — schema invalid, evidence missing, bridge unreachable, timeout exceeded, signature invalid, file not found — MUST result in the action being **blocked**. The implementation SHOULD emit an auditable decision record (log or event). There is no fallback to "allow anyway."

2. **Causal accountability.** Every high-impact action (`money`, `privacy`, `irreversible`) MUST trace back to at least one claim referencing evidence from **trusted** provenance. Actions lacking this causal chain are blocked.

3. **Tool binding integrity.** The proposal's declared `action.tool` MUST match the actual tool being invoked. A mismatch — indicating the agent proposed one action but attempted another — MUST be blocked.

4. **Local-first verification.** PIC verification is deterministic and can run fully locally; the reference implementation requires no external services. Remote verification deployments are still PIC-compliant if the verifier is under the operator's control and the enforcement decision remains fail-closed.

5. **Evidence is verified, not assumed.** Trust is an *output* of cryptographic verification, not an *input* assumption. Provenance trust levels MAY be upgraded after evidence passes verification (the reference implementation upgrades trust in-memory).

6. **Sandboxed evidence resolution.** File-based evidence (`file://` URIs) MUST be resolved within a configured `evidence_root_dir`. Path traversal attempts outside this boundary MUST be rejected.

7. **Key lifecycle management.** Trusted signing keys SHOULD support expiry timestamps (`expires_at`) and revocation lists (`revoked_keys`). Expired or revoked keys MUST NOT produce valid evidence.

8. **Deterministic verification.** Given the same proposal, evidence artifacts, keyring state, and policy configuration, the verifier MUST produce the same result every time.

---

## Non-Goals

PIC/1.0 explicitly does **not** address the following:

1. **Model output guardrails.** PIC does not constrain what the LLM generates or says. It operates solely at the action boundary, after reasoning is complete.

2. **User or agent authentication.** PIC does not verify the identity of users or agents. It verifies the provenance of *data* influencing the agent's decisions.

3. **Authorization / RBAC.** PIC does not manage which users or roles can invoke which tools. It verifies that a tool call has legitimate causal justification, regardless of who initiated it.

4. **Prompt filtering or firewall.** PIC does not inspect, filter, or modify prompt content. It operates post-reasoning, at the point where a tool call is about to be dispatched.

5. **Runtime execution sandbox.** PIC gates the *decision* to execute a tool call. It does not sandbox or isolate the tool's runtime execution.

6. **Logging, observability, or SIEM.** PIC produces structured audit events (blocked/allowed decisions with reasons). It is not itself a logging platform, dashboard, or SIEM.

7. **Input validation for tools.** Tool implementations MUST still validate their own inputs. PIC validates the *justification* for calling the tool, not the correctness of the tool's parameters.

8. **Protection against compromised trusted signers.** If a trusted signer's private key is compromised, the attacker can produce valid evidence. Key rotation and revocation are mitigations; PIC does not prevent key compromise itself.

---

## Protocol Summary: PIC/1.0 Action Proposal

Every tool call whose impact class is in the policy-defined PIC-required impacts set MUST be accompanied by an **Action Proposal** conforming to the `PIC/1.0` JSON Schema, submitted under the `__pic` key in tool arguments. Implementations MAY require PIC proposals for all tool calls regardless of impact class.

The policy mechanism is implementation-defined; PIC/1.0 specifies what MUST be enforced when a tool or impact class is declared PIC-required.

### Required Fields

| Field | Type | Description |
|-------|------|-------------|
| `protocol` | string (const) | `"PIC/1.0"` |
| `intent` | string | Plain-language description of what the agent is trying to do |
| `impact` | enum | Risk classification: `read`, `write`, `external`, `compute`, `money`, `privacy`, `irreversible` |
| `provenance` | array | Input sources with trust levels: `[{id, trust, source?}]` |
| `claims` | array | Agent assertions with evidence references: `[{text, evidence[]}]` |
| `action` | object | The actual tool call: `{tool, args}` |

### Optional Fields

| Field | Type | Description |
|-------|------|-------------|
| `evidence` | array | Evidence objects for verification: hash (`{id, type:"hash", ref, sha256}`) or sig (`{id, type:"sig", ref, payload, alg, signature, key_id}`) |

### Impact Taxonomy

| Class | Risk Level | Evidence Requirement |
|-------|-----------|---------------------|
| `read` | Low | Untrusted provenance allowed |
| `write` | Low | Untrusted provenance allowed |
| `external` | Low | Untrusted provenance allowed |
| `compute` | Low | Untrusted provenance allowed |
| `money` | **High** | Trusted evidence required |
| `privacy` | **High** | Trusted evidence required |
| `irreversible` | **High** | Trusted evidence required (multi-source recommended) |

### Verification Rule

For any Action Proposal where `impact` is in `{money, privacy, irreversible}`:
- At least one entry in `claims` MUST reference (via `evidence[]`) an evidence ID that resolves to a provenance entry with `trust == "trusted"`.
- If no such causal chain exists, the proposal MUST be rejected (fail-closed).

### ID Binding Convention

Evidence IDs SHOULD be stable identifiers reused across `provenance`, `claims`, and `evidence` objects to enable provenance trust upgrade after verification. The binding works as follows:

1. `provenance[].id` — identifies an input source and its initial trust level.
2. `claims[].evidence[]` — references provenance IDs that support the claim.
3. `evidence[].id` — matches a provenance ID; successful verification MAY upgrade that provenance entry's trust to `trusted` (the reference implementation upgrades trust in-memory).

This three-way binding is the mechanism by which untrusted provenance can be *bridged* to trusted status through cryptographic evidence verification.

---

## Prior Art & Differentiation

> This section is **informative (non-normative)** and reflects the state of third-party systems as of February 2026. It may change as those systems evolve. Comparisons are provided for context and are not claims about third-party security properties.

| Solution | What It Does | How PIC Differs |
|----------|-------------|-----------------|
| [OWASP LLM Top 10](https://owasp.org/www-project-top-10-for-large-language-model-applications/) | Threat taxonomy for LLM applications | PIC provides **runtime enforcement** at the action boundary, not a static threat taxonomy |
| [NeMo Guardrails](https://github.com/NVIDIA/NeMo-Guardrails) (NVIDIA) | Input/output content rails for LLMs | PIC gates **actions**, not **generations**; uses causal taint logic rather than content filtering |
| [Guardrails AI](https://github.com/guardrails-ai/guardrails) | Output structure validation | PIC validates **action justification** (provenance + evidence), not output format compliance |
| LangChain safety tools | Tool-level try/catch wrappers | PIC adds **structured provenance**, **cryptographic evidence**, and **fail-closed gating** beyond error handling |
| [Anthropic MCP](https://modelcontextprotocol.io/) | Tool calling protocol for LLMs | MCP specifies tool invocation; PIC specifies provenance and evidence gating at the action boundary |
| [OpenAI function calling](https://platform.openai.com/docs/guides/function-calling) | LLM-driven tool invocation | Specifies tool dispatch without pre-execution provenance verification, evidence chains, or fail-closed enforcement |
| [Google A2A](https://github.com/google/A2A) | Agent-to-agent communication protocol | A2A addresses how agents communicate; PIC addresses whether an individual agent's action is causally justified |
| [CrewAI](https://github.com/crewAIInc/crewAI) / [AutoGen](https://github.com/microsoft/autogen) | Multi-agent orchestration with task-level safety | Task-level safety without causal taint logic or cryptographic evidence verification at the individual action boundary |
| [ARF](https://github.com/petterjuan/agentic-reliability-framework) (Agentic Reliability Framework) | Infrastructure reliability via multi-agent advisory + deterministic policies | ARF gates via historical outcomes and action blacklists (SRE-focused, advisory-only in OSS). PIC gates via **cryptographic provenance chains** and **causal taint logic** at the individual tool-call level, with runtime enforcement |
| [Cordum](https://cordum.io) Safety Kernel | Workflow-level policy evaluation + approval routing | Cordum focuses on workflow gating and approvals; PIC focuses on provenance and evidence gating at the action boundary. Complementary, not competing |

---

## Implementation Timeline

This timeline establishes the chronological development of the PIC Standard, as evidenced by the public Git commit history and PyPI release records.

| Date | Version | Milestone | First Commit |
|------|---------|-----------|--------------|
| 2026-01-08 | — | Initial commit: README, schema, contributing guide | [`436cc2a`](https://github.com/madeinplutofabio/pic-standard/commit/436cc2a6e97da2a9ee6b3ff717ddab88144a06bd) |
| 2026-01-09 | v0.1.0 | PIC/1.0 JSON Schema + reference Python verifier + CLI (`pic-cli verify`, `pic-cli schema`). First PyPI release. | — |
| 2026-01-12 | v0.2.0 | LangGraph anchor integration (`PICToolNode`) | — |
| 2026-01-14 | v0.3.0 | SHA-256 evidence verification system (`evidence.py`) | — |
| 2026-01-19 | v0.3.2 | MCP integration with production hardening (DoS limits, evidence sandboxing, request tracing) | — |
| 2026-01-30 | v0.4.0 | Ed25519 signature evidence + trusted keyring | — |
| 2026-02-02 | v0.4.1 | Privacy enforced as high-impact + keyring expiry/revocation + `pic-cli keys` | — |
| 2026-02-09 | v0.5.0 | OpenClaw integration (TypeScript plugin, 3 hooks, HTTP bridge) | — |
| 2026-02-18 | v0.5.5 | OpenClaw plugin hardening (factory pattern, correct hook APIs) | — |
| 2026-02-21 | — | This RFC drafted | — |

---

## Conformance

The key words "MUST", "MUST NOT", "SHOULD", "SHOULD NOT", and "MAY" in this section are to be interpreted as described in [RFC 2119](https://www.rfc-editor.org/rfc/rfc2119).

### Conformance Levels

- **PIC/1.0 Core**: Schema validation + fail-closed enforcement + tool-binding verification + high-impact trusted-bridge rule. This is the minimum required for PIC/1.0 conformance.
- **PIC/1.0 Evidence**: Core + hash and/or signature evidence verification + keyring requirements. Implementations claiming Evidence-level conformance MUST also satisfy all Core requirements. If an implementation supports signature evidence, it MUST verify Ed25519 signatures against an operator-managed trusted public key set, and MUST reject signatures from revoked or expired keys where those fields are supported.

### MUST (Required for PIC/1.0 Core)

1. **Schema validation.** The implementation MUST validate every Action Proposal, when PIC enforcement is required by policy, against the PIC/1.0 JSON Schema before permitting execution.

2. **Fail-closed enforcement.** Any verification error — schema validation failure, evidence verification failure, tool binding mismatch, timeout, bridge unreachable, or internal error — MUST result in the action being blocked. The implementation MUST NOT fall back to permitting the action on any error path.

3. **Causal taint gating.** For high-impact actions (`money`, `privacy`, `irreversible`), the implementation MUST require at least one claim referencing evidence from trusted provenance. Proposals lacking this causal chain MUST be rejected.

4. **Tool binding verification.** The implementation MUST verify that the `action.tool` field in the proposal matches the actual tool being invoked. Mismatches MUST be rejected.

### SHOULD (Recommended)

5. **Evidence support.** The implementation SHOULD support at least one evidence verification type: hash (`sha256` over file artifacts) or sig (Ed25519 signature over payload). Implementations claiming **PIC/1.0 Evidence** conformance MUST support at least one.

6. **Structured audit logging.** The implementation SHOULD emit an auditable decision record for every verification decision (allowed/blocked) with a structured reason code and timestamp.

7. **Key lifecycle.** Implementations supporting signature evidence SHOULD enforce key expiry and honor revocation lists.

### MAY (Optional)

8. **Policy-driven impact mapping.** The implementation MAY support configurable tool-to-impact-class mapping via policy files.

9. **Approval routing.** The implementation MAY support routing verified-but-high-impact actions to a human approval workflow (e.g., `require_approval`).

10. **HTTP bridge.** The implementation MAY expose verification via an HTTP endpoint (`POST /verify`) for language-agnostic integration.

11. **Universal PIC gating.** The implementation MAY require PIC proposals for all tool calls regardless of impact class.

---

## Spec Fingerprint

The following SHA-256 digests anchor this RFC to the canonical artifacts at the time of publication. Anyone with access to the repository at the tagged commit can independently verify these fingerprints.

A companion file [`docs/RFC-0001.SHA256`](RFC-0001.SHA256) contains the full digest manifest, including this RFC, the schema, and key enforcement modules.

| Artifact | SHA-256 |
|----------|---------|
| `sdk-python/pic_standard/schemas/proposal_schema.json` | `910ab13433875b7824449c387a6652eff1f61a0b597b3ac0dd86537d0734e89a` |
| `sdk-python/pic_standard/verifier.py` | `f4c0dc74ce367b27e111c8f28cf9ce0686f6c40dedf13cd52a288f00363ea2ed` |
| `sdk-python/pic_standard/evidence.py` | `b14b600a8d1738c616285a39c14bba14dbe0d9f52763e870b5c96b77b2b2caec` |
| `sdk-python/pic_standard/keyring.py` | `8a572fa527f7f592c65166fea02e5b580144af5a2568bd89b8385b360fdfae9f` |

The RFC document itself is anchored by the **Git commit hash** that introduces it — a cryptographic content address covering the entire repository state at the time of publication.

---

## Archival & DOI

To further strengthen the prior-art timestamp, the author SHOULD:

1. Create a GitHub Release tagged `rfc-0001-v1` containing this document and the referenced schema.
2. Connect the repository to [Zenodo](https://zenodo.org/) via the GitHub-Zenodo integration to automatically mint a DOI (Digital Object Identifier) for the release.
3. Record the DOI in this section once issued.

A DOI provides a citable, immutable, independently-timestamped reference that exists outside of GitHub's infrastructure.

| Field | Value |
|-------|-------|
| **DOI** | _(to be minted upon GitHub Release + Zenodo archival)_ |

---

## Future Directions

The following areas are under consideration for future versions of the PIC Standard. They are listed here for completeness and do not constitute commitments.

- **Cordum integration (planned for v0.6.0)**: Go pack worker for workflow-level PIC verification gating, with NATS JetStream dispatch and three-way routing (`proceed` / `fail` / `require_approval`). Pending partner approval and integration availability.
- **TypeScript SDK**: Native TypeScript/JavaScript implementation of the PIC verifier and evidence system.
- **Audit dashboard**: Visual interface for reviewing PIC verification decisions, evidence chains, and blocked actions.
- **Domain-specific impact classes**: Extending the taxonomy for healthcare (`hipaa`), legal (`privilege`), financial regulation (`aml`), and other verticals.
- **Multi-agent provenance chains**: Extending provenance tracking across agent-to-agent delegations where one agent's output becomes another's input.
- **Formal verification**: Mathematical proof that the causal taint logic correctly prevents the specified threat classes.
- **Hardware-rooted evidence**: TPM/HSM-backed signatures for environments requiring hardware attestation.

---

*This document is maintained at https://github.com/madeinplutofabio/pic-standard and is licensed under Apache-2.0.*
