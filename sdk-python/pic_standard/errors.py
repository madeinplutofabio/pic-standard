from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional


class PICErrorCode(str, Enum):
    # Generic
    INVALID_REQUEST = "PIC_INVALID_REQUEST"
    LIMIT_EXCEEDED = "PIC_LIMIT_EXCEEDED"

    # Schema / verifier
    SCHEMA_INVALID = "PIC_SCHEMA_INVALID"
    VERIFIER_FAILED = "PIC_VERIFIER_FAILED"
    TOOL_BINDING_MISMATCH = "PIC_TOOL_BINDING_MISMATCH"

    # Evidence
    EVIDENCE_REQUIRED = "PIC_EVIDENCE_REQUIRED"
    EVIDENCE_FAILED = "PIC_EVIDENCE_FAILED"

    # Policy
    POLICY_VIOLATION = "PIC_POLICY_VIOLATION"


@dataclass
class PICError(Exception):
    """A structured error that can be safely returned to callers."""
    code: PICErrorCode
    message: str
    details: Optional[Dict[str, Any]] = None

    def __str__(self) -> str:
        # Keep it clean for logs / CLI
        return f"{self.code}: {self.message}"

    def to_public_dict(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {"code": self.code.value, "message": self.message}
        if self.details:
            out["details"] = self.details
        return out
