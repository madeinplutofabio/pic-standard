# PIC Specification Status

## RFC-0001 (Defensive Publication)

[RFC-0001](RFC-0001-pic-standard.md) is the original defensive publication for the PIC/1.0 protocol baseline. It is intentionally preserved with its original [SHA-256 fingerprint manifest](RFC-0001.SHA256) to maintain provenance integrity.

**Versions covered by the anchored artifact:** v0.1.0 through v0.5.5

### Changes since the RFC anchor

| Version | What changed | Wire format impact |
|---------|-------------|--------------------|
| v0.6.0–v0.6.1 | Shared verification pipeline, Dependabot, smoke tests, `/v1/version` endpoint | None — internal refactoring + HTTP surface |
| v0.7.0 | Injectable `KeyResolver` protocol, lazy trust resolution, evidence hot path fix | None — SDK runtime behavior only |
| v0.7.1 | Deferred integration imports, CLI import isolation, specification status note | None — packaging/docs hygiene only |
| v0.7.5 | Trust sanitization (`strict_trust`), deprecation warning for self-asserted trust, attestation object draft, migration guide | None — behavioral option only; wire format unchanged |
| v0.8.0 | PIC Canonical JSON v1 spec (`docs/canonicalization.md`) + reference implementation (`pic_standard.canonical`), initial canonicalization + core conformance suite, conformance runner (`python -m conformance.run`), `PIC Conformance` CI job, refined attestation object draft with byte-level worked example | None — new capability added; existing proposals and signature verification paths unchanged. Canonicalization is not yet wired into evidence signing in v0.8.0. |

The PIC/1.0 proposal structure and wire-level schema have remained stable since the RFC anchor. Post-RFC changes in v0.6.x–v0.8.x primarily affected shared pipeline behavior, trust resolution, integration surface, runtime efficiency, and canonicalization/conformance tooling rather than introducing a wire-format break.

**Current Python reference implementation:** v0.8.0

---

## Canonical PIC Vocabulary

Authoritative term definitions are maintained in [`docs/vocabulary.md`](vocabulary.md). External crosswalks and registries (e.g. `aeoess/agent-governance-vocabulary`) should reference that file rather than recoining PIC terminology. When upstream PIC docs evolve a term, `vocabulary.md` is updated in the same PR; treat divergence between the two as a bug.
