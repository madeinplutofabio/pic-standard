"""Tests for PIC v0.8 trust deprecation warning (PICTrustFutureWarning)."""

from __future__ import annotations

import warnings

import pytest

from pic_standard.errors import PICErrorCode
from pic_standard.pipeline import (
    PICTrustFutureWarning,
    PipelineOptions,
    verify_proposal,
)

from conftest import make_proposal


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
            extra_evidence=[{
                "id": "approved_invoice",
                "type": "hash",
                "ref": "file://nonexistent.txt",
                "sha256": "0" * 64,
            }],
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
            trust="untrusted", impact="read",
            tool="docs_search", intent="Search docs",
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
        """trust='semi_trusted' → no warning (only 'trusted' triggers)."""
        proposal = make_proposal(
            trust="semi_trusted", impact="read",
            tool="docs_search", intent="Search docs",
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
