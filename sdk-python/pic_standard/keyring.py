from __future__ import annotations

import base64
import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Set, Literal


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


def _parse_expires_at(value: str) -> datetime:
    """
    Parse ISO8601 datetime. Recommended: "...Z" or explicit offset.

    Accepts:
      - 2026-12-31T23:59:59Z
      - 2026-12-31T23:59:59+00:00
      - 2026-12-31T23:59:59 (treated as UTC)
    """
    v = value.strip()
    if not v:
        raise KeyRingError("expires_at must be a non-empty string")

    # Handle trailing Z
    if v.endswith("Z") or v.endswith("z"):
        v2 = v[:-1] + "+00:00"
    else:
        v2 = v

    try:
        dt = datetime.fromisoformat(v2)
    except Exception as e:
        raise KeyRingError("Invalid expires_at (expected ISO8601 datetime)") from e

    # If naive, treat as UTC (explicit and deterministic)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    return dt.astimezone(timezone.utc)


@dataclass(frozen=True)
class TrustedKey:
    """
    Single trusted key entry.

    public_key: raw Ed25519 public key bytes (32 bytes).
    expires_at: optional UTC datetime at which this key stops being trusted.
    """
    public_key: bytes
    expires_at: Optional[datetime] = None


KeyStatus = Literal["ok", "missing", "revoked", "expired"]


