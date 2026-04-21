# PIC Canonical JSON v1 — Conformance Vectors

This directory contains byte-exact conformance vectors for **PIC Canonical JSON v1** (PIC-CJSON/1.0), normatively defined in [`docs/canonicalization.md`](../../docs/canonicalization.md).

A conforming implementation of PIC-CJSON/1.0 MUST produce, for every `input` in every vector file in this directory, canonical output whose bytes are **byte-identical** to the vector's `expected_canonical_bytes_hex`, and whose SHA-256 digest is byte-identical to `expected_sha256_hex`.

These vectors are the executable conformance artifacts for the normative PIC-CJSON/1.0 specification. If the reference implementation and a vector disagree, the specification plus the vector's cited external source win, and the reference implementation is treated as a bug.

---

## Scope

Vectors in this directory cover canonicalization of in-memory values, i.e. the `canonicalize(value) -> bytes` API surface defined in [`docs/canonicalization.md`](../../docs/canonicalization.md) §7, plus the canonical-byte / canonical-JSON-digest rules exercised through that surface: §8.1, §8.2, and the canonical-byte rule in §8.4.

The following are explicitly **out of scope** for this directory:

- **§8.3 `intent_digest`** — this hashes the raw UTF-8 bytes of the `intent` string, not canonicalized JSON bytes, so it is tested in implementation unit tests rather than by vectors in this directory.
- **§8.4 transport/extraction behaviour** — parsing an evidence entry's `payload` string, extracting the attestation object, and re-canonicalizing before signing. That is a protocol-level flow, not a canonicalization primitive, and is tested separately under `conformance/core/` once evidence-mode vectors land. The canonical-byte rule of §8.4 (signing `canonicalize(attestation_object)`) **is** in scope and is exercised by the attestation-object worked-example vector.
- **PIC protocol constraints adjacent to canonicalization** — specifically, the Base64 variant rule (spec §7.10) and the file-hash rule (spec §7.11). These govern byte stability outside the JSON canonicalization algorithm itself and are covered by future evidence-profile conformance, per spec §12.
- **Duplicate object member names.** Duplicate keys are non-conformant input per spec §7.4 and MUST NOT appear as the `input` of any success vector. A future release MAY add raw-text (pre-parse) negative vectors that exercise duplicate-key rejection at a parser boundary, per spec §10.1; those will live in a separate subdirectory with their own format, because JSON object values in this directory are parsed by the harness before reaching `canonicalize()` and duplicate keys are collapsed at parse time.
- **Implementation-local rejection cases.** Inputs that cannot be represented as portable JSON values — host-language non-string keys, circular references, non-finite numbers (`NaN`, `+Infinity`, `-Infinity`) introduced outside a strict JSON parser, lone surrogates carried by host-language strings, and host-language types with no natural JSON mapping — are tested in implementation unit tests per spec §10.1, not here.

---

## Vector file format

Every vector file is a single JSON object with the following fields:

```json
{
  "id": "canon-NNN-short-slug",
  "description": "One-sentence human-readable description of what this vector tests.",
  "source": "RFC 8785 §3.2 Appendix A.1",
  "input": { "...": "..." },
  "expected_canonical_bytes_hex": "7b...",
  "expected_sha256_hex": "a1b2c3..."
}
```

### Field semantics

| Field | Type | Required | Meaning |
|---|---|---|---|
| `id` | string | yes | Stable identifier, matching the manifest entry. Format: `canon-<NNN>-<slug>`, where `<NNN>` is the three-digit file prefix and `<slug>` is a short kebab-case name. MUST be unique across this directory. |
| `description` | string | yes | One-sentence summary of what the vector covers. Not machine-interpreted. |
| `source` | string | yes | Where the expected output came from. See **External-seeding discipline** below. MUST be non-empty and MUST identify a specific source (RFC section + appendix, hand-verification with verifier name, or named second implementation with version). `"pic_standard.canonical"` alone is NOT an acceptable source. |
| `input` | any JSON value | yes | The non-canonical input. Encoded as ordinary JSON in the vector file; the harness parses it and hands the parsed value to `canonicalize()`. |
| `expected_canonical_bytes_hex` | string | yes | Lowercase hex encoding of the exact bytes `canonicalize(input)` MUST produce. No leading `0x`, no whitespace, no separators. |
| `expected_sha256_hex` | string | yes | Lowercase hex SHA-256 digest of `expected_canonical_bytes_hex` decoded to bytes. Redundant with `expected_canonical_bytes_hex` but kept for fast-path verification and to catch bit-flips. |

