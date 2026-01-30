from __future__ import annotations

import base64
import json
from pathlib import Path

import pytest

from pic_standard.evidence import EvidenceSystem


# --- helpers (tests-only) ---

def _b64(b: bytes) -> str:
    return base64.b64encode(b).decode("ascii")


def _make_keypair():
    """
    Generate an Ed25519 keypair using cryptography.
    These tests require 'cryptography' to be installed (your [crypto] extra).
    """
    try:
        from cryptography.hazmat.primitives.asymmetric import ed25519
        from cryptography.hazmat.primitives import serialization
    except Exception as e:  # pragma: no cover
        pytest.skip("cryptography not installed; install via `pip install 'pic-standard[crypto]'`")  # noqa: B904

    priv = ed25519.Ed25519PrivateKey.generate()
    pub = priv.public_key()
    pub_raw = pub.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return priv, pub_raw


def _proposal_with_sig(*, payload: str, signature_b64: str, key_id: str) -> dict:
    return {
        "evidence": [
            {
                "id": "approval_123",
                "type": "sig",
                "ref": "inline:approval_payload",
                "payload": payload,
                "alg": "ed25519",
                "signature": signature_b64,
                "key_id": key_id,
                "signer": key_id,
                "attestor": "test",
            }
        ],
        # provenance included because your system upgrades provenance IDs (not strictly required for verify_all)
        "provenance": [{"id": "approval_123", "trust": "untrusted", "source": "evidence"}],
        "claims": [{"text": "Pay", "evidence": ["approval_123"]}],
        "protocol": "PIC/1.0",
        "intent": "Test",
        "impact": "money",
        "action": {"tool": "payments_send", "args": {"amount": 500}},
    }


# --- tests ---

def test_sig_evidence_verifies_ok(monkeypatch, tmp_path: Path):
    priv, pub_raw = _make_keypair()

    payload = "amount=500;currency=USD;invoice=123"
    sig_raw = priv.sign(payload.encode("utf-8"))
    sig_b64 = _b64(sig_raw)

    # Write a hermetic keyring file and point PIC_KEYS_PATH to it
    keys_path = tmp_path / "pic_keys.json"
    keys_path.write_text(
        json.dumps(
            {"trusted_keys": {"demo_signer_v1": _b64(pub_raw)}},
            indent=2,
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("PIC_KEYS_PATH", str(keys_path))

    proposal = _proposal_with_sig(payload=payload, signature_b64=sig_b64, key_id="demo_signer_v1")

    es = EvidenceSystem()
    report = es.verify_all(proposal, base_dir=tmp_path)

    assert report.ok is True
    assert "approval_123" in report.verified_ids
    assert any(r.id == "approval_123" and r.ok for r in report.results)


def test_sig_evidence_fails_when_payload_tampered(monkeypatch, tmp_path: Path):
    priv, pub_raw = _make_keypair()

    payload_signed = "amount=500;currency=USD;invoice=123"
    sig_raw = priv.sign(payload_signed.encode("utf-8"))
    sig_b64 = _b64(sig_raw)

    keys_path = tmp_path / "pic_keys.json"
    keys_path.write_text(
        json.dumps({"trusted_keys": {"demo_signer_v1": _b64(pub_raw)}}, indent=2),
        encoding="utf-8",
    )
    monkeypatch.setenv("PIC_KEYS_PATH", str(keys_path))

    # Tamper payload but keep same signature -> must fail
    proposal = _proposal_with_sig(
        payload="amount=600;currency=USD;invoice=123",
        signature_b64=sig_b64,
        key_id="demo_signer_v1",
    )

    es = EvidenceSystem()
    report = es.verify_all(proposal, base_dir=tmp_path)

    assert report.ok is False
    assert "approval_123" not in report.verified_ids
    # Ensure the failure message is about signature
    msgs = [r.message for r in report.results if r.id == "approval_123"]
    assert msgs and any("signature" in m.lower() for m in msgs)


def test_sig_evidence_fails_unknown_key_id(monkeypatch, tmp_path: Path):
    priv, pub_raw = _make_keypair()

    payload = "amount=500;currency=USD;invoice=123"
    sig_raw = priv.sign(payload.encode("utf-8"))
    sig_b64 = _b64(sig_raw)

    # Keyring does NOT contain the key_id we reference in evidence
    keys_path = tmp_path / "pic_keys.json"
    keys_path.write_text(
        json.dumps({"trusted_keys": {"some_other_key": _b64(pub_raw)}}, indent=2),
        encoding="utf-8",
    )
    monkeypatch.setenv("PIC_KEYS_PATH", str(keys_path))

    proposal = _proposal_with_sig(payload=payload, signature_b64=sig_b64, key_id="demo_signer_v1")

    es = EvidenceSystem()
    report = es.verify_all(proposal, base_dir=tmp_path)

    assert report.ok is False
    assert "approval_123" not in report.verified_ids
    msgs = [r.message for r in report.results if r.id == "approval_123"]
    assert msgs and any("unknown key_id" in m.lower() or "not present" in m.lower() for m in msgs)


def test_sig_evidence_blocks_large_payload(monkeypatch, tmp_path: Path):
    priv, pub_raw = _make_keypair()

    payload = "x" * (16 * 1024 + 1)  # exceeds default max_payload_bytes=16KB
    sig_raw = priv.sign(payload.encode("utf-8"))
    sig_b64 = _b64(sig_raw)

    keys_path = tmp_path / "pic_keys.json"
    keys_path.write_text(
        json.dumps({"trusted_keys": {"demo_signer_v1": _b64(pub_raw)}}, indent=2),
        encoding="utf-8",
    )
    monkeypatch.setenv("PIC_KEYS_PATH", str(keys_path))

    proposal = _proposal_with_sig(payload=payload, signature_b64=sig_b64, key_id="demo_signer_v1")

    es = EvidenceSystem()
    report = es.verify_all(proposal, base_dir=tmp_path)

    assert report.ok is False
    msgs = [r.message for r in report.results if r.id == "approval_123"]
    assert msgs and any("payload too large" in m.lower() for m in msgs)
