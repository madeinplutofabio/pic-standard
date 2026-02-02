from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from pic_standard.evidence import EvidenceSystem


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_evidence_verify_mixed_hash_and_sig(monkeypatch, tmp_path: Path):
    """
    Mixed evidence: one hash + one sig in the same proposal should verify both.

    This asserts:
      - hash evidence is verified against examples/artifacts/...
      - sig evidence is verified using a temp keyring file via PIC_KEYS_PATH
    """
    if importlib.util.find_spec("cryptography") is None:
        pytest.skip("cryptography not installed; signature evidence requires it")

    repo_root = Path(__file__).resolve().parents[1]
    examples_dir = repo_root / "examples"

    # Reuse the canonical examples so the test stays stable.
    hash_ok = _load_json(examples_dir / "financial_hash_ok.json")
    sig_ok = _load_json(examples_dir / "financial_sig_ok.json")

    hash_ev = (hash_ok.get("evidence") or [])[0]
    sig_ev = (sig_ok.get("evidence") or [])[0]

    assert hash_ev.get("type") == "hash"
    assert sig_ev.get("type") == "sig"

    # Provide the signer key via a temp keyring file to keep tests hermetic.
    # This must match the key used for examples/financial_sig_ok.json.
    keyring_path = tmp_path / "pic_keys.test.json"
    keyring_path.write_text(
        json.dumps(
            {
                "trusted_keys": {
                    "demo_signer_v1": "u1esUbs/ZYS3PTPMIxiwsh47pyCUAv5VgzrmjEKbw6k="
                }
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("PIC_KEYS_PATH", str(keyring_path))

    proposal = {"evidence": [hash_ev, sig_ev]}

    es = EvidenceSystem()
    report = es.verify_all(proposal, base_dir=examples_dir)

    assert report.ok is True
    assert "invoice_123" in report.verified_ids
    assert "approval_123" in report.verified_ids
