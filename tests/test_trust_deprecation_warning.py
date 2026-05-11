"""Tests for PIC v0.8.x trust deprecation warnings.

Covers two warning surfaces:

- ``PICTrustFutureWarning`` (v0.7.5): self-asserted ``trust='trusted'``
  under non-strict mode where evidence verification will not actually run.

- ``PICSemiTrustedDeprecationWarning`` (v0.8.1): inbound
  ``trust='semi_trusted'`` is deprecated; canonical normalization is the
  ``Provenance.trust`` field validator in ``pic_standard.verifier``.

Plus a verdict-regression matrix that pins v0.8.0 baseline outcomes for
representative example proposals, so any future refactor that touches the
dict-vs-model boundary surfaces immediately as a CI failure.
"""

from __future__ import annotations

import json
import warnings
from pathlib import Path

import pytest
from conftest import make_proposal
from pic_standard.errors import PICErrorCode
from pic_standard.pipeline import (
    PICTrustFutureWarning,
    PipelineOptions,
    verify_proposal,
)
from pic_standard.verifier import (
    ActionProposal,
    PICSemiTrustedDeprecationWarning,
    Provenance,
    TrustLevel,
)


class TestTrustFutureWarning:
    """PICTrustFutureWarning fires when self-asserted trust is present and
    effective evidence verification will not run for the proposal."""

    def test_warning_fires_on_self_asserted_trust_without_evidence(self) -> None:
        """trust='trusted' + verify_evidence=False → warning emitted, result still ok."""
        proposal = make_proposal(trust="trusted", impact="money")
        with pytest.warns(PICTrustFutureWarning):
            result = verify_proposal(
                proposal,
                options=PipelineOptions(verify_evidence=False, strict_trust=False),
            )
        assert result.ok

    def test_no_warning_when_evidence_will_actually_run(self) -> None:
        """trust='trusted' + verify_evidence=True + evidence entries present → no warning.

        Evidence will actually run, so no migration warning is needed.
        We use a deliberately invalid evidence entry to prove the evidence path
        was taken (the pipeline should fail with EVIDENCE_FAILED).
        """
        proposal = make_proposal(
            trust="trusted",
            impact="money",
            extra_evidence=[
                {
                    "id": "approved_invoice",
                    "type": "hash",
                    "ref": "file://nonexistent.txt",
                    "sha256": "0" * 64,
                }
            ],
        )
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            result = verify_proposal(
                proposal,
                options=PipelineOptions(verify_evidence=True, strict_trust=False),
            )
        pic_warnings = [w for w in caught if issubclass(w.category, PICTrustFutureWarning)]
        assert not pic_warnings
        # Prove the evidence path was actually taken
        assert not result.ok
        assert result.error is not None
        assert result.error.code == PICErrorCode.EVIDENCE_FAILED

    def test_no_warning_when_strict_trust_enabled(self) -> None:
        """strict_trust=True → blocks, does not warn."""
        proposal = make_proposal(trust="trusted", impact="money")
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            result = verify_proposal(
                proposal,
                options=PipelineOptions(strict_trust=True),
            )
        pic_warnings = [w for w in caught if issubclass(w.category, PICTrustFutureWarning)]
        assert not pic_warnings
        assert not result.ok  # blocked by sanitization

    def test_no_warning_when_trust_is_untrusted(self) -> None:
        """trust='untrusted' → no warning (nothing to warn about)."""
        proposal = make_proposal(
            trust="untrusted",
            impact="read",
            tool="docs_search",
            intent="Search docs",
        )
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            verify_proposal(
                proposal,
                options=PipelineOptions(verify_evidence=False),
            )
        pic_warnings = [w for w in caught if issubclass(w.category, PICTrustFutureWarning)]
        assert not pic_warnings

    def test_no_warning_for_semi_trusted(self) -> None:
        """trust='semi_trusted' → no PICTrustFutureWarning (only 'trusted' triggers).

        Note: PICSemiTrustedDeprecationWarning DOES fire for semi_trusted under
        v0.8.1+ (covered by TestSemiTrustedDeprecationWarning below). This test
        only asserts the absence of the OTHER warning class.
        """
        proposal = make_proposal(
            trust="semi_trusted",
            impact="read",
            tool="docs_search",
            intent="Search docs",
        )
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            verify_proposal(
                proposal,
                options=PipelineOptions(verify_evidence=False),
            )
        pic_warnings = [w for w in caught if issubclass(w.category, PICTrustFutureWarning)]
        assert not pic_warnings

    def test_warning_fires_when_verify_evidence_true_but_evidence_will_not_run(self) -> None:
        """verify_evidence=True but NO evidence entries and NO policy → warning fires.

        This is the nuance case: the flag is set but evidence won't actually execute
        because there are no evidence entries and no policy requiring evidence.
        """
        proposal = make_proposal(trust="trusted", impact="money")
        with pytest.warns(PICTrustFutureWarning):
            result = verify_proposal(
                proposal,
                options=PipelineOptions(verify_evidence=True, strict_trust=False),
            )
        assert result.ok

    def test_warning_message_contains_migration_guidance(self) -> None:
        """Warning text must mention key migration concepts."""
        proposal = make_proposal(trust="trusted", impact="money")
        with pytest.warns(PICTrustFutureWarning) as record:
            verify_proposal(
                proposal,
                options=PipelineOptions(verify_evidence=False, strict_trust=False),
            )
        assert len(record) == 1
        msg = str(record[0].message)
        assert "verifiable evidence" in msg
        assert "strict_trust=True" in msg
        assert "migration-trust-sanitization.md" in msg