@dataclass(frozen=True)
class TrustedKeyRing:
    """
    Trusted key registry.

    - keys maps key_id -> TrustedKey(public_key, expires_at)
    - revoked_keys contains key_ids that must be treated as untrusted
    """
    keys: Dict[str, TrustedKey]
    revoked_keys: Set[str]

    def get(self, key_id: str, *, now: Optional[datetime] = None) -> Optional[bytes]:
        """
        Return raw public key bytes ONLY if the key is active (not revoked, not expired).
        """
        if not isinstance(key_id, str) or not key_id.strip():
            return None

        kid = key_id.strip()
        if kid in self.revoked_keys:
            return None

        entry = self.keys.get(kid)
        if entry is None:
            return None

        if entry.expires_at is not None:
            n = now or datetime.now(timezone.utc)
            if n.tzinfo is None:
                n = n.replace(tzinfo=timezone.utc)
            n = n.astimezone(timezone.utc)

            if n >= entry.expires_at:
                return None

        return entry.public_key

    # ---- NEW: status helpers (for evidence.py / CLI UX) ----

    def key_status(self, key_id: str, *, now: Optional[datetime] = None) -> KeyStatus:
        """
        Return a stable status string for key_id:
          - "missing"  -> not present in keys
          - "revoked"  -> listed in revoked_keys
          - "expired"  -> present but expires_at <= now
          - "ok"       -> present and active
        """
        if not isinstance(key_id, str) or not key_id.strip():
            return "missing"

        kid = key_id.strip()
        if kid in self.revoked_keys:
            return "revoked"

        entry = self.keys.get(kid)
        if entry is None:
            return "missing"

        if entry.expires_at is not None:
            n = now or datetime.now(timezone.utc)
            if n.tzinfo is None:
                n = n.replace(tzinfo=timezone.utc)
            n = n.astimezone(timezone.utc)

            if n >= entry.expires_at:
                return "expired"

        return "ok"

    def get_entry(self, key_id: str) -> Optional[TrustedKey]:
        """
        Return the raw TrustedKey entry (even if expired), or None if missing.
        Intended for diagnostics / tooling.
        """
        if not isinstance(key_id, str) or not key_id.strip():
            return None
        return self.keys.get(key_id.strip())

    # ---- existing helpers ----

    def is_revoked(self, key_id: str) -> bool:
        return isinstance(key_id, str) and key_id.strip() in self.revoked_keys

    def is_expired(self, key_id: str, *, now: Optional[datetime] = None) -> bool:
        entry = self.keys.get(key_id.strip()) if isinstance(key_id, str) else None
        if entry is None or entry.expires_at is None:
            return False
        n = now or datetime.now(timezone.utc)
        if n.tzinfo is None:
            n = n.replace(tzinfo=timezone.utc)
        return n.astimezone(timezone.utc) >= entry.expires_at

    @staticmethod
    def _parse_trusted_keys_obj(obj: Dict[str, Any]) -> Dict[str, TrustedKey]:
        """
        Parse trusted_keys object.

        Supported:
          - "key_id": "<base64-or-hex-or-pem>"
          - "key_id": { "public_key": "<...>", "expires_at": "..." }
        """
        out: Dict[str, TrustedKey] = {}

        for key_id, v in obj.items():
            if not isinstance(key_id, str) or not key_id.strip():
                raise KeyRingError("key_id must be a non-empty string")
            kid = key_id.strip()

            # Case A: shorthand string
            if isinstance(v, str):
                key_str = v
                raw = _parse_public_key_to_bytes(key_str)

                if len(raw) != 32:
                    raise KeyRingError(
                        f"Public key for '{kid}' has invalid length {len(raw)} bytes "
                        "(expected 32 bytes for Ed25519)"
                    )

                out[kid] = TrustedKey(public_key=raw, expires_at=None)
                continue

            # Case B: structured object
            if isinstance(v, dict):
                pk = v.get("public_key")
                if not isinstance(pk, str) or not pk.strip():
                    raise KeyRingError(f"Public key for '{kid}' must be a non-empty string")

                raw = _parse_public_key_to_bytes(pk)

                if len(raw) != 32:
                    raise KeyRingError(
                        f"Public key for '{kid}' has invalid length {len(raw)} bytes "
                        "(expected 32 bytes for Ed25519)"
                    )

                expires_at_val = v.get("expires_at")
                expires_at: Optional[datetime] = None
                if expires_at_val is not None:
                    if not isinstance(expires_at_val, str):
                        raise KeyRingError(f"expires_at for '{kid}' must be a string (ISO8601)")
                    expires_at = _parse_expires_at(expires_at_val)

                out[kid] = TrustedKey(public_key=raw, expires_at=expires_at)
                continue

            raise KeyRingError(
                f"Invalid trusted_keys entry for '{kid}': expected string or object"
            )

        return out

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "TrustedKeyRing":
        """
        Build a keyring from a dict.

        Supported formats:

        1) Recommended:
          {
            "trusted_keys": {
              "cfo_key_v1": "<base64-or-hex-or-pem>",
              "billing_key_v2": { "public_key": "<...>", "expires_at": "..." }
            },
            "revoked_keys": ["old_key_v0"]
          }

        2) Minimal legacy:
          {
            "cfo_key_v1": "<...>",
            "billing_key_v2": "<...>"
          }
        """
        if not isinstance(d, dict):
            raise KeyRingError("Keyring JSON must be an object")

        revoked: Set[str] = set()

        # Preferred: explicit trusted_keys object
        if "trusted_keys" in d and isinstance(d.get("trusted_keys"), dict):
            keys_obj = d["trusted_keys"]
            keys = TrustedKeyRing._parse_trusted_keys_obj(keys_obj)

            rk = d.get("revoked_keys")
            if rk is not None:
                if not isinstance(rk, list) or not all(isinstance(x, str) for x in rk):
                    raise KeyRingError("revoked_keys must be a list of strings")
                revoked = {x.strip() for x in rk if x.strip()}

            return TrustedKeyRing(keys=keys, revoked_keys=revoked)

        # Legacy/minimal: assume the whole dict is key_id -> key_string
        # Ignore optional top-level fields if someone accidentally included them.
        filtered: Dict[str, Any] = {
            k: v for k, v in d.items() if k not in {"revoked_keys", "trusted_keys"}
        }

        # If they used minimal, values must be strings
        for k, v in filtered.items():
            if not isinstance(v, str):
                raise KeyRingError(
                    "Legacy keyring format expects a mapping of key_id -> key_string"
                )

        keys = TrustedKeyRing._parse_trusted_keys_obj(filtered)  # type: ignore[arg-type]
        return TrustedKeyRing(keys=keys, revoked_keys=set())

    @staticmethod
    def from_json_file(path: Path) -> "TrustedKeyRing":
        """
        Load from a JSON file.
        """
        if not path.exists():
            raise KeyRingError(f"Keyring file not found: {path}")

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception as e:
            raise KeyRingError(f"Invalid JSON in keyring file: {path}") from e

        if not isinstance(data, dict):
            raise KeyRingError("Keyring JSON must be an object")

        return TrustedKeyRing.from_dict(data)

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

        return TrustedKeyRing(keys={}, revoked_keys=set())
