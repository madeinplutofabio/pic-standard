from __future__ import annotations

import warnings
from enum import Enum
from typing import Any, Dict, List, Optional, Set

from pydantic import BaseModel, field_validator, model_validator

# ------------------------------------------------------------------
# v0.8.1: semi_trusted deprecation warning
# ------------------------------------------------------------------


class PICSemiTrustedDeprecationWarning(FutureWarning):
    """Emitted when a Provenance entry is constructed with trust='semi_trusted'.

    The 'semi_trusted' value is deprecated in v0.8.1 and will be removed from
    the proposal schema and TrustLevel enum in v0.9.0. The pydantic field
    validator on Provenance.trust normalizes the value to 'untrusted' at
    construction time and emits this warning, in all modes (not only
    strict_trust=True).

    Producers should migrate to trust='untrusted' and attach verifiable
    evidence; verifiers derive effective trust from successful evidence
    verification per the trust axiom (v0.7.5).
    """

    pass


class TrustLevel(str, Enum):
    TRUSTED = "trusted"
    SEMI_TRUSTED = "semi_trusted"
    UNTRUSTED = "untrusted"


class ImpactClass(str, Enum):
    READ = "read"
    WRITE = "write"
    EXTERNAL = "external"
    IRREVERSIBLE = "irreversible"
    MONEY = "money"
    COMPUTE = "compute"
    PRIVACY = "privacy"


class Provenance(BaseModel):
    id: str
    trust: TrustLevel

    @field_validator("trust", mode="before")
    @classmethod
    def _normalize_semi_trusted(cls, v: Any) -> Any:
        """Canonical normalization boundary for the deprecated 'semi_trusted' value.

        Fires at Provenance construction time, in all modes. Any path that bypasses
        this validator is non-conformant with the v0.8.1 behavior contract.

        Detects 'semi_trusted' as either the raw string or the TrustLevel enum
        member (TrustLevel is a str-Enum, so equality unifies both forms).
        Emits PICSemiTrustedDeprecationWarning and returns TrustLevel.UNTRUSTED;
        all other values pass through unchanged for pydantic to coerce normally.
        """
        if v == "semi_trusted":
            warnings.warn(
                "PIC deprecation: provenance trust='semi_trusted' is "
                "deprecated in v0.8.1 and will be removed in v0.9.0. "
                "Normalizing to 'untrusted'. Producers should migrate "
                "to trust='untrusted' with verifiable evidence; "
                "verifiers derive effective trust from evidence per the "
                "trust axiom. See docs/migration-trust-sanitization.md.",
                PICSemiTrustedDeprecationWarning,
                stacklevel=2,
            )
            return TrustLevel.UNTRUSTED
        return v


class Claim(BaseModel):
    text: str
    evidence: List[str]


class ActionProposal(BaseModel):
    protocol: str = "PIC/1.0"
    intent: str
    impact: ImpactClass
    provenance: List[Provenance]
    claims: List[Claim]
    action: Dict[str, Any]

    # Impacts which require at least one claim referencing TRUSTED provenance evidence.
    # This aligns with your stated gap: privacy should be enforced too.
    HIGH_IMPACT: Set[ImpactClass] = {
        ImpactClass.MONEY,
        ImpactClass.IRREVERSIBLE,
        ImpactClass.PRIVACY,
    }

    @model_validator(mode="after")
    def verify_causal_contract(self) -> "ActionProposal":
        # Minimal reference rule: high-impact actions require trusted evidence
        if self.impact in self.HIGH_IMPACT:
            trusted_ids = {p.id for p in self.provenance if p.trust == TrustLevel.TRUSTED}

            has_trusted_evidence = any(
                any(ev_id in trusted_ids for ev_id in claim.evidence) for claim in self.claims
            )

            if not has_trusted_evidence:
                raise ValueError(
                    f"Contract Violation: Action of type '{self.impact}' cannot proceed "
                    f"without evidence from a TRUSTED source."
                )

        return self

    def verify_with_context(self, *, expected_tool: Optional[str] = None) -> None:
        """
        Optional integration-time checks that require runtime context.

        expected_tool:
          - If provided, enforce tool binding: proposal.action.tool must match.
          - If not provided, no tool-binding enforcement is performed (offline-safe).
        """
        if expected_tool is None:
            return

        exp = expected_tool.strip()
        if not exp:
            return

        tool = self.action.get("tool")
        if not isinstance(tool, str) or not tool.strip():
            raise ValueError("Contract Violation: proposal.action.tool must be a non-empty string")

        if tool.strip() != exp:
            raise ValueError(
                f"Contract Violation: Tool binding mismatch (proposal.action.tool='{tool.strip()}' "
                f"but actual tool='{exp}')."
            )