### Why hex, not a JSON string

The canonical output is stored as hex-encoded bytes rather than a JSON string because the vector file itself is not canonicalized — embedding canonical output as a JSON string would require the vector file to answer "what is the canonical form of a string containing canonical JSON?" recursively. Hex sidesteps that.

### Why both `expected_canonical_bytes_hex` and `expected_sha256_hex`

A runner that only checks the hash can miss cases where the canonical bytes disagree in a way that happens to collide (astronomically unlikely, but not the point — the redundancy is cheap). A runner that only checks the bytes can still report useful diagnostics but a digest mismatch is a fast-path signal. Both together also let the worked examples in `docs/canonicalization.md` §9 be mechanically cross-checked against a vector.

### Canonicality of the `input` field

The `input` field is parsed as ordinary JSON. Its in-file whitespace, key order, and number formatting have no protocol meaning — they are only the serialization the vector author chose. What matters is the **parsed value**, which the harness passes to `canonicalize()`. Vector authors SHOULD format `input` for readability (pretty-printed, arbitrary key order, etc.).

---

## External-seeding discipline

Vectors in this directory MUST NOT be generated solely by running inputs through `pic_standard.canonical` and committing its output. That would make the suite self-fulfilling: the reference implementation would pass its own vectors by definition, and any bug in the reference implementation would silently become "correct" behaviour.

Every vector's `expected_canonical_bytes_hex` MUST come from **at least one** of the following independent sources, which MUST be named in the `source` field:

1. **RFC 8785 appendix / worked examples.** RFC 8785 includes worked examples with canonical output. Vectors that reuse these are seeded by the RFC itself.
2. **Hand-verification against the spec.** The vector author computes the canonical form on paper by applying PIC-CJSON/1.0 rules byte-by-byte, with a reviewer independently re-checking. `source` MUST name the verifier(s), e.g. `"hand-verified by <initials or name>, 2026-04-18"`.
3. **Second implementation.** A non-PIC JCS implementation (e.g. the upstream `rfc8785.py` package at a named version, an npm JCS library at a named version, `jsontool`) produces the canonical bytes, which are then compared against the reference implementation. `source` MUST name the implementation and version, e.g. `"trailofbits/rfc8785.py v0.1.4"`.

If the only available source is "pic_standard.canonical produces this output", the vector is NOT acceptable and MUST NOT be committed. Vectors exist to hold the reference implementation accountable, not to certify it against itself.

### Using the reference implementation as a scaffold

The reference implementation MAY be used during authoring to propose a candidate `expected_canonical_bytes_hex`, but the commit MUST NOT rest on that proposal. The author still has to either match the candidate to an RFC-seeded source, hand-verify it against §7 of the spec, or cross-check it against a named second implementation. The `source` field records which.

---

## Required coverage

The suite MUST collectively cover at least the following behaviours. Individual vectors typically exercise one or two; the manifest is the list of what is actually covered. Section references below point to [`docs/canonicalization.md`](../../docs/canonicalization.md).

- **Key ordering (§7.2).** UTF-16 code unit ordering, including:
  - Simple ASCII keys.
  - Mixed-case keys (case sensitivity).
  - Non-ASCII keys in the BMP.
  - Keys containing supplementary-plane characters (so that UTF-16 surrogate-pair ordering is exercised, not just code-point ordering).
  - Nested objects where both outer and inner keys require sorting.
