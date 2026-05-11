"""Tests for v0.7 Key Resolution Architecture."""

from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path
from typing import Any, Dict

import pytest
from pic_standard.evidence import EvidenceSystem
from pic_standard.keyring import (
    KeyResolver,
    StaticKeyRingResolver,
    TrustedKeyRing,
)

# --- helpers ---


def _b64(b: bytes) -> str:
    return base64.b64encode(b).decode("ascii")


def _make_keypair():
    try:
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import ed25519
    except Exception:
        pytest.skip("cryptography not installed")

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
        "provenance": [{"id": "approval_123", "trust": "untrusted", "source": "evidence"}],
        "claims": [{"text": "Pay", "evidence": ["approval_123"]}],
        "protocol": "PIC/1.0",
        "intent": "Test",
        "impact": "money",
        "action": {"tool": "payments_send", "args": {"amount": 500}},
    }


def _proposal_with_hash(*, sha256: str, ref: str) -> dict:
    return {
        "evidence": [
            {
                "id": "file_check_1",
                "type": "hash",
                "ref": ref,
                "sha256": sha256,
                "attestor": "test",
            }
        ],
        "provenance": [{"id": "file_check_1", "trust": "untrusted", "source": "evidence"}],
        "claims": [{"text": "Verify file", "evidence": ["file_check_1"]}],
        "protocol": "PIC/1.0",
        "intent": "Test",
        "impact": "data",
        "action": {"tool": "file_read", "args": {"path": "invoice.txt"}},
    }


# --- StaticKeyRingResolver unit tests ---


def test_static_resolver_get_key_ok():
    _, pub_raw = _make_keypair()
    kr = TrustedKeyRing.from_dict({"trusted_keys": {"k1": _b64(pub_raw)}})
    resolver = StaticKeyRingResolver(kr)

    result = resolver.get_key("k1")
    assert result == pub_raw


def test_static_resolver_key_status_variants():
    kr = TrustedKeyRing.from_dict(
        {
            "trusted_keys": {
                "active": _b64(b"\x00" * 32),
                "expired": {
                    "public_key": _b64(b"\x01" * 32),
                    "expires_at": "2020-01-01T00:00:00Z",
                },
            },
            "revoked_keys": ["revoked_key"],
        }
    )
    resolver = StaticKeyRingResolver(kr)

    assert resolver.key_status("active") == "ok"
    assert resolver.key_status("missing_key") == "missing"
    assert resolver.key_status("revoked_key") == "revoked"
    assert resolver.key_status("expired") == "expired"


def test_static_resolver_satisfies_protocol():
    kr = TrustedKeyRing(keys={}, revoked_keys=set())
    resolver = StaticKeyRingResolver(kr)
    assert isinstance(resolver, KeyResolver)


# --- EvidenceSystem injection tests ---


def test_evidence_system_with_injected_resolver(tmp_path: Path):
    """Custom resolver works without PIC_KEYS_PATH — proves resolver injection."""
    priv, pub_raw = _make_keypair()

    # Build a resolver directly — no file, no env var
    kr = TrustedKeyRing.from_dict({"trusted_keys": {"injected_key": _b64(pub_raw)}})
    resolver = StaticKeyRingResolver(kr)

    payload = "amount=500;currency=USD;invoice=123"
    sig_raw = priv.sign(payload.encode("utf-8"))
    sig_b64 = _b64(sig_raw)

    proposal = _proposal_with_sig(payload=payload, signature_b64=sig_b64, key_id="injected_key")

    es = EvidenceSystem(key_resolver=resolver)
    report = es.verify_all(proposal, base_dir=tmp_path)

    assert report.ok is True
    assert "approval_123" in report.verified_ids


