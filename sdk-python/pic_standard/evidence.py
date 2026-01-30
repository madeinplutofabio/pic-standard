from __future__ import annotations

import base64
import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Union
from urllib.parse import urlparse

from pydantic import BaseModel, Field
from typing import Literal


# ----------------------------
# Models (match schema intent)
# ----------------------------

class HashEvidenceRef(BaseModel):
    """v0.3: deterministic sha256 over file bytes."""
    id: str
    type: Literal["hash"] = "hash"
    ref: str = Field(..., description="file://... (sandboxed)")
    sha256: str = Field(..., description="Expected SHA-256 hex digest (64 chars)")
    attestor: Optional[str] = None


class SigEvidenceRef(BaseModel):
    """v0.4: Ed25519 signature over payload bytes."""
    id: str
    type: Literal["sig"] = "sig"

    # ref is informational for now (e.g. "inline:approval_payload")
    ref: str = Field(..., description="Evidence reference label (e.g. inline:...)")

    payload: str = Field(..., description="Exact bytes-to-verify as UTF-8 string")
    alg: Literal["ed25519"] = "ed25519"
    signature: str = Field(..., description="Base64 Ed25519 signature over payload bytes")
    key_id: str = Field(..., description="Key id resolved in trusted keyring")
    signer: Optional[str] = Field(None, description="Human/service identity (informational)")
    attestor: Optional[str] = None


EvidenceRef = Union[HashEvidenceRef, SigEvidenceRef]


# ----------------------------
# Report types
# ----------------------------

@dataclass
class EvidenceResult:
    id: str
    ok: bool
    message: str


@dataclass
class EvidenceReport:
    ok: bool
    results: List[EvidenceResult]
    verified_ids: Set[str]


# ----------------------------
# Helpers
# ----------------------------

def _compute_sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _is_relative_to(path: Path, root: Path) -> bool:
    """Python 3.10 compatible Path.is_relative_to()."""
    try:
        path.relative_to(root)
        return True
    except Exception:
        return False


def _resolve_file_uri_path(ref: str, *, base_dir: Path) -> Path:
    """Parse file:// URI into a Path (not yet sandbox-validated).

    Supports:
      - file://artifacts/invoice.txt      (relative)
      - file://invoice.txt               (relative)
      - file:///C:/path/on/windows       (absolute)
      - file:///absolute/path            (POSIX absolute)
      - file://C:/path/on/windows        (sometimes seen; absolute)
    """
    if not ref.startswith("file://"):
        raise ValueError(f"Unsupported ref scheme for hash evidence: {ref}")

    parsed = urlparse(ref)

    # file://A/B -> netloc="A", path="/B"
    netloc = parsed.netloc or ""
    path_part = parsed.path or ""

    if netloc and path_part:
        combined = f"{netloc}/{path_part.lstrip('/')}"
    elif netloc and not path_part:
        combined = netloc
    else:
        combined = path_part

    if not combined:
        raise ValueError("Empty file URI path")

    # Windows: "/C:/..." -> "C:/..."
    if combined.startswith("/") and len(combined) >= 3 and combined[2] == ":":
        combined = combined.lstrip("/")

    p = Path(combined)

    if not p.is_absolute():
        p = (base_dir / p).resolve()
    else:
        p = p.resolve()

    return p


def _read_sandboxed_file(
    ref: str,
    *,
    base_dir: Path,
    evidence_root_dir: Path,
    max_file_bytes: int,
) -> bytes:
    """Resolve file:// URI and enforce sandbox."""
    p = _resolve_file_uri_path(ref, base_dir=base_dir)

    root = evidence_root_dir.resolve()
    if not _is_relative_to(p, root):
        raise ValueError(f"Evidence file escapes evidence_root_dir: {p} not under {root}")

    if not p.exists():
        raise FileNotFoundError(f"Evidence file not found: {p}")

    size = p.stat().st_size
    if size > max_file_bytes:
        raise ValueError(f"Evidence file too large: {size} bytes (max {max_file_bytes})")

    return p.read_bytes()


def _b64decode(s: str, *, what: str) -> bytes:
    """Accept standard or urlsafe base64, with/without padding."""
    try:
        raw = s.strip().replace("-", "+").replace("_", "/")
        pad = "=" * ((4 - len(raw) % 4) % 4)
        return base64.b64decode(raw + pad, validate=True)
    except Exception as e:
        raise ValueError(f"Invalid base64 for {what}") from e


def _load_public_key_from_keyring(key_id: str) -> bytes:
    """Resolve raw public key bytes from TrustedKeyRing via key_id."""
    from pic_standard.keyring import TrustedKeyRing

    kr = TrustedKeyRing.load_default()
    pub = kr.get(key_id)

    if not pub:
        raise ValueError(f"Unknown key_id '{key_id}' (not present in trusted keyring)")
    if not isinstance(pub, (bytes, bytearray)):
        raise ValueError(f"Invalid key type for '{key_id}' (expected bytes)")
    if len(pub) != 32:
        raise ValueError(f"Invalid Ed25519 public key length for '{key_id}' (expected 32 bytes)")

    return bytes(pub)


