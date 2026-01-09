from enum import Enum
from typing import List, Dict, Any
from pydantic import BaseModel, model_validator

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

class Claim(BaseModel):
    text: str
    evidence: List[str]  # Must match a Provenance ID

class ActionProposal(BaseModel):
    protocol: str = "PIC/1.0"
    intent: str
    impact: ImpactClass
    provenance: List[Provenance]
    claims: List[Claim]
    action: Dict[str, Any]

    @model_validator(mode="after")
    def verify_causal_contract(self) -> 'ActionProposal':
        # RULE: High-impact actions require Trusted provenance evidence
        if self.impact in [ImpactClass.MONEY, ImpactClass.IRREVERSIBLE]:
            trusted_ids = {p.id for p in self.provenance if p.trust == TrustLevel.TRUSTED}
            
            # Check if at least one claim is backed by a trusted source
            has_trusted_evidence = any(
                any(ev_id in trusted_ids for ev_id in claim.evidence)
                for claim in self.claims
            )
            
            if not has_trusted_evidence:
                raise ValueError(
                    f"Contract Violation: Action of type '{self.impact}' "
                    f"cannot proceed without evidence from a TRUSTED source."
                )
        return self

# Example Validation
if __name__ == "__main__":
    test_data = {
        "intent": "Authorize Ad Spend",
        "impact": "money",
        "provenance": [{"id": "budget_v1", "trust": "trusted"}],
        "claims": [{"text": "Approved budget $500", "evidence": ["budget_v1"]}],
        "action": {"tool": "ads.pay", "args": {"amount": 500}}
    }
    
    try:
        proposal = ActionProposal(**test_data)
        print("✅ Contract Validated Successfully.")
    except Exception as e:
        print(f"❌ Contract Breach: {e}")
