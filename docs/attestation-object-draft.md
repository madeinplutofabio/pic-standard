# PIC Attestation Object v1 — Draft

> **Status:** DRAFT — non-normative, subject to change.
> This document is published for community feedback as part of PIC v0.7.5.
> It will be formalized in Phase 1.1b of the [PIC Roadmap](../ROADMAP.md).
>
> This draft uses proposed normative language (MUST, SHOULD, OPTIONAL) to preview
> intended Phase 1.1b semantics. These requirements are not binding until the
> attestation object specification is formally adopted.

---

## Motivation

PIC v0.7.x signs the `evidence.payload` field — a UTF-8 string whose content and canonicalization are the producer's responsibility. This works, but it has two structural weaknesses:

1. **Payload strings are fragile.** Semantically identical payloads can differ bytewise across producers, languages, and serialization libraries. There is no normative definition of what bytes constitute the "same" payload.

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

To avoid ambiguity, each digest is computed over a specific input:

- **`args_digest`** = SHA-256 of the canonicalized JSON representation of `action.args` (the args object exactly as it appears in the proposal, canonicalized via PIC Canonical JSON v1).
- **`claims_digest`** = SHA-256 of the canonicalized JSON representation of the full `claims` array, preserving proposal array order.
- **`intent_digest`** = SHA-256 of the raw UTF-8 bytes of the `intent` string (no JSON wrapping, no canonicalization — the string value directly).
- **`provenance_ids`** = provenance entry IDs listed in the same order as they appear in the proposal's `provenance` array.

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
  "signature": "<base64 Ed25519 signature over canonical bytes of payload>",
  "key_id": "org:finance-signer-2026"
}
```

The `payload` field contains the attestation object serialized as PIC Canonical JSON v1. The `signature` is computed over the exact bytes of that string.

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

The corresponding attestation object would be:

```json
{
  "attestation_version": "PIC-ATT/1.0",
  "tool": "payments_send",
  "args_digest": "<sha256_hex_of_canonicalized_args>",
  "impact": "money",
  "intent_digest": "<sha256_hex_of_utf8_intent>",
  "provenance_ids": ["approved_invoice"],
  "claims_digest": "<sha256_hex_of_canonicalized_claims>",
  "issued_at": "2026-04-03T12:00:00Z"
}
```

*(Placeholder digests shown — actual values depend on PIC Canonical JSON v1, which is not yet specified.)*

---

## Signing Process

1. **Construct** the attestation object from proposal fields, computing digests as specified above.
2. **Canonicalize** the attestation object using PIC Canonical JSON v1 (lexicographic keys, UTF-8, no whitespace, precision-critical fields as strings — per RFC 8785 baseline).
3. **Sign** the canonical bytes with Ed25519.
4. **Embed** the canonical JSON string as `payload` and the signature as `signature` in a `sig`-type evidence entry in the proposal's `evidence` array.

---

## Backward Compatibility

Existing `sig`-type evidence entries that do not contain `attestation_version` in their payload are treated as **v0 legacy mode**. The intended compatibility rule is that verifiers continue to accept v0 signatures until PIC/1.0 normative semantics specify otherwise.

New attestation-object signatures are identified by the presence of `attestation_version` in the parsed evidence payload.

---

## Freshness Semantics

When `expires_at` is present, the intended PIC/1.0 rule is reject-on-expiry. Clock skew tolerance is deployment-configured, not protocol-mandated. When `issued_at` is present, verifiers may use it for audit and freshness assessment.

Full replay prevention (nonce caches, bounded TTL registries) is not part of the attestation object specification. It is deferred to a profile-level mechanism.

---

## Open Questions

The following questions are open for community feedback before this draft is formalized:

1. **`args_digest` scope:** Should the digest cover the full canonical `action.args`, or should tools be able to declare a normalized "execution args" subset? Full args is simpler; subsets are more resilient to transport-added metadata.

2. **`audience` semantics:** Should `audience` be a single string (verifier identity) or a list (multiple authorized verifiers)? Single string is simpler; lists support multi-verifier deployments.

3. **Digest algorithm agility:** Should the attestation object support algorithm identifiers for digests (e.g., `"args_digest_alg": "sha256"`), or is SHA-256 sufficient as the only normative algorithm for v1?

---

## Dependencies

- **PIC Canonical JSON v1** (Phase 1.1) — defines the byte-level serialization rules for canonicalization. The attestation object cannot be fully specified or implemented until canonicalization is normative.
- **PIC/1.0 Normative Semantics** (Phase 1.4) — will formalize the Trust Axiom, freshness semantics, and registry definitions that the attestation object references.

---

## References

- [ROADMAP.md — Phase 1.1b](../ROADMAP.md) — Attestation Object v1 in the PIC roadmap
- [RFC 8785](https://www.rfc-editor.org/rfc/rfc8785) — JSON Canonicalization Scheme (JCS)
- [RFC 3339](https://www.rfc-editor.org/rfc/rfc3339) — Date and Time on the Internet: Timestamps
- [RFC 4648](https://www.rfc-editor.org/rfc/rfc4648) — Base Encodings (Base64)
- [in-toto Statement](https://github.com/in-toto/attestation/blob/main/spec/v1/statement.md) — supply-chain attestation pattern (digest-based subject binding)
- [SLSA Provenance](https://slsa.dev/provenance/v1) — materials with digest sets