- **Array order preservation (§7.5).** Arrays are NOT sorted; element order comes from the input.
- **Whitespace (§7.6).** No insignificant whitespace is emitted.
- **String escaping (§7.7).** Minimal escape set including `"`, `\`, `\b`, `\f`, `\n`, `\r`, `\t`, and control characters `U+0000`..`U+001F`. Characters that MUST NOT be escaped (e.g. `/`) also covered by positive vectors.
- **Unicode passthrough (§7.8).** BMP and supplementary-plane characters round-trip byte-exactly as UTF-8 with no normalization applied.
- **Number serialization (§7.9).** Finite JSON numbers formatted per RFC 8785 / ECMAScript `Number.prototype.toString()` semantics, including:
  - Zero (`0`).
  - Small and large positive/negative integers within the safe range.
  - Values requiring scientific notation per the spec.
  - Values at the edge of IEEE 754 precision.
  - Integer-valued floats (MUST NOT carry a trailing `.0`).
- **Booleans and null (§7.12).** `true`, `false`, `null`.
- **Digest byte rules (§8.1 and §8.2).** At least one vector demonstrating `args_digest`-shaped input (arbitrary JSON value canonicalized then SHA-256'd) and one demonstrating a `claims`-array-shaped input.
- **Attestation object canonical bytes (§8.4 canonical-byte rule).** A worked-example vector matching the attestation-object worked example in §9 of the spec, used as the reference point for §8.4 canonical-byte computation. The §8.4 transport/extraction behaviour (parsing payload strings, etc.) is out of scope for this directory, as noted above.

### What is NOT covered here

The following behaviours are tested in reference-implementation unit tests (`sdk-python/pic_standard/canonical.py` exercised by `tests/test_canonical.py`), not in portable vectors, because their inputs cannot be represented reliably across JSON parsers and host runtimes.

**Rejection behaviours** — inputs that cannot be represented as valid JSON values in a shared vector file (per spec §10.1):

- Non-finite numeric values (`NaN`, `+Infinity`, `-Infinity`) introduced outside a strict JSON parser.
- Host-language structures with non-string keys (spec §7.3).
- Circular references among host-language objects.
- Host-language types with no natural JSON mapping (e.g. Python `set`, user-defined classes without a serializer, Python `tuple` where the spec reference implementation rejects tuples to surface intent ambiguity).
- Lone surrogate code points carried through host-language strings (spec §7.13).

**Host-representation-dependent positive behaviours** — inputs that are valid JSON in principle but whose round-trip through a parser is not portable across implementations:

- **Negative zero (spec §7.9).** When a host runtime preserves `-0` as a distinct float value, canonicalization MUST produce `0`. Portable JSON parsers do not uniformly preserve the `-0` / `+0` distinction on input: some collapse `-0` to `0` at parse time, some preserve it, and some lift `-0` to an integer zero. A portable vector with input literal `-0` therefore cannot have a deterministic expected outcome across conformant implementations. This requirement is enforced in unit tests, where a host `float` (or equivalent numeric type) carrying a known `-0` value is handed to the canonicalizer directly, bypassing the parser.

Other language bindings of PIC-CJSON/1.0 MUST likewise exercise these behaviours in their own unit tests, in whatever form is idiomatic for their host type system.

---

## File naming and numbering

Vector files follow `NNN_<slug>.json`, where `NNN` is a zero-padded three-digit decimal counter starting at `001`. Numbers are assigned in the order vectors are committed and are **never renumbered**. Gaps from removed vectors are left as-is (removal is a deliberate, documented act in the CHANGELOG).

The `id` field embeds the same number, e.g. file `003_key_ordering.json` has `id: "canon-003-key-ordering"`. The slug portion SHOULD match between filename and id.

---

## Relationship to the manifest

This directory is indexed by [`conformance/manifest.json`](../manifest.json). Every vector file in this directory MUST have a corresponding manifest entry with `"mode": "canonicalization"`. Adding a vector file without a manifest entry is a conformance-suite bug — the runner only executes what the manifest lists.

---

## Relationship to `pic_standard.canonical`

The Python reference implementation at [`sdk-python/pic_standard/canonical.py`](../../sdk-python/pic_standard/canonical.py) is one consumer of these vectors, exercised through `tests/test_canonical.py`. Any other language implementation of PIC-CJSON/1.0 — present or future — MUST pass the same vectors. The suite is deliberately language-neutral: JSON files + a hex expectation + a SHA-256 expectation are trivially consumable from Python, TypeScript, Go, Rust, and anything else that can parse JSON and decode hex.