# ============================================================================
# v0.8.1: PICSemiTrustedDeprecationWarning
# ============================================================================


class TestSemiTrustedDeprecationWarning:
    """PICSemiTrustedDeprecationWarning fires when a Provenance entry is
    constructed with trust='semi_trusted'.

    The pydantic field validator on Provenance.trust is the canonical
    normalization boundary for v0.8.1+: it warns + normalizes the value
    to TrustLevel.UNTRUSTED at construction time, in all modes.
    """

    def test_warning_fires_on_direct_construction_string_form(self) -> None:
        """Provenance(trust='semi_trusted') as raw string → warns + normalizes."""
        with pytest.warns(PICSemiTrustedDeprecationWarning):
            p = Provenance(id="x", trust="semi_trusted")
        assert p.trust == TrustLevel.UNTRUSTED

    def test_warning_fires_on_direct_construction_enum_form(self) -> None:
        """Provenance(trust=TrustLevel.SEMI_TRUSTED) as enum → warns + normalizes.

        TrustLevel is a str-Enum, so equality unifies string and enum forms.
        """
        with pytest.warns(PICSemiTrustedDeprecationWarning):
            p = Provenance(id="x", trust=TrustLevel.SEMI_TRUSTED)
        assert p.trust == TrustLevel.UNTRUSTED

    def test_warning_cascades_through_action_proposal_per_entry(self) -> None:
        """Constructing ActionProposal with N semi_trusted entries fires N warnings
        (one per Provenance instance — the field-validator fires per-instance,
        not once-per-proposal)."""
        proposal_dict = {
            "protocol": "PIC/1.0",
            "intent": "x",
            "impact": "read",
            "provenance": [
                {"id": "a", "trust": "semi_trusted"},
                {"id": "b", "trust": "semi_trusted"},
            ],
            "claims": [{"text": "x", "evidence": ["a"]}],
            "action": {"tool": "t", "args": {}},
        }
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            ap = ActionProposal(**proposal_dict)
        semi = [w for w in caught if issubclass(w.category, PICSemiTrustedDeprecationWarning)]
        assert len(semi) == 2  # one warning per semi_trusted entry
        assert all(p.trust == TrustLevel.UNTRUSTED for p in ap.provenance)

    def test_verify_proposal_non_strict_fires_warning_and_normalizes(self) -> None:
        """Non-strict mode: bridge helper triggers validator, warning fires,
        semi_trusted -> untrusted, existing verdict behavior preserved."""
        proposal = make_proposal(
            trust="semi_trusted",
            impact="read",
            tool="docs_search",
            intent="search",
        )
        with pytest.warns(PICSemiTrustedDeprecationWarning):
            r = verify_proposal(proposal, options=PipelineOptions(strict_trust=False))
        assert r.ok  # low impact, normalization to untrusted is fine

    def test_verify_proposal_strict_trust_still_fires_warning(self) -> None:
        """Strict mode: warning STILL fires because the bridge helper runs BEFORE
        strict-trust flattening. This is the load-bearing Path A property — the
        whole reason the pipeline triggers the validator early instead of relying
        on full ActionProposal instantiation alone."""
        proposal = make_proposal(
            trust="semi_trusted",
            impact="read",
            tool="docs_search",
            intent="search",
        )
        with pytest.warns(PICSemiTrustedDeprecationWarning):
            r = verify_proposal(proposal, options=PipelineOptions(strict_trust=True))
        assert r.ok  # low impact

    def test_mixed_provenance_only_fires_for_semi_trusted_entries(self) -> None:
        """Proposal with one trusted, one semi_trusted, one untrusted entry:
        exactly one PICSemiTrustedDeprecationWarning fires (for the single
        semi_trusted entry); trusted and untrusted pass through unchanged."""
        proposal = make_proposal(
            trust="trusted",
            impact="read",
            tool="docs_search",
            intent="search",
            extra_provenance=[
                {"id": "p2", "trust": "semi_trusted"},
                {"id": "p3", "trust": "untrusted"},
            ],
        )
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            verify_proposal(proposal, options=PipelineOptions(strict_trust=False))
        semi = [w for w in caught if issubclass(w.category, PICSemiTrustedDeprecationWarning)]
        assert len(semi) == 1

    def test_no_warning_when_no_semi_trusted_present(self) -> None:
        """Regression guard: no semi_trusted -> no PICSemiTrustedDeprecationWarning."""
        proposal = make_proposal(
            trust="untrusted",
            impact="read",
            tool="docs_search",
            intent="search",
        )
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            verify_proposal(proposal, options=PipelineOptions(strict_trust=False))
        semi = [w for w in caught if issubclass(w.category, PICSemiTrustedDeprecationWarning)]
        assert not semi

    def test_warning_message_contains_migration_guidance(self) -> None:
        """Warning text mentions key migration concepts."""
        with pytest.warns(PICSemiTrustedDeprecationWarning) as record:
            Provenance(id="x", trust="semi_trusted")
        assert len(record) == 1
        msg = str(record[0].message)
        assert "deprecated in v0.8.1" in msg
        assert "v0.9.0" in msg
        assert "migration-trust-sanitization.md" in msg


