from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, Optional, Tuple

from importlib import resources
from jsonschema import ValidationError as JSValidationError
from jsonschema import validate as js_validate

from pic_standard.errors import PICError, PICErrorCode
from pic_standard.policy import PICPolicy
from pic_standard.verifier import ActionProposal

# v0.3+ evidence (optional)
try:
    from pic_standard.evidence import EvidenceSystem, apply_verified_ids_to_provenance
except Exception:  # pragma: no cover
    EvidenceSystem = None  # type: ignore
    apply_verified_ids_to_provenance = None  # type: ignore

log = logging.getLogger("pic_standard.mcp")


def _debug_enabled() -> bool:
    v = (os.getenv("PIC_DEBUG") or "").strip().lower()
    return v in {"1", "true", "yes", "on"}


def _mcp_error_payload(err: PICError) -> Dict[str, Any]:
    """
    MCP-facing error envelope.
    - Always includes code + message
    - Includes details ONLY when PIC_DEBUG is enabled (prevents leakage)
    """
    payload: Dict[str, Any] = {
        "code": err.code.value if hasattr(err.code, "value") else str(err.code),
        "message": err.message,
    }
    details = getattr(err, "details", None)
    if _debug_enabled() and isinstance(details, dict) and details:
        payload["details"] = details
    return payload


def _is_pic_envelope(obj: Any) -> bool:
    """Detect if obj already looks like PIC MCP envelope."""
    return isinstance(obj, dict) and ("isError" in obj) and ("error" in obj or "result" in obj)


def _wrap_success(result: Any) -> Dict[str, Any]:
    """Return deterministic success envelope."""
    if _is_pic_envelope(result):
        return result  # already wrapped
    return {"isError": False, "result": result}


@dataclass
class PICEvaluateLimits:
    """Hard limits to avoid abuse / resource exhaustion."""
    max_proposal_bytes: int = 64_000         # 64KB JSON
    max_provenance_items: int = 64
    max_claims: int = 64
    max_evidence_items: int = 64
    max_eval_ms: int = 500                  # policy evaluation budget (schema + verifier + evidence)


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


def verify_pic_proposal(proposal: Dict[str, Any]) -> ActionProposal:
    """
    Verify PIC proposal:
      1) JSON Schema validation
      2) Reference verifier (pydantic + PIC rules)

    NOTE:
    Tool binding is enforced in integrations via:
      ActionProposal.verify_with_context(expected_tool=...)
    """
    schema = _load_packaged_schema()

    try:
        js_validate(instance=proposal, schema=schema)
    except JSValidationError as e:
        raise PICError(
            code=PICErrorCode.SCHEMA_INVALID,
            message=f"PIC schema validation failed: {e.message}",
        ) from e

    try:
        ap = ActionProposal(**proposal)
        return ap
    except Exception as e:
        msg = str(e) or "PIC contract violation"
        if _debug_enabled():
            raise PICError(
                code=PICErrorCode.POLICY_VIOLATION,
                message="PIC contract violation",
                details={"verifier_error": msg},
            ) from e
        raise PICError(
            code=PICErrorCode.POLICY_VIOLATION,
            message="PIC contract violation",
        ) from e


def _audit_decision(
    *,
    decision: str,
    tool_name: str,
    impact: Optional[str],
    request_id: Optional[str] = None,
    reason_code: Optional[str] = None,
    reason: Optional[str] = None,
    proposal_id: Optional[str] = None,
    verified_evidence_count: Optional[int] = None,
    eval_ms: Optional[int] = None,
) -> None:
    payload: Dict[str, Any] = {
        "event": "pic_mcp_decision",
        "decision": decision,
        "tool": tool_name,
        "impact": impact,
    }
    if request_id:
        payload["request_id"] = request_id
    if proposal_id:
        payload["proposal_id"] = proposal_id
    if verified_evidence_count is not None:
        payload["verified_evidence_count"] = verified_evidence_count
    if eval_ms is not None:
        payload["eval_ms"] = eval_ms
    if reason_code:
        payload["reason_code"] = reason_code
    if reason:
        payload["reason"] = reason

    try:
        log.info(json.dumps(payload, ensure_ascii=False))
    except Exception:
        log.info("pic_mcp_decision=%r", payload)