def _verify_ed25519_signature(*, public_key_raw: bytes, signature_b64: str, message: bytes) -> bool:
    """Verify Ed25519 signature using cryptography."""
    try:
        from cryptography.hazmat.primitives.asymmetric import ed25519
    except Exception as e:  # pragma: no cover
        raise ValueError(
            "cryptography is required for signature evidence. "
            "Install it via: pip install 'pic-standard[crypto]'"
        ) from e

    sig_raw = _b64decode(signature_b64, what="signature")
    if len(sig_raw) != 64:
        raise ValueError("Invalid Ed25519 signature length (expected 64 raw bytes)")

    pk = ed25519.Ed25519PublicKey.from_public_bytes(public_key_raw)
    try:
        pk.verify(sig_raw, message)
        return True
    except Exception:
        return False


# ----------------------------
# EvidenceSystem
# ----------------------------

class EvidenceSystem:
    """Evidence verification engine.

    Supported evidence:
      - v0.3: type="hash" (sha256 over sandboxed file bytes)
      - v0.4: type="sig"  (ed25519 signature over payload bytes)

    Hardening:
      - sandbox file:// under evidence_root_dir
      - max_file_bytes
      - max_payload_bytes
    """

    def __init__(
        self,
        *,
        max_file_bytes: int = 5 * 1024 * 1024,   # 5MB
        max_payload_bytes: int = 16 * 1024,       # 16KB payload cap (DoS guard)
        allow_file_evidence: bool = True,
        allow_sig_evidence: bool = True,
    ) -> None:
        self.max_file_bytes = int(max_file_bytes)
        self.max_payload_bytes = int(max_payload_bytes)
        self.allow_file_evidence = bool(allow_file_evidence)
        self.allow_sig_evidence = bool(allow_sig_evidence)

    def verify_all(
        self,
        proposal: Dict[str, Any],
        *,
        base_dir: Path,
        evidence_root_dir: Optional[Path] = None,
    ) -> EvidenceReport:
        evidence_list = proposal.get("evidence") or []
        if not evidence_list:
            return EvidenceReport(ok=False, results=[], verified_ids=set())

        root_dir = (evidence_root_dir or base_dir).resolve()

        results: List[EvidenceResult] = []
        verified: Set[str] = set()

        for raw in evidence_list:
            ev_id = raw.get("id", "<missing id>")
            try:
                # Parse by declared type (fail-closed)
                ev_type = raw.get("type")
                if ev_type == "hash":
                    ev: EvidenceRef = HashEvidenceRef(**raw)
                elif ev_type == "sig":
                    ev = SigEvidenceRef(**raw)
                else:
                    raise ValueError(f"Unsupported evidence type: {ev_type!r}")

                if isinstance(ev, HashEvidenceRef):
                    if not self.allow_file_evidence:
                        raise ValueError("file evidence is disabled by policy")

                    expected = (ev.sha256 or "").strip().lower()
                    if len(expected) != 64:
                        raise ValueError("Invalid sha256 (expected 64 hex chars)")

                    data = _read_sandboxed_file(
                        ev.ref,
                        base_dir=base_dir,
                        evidence_root_dir=root_dir,
                        max_file_bytes=self.max_file_bytes,
                    )
                    actual = _compute_sha256(data).lower()

                    if actual != expected:
                        results.append(EvidenceResult(id=ev.id, ok=False, message=f"sha256 mismatch (expected {expected}, got {actual})"))
                        continue

                    verified.add(ev.id)
                    results.append(EvidenceResult(id=ev.id, ok=True, message="sha256 verified"))
                    continue

                # SigEvidenceRef
                if not self.allow_sig_evidence:
                    raise ValueError("signature evidence is disabled by policy")

                payload_bytes = ev.payload.encode("utf-8")
                if len(payload_bytes) > self.max_payload_bytes:
                    raise ValueError(f"Payload too large: {len(payload_bytes)} bytes (max {self.max_payload_bytes})")

                pub_raw = _load_public_key_from_keyring(ev.key_id)
                ok = _verify_ed25519_signature(
                    public_key_raw=pub_raw,
                    signature_b64=ev.signature,
                    message=payload_bytes,
                )
                if not ok:
                    results.append(EvidenceResult(id=ev.id, ok=False, message=f"signature invalid (key_id='{ev.key_id}')"))
                    continue

                verified.add(ev.id)
                results.append(EvidenceResult(id=ev.id, ok=True, message=f"signature verified (key_id='{ev.key_id}')"))

            except Exception as e:
                results.append(EvidenceResult(id=str(ev_id), ok=False, message=str(e)))

        ok = all(r.ok for r in results) and len(results) > 0
        return EvidenceReport(ok=ok, results=results, verified_ids=verified)


def apply_verified_ids_to_provenance(proposal: Dict[str, Any], verified_ids: Set[str]) -> Dict[str, Any]:
    """Upgrade provenance trust levels in-memory based on verified evidence IDs.

    v0.3/v0.4 behavior:
      - If a provenance entry's id is verified, upgrade trust to 'trusted'.
      - Ensure 'source' exists (defensive).
    """
    out = dict(proposal)
    prov_in = proposal.get("provenance") or []
    prov: List[Dict[str, Any]] = [dict(p) for p in prov_in if isinstance(p, dict)]

    for p in prov:
        if p.get("id") in verified_ids:
            p["trust"] = "trusted"
            if not p.get("source"):
                p["source"] = "evidence"

    out["provenance"] = prov
    return out