from __future__ import annotations

import json
import os
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, Optional

from pic_standard.policy import PICPolicy


DEFAULT_FILENAMES = ("pic_policy.json", "pic_policy.local.json")


def _coerce_set(value: Any) -> set[str]:
    if value is None:
        return set()
    if isinstance(value, (list, tuple, set)):
        return {str(x) for x in value}
    raise ValueError("Expected a list for set-like policy fields")


def policy_from_dict(data: Dict[str, Any]) -> PICPolicy:
    impact_by_tool = data.get("impact_by_tool") or {}
    if not isinstance(impact_by_tool, dict):
        raise ValueError("impact_by_tool must be a JSON object mapping tool->impact")

    require_pic_for_impacts = _coerce_set(data.get("require_pic_for_impacts")) or {"money", "privacy", "irreversible"}
    require_evidence_for_impacts = _coerce_set(data.get("require_evidence_for_impacts")) or {"money", "privacy", "irreversible"}

    return PICPolicy(
        impact_by_tool={str(k): str(v) for k, v in impact_by_tool.items()},
        require_pic_for_impacts=require_pic_for_impacts,
        require_evidence_for_impacts=require_evidence_for_impacts,
    )


def load_policy(
    *,
    repo_root: Optional[Path] = None,
    explicit_path: Optional[Path] = None,
) -> PICPolicy:
    """Load PICPolicy from JSON.

    Priority:
      1) explicit_path (if provided)
      2) env var PIC_POLICY_PATH (if set)
      3) first existing file in DEFAULT_FILENAMES (repo root)
      4) default PICPolicy() (sane defaults, empty impact_by_tool)
    """
    repo_root = repo_root or Path(".").resolve()

    env_path = os.getenv("PIC_POLICY_PATH")
    if explicit_path is not None:
        path = explicit_path
    elif env_path:
        path = Path(env_path)
    else:
        path = None
        for name in DEFAULT_FILENAMES:
            candidate = repo_root / name
            if candidate.exists():
                path = candidate
                break

    if path is None:
        return PICPolicy()

    raw = path.read_text(encoding="utf-8")
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("Policy JSON must be an object")

    return policy_from_dict(data)


def dump_policy(policy: PICPolicy) -> Dict[str, Any]:
    """Useful for debugging / CLI output."""
    # sets aren't JSON-serializable; convert to sorted lists
    return {
        "impact_by_tool": dict(policy.impact_by_tool),
        "require_pic_for_impacts": sorted(list(policy.require_pic_for_impacts)),
        "require_evidence_for_impacts": sorted(list(policy.require_evidence_for_impacts)),
    }
