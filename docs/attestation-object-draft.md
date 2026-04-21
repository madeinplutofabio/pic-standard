# PIC Attestation Object v1 — Draft

> **Status:** DRAFT — attestation-object semantics remain subject to Phase 1.1b formalization.
>
> **What's frozen as of PIC v0.8.0:**
> - The canonicalization rules used to compute `args_digest`, `claims_digest`, and the signed bytes of the attestation object itself are normatively defined in [`docs/canonicalization.md`](canonicalization.md) (PIC Canonical JSON v1 / PIC-CJSON/1.0). Those rules are frozen for PIC-CJSON/1.0 and will not change within v0.8.x.
> - The byte inputs for each digest are precise enough for conformance vectors. See [Test Vectors](#test-vectors) below.
>
> **What is still DRAFT in this document:**
> - Field set, field names, and presence requirements (MUST / SHOULD / OPTIONAL) are subject to Phase 1.1b review.
> - Freshness semantics (`issued_at`, `expires_at`) and `audience` semantics are not yet normatively specified.
> - The Open Questions section below may change field definitions before formal adoption.
>
> This draft uses proposed normative language (MUST, SHOULD, OPTIONAL) to preview intended Phase 1.1b semantics. These requirements are not binding until the attestation object specification is formally adopted.
>
> Published for community feedback; the attestation object is scheduled for formalization in Phase 1.1b of the [PIC Roadmap](../ROADMAP.md).

---

## Motivation

PIC v0.7.x signs the `evidence.payload` field — a UTF-8 string whose content and canonicalization are the producer's responsibility. This works, but it has two structural weaknesses:

1. **Payload strings are fragile.** Semantically identical payloads can differ bytewise across producers, languages, and serialization libraries. Before PIC-CJSON/1.0 (v0.8.0) there was no normative definition of what bytes constitute the "same" payload.

2. **Full-proposal signing is brittle.** Signing the entire Action Proposal couples the signature to transport-specific fields, runtime-specific metadata, and field ordering that may vary across integrations and evolve over time.

The **Attestation Object** is a minimal, stable JSON object that sits between these extremes. It binds the security-relevant fields of a proposal — tool, args, impact, provenance, claims — by value or digest, while remaining small enough for portable cross-language verification and stable enough to survive protocol evolution.

---

## Design Principles

- **Sign what matters, not everything.** The attestation object includes only fields that affect the allow/block decision or the audit trail.
- **Use digests for descriptive content.** Intent and claims are human-readable context. Binding them by digest preserves audit linkage without copying sensitive text into the signed core.
- **Freshness hooks now, replay caches later.** `issued_at` and `expires_at` are defined in v1 so verifiers can enforce them when present. Full replay prevention (nonce caches, bounded TTL registries) is deferred to a profile-level specification.
- **Backward compatible.** Existing payload-string signatures remain valid as "v0 legacy mode." Attestation-object signatures are identified by the presence of `attestation_version` in the evidence payload.

---

## Fields

| Field | Type | Presence | Description |
|-------|------|----------|-------------|
| `attestation_version` | string | MUST | `"PIC-ATT/1.0"` |
| `tool` | string | MUST | Tool name from `action.tool` |
| `args_digest` | string | MUST | SHA-256 hex digest of canonicalized `action.args` |
| `impact` | string | MUST | Normalized impact class |
| `intent_digest` | string | SHOULD | SHA-256 hex digest of UTF-8 `intent` string |
| `provenance_ids` | string[] | MUST | Provenance entry IDs in proposal array order |
| `claims_digest` | string | MUST | SHA-256 hex digest of canonicalized `claims` array |
| `issued_at` | string | SHOULD | RFC 3339 timestamp — freshness hook |
| `expires_at` | string | OPTIONAL | RFC 3339 timestamp — freshness hook |
| `audience` | string | OPTIONAL | Deployment/verifier identity for replay resistance |

### Why `intent_digest` is SHOULD, not OPTIONAL

Intent is the human-readable audit trail. If it is not bound to the signature at all, an attacker can swap intent text without invalidating the signature. The digest is cheap and preserves the audit chain.

### Why `claims_digest` uses a digest

- **Privacy:** Full claims may contain sensitive business text. Digests preserve audit linkage without copying content into signed artifacts or logs.
- **Stability:** Natural-language claim text is often reformatted or redacted. Digests reduce brittle verification failures from cosmetic changes.

### Why `args_digest` uses a digest

- **Compactness:** Full execution args can be large. A digest keeps the signed core small and portable.
- **Avoids duplication:** The full args already exist in `action.args`. Embedding them again in the attestation object would be redundant.
- **Verifiability preserved:** The verifier can recompute the digest from `action.args` using the same canonicalization rules, so the binding is equally strong.

### Canonicalization inputs for each digest

Each digest is computed over a specific input. The byte-level rules are normative in [`docs/canonicalization.md`](canonicalization.md):

- **`args_digest`** — SHA-256 of `canonicalize(action.args)`, per [`docs/canonicalization.md` §8.1](canonicalization.md#81-args_digest). `canonicalize` is PIC Canonical JSON v1 applied to the `action.args` value exactly as it appears in the Action Proposal.
- **`claims_digest`** — SHA-256 of `canonicalize(claims)`, per [`docs/canonicalization.md` §8.2](canonicalization.md#82-claims_digest). `claims` is the full `claims` array with array element order preserved as in the proposal.
- **`intent_digest`** — SHA-256 of the raw UTF-8 bytes of the `intent` string, per [`docs/canonicalization.md` §8.3](canonicalization.md#83-intent_digest). Intent is a scalar string and is **not** JSON-wrapped or canonicalized; the digest is computed over the string's UTF-8 bytes directly. This is the one case where the inputs to a PIC digest are not canonical JSON bytes.
- **`provenance_ids`** — provenance entry IDs listed in the same order as they appear in the proposal's `provenance` array. No digest; the ids themselves are included by value.

---

## Attestation Object vs. Evidence Entry

The attestation object and the evidence entry serve different roles:

- The **attestation object** is the thing being canonicalized and signed. It contains only security-relevant bindings (tool, digests, impact, provenance IDs, freshness).
- The **evidence entry** is the transport wrapper that carries the attestation object, its signature, and key metadata within the proposal's `evidence` array.

Example evidence entry carrying an attestation object:

```json
{
  "id": "approved_invoice",
  "type": "sig",
  "ref": "inline:attestation",
  "payload": "{\"attestation_version\":\"PIC-ATT/1.0\",\"tool\":\"payments_send\", ...}",
  "alg": "ed25519",
  "signature": "<base64 Ed25519 signature over canonicalize(attestation_object)>",
  "key_id": "org:finance-signer-2026"
}
```

The `payload` field contains the attestation object serialized as PIC Canonical JSON v1. The `signature` is computed over `canonicalize(attestation_object)` per [`docs/canonicalization.md` §8.4](canonicalization.md#84-attestation-object-serialization) — see [Signing Process](#signing-process) below for the complete signer/verifier contract.

---

## Example

Given this Action Proposal:

```json
{
  "protocol": "PIC/1.0",
  "intent": "Send $500 to vendor for invoice #1234",
  "impact": "money",
  "provenance": [
    {"id": "approved_invoice", "trust": "trusted", "source": "erp_system"}
  ],
  "claims": [
    {"text": "Invoice verified in ERP", "evidence": ["approved_invoice"]}
  ],
  "action": {
    "tool": "payments_send",
    "args": {"amount": 500, "recipient": "vendor-abc"}
  }
}
```

The digests for the attestation object are computed as follows.

**`args_digest`** (per §8.1):

- Input: `action.args = {"amount": 500, "recipient": "vendor-abc"}`
- Canonical bytes: `{"amount":500,"recipient":"vendor-abc"}` (39 bytes, keys sorted; `amount` < `recipient` by UTF-16 code unit)
- SHA-256 hex: `b6f5e7a7ab11623e3d09cb141bb97b196d0891bd1b158d38919ca6642da207d6`

**`claims_digest`** (per §8.2):

- Input: `claims` array with one element.
- Canonical bytes: `[{"evidence":["approved_invoice"],"text":"Invoice verified in ERP"}]` (68 bytes; inner keys sorted, `evidence` < `text`; array element order preserved)
- SHA-256 hex: `b74d51c658c6e980599f63ddfe626918c3fdad34c9ec9ef39940b015b0ebe44f`

**`intent_digest`** (per §8.3):

- Input: raw UTF-8 bytes of the `intent` string `"Send $500 to vendor for invoice #1234"` (37 bytes, all ASCII in this example).
- **No canonicalization applied** — the intent is a scalar string; the digest is over its UTF-8 bytes directly.
- SHA-256 hex: `0144f52c71b5fbefde848dc9cdb7a9f4c54199a29cdea4b53f5987f491b307d3`

The corresponding attestation object is:

```json
{
  "attestation_version": "PIC-ATT/1.0",
  "tool": "payments_send",
  "args_digest": "b6f5e7a7ab11623e3d09cb141bb97b196d0891bd1b158d38919ca6642da207d6",
  "impact": "money",
  "intent_digest": "0144f52c71b5fbefde848dc9cdb7a9f4c54199a29cdea4b53f5987f491b307d3",
  "provenance_ids": ["approved_invoice"],
  "claims_digest": "b74d51c658c6e980599f63ddfe626918c3fdad34c9ec9ef39940b015b0ebe44f",
  "issued_at": "2026-04-03T12:00:00Z"
}
```

Its canonicalization per §8.4 produces 397 bytes beginning `{"args_digest":"b6f5e7a7…`. Those 397 bytes are the `signed_bytes` input to Ed25519 — see [Signing Process](#signing-process).

---

## Signing Process

The signer and verifier both compute `signed_bytes` from the parsed attestation object, never from the raw payload text. This follows [`docs/canonicalization.md` §8.4](canonicalization.md#84-attestation-object-serialization) exactly.

**Producer:**

1. **Construct** the attestation object from proposal fields, computing digests as specified in [Canonicalization inputs for each digest](#canonicalization-inputs-for-each-digest) above (§8.1 / §8.2 / §8.3).
2. **Canonicalize**: `signed_bytes = canonicalize(attestation_object)` using [PIC Canonical JSON v1](canonicalization.md).
3. **Sign**: compute an Ed25519 signature over `signed_bytes`.
4. **Embed**: store `signed_bytes` (decoded as a UTF-8 string) as the `payload` field of a `sig`-type evidence entry, and the base64-encoded signature (standard Base64 with `=` padding per RFC 4648 §4, not URL-safe) as the `signature` field. Include `alg`, `key_id`, and other metadata per the evidence entry format.

**Verifier:**

1. **Parse**: take the `payload` string, parse it as JSON, and treat the resulting value as the attestation object. The verifier MUST NOT treat the raw payload UTF-8 bytes as authoritative.
2. **Re-canonicalize**: compute `signed_bytes = canonicalize(parsed_attestation_object)` — exactly the same operation the producer performed.
3. **Verify**: check the Ed25519 signature against `signed_bytes` using the key identified by `key_id`.
4. **Enforce semantics**: after signature verification, check `attestation_version` is supported, `tool` matches the intended invocation, `issued_at` / `expires_at` are within policy, and the digests match the corresponding canonicalized fields of the Action Proposal.

This strict re-canonicalization on the verifier side guards against lossy transport (e.g., middleware that re-serializes JSON, re-orders keys, or normalizes whitespace). The signature is always over canonical bytes, never over raw payload text.

---

## Backward Compatibility

Existing `sig`-type evidence entries that do not contain `attestation_version` in their payload are treated as **v0 legacy mode**. The intended compatibility rule is that verifiers continue to accept v0 signatures until PIC/1.0 normative semantics specify otherwise.

New attestation-object signatures are identified by the presence of `attestation_version` in the parsed evidence payload.

---

## Freshness Semantics

When `expires_at` is present, the intended PIC/1.0 rule is reject-on-expiry. Clock skew tolerance is deployment-configured, not protocol-mandated. When `issued_at` is present, verifiers may use it for audit and freshness assessment.

Full replay prevention (nonce caches, bounded TTL registries) is not part of the attestation object specification. It is deferred to a profile-level mechanism.

---

## Test Vectors

Conformance vectors for attestation-object canonicalization and the §8.4 canonical-byte rule live under [`conformance/canonicalization/`](../conformance/canonicalization/):

- [`004_attestation_object_example.json`](../conformance/canonicalization/004_attestation_object_example.json) — pins the canonical bytes of a full attestation object (8 keys, mixed shared-prefix sort order: `args_digest` / `attestation_version`, and `impact` / `intent_digest` / `issued_at`). Matches the worked example in [`docs/canonicalization.md` §9.4](canonicalization.md#94-attestation-object-example) and contributes the authoritative SHA-256 of the canonical bytes for that example.

Any implementation claiming conformance to this attestation-object draft MUST produce canonical bytes that match every attestation-object vector in that directory byte-exactly. The vectors are executed on every PR by the [`PIC Conformance` CI workflow](../.github/workflows/conformance.yml) via the [PIC Conformance Runner](../conformance/run.py).

Additional vectors covering digest-specific cases (`args_digest` over non-trivial args, `claims_digest` over multi-element claims arrays, `intent_digest` over Unicode intent strings) land alongside expanded attestation-object scope in v0.8.1+.

---

## Open Questions

The following questions are open for community feedback before this draft is formalized:

1. **`args_digest` scope:** Should the digest cover the full canonical `action.args`, or should tools be able to declare a normalized "execution args" subset? Full args is simpler; subsets are more resilient to transport-added metadata.

2. **`audience` semantics:** Should `audience` be a single string (verifier identity) or a list (multiple authorized verifiers)? Single string is simpler; lists support multi-verifier deployments.

3. **Digest algorithm agility:** Should the attestation object support algorithm identifiers for digests (e.g., `"args_digest_alg": "sha256"`), or is SHA-256 sufficient as the only normative algorithm for v1?

---

## Dependencies

- **PIC Canonical JSON v1** (Phase 1.1, **shipped in v0.8.0**) — the byte-level serialization rules used by this draft are normatively defined in [`docs/canonicalization.md`](canonicalization.md). The attestation object's digest and signing semantics (§8.1–§8.4 of that spec) are concrete and conformance-tested as of v0.8.0.
- **PIC/1.0 Normative Semantics** (Phase 1.4) — will formalize the Trust Axiom, freshness semantics, and registry definitions that the attestation object references.

---

## References

- [ROADMAP.md — Phase 1.1b](../ROADMAP.md) — Attestation Object v1 in the PIC roadmap
- [`docs/canonicalization.md`](canonicalization.md) — PIC Canonical JSON v1 (PIC-CJSON/1.0), normative as of v0.8.0
- [`conformance/canonicalization/`](../conformance/canonicalization/) — canonicalization and attestation-object conformance vectors
- [RFC 8785](https://www.rfc-editor.org/rfc/rfc8785) — JSON Canonicalization Scheme (JCS), the normative baseline for PIC Canonical JSON v1
- [RFC 3339](https://www.rfc-editor.org/rfc/rfc3339) — Date and Time on the Internet: Timestamps
- [RFC 4648](https://www.rfc-editor.org/rfc/rfc4648) — Base Encodings (Base64)
- [in-toto Statement](https://github.com/in-toto/attestation/blob/main/spec/v1/statement.md) — supply-chain attestation pattern (digest-based subject binding)
- [SLSA Provenance](https://slsa.dev/provenance/v1) — materials with digest sets
