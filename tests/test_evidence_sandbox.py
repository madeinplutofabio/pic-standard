from __future__ import annotations

import hashlib
import json
from pathlib import Path

from pic_standard.evidence import EvidenceSystem


def _sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def test_file_evidence_inside_root_ok(tmp_path: Path):
    root = tmp_path / "root"
    root.mkdir()

    artifacts = root / "artifacts"
    artifacts.mkdir()

    f = artifacts / "invoice_123.txt"
    data = b"hello evidence"
    f.write_bytes(data)

    proposal = {
        "evidence": [
            {
                "id": "invoice_123",
                "type": "hash",
                "ref": "file://artifacts/invoice_123.txt",
                "sha256": _sha256_bytes(data),
                "attestor": "test",
            }
        ]
    }

    es = EvidenceSystem()
    report = es.verify_all(proposal, base_dir=root, evidence_root_dir=root)
    assert report.ok
    assert "invoice_123" in report.verified_ids


def test_file_evidence_path_traversal_blocked(tmp_path: Path):
    root = tmp_path / "root"
    root.mkdir()

    (root / "artifacts").mkdir()
    (tmp_path / "secrets.txt").write_text("nope", encoding="utf-8")

    proposal = {
        "evidence": [
            {
                "id": "evil",
                "type": "hash",
                "ref": "file://../secrets.txt",
                "sha256": "0" * 64,
                "attestor": "test",
            }
        ]
    }

    es = EvidenceSystem()
    report = es.verify_all(proposal, base_dir=root, evidence_root_dir=root)
    assert report.ok is False
    assert report.results
    assert report.results[0].ok is False
    assert "escapes evidence_root_dir" in report.results[0].message


def test_file_evidence_absolute_outside_root_blocked(tmp_path: Path):
    root = tmp_path / "root"
    root.mkdir()

    outside = tmp_path / "outside.txt"
    outside.write_text("outside", encoding="utf-8")

    proposal = {
        "evidence": [
            {
                "id": "abs",
                "type": "hash",
                "ref": f"file://{outside.as_posix()}",
                "sha256": "0" * 64,
                "attestor": "test",
            }
        ]
    }

    es = EvidenceSystem()
    report = es.verify_all(proposal, base_dir=root, evidence_root_dir=root)
    assert report.ok is False
    assert report.results
    assert "escapes evidence_root_dir" in report.results[0].message