class TestPICTrustFutureWarningStillWorksAfterRefactor:
    """Regression guard: PICTrustFutureWarning behavior is unchanged after
    v0.8.1's bridge-helper insertion. The two warnings are independent
    (different layers, different conditions)."""

    def test_self_asserted_trusted_still_warns_after_v081_refactor(self) -> None:
        """The existing self-asserted 'trusted' + no-evidence warning still fires
        after the v0.8.1 bridge helper was inserted. The bridge only normalizes
        semi_trusted; it does not interfere with the trusted-flow warning logic."""
        proposal = make_proposal(trust="trusted", impact="money")
        with pytest.warns(PICTrustFutureWarning):
            r = verify_proposal(
                proposal,
                options=PipelineOptions(verify_evidence=False, strict_trust=False),
            )
        assert r.ok


# ============================================================================
# v0.8.1: Verdict-regression matrix (codified, parametrized)
# ============================================================================
#
# Permanent CI guard against any future refactor that touches the dict-vs-model
# boundary in pipeline.verify_proposal(). Asserts only the STABLE verdict-bearing
# fields of PipelineResult — `ok` (bool) and, when ok=False, `error.code`
# compared against a PICErrorCode enum member. Does NOT assert on
# `error.message`, `impact`, `eval_ms`, or other unstable fields. Does NOT
# compare against the enum's `.value` string — the enum member is the stable
# API; `.value` is an implementation detail.
#
# Expected baseline values are HARDCODED LITERALS (enum members for error
# codes; bool / None for verdicts) captured at v0.8.1 design time from the
# v0.8.0 baseline behavior. They are NOT derived at test time by calling
# verify_proposal() or any helper that shares a code path with the system
# under test — that would defeat the guard's purpose (the test would just
# assert that the current behavior matches the current behavior).
#
# Excluded: financial_sig_ok.json — its verify_evidence=True path requires
# keyring environment setup (PIC_KEYS_PATH or explicit key_resolver) and would
# make the regression matrix brittle. Sig-flow regression is covered by
# dedicated sig tests elsewhere in the suite.

EXAMPLES_DIR = Path(__file__).resolve().parent.parent / "examples"


