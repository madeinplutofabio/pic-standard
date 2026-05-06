# Migrating to Verifier-Derived Trust

> **Applies to:** PIC v0.7.5 → v1.0 migration path
>
> This guide explains the trust model change introduced in v0.7.5 and how to
> prepare your deployment for PIC/1.0, where trust sanitization becomes the
> only conformant mode.

---

## What Is Changing

In PIC v0.7.x and earlier, the verification pipeline ultimately treats inbound `provenance[].trust` as authoritative for high-impact authorization unless evidence verification upgrades or challenges it. If a proposal declares `trust: "trusted"`, the verifier treats that provenance entry as trusted for the purpose of high-impact authorization — even when no evidence verification has occurred.

This creates a **config hazard**: a deployment that does not enable evidence verification (the current default) will accept self-asserted trust for high-impact actions like `money`, `privacy`, and `irreversible`. In that configuration, prompt injection or a misconfigured adapter can declare `trust: "trusted"` and bypass the security boundary.

Starting in v0.8.0, PIC introduces a migration path to **verifier-derived trust**, where trust is never accepted from the proposal — it is computed solely from successful evidence verification.

This migration changes verifier behavior and integration defaults over time; it does not change the PIC proposal wire format in v0.8.0. Existing proposals continue to parse and validate against the same JSON Schema.

---

## Timeline

| Version | Behavior |
|---------|----------|
| **v0.7.x** | `provenance[].trust` accepted at face value. No warnings. |
| **v0.8.0** | `PICTrustFutureWarning` emitted when self-asserted `trust="trusted"` is present and effective evidence verification will not run. New `strict_trust` pipeline option available (default `False`). Wire format unchanged. |
| **v1.0** | `strict_trust=True` is the default and the only conformant mode. Non-sanitizing mode is explicitly **legacy and non-conformant** — implementations that disable trust sanitization MUST NOT claim PIC/1.0 conformance. |

---

## The Warning

When you upgrade to v0.8.0, you may see this warning:

```
PICTrustFutureWarning: PIC deprecation: proposal contains provenance with
trust='trusted' but effective evidence verification will not run for this
proposal. In PIC/1.0, trust will be verifier-derived only — self-asserted
trust will be sanitized to 'untrusted'. To migrate: provide verifiable
evidence (hash or signature) and enable verify_evidence=True where evidence
will actually be enforced, or opt in early with strict_trust=True. See
docs/migration-trust-sanitization.md for details.
```

This warning fires when **all three** of these conditions are true:

1. `strict_trust=False` (the current default)
2. At least one provenance entry has `trust="trusted"`
3. Effective evidence verification will not run for this proposal

**Important:** The warning is based on whether evidence verification will *actually execute*, not just whether `verify_evidence=True` is set. Evidence verification only runs when both `verify_evidence=True` AND either evidence entries are present in the proposal or policy requires evidence for the resolved impact. Without either condition, the evidence step is skipped and inbound trust is still accepted at face value.

---

## Migration Steps

### Step 1: Audit

Identify deployments that rely on self-asserted trust without evidence:

- Search for proposals where `provenance[].trust == "trusted"` but no `evidence` array is present.
- Check pipeline/guard configurations for `verify_evidence=False` (the default).
- Review policy configurations: does `require_evidence_for_impacts` include the impacts your tools use?

### Step 2: Add Evidence

For each high-impact tool flow that currently relies on self-asserted trust, add verifiable evidence:

**Hash evidence** (simplest — proves a file artifact exists and is unmodified):

```json
{
  "id": "invoice_evidence",
  "type": "hash",
  "ref": "file://artifacts/invoice_123.pdf",
  "sha256": "a1b2c3d4..."
}
```

**Signature evidence** (strongest — proves a trusted signer attested the payload):

```json
{
  "id": "invoice_evidence",
  "type": "sig",
  "ref": "inline:invoice-attestation",
  "payload": "invoice_123 approved by finance team",
  "alg": "ed25519",
  "signature": "<base64 signature>",
  "key_id": "org:finance-signer"
}
```

See [docs/evidence.md](evidence.md) for the full evidence guide.

### Step 3: Enable Verification

Update your pipeline or guard configuration to enable evidence verification:

**Pipeline (direct):**

```python
from pic_standard.pipeline import PipelineOptions, verify_proposal

result = verify_proposal(proposal, options=PipelineOptions(
    verify_evidence=True,
    # ... other options
))
```

**MCP guard:**

