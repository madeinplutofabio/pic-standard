# Evidence Verification Guide

PIC supports deterministic evidence verification that can upgrade provenance trust **in-memory** (fail‑closed).

- Evidence verification runs **before** the verifier (when enabled in your integration/CLI).
- Any verified evidence ID upgrades `provenance[].trust → trusted` for matching provenance IDs.
- Evidence lists may contain **mixed evidence types** (hash + signature) in the same proposal.

---

## Evidence v0.3 — Resolvable SHA‑256 artifacts (`type="hash"`)

PIC v0.3 adds **deterministic evidence verification**: evidence IDs can point to a real artifact and be validated via **SHA‑256**.

What this gives you:

- `evidence[].id` is no longer just a label — it can be **resolved** to a file (`file://...`) and **verified**.
- Verification is **fail‑closed**: if evidence can't be resolved or verified, high‑impact actions are blocked.
- "Trusted" becomes an **output** of verification (in‑memory): verified evidence IDs upgrade `provenance[].trust` → `trusted` before the verifier runs.

### Verify hash evidence

```bash
pic-cli evidence-verify examples/financial_hash_ok.json
```

Expected output:

```text
✅ Schema valid
✅ Evidence invoice_123: sha256 verified
✅ Evidence verification passed
```

### Fail (expected)

```bash
pic-cli evidence-verify examples/failing/financial_hash_bad.json
```

Expected output:

```text
✅ Schema valid
❌ Evidence invoice_123: sha256 mismatch (expected ..., got ...)
❌ Evidence verification failed
```

### Gate the verifier on evidence

Full pipeline: schema → evidence verify → provenance upgrade → verifier:

```bash
pic-cli verify examples/financial_hash_ok.json --verify-evidence
```

Fail‑closed:

```bash
pic-cli verify examples/failing/financial_hash_bad.json --verify-evidence
```

### Hash evidence references (`file://`)

`file://artifacts/invoice_123.txt` is resolved relative to the JSON proposal directory:

- `examples/financial_hash_ok.json` → `examples/artifacts/invoice_123.txt`

Evidence is sandboxed: the resolved path must stay under the configured `evidence_root_dir` (default: the proposal directory / server-configured root).

**On Windows, recompute SHA‑256 with:**

```powershell
Get-FileHash .\examples\artifacts\invoice_123.txt -Algorithm SHA256
```

---

## Evidence v0.4 — Signature evidence (Ed25519) (`type="sig"`)

PIC v0.4 adds **signature verification** so approvals can be endorsed by trusted signers (CFO, internal service, billing system) **without shipping the raw artifact**.

### How it works

The proposal includes an evidence entry with:
- `payload` (the exact bytes-to-verify, as UTF‑8 string)
- `signature` (base64 Ed25519 signature)
- `key_id` (public key identifier)

The verifier resolves `key_id` against a **trusted keyring** (not inside the proposal).

> Canonicalization is the caller's responsibility. If you change whitespace, ordering, or separators in `payload`, signatures will fail.

### Install

```bash
pip install "pic-standard[crypto]"
```

### Verify signature evidence

Signed example:

```bash
pic-cli evidence-verify examples/financial_sig_ok.json
```

Expected output:

```text
✅ Schema valid
✅ Evidence approval_123: signature verified (key_id='demo_signer_v1')
✅ Evidence verification passed
```

Tampered example (expected fail):

```bash
pic-cli evidence-verify examples/failing/financial_sig_bad.json
```

Expected output:

```text
✅ Schema valid
❌ Evidence approval_123: signature invalid (key_id='demo_signer_v1')
❌ Evidence verification failed
```

---

## Mixed Evidence

Evidence lists may contain **mixed evidence types** (hash + signature) in the same proposal. Each evidence entry is verified independently according to its type.

---

## Enterprise Notes

### Evidence sandboxing

For server deployments (MCP, HTTP bridge), evidence file resolution is sandboxed:

- `evidence_root_dir` — configurable root directory for `file://` resolution
- `max_file_bytes` — maximum file size (default 5MB)

This prevents path traversal attacks and memory exhaustion.

### Fail-closed design

All evidence verification is fail-closed:

- Missing evidence file → blocked
- Hash mismatch → blocked
- Invalid signature → blocked
- Unknown key_id → blocked
- Expired/revoked key → blocked

---

## See Also

- [Keyring Guide](keyring.md) — managing trusted signers for signature evidence
- [OpenClaw Integration](openclaw-integration.md) — evidence verification in the HTTP bridge