# (filename, strict_trust, verify_evidence, expected_ok, expected_error_code_or_None)
VERDICT_REGRESSION_MATRIX: list[tuple[str, bool, bool, bool, PICErrorCode | None]] = [
    # Low-impact: always allowed regardless of trust
    ("compute_risk.json", False, False, True, None),
    ("compute_risk.json", False, True, True, None),
    ("compute_risk.json", True, False, True, None),
    ("compute_risk.json", True, True, True, None),
    ("read_only_query.json", False, False, True, None),
    ("read_only_query.json", False, True, True, None),
    ("read_only_query.json", True, False, True, None),
    ("read_only_query.json", True, True, True, None),
    # CANARY for "did instantiation move ahead of evidence verification?".
    # financial_hash_ok.json has high-impact (money) + untrusted provenance +
    # hash evidence. With verify_evidence=True the hash must verify and upgrade
    # trust to trusted BEFORE the contract check sees the model. If any future
    # refactor moves full ActionProposal instantiation ahead of evidence
    # verification, these two ok=True rows flip to ok=False — the test fails
    # immediately and points at the regression.
    ("financial_hash_ok.json", False, False, False, PICErrorCode.VERIFIER_FAILED),
    ("financial_hash_ok.json", False, True, True, None),  # canary
    ("financial_hash_ok.json", True, False, False, PICErrorCode.VERIFIER_FAILED),
    ("financial_hash_ok.json", True, True, True, None),  # canary (strict mode)
    # High-impact (money). Has cfo_signed_invoice_hash:trusted as load-bearing
    # entry. Non-strict: contract satisfied. Strict: all flattened to untrusted,
    # contract fails.
    ("financial_irreversible.json", False, False, True, None),
    ("financial_irreversible.json", False, True, True, None),
    ("financial_irreversible.json", True, False, False, PICErrorCode.VERIFIER_FAILED),
    ("financial_irreversible.json", True, True, False, PICErrorCode.VERIFIER_FAILED),
    # High-impact (privacy) with user_email_consent:trusted.
    ("privacy_risk.json", False, False, True, None),
    ("privacy_risk.json", False, True, True, None),
    ("privacy_risk.json", True, False, False, PICErrorCode.VERIFIER_FAILED),
    ("privacy_risk.json", True, True, False, PICErrorCode.VERIFIER_FAILED),
    # High-impact (irreversible) with lidar_safety_trigger:trusted as load-bearing.
    ("robotic_action.json", False, False, True, None),
    ("robotic_action.json", False, True, True, None),
    ("robotic_action.json", True, False, False, PICErrorCode.VERIFIER_FAILED),
    ("robotic_action.json", True, True, False, PICErrorCode.VERIFIER_FAILED),
]


@pytest.mark.parametrize(
    "filename,strict_trust,verify_evidence,expected_ok,expected_error_code",
    VERDICT_REGRESSION_MATRIX,
)
def test_verdict_regression_matrix(
    filename: str,
    strict_trust: bool,
    verify_evidence: bool,
    expected_ok: bool,
    expected_error_code: PICErrorCode | None,
) -> None:
    """Pins v0.8.0 baseline outcomes for representative example proposals.

    Asserts only the stable verdict-bearing fields. See module-level matrix
    comment for the design rationale.
    """
    proposal = json.loads((EXAMPLES_DIR / filename).read_text(encoding="utf-8"))

    # Suppress deprecation warnings — they fire for some examples (semi_trusted
    # in financial_irreversible/robotic_action pre-migration; PICTrustFutureWarning
    # for self-asserted trusted entries). The matrix asserts verdicts, not
    # warning emission. Warning emission is covered by the dedicated tests above.
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        result = verify_proposal(
            proposal,
            options=PipelineOptions(
                strict_trust=strict_trust,
                verify_evidence=verify_evidence,
                proposal_base_dir=EXAMPLES_DIR,
                evidence_root_dir=EXAMPLES_DIR,
            ),
        )

    assert result.ok is expected_ok, (
        f"verdict regression: {filename} "
        f"(strict_trust={strict_trust}, verify_evidence={verify_evidence}) "
        f"returned ok={result.ok}, expected ok={expected_ok}"
    )
    if not expected_ok:
        assert result.error is not None
        assert result.error.code == expected_error_code, (
            f"error.code regression: {filename} returned "
            f"{result.error.code!r}, expected {expected_error_code!r}"
        )


# ============================================================================
# v0.8.1: Public API surface — package-root re-export pin
# ============================================================================


class TestPublicAPISurface:
    """Pins v0.8.1's package-root re-export of both deprecation warning classes.

    Future refactors that touch ``sdk-python/pic_standard/__init__.py`` cannot
    silently drop these re-exports without this test failing.
    """

    def test_deprecation_warnings_importable_at_package_root(self) -> None:
        from pic_standard import (
            PICSemiTrustedDeprecationWarning as PicSemi,
        )
        from pic_standard import (
            PICTrustFutureWarning as PicTrust,
        )

        assert issubclass(PicSemi, FutureWarning)
        assert issubclass(PicTrust, FutureWarning)