def evaluate_pic_for_tool_call(
    *,
    tool_name: str,
    tool_args: Dict[str, Any],
    policy: PICPolicy,
    limits: Optional[PICEvaluateLimits] = None,
    verify_evidence: bool = False,
    proposal_base_dir: Optional[Path] = None,
    evidence_root_dir: Optional[Path] = None,
    request_id: Optional[str] = None,
) -> Tuple[Optional[ActionProposal], Dict[str, Any]]:
    """
    Evaluate PIC for a tool call. Fail-closed via PICError.

    Returns:
      (action_proposal_or_none, tool_args)
    """
    limits = limits or PICEvaluateLimits()

    t0 = time.perf_counter()

    proposal = tool_args.get("__pic")
    impact_from_policy = policy.impact_by_tool.get(tool_name)

    if proposal is None:
        if impact_from_policy and impact_from_policy in policy.require_pic_for_impacts:
            raise PICError(
                code=PICErrorCode.INVALID_REQUEST,
                message="Missing required PIC proposal for high-impact tool",
                details={"tool": tool_name, "impact": impact_from_policy, "expected_arg": "__pic"},
            )
        eval_ms = int((time.perf_counter() - t0) * 1000)
        _audit_decision(
            decision="allow",
            tool_name=tool_name,
            impact=impact_from_policy,
            request_id=request_id,
            reason="no_pic_required",
            eval_ms=eval_ms,
        )
        return None, tool_args

    if not isinstance(proposal, dict):
        raise PICError(
            code=PICErrorCode.INVALID_REQUEST,
            message="PIC proposal must be an object",
        )

    _enforce_limits(proposal, limits)

    # If policy does not define impact, we can still use the proposal's impact
    proposal_impact = proposal.get("impact")
    impact = policy.get_tool_impact(tool_name, proposal_impact=proposal_impact)

    # Schema + verifier rules (offline-capable)
    ap = verify_pic_proposal(proposal)

    # Tool binding is enforced only when runtime context exists (integration boundary)
    try:
        ap.verify_with_context(expected_tool=tool_name)
    except Exception as e:
        msg = str(e) or "Tool binding mismatch"
        if _debug_enabled():
            raise PICError(
                code=PICErrorCode.TOOL_BINDING_MISMATCH,
                message="Tool binding mismatch",
                details={"expected": tool_name, "error": msg},
            ) from e
        raise PICError(
            code=PICErrorCode.TOOL_BINDING_MISMATCH,
            message="Tool binding mismatch",
        ) from e

    verified_count = 0

    if verify_evidence:
        if EvidenceSystem is None:
            raise PICError(
                code=PICErrorCode.EVIDENCE_FAILED,
                message="Evidence verification requested but evidence module is unavailable",
            )

        if impact and impact in policy.require_evidence_for_impacts:
            es = EvidenceSystem()  # type: ignore
            base_dir = proposal_base_dir or Path(".").resolve()
            root_dir = evidence_root_dir or base_dir

            report = es.verify_all(proposal, base_dir=base_dir, evidence_root_dir=root_dir)  # type: ignore

            if not report.results:
                raise PICError(
                    code=PICErrorCode.EVIDENCE_REQUIRED,
                    message="Evidence required for this impact but no evidence entries were provided",
                    details={"tool": tool_name, "impact": impact},
                )

            if not report.ok:
                failed = [{"id": r.id, "message": r.message} for r in report.results if not r.ok]
                raise PICError(
                    code=PICErrorCode.EVIDENCE_FAILED,
                    message="Evidence verification failed",
                    details={"failed": failed},
                )

            verified_count = len(report.verified_ids)
            upgraded = apply_verified_ids_to_provenance(proposal, report.verified_ids)  # type: ignore

            ap = verify_pic_proposal(upgraded)

            # Enforce binding again on the upgraded proposal
            try:
                ap.verify_with_context(expected_tool=tool_name)
            except Exception as e:
                msg = str(e) or "Tool binding mismatch"
                if _debug_enabled():
                    raise PICError(
                        code=PICErrorCode.TOOL_BINDING_MISMATCH,
                        message="Tool binding mismatch",
                        details={"expected": tool_name, "error": msg},
                    ) from e
                raise PICError(
                    code=PICErrorCode.TOOL_BINDING_MISMATCH,
                    message="Tool binding mismatch",
                ) from e

    eval_ms = int((time.perf_counter() - t0) * 1000)
    if eval_ms > int(limits.max_eval_ms):
        raise PICError(
            code=PICErrorCode.LIMIT_EXCEEDED,
            message="PIC evaluation exceeded time budget",
            details={"max_eval_ms": int(limits.max_eval_ms), "eval_ms": eval_ms},
        )

    _audit_decision(
        decision="allow",
        tool_name=tool_name,
        impact=impact,
        request_id=request_id,
        proposal_id=proposal.get("id"),
        verified_evidence_count=verified_count if verify_evidence else None,
        eval_ms=eval_ms,
    )
    return ap, tool_args


def _extract_request_id(kwargs: Dict[str, Any]) -> Optional[str]:
    """
    Correlation ID sources:
      - __pic_request_id: reserved safe key
      - request_id: common name in tool calls
    """
    rid = kwargs.get("__pic_request_id")
    if isinstance(rid, str) and rid.strip():
        return rid.strip()
    rid2 = kwargs.get("request_id")
    if isinstance(rid2, str) and rid2.strip():
        return rid2.strip()
    return None


