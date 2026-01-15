import json
import pytest
from pathlib import Path
import hashlib
import tempfile

from pic_standard.evidence import EvidenceSystem, apply_verified_ids_to_provenance
from pic_standard.verifier import ActionProposal

ROOT = Path(__file__).resolve().parents[1]


def verify_multiple_evidences(proposal: dict, base_dir: Path) -> dict:
    """Helper function to verify multiple pieces of evidence in a proposal.
    
    Processes all evidence items and returns a summary with verification results.
    """
    system = EvidenceSystem()
    report = system.verify_all(proposal, base_dir=base_dir)
    return {
        "ok": report.ok,
        "total_evidence": len(report.results),
        "verified_count": len(report.verified_ids),
        "verified_ids": report.verified_ids,
        "results": report.results,
    }


def test_evidence_hash_ok_verifies_and_upgrades_provenance():
    proposal_path = ROOT / "examples" / "financial_hash_ok.json"
    proposal = json.loads(proposal_path.read_text(encoding="utf-8"))

    report = EvidenceSystem().verify_all(proposal, base_dir=proposal_path.parent)
    assert report.ok
    assert "invoice_123" in report.verified_ids

    upgraded = apply_verified_ids_to_provenance(proposal, report.verified_ids)
    # Should pass verifier after upgrade (money requires TRUSTED evidence)
    ActionProposal(**upgraded)


def test_evidence_hash_bad_fails():
    proposal_path = ROOT / "examples" / "failing" / "financial_hash_bad.json"
    proposal = json.loads(proposal_path.read_text(encoding="utf-8"))

    report = EvidenceSystem().verify_all(proposal, base_dir=proposal_path.parent)
    assert not report.ok
    assert report.results
    assert any((not r.ok) for r in report.results)


def test_evidence_invalid_file_path_raises_error():
    """Verify that verify_evidence handles FileNotFoundError for non-existent files."""
    proposal = {
        "evidence": [
            {
                "id": "missing_file",
                "type": "hash",
                "ref": "file://nonexistent/path/to/file.txt",
                "sha256": "0000000000000000000000000000000000000000000000000000000000000000",
            }
        ]
    }
    
    report = EvidenceSystem().verify_all(proposal, base_dir=ROOT)
    assert not report.ok
    assert len(report.results) == 1
    result = report.results[0]
    assert result.id == "missing_file"
    assert not result.ok
    assert "Evidence file not found" in result.message


def test_evidence_invalid_hash_string_fails():
    """Verify that evidence verification fails when hash string is malformed."""
    # Create a proposal with an existing file but an invalid hash
    proposal_path = ROOT / "examples" / "artifacts" / "invoice_123.txt"
    proposal = {
        "evidence": [
            {
                "id": "invoice_bad_hash",
                "type": "hash",
                "ref": f"file://{proposal_path.name}",
                "sha256": "not_a_valid_hash_string",
            }
        ]
    }
    
    report = EvidenceSystem().verify_all(proposal, base_dir=proposal_path.parent)
    assert not report.ok
    assert len(report.results) == 1
    result = report.results[0]
    assert result.id == "invoice_bad_hash"
    assert not result.ok
    assert "sha256 mismatch" in result.message


def test_evidence_large_file_verification():
    """Verify that evidence verification handles large files (>1 MB) correctly."""
    # Create a temporary directory and large file
    temp_dir = Path(tempfile.gettempdir())
    large_file_path = temp_dir / "test_large_evidence.bin"
    
    try:
        # Create a file larger than 1 MB (2 MB in this case)
        file_size = 2 * 1024 * 1024  # 2 MB
        with open(large_file_path, "wb") as f:
            f.write(b"x" * file_size)
        
        # Compute the SHA256 hash
        with open(large_file_path, "rb") as f:
            file_hash = hashlib.sha256(f.read()).hexdigest()
        
        # Create a proposal with the large file evidence
        proposal = {
            "evidence": [
                {
                    "id": "large_file_evidence",
                    "type": "hash",
                    "ref": f"file://{large_file_path.name}",
                    "sha256": file_hash,
                }
            ]
        }
        
        # Verify the large file evidence
        report = EvidenceSystem().verify_all(proposal, base_dir=temp_dir)
        assert report.ok
        assert len(report.results) == 1
        result = report.results[0]
        assert result.id == "large_file_evidence"
        assert result.ok
        assert "sha256 verified" in result.message
        assert "large_file_evidence" in report.verified_ids
        
    finally:
        # Clean up the temporary file
        if large_file_path.exists():
            large_file_path.unlink()


def test_evidence_multiple_pieces_verification():
    """Verify that multiple pieces of evidence are validated correctly."""
    temp_dir = Path(tempfile.gettempdir())
    file1_path = temp_dir / "evidence_file1.txt"
    file2_path = temp_dir / "evidence_file2.txt"
    file3_path = temp_dir / "evidence_file3.txt"
    
    try:
        # Create three test files with different content
        file1_path.write_text("First evidence file")
        file2_path.write_text("Second evidence file with different content")
        file3_path.write_text("Third evidence file")
        
        # Compute SHA256 hashes for each file
        hash1 = hashlib.sha256(file1_path.read_bytes()).hexdigest()
        hash2 = hashlib.sha256(file2_path.read_bytes()).hexdigest()
        hash3 = hashlib.sha256(file3_path.read_bytes()).hexdigest()
        
        # Create a proposal with multiple evidence items
        proposal = {
            "evidence": [
                {
                    "id": "evidence_1",
                    "type": "hash",
                    "ref": f"file://{file1_path.name}",
                    "sha256": hash1,
                },
                {
                    "id": "evidence_2",
                    "type": "hash",
                    "ref": f"file://{file2_path.name}",
                    "sha256": hash2,
                },
                {
                    "id": "evidence_3",
                    "type": "hash",
                    "ref": f"file://{file3_path.name}",
                    "sha256": hash3,
                },
            ]
        }
        
        # Verify multiple evidences using the helper function
        summary = verify_multiple_evidences(proposal, temp_dir)
        
        # Assertions
        assert summary["ok"], "All evidence should be verified successfully"
        assert summary["total_evidence"] == 3, "Should have 3 evidence items"
        assert summary["verified_count"] == 3, "All 3 evidence items should be verified"
        assert "evidence_1" in summary["verified_ids"]
        assert "evidence_2" in summary["verified_ids"]
        assert "evidence_3" in summary["verified_ids"]
        
        # Verify each result is successful
        for result in summary["results"]:
            assert result.ok, f"Evidence {result.id} should be verified"
            assert "sha256 verified" in result.message
        
    finally:
        # Clean up all temporary files
        for file_path in [file1_path, file2_path, file3_path]:
            if file_path.exists():
                file_path.unlink()
