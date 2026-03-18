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

The PIC/1.0 proposal structure and wire-level schema have remained stable since the RFC anchor. Post-RFC changes in v0.6.x–v0.7.x primarily affected shared pipeline behavior, trust resolution, integration surface, and runtime efficiency rather than introducing a wire-format break.

**Current Python reference implementation:** v0.7.1