def test_evidence_system_default_resolver(monkeypatch, tmp_path: Path):
    """EvidenceSystem() with no args resolves keys via PIC_KEYS_PATH — regression guard."""
    priv, pub_raw = _make_keypair()

    keys_path = tmp_path / "pic_keys.json"
    keys_path.write_text(
        json.dumps({"trusted_keys": {"default_key": _b64(pub_raw)}}, indent=2),
        encoding="utf-8",
    )
    monkeypatch.setenv("PIC_KEYS_PATH", str(keys_path))

    payload = "amount=500;currency=USD;invoice=123"
    sig_raw = priv.sign(payload.encode("utf-8"))
    sig_b64 = _b64(sig_raw)

    proposal = _proposal_with_sig(payload=payload, signature_b64=sig_b64, key_id="default_key")

    es = EvidenceSystem()  # no args — lazy default
    report = es.verify_all(proposal, base_dir=tmp_path)

    assert report.ok is True
    assert "approval_123" in report.verified_ids


# --- Pipeline threading test ---


def test_pipeline_threads_resolver(monkeypatch):
    """PipelineOptions.key_resolver reaches EvidenceSystem constructor."""
    from pic_standard.pipeline import PipelineOptions, verify_proposal

    captured_kwargs: Dict[str, Any] = {}

    class StubEvidenceSystem:
        def __init__(self, **kwargs):
            captured_kwargs.update(kwargs)

        def verify_all(self, proposal, *, base_dir, evidence_root_dir=None):
            from pic_standard.evidence import EvidenceReport

            return EvidenceReport(ok=True, results=[], verified_ids=set())

    monkeypatch.setattr("pic_standard.pipeline.EvidenceSystem", StubEvidenceSystem)

    sentinel_resolver = object()  # unique sentinel

    # Minimal valid proposal with evidence (so EvidenceSystem gets instantiated)
    proposal = {
        "protocol": "PIC/1.0",
        "intent": "Test",
        "impact": "read",
        "action": {"tool": "read_file", "args": {"path": "x.txt"}},
        "provenance": [{"id": "e1", "trust": "untrusted", "source": "evidence"}],
        "claims": [{"text": "check", "evidence": ["e1"]}],
        "evidence": [
            {
                "id": "e1",
                "type": "sig",
                "ref": "inline:test",
                "payload": "test",
                "alg": "ed25519",
                "signature": "AAAA",
                "key_id": "k1",
                "signer": "test",
            }
        ],
    }

    verify_proposal(
        proposal,
        options=PipelineOptions(verify_evidence=True, key_resolver=sentinel_resolver),
    )

    assert "key_resolver" in captured_kwargs
    assert captured_kwargs["key_resolver"] is sentinel_resolver


# --- Lazy default semantics test ---


def test_hash_only_does_not_load_keyring(monkeypatch, tmp_path: Path):
    """Hash-only evidence must NOT trigger keyring loading. Sig evidence must."""

    # Poison load_default — any call will raise this distinctive error
    def _boom():
        raise RuntimeError("should not be called")

    monkeypatch.setattr(TrustedKeyRing, "load_default", staticmethod(_boom))

    # Create a real file for hash evidence
    artifact = tmp_path / "invoice.txt"
    artifact.write_text("invoice data", encoding="utf-8")
    expected_hash = hashlib.sha256(artifact.read_bytes()).hexdigest()

    proposal = _proposal_with_hash(
        sha256=expected_hash,
        ref=f"file://{artifact.name}",
    )

    # Hash-only: should succeed without touching load_default
    es = EvidenceSystem()
    report = es.verify_all(proposal, base_dir=tmp_path)
    assert report.ok is True

    # Sig evidence: should fail because lazy resolver calls load_default → RuntimeError
    sig_proposal = _proposal_with_sig(
        payload="test",
        signature_b64=_b64(b"\x00" * 64),
        key_id="any_key",
    )

    es2 = EvidenceSystem()
    report2 = es2.verify_all(sig_proposal, base_dir=tmp_path)

    assert report2.ok is False
    # The failure must be from our injected RuntimeError, not a generic sig failure
    assert any("should not be called" in r.message for r in report2.results)
