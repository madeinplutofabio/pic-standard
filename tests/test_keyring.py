from __future__ import annotations

import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from pic_standard.keyring import KeyRingError, TrustedKeyRing


# 32-byte Ed25519 public key for tests (raw bytes), encoded as base64:
# bytes(range(32)) -> base64 = AAECAwQFBgcICQoLDA0ODxAREhMUFRYXGBkaGxwdHh8=
PUBKEY_B64_32 = "AAECAwQFBgcICQoLDA0ODxAREhMUFRYXGBkaGxwdHh8="

# Same key as hex (64 hex chars)
PUBKEY_HEX_32 = "".join(f"{i:02x}" for i in range(32))
PUBKEY_HEX_32_0X = "0x" + PUBKEY_HEX_32


def _write_json(p: Path, obj: dict) -> None:
    p.write_text(json.dumps(obj, indent=2), encoding="utf-8")


def test_keyring_parses_base64_ok():
    kr = TrustedKeyRing.from_dict({"trusted_keys": {"k1": PUBKEY_B64_32}})
    b = kr.get("k1")
    assert b is not None
    assert isinstance(b, (bytes, bytearray))
    assert len(b) == 32
    assert kr.key_status("k1") == "ok"


def test_keyring_parses_hex_ok():
    kr = TrustedKeyRing.from_dict({"trusted_keys": {"k1": PUBKEY_HEX_32}})
    b = kr.get("k1")
    assert b is not None
    assert len(b) == 32
    assert kr.key_status("k1") == "ok"


def test_keyring_parses_hex_with_0x_ok():
    kr = TrustedKeyRing.from_dict({"trusted_keys": {"k1": PUBKEY_HEX_32_0X}})
    b = kr.get("k1")
    assert b is not None
    assert len(b) == 32
    assert kr.key_status("k1") == "ok"


def test_keyring_rejects_invalid_base64():
    with pytest.raises(KeyRingError):
        TrustedKeyRing.from_dict({"trusted_keys": {"k1": "NOT_BASE64!!"}})


def test_keyring_rejects_wrong_length_key():
    # 16 bytes base64 -> should fail (Ed25519 pubkey must be 32 bytes)
    with pytest.raises(KeyRingError):
        TrustedKeyRing.from_dict({"trusted_keys": {"k1": "AQIDBAUGBwgJCgsMDQ4PEA=="}})


def test_keyring_rejects_invalid_expires_at():
    with pytest.raises(KeyRingError):
        TrustedKeyRing.from_dict(
            {"trusted_keys": {"k1": {"public_key": PUBKEY_B64_32, "expires_at": "not-a-date"}}}
        )


def test_keyring_expires_at_enforced():
    kr = TrustedKeyRing.from_dict(
        {"trusted_keys": {"k1": {"public_key": PUBKEY_B64_32, "expires_at": "2026-01-01T00:00:00Z"}}}
    )

    before = datetime(2025, 12, 31, 23, 0, 0, tzinfo=timezone.utc)
    after = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)

    assert kr.get("k1", now=before) is not None
    assert kr.key_status("k1", now=before) == "ok"

    assert kr.get("k1", now=after) is None
    assert kr.key_status("k1", now=after) == "expired"

    entry = kr.get_entry("k1")
    assert entry is not None
    assert entry.expires_at is not None
    assert entry.expires_at.tzinfo is not None


def test_keyring_revocation_enforced():
    kr = TrustedKeyRing.from_dict({"trusted_keys": {"k1": PUBKEY_B64_32}, "revoked_keys": ["k1"]})
    assert kr.get("k1") is None
    assert kr.key_status("k1") == "revoked"


def test_keyring_missing_key_status():
    kr = TrustedKeyRing.from_dict({"trusted_keys": {"k1": PUBKEY_B64_32}})
    assert kr.key_status("does_not_exist") == "missing"
    assert kr.get("does_not_exist") is None


def test_keyring_loads_recommended_json_format(tmp_path: Path):
    p = tmp_path / "keys.json"
    _write_json(p, {"trusted_keys": {"k1": PUBKEY_B64_32}, "revoked_keys": []})
    kr = TrustedKeyRing.from_json_file(p)
    assert kr.get("k1") is not None
    assert kr.key_status("k1") == "ok"


def test_keyring_loads_legacy_minimal_json_format(tmp_path: Path):
    # legacy format is key_id -> key_string at root
    p = tmp_path / "keys.json"
    _write_json(p, {"k1": PUBKEY_B64_32})
    kr = TrustedKeyRing.from_json_file(p)
    assert kr.get("k1") is not None
    assert kr.key_status("k1") == "ok"


def test_keyring_rejects_non_object_json(tmp_path: Path):
    p = tmp_path / "keys.json"
    p.write_text(json.dumps(["not", "an", "object"]), encoding="utf-8")
    with pytest.raises(KeyRingError):
        TrustedKeyRing.from_json_file(p)


def test_keyring_rejects_bad_revoked_keys_type():
    with pytest.raises(KeyRingError):
        TrustedKeyRing.from_dict({"trusted_keys": {"k1": PUBKEY_B64_32}, "revoked_keys": "k1"})


def test_keyring_rejects_empty_key_id():
    with pytest.raises(KeyRingError):
        TrustedKeyRing.from_dict({"trusted_keys": {"": PUBKEY_B64_32}})


def test_keyring_rejects_empty_key_value():
    with pytest.raises(KeyRingError):
        TrustedKeyRing.from_dict({"trusted_keys": {"k1": ""}})


def test_keyring_pem_behavior_depends_on_crypto():
    """
    This test is stable regardless of whether cryptography is installed:
      - If cryptography is missing: PEM should raise KeyRingError about missing cryptography.
      - If cryptography exists: invalid PEM should raise KeyRingError("Invalid PEM public key").
    """
    pem = "-----BEGIN PUBLIC KEY-----\nMIIB...fake...\n-----END PUBLIC KEY-----\n"

    crypto_available = importlib.util.find_spec("cryptography") is not None

    with pytest.raises(KeyRingError) as exc:
        TrustedKeyRing.from_dict({"trusted_keys": {"k1": pem}})

    msg = str(exc.value).lower()
    if crypto_available:
        assert "invalid pem public key" in msg
    else:
        assert "cryptography" in msg
