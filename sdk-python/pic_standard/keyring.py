from __future__ import annotations

import base64
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional


_HEX_RE = re.compile(r"^[0-9a-fA-F]+$")


class KeyRingError(ValueError):
    """Raised when the keyring file or key formats are invalid."""


def _maybe_b64decode(s: str) -> bytes:
    # Accept URL-safe base64 too; handle missing padding
    raw = s.strip()
    raw = raw.replace("-", "+").replace("_", "/")
    pad = "=" * ((4 - len(raw) % 4) % 4)
    try:
        return base64.b64decode(raw + pad, validate=True)
    except Exception as e:
        raise KeyRingError("Invalid base64 public key") from e


def _parse_public_key_to_bytes(value: str) -> bytes:
    """
    Parse a public key string into raw bytes.

    Supported formats:
      - raw hex (64 hex chars = 32 bytes Ed25519 public key)
      - base64 (recommended)
      - PEM public key (-----BEGIN PUBLIC KEY----- ...)

    Returns:
      bytes (expected length for Ed25519 public key = 32)
    """
    v = value.strip()

    # PEM (optional): requires cryptography, loaded lazily
    if v.startswith("-----BEGIN"):
        try:
            from cryptography.hazmat.primitives import serialization
        except Exception as e:
            raise KeyRingError(
                "PEM public key provided but 'cryptography' is not installed. "
                "Install it or use base64/hex keys."
            ) from e

        try:
            pub = serialization.load_pem_public_key(v.encode("utf-8"))
            # For Ed25519, extract raw bytes if possible
            raw = pub.public_bytes(
                encoding=serialization.Encoding.Raw,
                format=serialization.PublicFormat.Raw,
            )
            return raw
        except Exception as e:
            raise KeyRingError("Invalid PEM public key") from e

    # Hex (common for raw Ed25519 keys)
    if len(v) in (64, 66) and _HEX_RE.match(v.replace("0x", "")):
        vv = v[2:] if v.lower().startswith("0x") else v
        if len(vv) % 2 != 0:
            raise KeyRingError("Hex public key must have even length")
        b = bytes.fromhex(vv)
        return b

    # Otherwise assume base64
    return _maybe_b64decode(v)


@dataclass(frozen=True)
class TrustedKeyRing:
    """
    Trusted key registry.

    keys maps key_id -> raw public key bytes (Ed25519 public key should be 32 bytes).
    """
    keys: Dict[str, bytes]

    def get(self, key_id: str) -> Optional[bytes]:
        return self.keys.get(key_id)

    @staticmethod
    def from_dict(d: Dict[str, str]) -> "TrustedKeyRing":
        """
        Accept a dict mapping key_id -> key_string (base64/hex/PEM).
        """
        out: Dict[str, bytes] = {}
        for key_id, key_str in d.items():
            if not isinstance(key_id, str) or not key_id.strip():
                raise KeyRingError("key_id must be a non-empty string")

            if not isinstance(key_str, str) or not key_str.strip():
                raise KeyRingError(f"Public key for '{key_id}' must be a non-empty string")

            raw = _parse_public_key_to_bytes(key_str)

            # Ed25519 public keys are 32 bytes
            if len(raw) != 32:
                raise KeyRingError(
                    f"Public key for '{key_id}' has invalid length {len(raw)} bytes "
                    "(expected 32 bytes for Ed25519)"
                )

            out[key_id] = raw

        return TrustedKeyRing(keys=out)

    @staticmethod
    def from_json_file(path: Path) -> "TrustedKeyRing":
        """
        Load from a JSON file.

        Supported file format (recommended):
          {
            "trusted_keys": {
              "cfo_key_v1": "<base64-or-hex-or-pem>",
              "billing_key_v2": "<...>"
            }
          }

        Also accepted (minimal):
          {
            "cfo_key_v1": "<...>",
            "billing_key_v2": "<...>"
          }
        """
        if not path.exists():
            raise KeyRingError(f"Keyring file not found: {path}")

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception as e:
            raise KeyRingError(f"Invalid JSON in keyring file: {path}") from e

        if isinstance(data, dict) and "trusted_keys" in data and isinstance(data["trusted_keys"], dict):
            return TrustedKeyRing.from_dict(data["trusted_keys"])

        if isinstance(data, dict):
            # assume it's already a key_id -> key map
            # (this keeps the format dead simple if you want)
            return TrustedKeyRing.from_dict({k: v for k, v in data.items()})

        raise KeyRingError("Keyring JSON must be an object")

    @staticmethod
    def load_default() -> "TrustedKeyRing":
        """
        Default loader:
          - if PIC_KEYS_PATH is set, load from that file
          - else look for ./pic_keys.json in the current working directory
          - else return empty keyring (no trusted signers configured)
        """
        env = (os.getenv("PIC_KEYS_PATH") or "").strip()
        if env:
            return TrustedKeyRing.from_json_file(Path(env))

        default = Path("pic_keys.json")
        if default.exists():
            return TrustedKeyRing.from_json_file(default)

        return TrustedKeyRing(keys={})
