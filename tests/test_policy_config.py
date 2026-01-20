from __future__ import annotations

import json
from pathlib import Path

from pic_standard.config import load_policy, dump_policy


def test_load_policy_from_repo_root(tmp_path: Path):
    policy_path = tmp_path / "pic_policy.json"
    policy_path.write_text(
        json.dumps(
            {
                "impact_by_tool": {"payments_send": "money"},
                "require_pic_for_impacts": ["money"],
                "require_evidence_for_impacts": ["money"],
            }
        ),
        encoding="utf-8",
    )

    policy = load_policy(repo_root=tmp_path)
    dumped = dump_policy(policy)

    assert dumped["impact_by_tool"]["payments_send"] == "money"
    assert "money" in dumped["require_pic_for_impacts"]
    assert "money" in dumped["require_evidence_for_impacts"]
