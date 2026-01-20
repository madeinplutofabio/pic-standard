from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional, Set


@dataclass
class PICPolicy:
    """Policy configuration for enforcing PIC at tool boundaries.

    - impact_by_tool: map tool name -> impact class (money/privacy/compute/etc)
    - require_evidence_for_impacts: impact classes that must pass evidence verification (if enabled)
    - require_pic_for_impacts: impact classes that must include a __pic proposal (recommended)
    """
    impact_by_tool: Dict[str, str] = field(default_factory=dict)

    # If a tool's impact is in this set, a __pic proposal must be provided
    require_pic_for_impacts: Set[str] = field(default_factory=lambda: {"money", "privacy", "irreversible"})

    # If a tool's impact is in this set, evidence verification must pass (when verify_evidence=True)
    require_evidence_for_impacts: Set[str] = field(default_factory=lambda: {"money", "privacy", "irreversible"})

    def get_tool_impact(self, tool_name: str, proposal_impact: Optional[str] = None) -> Optional[str]:
        # Prefer explicit policy mapping if present; fallback to proposal impact.
        return self.impact_by_tool.get(tool_name) or proposal_impact
