"""
PIC Shared Verification Pipeline — single source of truth.

Every consumer (MCP guard, LangGraph, CLI, HTTP bridge) delegates to
``verify_proposal()`` instead of reimplementing the verification chain.

This module is the ONE function that conformance tests will target.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from functools import lru_cache
from importlib import resources
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from jsonschema import ValidationError as JSValidationError
from jsonschema import validate as js_validate

from pic_standard.errors import PICError, PICErrorCode, _debug_enabled
from pic_standard.policy import PICPolicy
from pic_standard.verifier import ActionProposal

# v0.3+ evidence (optional — graceful degradation when crypto not installed)
try:
    from pic_standard.evidence import (
        EvidenceSystem,
        apply_verified_ids_to_provenance,
    )
except ImportError:  # pragma: no cover
    EvidenceSystem = None  # type: ignore[assignment,misc]
    apply_verified_ids_to_provenance = None  # type: ignore[assignment]

log = logging.getLogger("pic_standard.pipeline")


# ------------------------------------------------------------------
# Shared helpers (moved from mcp_pic_guard.py — single copy)
# ------------------------------------------------------------------

@dataclass
class PICEvaluateLimits:
    """Hard limits to avoid abuse / resource exhaustion."""
    max_proposal_bytes: int = 64_000         # 64KB JSON
    max_provenance_items: int = 64
    max_claims: int = 64
    max_evidence_items: int = 64
    max_eval_ms: int = 500                   # post-evaluation budget check (fail-closed), not a preemptive timeout


@lru_cache(maxsize=1)
def _load_packaged_schema() -> Dict[str, Any]:
    schema_text = (
        resources.files("pic_standard")
        .joinpath("schemas/proposal_schema.json")
        .read_text(encoding="utf-8")
    )
    return json.loads(schema_text)


def _proposal_size_bytes(proposal: Dict[str, Any]) -> int:
    return len(json.dumps(proposal, ensure_ascii=False).encode("utf-8"))


def _enforce_limits(proposal: Dict[str, Any], limits: PICEvaluateLimits) -> None:
    size = _proposal_size_bytes(proposal)
    if size > limits.max_proposal_bytes:
        raise PICError(
            code=PICErrorCode.LIMIT_EXCEEDED,
            message="PIC proposal exceeds max size",
            details={"max_bytes": limits.max_proposal_bytes, "actual_bytes": size},
        )

    prov = proposal.get("provenance") or []
    claims = proposal.get("claims") or []
    ev = proposal.get("evidence") or []

    if len(prov) > limits.max_provenance_items:
        raise PICError(
            PICErrorCode.LIMIT_EXCEEDED,
            "Too many provenance items",
            {"max": limits.max_provenance_items, "actual": len(prov)},
        )
    if len(claims) > limits.max_claims:
        raise PICError(
            PICErrorCode.LIMIT_EXCEEDED,
            "Too many claims",
            {"max": limits.max_claims, "actual": len(claims)},
        )
    if len(ev) > limits.max_evidence_items:
        raise PICError(
            PICErrorCode.LIMIT_EXCEEDED,
            "Too many evidence items",
            {"max": limits.max_evidence_items, "actual": len(ev)},
        )


# ------------------------------------------------------------------
# Pipeline input / output types
# ------------------------------------------------------------------

@dataclass
class PipelineOptions:
    """Configuration for a single ``verify_proposal()`` call."""
    tool_name: Optional[str] = None               # tool being invoked (used for binding + impact resolution)
    expected_tool: Optional[str] = None            # tool binding enforcement (usually == tool_name)
    policy: Optional[PICPolicy] = None
    limits: Optional[PICEvaluateLimits] = None     # None = skip limits
    verify_evidence: bool = False
    proposal_base_dir: Optional[Path] = None
    evidence_root_dir: Optional[Path] = None
    time_budget_ms: Optional[int] = None           # None = no budget; falls back to limits.max_eval_ms


@dataclass
class PipelineResult:
    """Outcome of ``verify_proposal()``.  Never raises — all errors captured here."""
    ok: bool
    action_proposal: Optional[ActionProposal] = None
    error: Optional[PICError] = None
    evidence_report: Any = None                    # Optional[EvidenceReport] — typed as Any to avoid import issues
    impact: Optional[str] = None                   # resolved impact (from policy + proposal), always normalized to str
    eval_ms: int = 0


# ------------------------------------------------------------------
# Private helpers (deduplicated — used pre-evidence and post-upgrade)
# ------------------------------------------------------------------

def _instantiate_action_proposal(
    proposal: Dict[str, Any],
) -> Tuple[Optional[ActionProposal], Optional[PICError]]:
    """Parse proposal via pydantic + verifier rules. Returns (ap, None) or (None, err)."""
    try:
        return ActionProposal(**proposal), None
    except Exception as e:
        msg = str(e) or "PIC contract violation"
        details = {"verifier_error": msg} if _debug_enabled() else None
        return None, PICError(
            code=PICErrorCode.VERIFIER_FAILED,
            message="PIC contract violation",
            details=details,
        )


def _verify_tool_binding(
    ap: ActionProposal, expected_tool: str,
) -> Optional[PICError]:
    """Enforce tool binding. Returns None on success, PICError on mismatch."""
    try:
        ap.verify_with_context(expected_tool=expected_tool)
        return None
    except Exception as e:
        msg = str(e) or "Tool binding mismatch"
        details = {"expected": expected_tool, "error": msg} if _debug_enabled() else None
        return PICError(
            code=PICErrorCode.TOOL_BINDING_MISMATCH,
            message="Tool binding mismatch",
            details=details,
        )


# ------------------------------------------------------------------
# Core pipeline: the ONE function conformance tests target
# ------------------------------------------------------------------

def verify_proposal(
    proposal: Dict[str, Any],
    *,
    options: Optional[PipelineOptions] = None,
) -> PipelineResult:
    """
    Run the full PIC verification pipeline.

    Pipeline steps (in order):
      1. Limits check (skip if ``options.limits`` is None)
      2. JSON Schema validation
      3. Resolve impact (policy + proposal, falls back to expected_tool)
      4. ``ActionProposal`` instantiation (pydantic + PIC rules)
      5. Tool binding via ``verify_with_context`` (skip if ``expected_tool`` is None)
      6. Evidence verification — gated by impact + policy OR presence of evidence entries
      7. Time budget check (effective_budget_ms from time_budget_ms or limits.max_eval_ms)

    Returns ``PipelineResult`` — **never raises**.
    """
    opts = options or PipelineOptions()
    t0 = time.perf_counter()

    def _elapsed_ms() -> int:
        return int((time.perf_counter() - t0) * 1000)

    def _fail(err: PICError, *, impact: Optional[str] = None) -> PipelineResult:
        return PipelineResult(ok=False, error=err, impact=impact, eval_ms=_elapsed_ms())

    try:
        # 1. Limits check
        if opts.limits is not None:
            _enforce_limits(proposal, opts.limits)

        # 2. JSON Schema validation
        schema = _load_packaged_schema()
        try:
            js_validate(instance=proposal, schema=schema)
        except JSValidationError as e:
            return _fail(PICError(
                code=PICErrorCode.SCHEMA_INVALID,
                message=f"PIC schema validation failed: {e.message}",
            ))

        # 3. Resolve impact (fall back to expected_tool for LangGraph)
        tool_for_policy = opts.tool_name or opts.expected_tool
        proposal_impact = proposal.get("impact")
        if opts.policy and tool_for_policy:
            impact: Optional[str] = opts.policy.get_tool_impact(
                tool_for_policy, proposal_impact=proposal_impact,
            )
        else:
            impact = proposal_impact
        # Normalize enum-like impacts to strings for comparisons / serialization
        if hasattr(impact, "value"):
            impact = impact.value

        # 4. ActionProposal instantiation (pydantic + verifier rules)
        ap, err = _instantiate_action_proposal(proposal)
        if err is not None:
            return _fail(err, impact=impact)

        # 5. Tool binding
        if opts.expected_tool is not None:
            bind_err = _verify_tool_binding(ap, opts.expected_tool)  # type: ignore[arg-type]
            if bind_err is not None:
                return _fail(bind_err, impact=impact)

        # 6. Evidence verification
        evidence_report = None
        if opts.verify_evidence:
            evidence_entries = proposal.get("evidence") or []

            # Normalize policy set (enum safety)
            require_for: set[str] = set()
            if opts.policy:
                require_for = {
                    i.value if hasattr(i, "value") else i
                    for i in (opts.policy.require_evidence_for_impacts or [])
                }

            evidence_required_by_policy = bool(impact and impact in require_for)
            should_verify = evidence_required_by_policy or bool(evidence_entries)

            if should_verify:
                if EvidenceSystem is None or apply_verified_ids_to_provenance is None:
                    return _fail(PICError(
                        code=PICErrorCode.EVIDENCE_FAILED,
                        message="Evidence verification requested but evidence module is unavailable",
                    ), impact=impact)

                es = EvidenceSystem()  # type: ignore[misc]
                base_dir = opts.proposal_base_dir or Path(".").resolve()
                root_dir = opts.evidence_root_dir or base_dir

                evidence_report = es.verify_all(  # type: ignore[union-attr]
                    proposal, base_dir=base_dir, evidence_root_dir=root_dir,
                )

                # EVIDENCE_REQUIRED only when policy mandates it AND no entries
                if evidence_required_by_policy and not evidence_report.results:
                    return _fail(PICError(
                        code=PICErrorCode.EVIDENCE_REQUIRED,
                        message="Evidence required for this impact but no evidence entries were provided",
                        details={"tool": tool_for_policy, "impact": impact},
                    ), impact=impact)

                if not evidence_report.ok:
                    failed = [{"id": r.id, "message": r.message} for r in evidence_report.results if not r.ok]
                    return _fail(PICError(
                        code=PICErrorCode.EVIDENCE_FAILED,
                        message="Evidence verification failed",
                        details={"failed": failed},
                    ), impact=impact)

                # Trust upgrade + re-verify
                # Returns new dict — does not mutate caller's proposal
                upgraded = apply_verified_ids_to_provenance(proposal, evidence_report.verified_ids)

                ap, err = _instantiate_action_proposal(upgraded)
                if err is not None:
                    return _fail(err, impact=impact)

                # Re-verify tool binding on upgraded proposal
                if opts.expected_tool is not None:
                    bind_err = _verify_tool_binding(ap, opts.expected_tool)  # type: ignore[arg-type]
                    if bind_err is not None:
                        return _fail(bind_err, impact=impact)

        # 7. Time budget check (effective budget: explicit > limits.max_eval_ms)
        eval_ms = _elapsed_ms()
        effective_budget_ms = opts.time_budget_ms
        if effective_budget_ms is None and opts.limits is not None:
            effective_budget_ms = opts.limits.max_eval_ms
        if effective_budget_ms is not None and eval_ms > effective_budget_ms:
            return _fail(PICError(
                code=PICErrorCode.LIMIT_EXCEEDED,
                message="PIC evaluation exceeded time budget",
                details={"max_eval_ms": effective_budget_ms, "eval_ms": eval_ms},
            ), impact=impact)

        return PipelineResult(
            ok=True,
            action_proposal=ap,
            evidence_report=evidence_report,
            impact=impact,
            eval_ms=eval_ms,
        )

    except PICError as e:
        # Limits check raises PICError — catch and wrap
        return _fail(e, impact=proposal.get("impact"))

    except Exception as e:
        # Unexpected error → fail closed
        log.exception("Unexpected error in PIC pipeline")
        details = {"exception_type": type(e).__name__, "exception": str(e)} if _debug_enabled() else None
        return _fail(PICError(
            code=PICErrorCode.INTERNAL_ERROR,
            message="Internal error in PIC verification pipeline",
            details=details,
        ), impact=proposal.get("impact"))