```python
from pic_standard.integrations.mcp_pic_guard import guard_mcp_tool

guarded = guard_mcp_tool(
    "payments_send", tool_fn,
    policy=policy,
    verify_evidence=True,
)
```

**LangGraph:**

```python
from pic_standard.integrations import PICToolNode

node = PICToolNode(
    tools=[payments_send],
    verify_evidence=True,
)
```

**Important caveat:** Enabling `verify_evidence=True` alone is not sufficient unless verifiable evidence entries (hash or signature) are provided in the proposal or policy requires evidence for the action's impact. Without either condition, the evidence verification step does not run, and inbound trust is still accepted at face value. For immediate v1.0-style behavior, use `strict_trust=True` (see Step 4).

### Step 4: Opt In Early

To test v1.0 behavior now, enable `strict_trust=True`:

```python
# Pipeline
result = verify_proposal(proposal, options=PipelineOptions(
    strict_trust=True,
    verify_evidence=True,
))

# MCP guard
guarded = guard_mcp_tool(
    "payments_send", tool_fn,
    policy=policy,
    strict_trust=True,
    verify_evidence=True,
)

# LangGraph
node = PICToolNode(
    tools=[payments_send],
    strict_trust=True,
    verify_evidence=True,
)
```

When `strict_trust=True`:

- All inbound `provenance[].trust` values are sanitized to `"untrusted"` before verification.
- Evidence verification + trust upgrade is the only path to `"trusted"` status.
- High-impact proposals without valid evidence will be blocked.
- The `PICTrustFutureWarning` is not emitted (strict mode acts, it does not warn).

---

## FAQ

**Q: Will my existing low-impact tools break?**

No. Trust sanitization only affects the allow/block decision for high-impact actions (`money`, `privacy`, `irreversible`). Low-impact actions (`read`, `write`, `compute`, `external`) do not require trusted provenance, so sanitization has no effect on them.

**Q: Can I suppress the warning without migrating?**

You can filter `PICTrustFutureWarning` using Python's `warnings` module, but this only hides the symptom. The underlying config hazard remains, and your deployment will break when v1.0 makes strict trust the only conformant mode.

**Q: What if I use `verify_evidence=True` but my proposals have no evidence?**

The warning will still fire, because evidence verification will not actually run without evidence entries or a policy requirement. This is by design — `verify_evidence=True` is necessary but not sufficient.

**Q: What happens to proposals with `trust: "semi_trusted"`?**

**Today (v0.8.0):** in strict mode, `semi_trusted` is sanitized to `"untrusted"`. Only evidence verification can upgrade trust. The `PICTrustFutureWarning` (described above) only fires for `trust="trusted"` — that warning targets the most dangerous case (self-asserted full trust); `semi_trusted` is handled silently in strict mode.

**v0.8.1 (planned):** `semi_trusted` enters formal deprecation. A new `PICSemiTrustedDeprecationWarning` will fire at all public proposal-ingestion paths (the shared schema-validation boundary) whenever `trust: "semi_trusted"` is observed, regardless of strict-trust mode. The warning cites this guide and the [PIC Roadmap](../ROADMAP.md) for context.

**v0.9.0 (planned):** `"semi_trusted"` is **removed** from the trust enum entirely. Proposals carrying it will fail schema validation. The only conformant trust values become `"trusted"` and `"untrusted"`, with `"trusted"` requiring evidence verification under strict mode (the v1.0 default).

**Migration path for producers using `trust: "semi_trusted"` today:**
1. Treat the value as deprecated immediately. Plan to remove it before v0.9.0.
2. Replace `trust: "semi_trusted"` with `trust: "untrusted"` now. This is the forward-compatible choice for all producers.
3. If the proposal carries verifiable evidence (hash, signature, attestation), keep that evidence attached and let the verifier derive effective trust from successful verification.
4. Do not rely on producer-declared trust labels for authorization. Under the trust axiom (v0.7.5), inbound `trust` is non-authoritative; only verifier-controlled context or successful evidence verification can establish trusted status.

See the [PIC Roadmap](../ROADMAP.md) — Phase 0 (this entry) and Phase 1 (`semi_trusted` deprecation in v0.8.1) — for the full trajectory and rationale.

---

## References

- [PIC Evidence Guide](evidence.md) — how to add hash and signature evidence
- [PIC Keyring Guide](keyring.md) — managing trusted signing keys
- [Attestation Object Draft](attestation-object-draft.md) — the future signing target (community feedback welcome)
