from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
from urllib.parse import urlparse

from pydantic import BaseModel, Field


class EvidenceRef(BaseModel):
    """Resolvable evidence reference.

    v0.3 supports deterministic SHA-256 verification of file-backed artifacts.
    """
    id: str
    type: str = Field(..., description="Evidence type. v0.3 supports: 'hash'")
    ref: str = Field(..., description="Resolvable reference. v0.3 supports file:// URIs")
    sha256: str = Field(..., description="Expected SHA-256 hex digest (64 chars)")
    attestor: Optional[str] = None


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


def _compute_sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _is_relative_to(path: Path, root: Path) -> bool:
    """Python 3.10 compatible version of Path.is_relative_to()."""
    try:
        path.relative_to(root)
        return True
    except Exception:
        return False


def _resolve_file_uri_path(ref: str, *, base_dir: Path) -> Path:
    """Parse file:// URI into a Path (not yet sandbox-validated).

    Supports:
      - file://artifacts/invoice.txt      (treat as relative: artifacts/invoice.txt)
      - file://invoice.txt               (relative: invoice.txt)
      - file:///C:/path/on/windows       (absolute: C:/path/on/windows)
      - file:///absolute/path            (POSIX absolute)
      - file://C:/path/on/windows        (sometimes seen; treat as absolute)

    NOTE: v0.3 intentionally does NOT support http(s).
    """
    if not ref.startswith("file://"):
        raise ValueError(f"Unsupported ref scheme for v0.3: {ref}")

    parsed = urlparse(ref)

    # IMPORTANT:
    # file://A/B is parsed as netloc="A", path="/B"
    # So we must recombine them into "A/B" (a relative path).
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

    # Handle common Windows form: "/C:/..." -> "C:/..."
    if combined.startswith("/") and len(combined) >= 3 and combined[2] == ":":
        combined = combined.lstrip("/")

    p = Path(combined)

    # If it looks like a Windows drive path (e.g. "C:/x" or "C:\\x") treat as absolute
    # Path("C:/x").is_absolute() is True on Windows.
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
    """
    Resolve file:// URI and enforce sandbox:

      - evidence_root_dir is the only allowed root for evidence files
      - blocks path traversal by verifying resolved path stays under root
      - blocks absolute paths outside root
      - enforces max file size
    """
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


class EvidenceSystem:
    """Evidence verification engine (v0.3: SHA-256 hash evidence).

    v0.3.2 hardening:
      - sandbox file evidence to evidence_root_dir (default: base_dir)
      - prevents path traversal / escape
      - enforces max evidence file size
      - allow_file_evidence switch
    """

    def __init__(
        self,
        *,
        max_file_bytes: int = 5 * 1024 * 1024,  # 5MB
        allow_file_evidence: bool = True,
    ) -> None:
        self.max_file_bytes = int(max_file_bytes)
        self.allow_file_evidence = bool(allow_file_evidence)

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
                ev = EvidenceRef(**raw)

                if ev.type != "hash":
                    raise ValueError(f"Unsupported evidence type for v0.3: {ev.type}")

                if not self.allow_file_evidence:
                    raise ValueError("file evidence is disabled by policy")

                expected = ev.sha256.lower()
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
                    results.append(
                        EvidenceResult(
                            id=ev.id,
                            ok=False,
                            message=f"sha256 mismatch (expected {expected}, got {actual})",
                        )
                    )
                    continue

                verified.add(ev.id)
                results.append(EvidenceResult(id=ev.id, ok=True, message="sha256 verified"))

            except Exception as e:
                results.append(EvidenceResult(id=str(ev_id), ok=False, message=str(e)))

        ok = all(r.ok for r in results) and len(results) > 0
        return EvidenceReport(ok=ok, results=results, verified_ids=verified)


def apply_verified_ids_to_provenance(proposal: Dict[str, Any], verified_ids: Set[str]) -> Dict[str, Any]:
    """Upgrade provenance trust levels in-memory based on verified evidence IDs.

    v0.3.2 hardening:
      - ensure schema-required 'source' exists when upgrading (defensive)
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