def guard_mcp_tool(
    tool_name: str,
    tool_fn: Callable[..., Any],
    *,
    policy: Optional[PICPolicy] = None,
    limits: Optional[PICEvaluateLimits] = None,
    verify_evidence: bool = False,
    proposal_base_dir: Optional[Path] = None,
    evidence_root_dir: Optional[Path] = None,
) -> Callable[..., Any]:
    """
    Wrap a *sync* tool function with PIC enforcement.

    Returns:
      - {"isError": True, "error": {...}} on blocks
      - {"isError": False, "result": <tool_return>} on allow
    """
    policy = policy or PICPolicy()
    limits = limits or PICEvaluateLimits()
    proposal_base_dir = proposal_base_dir or Path(".").resolve()

    def wrapped(**kwargs: Any) -> Any:
        request_id = _extract_request_id(kwargs)

        try:
            evaluate_pic_for_tool_call(
                tool_name=tool_name,
                tool_args=kwargs,
                policy=policy,
                limits=limits,
                verify_evidence=verify_evidence,
                proposal_base_dir=proposal_base_dir,
                evidence_root_dir=evidence_root_dir,
                request_id=request_id,
            )
            # Remove PIC meta before calling business tool
            kwargs.pop("__pic", None)
            kwargs.pop("__pic_request_id", None)

            result = tool_fn(**kwargs)
            return _wrap_success(result)

        except PICError as e:
            _audit_decision(
                decision="block",
                tool_name=tool_name,
                impact=policy.impact_by_tool.get(tool_name),
                request_id=request_id,
                reason_code=e.code.value,
                reason=e.message,
            )
            return {"isError": True, "error": _mcp_error_payload(e)}

        except Exception as e:
            details = {"exception_type": type(e).__name__, "exception": str(e)} if _debug_enabled() else None
            pe = PICError(PICErrorCode.POLICY_VIOLATION, "Internal error while enforcing PIC", details=details)
            _audit_decision(
                decision="block",
                tool_name=tool_name,
                impact=policy.impact_by_tool.get(tool_name),
                request_id=request_id,
                reason_code=pe.code.value,
                reason=f"{type(e).__name__}: {e}",
            )
            return {"isError": True, "error": _mcp_error_payload(pe)}

    return wrapped


def guard_mcp_tool_async(
    tool_name: str,
    tool_fn: Callable[..., Awaitable[Any]],
    *,
    policy: Optional[PICPolicy] = None,
    limits: Optional[PICEvaluateLimits] = None,
    verify_evidence: bool = False,
    proposal_base_dir: Optional[Path] = None,
    evidence_root_dir: Optional[Path] = None,
    max_tool_ms: Optional[int] = None,
) -> Callable[..., Awaitable[Any]]:
    """
    Wrap an *async* tool function with PIC enforcement + optional tool timeout.

    Tool timeout is ONLY enforceable for async tools.
    For sync tools, use a subprocess/worker execution model if you need killable timeouts.
    """
    policy = policy or PICPolicy()
    limits = limits or PICEvaluateLimits()
    proposal_base_dir = proposal_base_dir or Path(".").resolve()

    async def wrapped(**kwargs: Any) -> Any:
        request_id = _extract_request_id(kwargs)

        try:
            evaluate_pic_for_tool_call(
                tool_name=tool_name,
                tool_args=kwargs,
                policy=policy,
                limits=limits,
                verify_evidence=verify_evidence,
                proposal_base_dir=proposal_base_dir,
                evidence_root_dir=evidence_root_dir,
                request_id=request_id,
            )
            kwargs.pop("__pic", None)
            kwargs.pop("__pic_request_id", None)

            if max_tool_ms is not None:
                try:
                    result = await asyncio.wait_for(tool_fn(**kwargs), timeout=float(max_tool_ms) / 1000.0)
                except asyncio.TimeoutError as e:
                    details = {"max_tool_ms": int(max_tool_ms)} if _debug_enabled() else None
                    raise PICError(
                        code=PICErrorCode.LIMIT_EXCEEDED,
                        message="Tool execution timed out",
                        details=details,
                    ) from e
            else:
                result = await tool_fn(**kwargs)

            return _wrap_success(result)

        except PICError as e:
            _audit_decision(
                decision="block",
                tool_name=tool_name,
                impact=policy.impact_by_tool.get(tool_name),
                request_id=request_id,
                reason_code=e.code.value,
                reason=e.message,
            )
            return {"isError": True, "error": _mcp_error_payload(e)}

        except Exception as e:
            details = {"exception_type": type(e).__name__, "exception": str(e)} if _debug_enabled() else None
            pe = PICError(PICErrorCode.POLICY_VIOLATION, "Internal error while enforcing PIC", details=details)
            _audit_decision(
                decision="block",
                tool_name=tool_name,
                impact=policy.impact_by_tool.get(tool_name),
                request_id=request_id,
                reason_code=pe.code.value,
                reason=f"{type(e).__name__}: {e}",
            )
            return {"isError": True, "error": _mcp_error_payload(pe)}

    return wrapped
