from __future__ import annotations

import sys
from pathlib import Path

# Ensure sdk-python is importable without install
_sdk_path = str(Path(__file__).resolve().parent.parent / "sdk-python")
if _sdk_path not in sys.path:
    sys.path.insert(0, _sdk_path)

# E402: pytest import deliberately follows the sys.path setup above so the
# in-tree pic_standard package resolves without `pip install -e .`.
import pytest  # noqa: E402


def make_proposal(
    *,
    tool: str = "payments_send",
    args: dict | None = None,
    impact: str = "money",
    intent: str = "Send $50 to vendor for invoice #1234",
    trust: str = "trusted",
    prov_id: str = "approved_invoice",
    claim_text: str | None = None,
    extra_provenance: list[dict] | None = None,
    extra_evidence: list[dict] | None = None,
    **overrides: object,
) -> dict:
    """
    Build a minimal valid PIC proposal dict.

    Defaults to a trusted money proposal (the most common test case).
    Override any field via keyword arguments.
    """
    provenance = [{"id": prov_id, "trust": trust}]
    if extra_provenance:
        provenance.extend(extra_provenance)

    claim = claim_text or intent
    claims = [{"text": claim, "evidence": [prov_id]}]

    proposal: dict = {
        "protocol": "PIC/1.0",
        "intent": intent,
        "impact": impact,
        "provenance": provenance,
        "claims": claims,
        "action": {"tool": tool, "args": args or {}},
    }
    if extra_evidence is not None:
        proposal["evidence"] = extra_evidence

    proposal.update(overrides)
    return proposal


# ---------------------------------------------------------------------------
# Reusable pytest fixtures (built on make_proposal)
# ---------------------------------------------------------------------------


@pytest.fixture
def money_proposal() -> dict:
    return make_proposal()


@pytest.fixture
def untrusted_money_proposal() -> dict:
    return make_proposal(trust="untrusted", prov_id="web_page")


@pytest.fixture
def read_proposal() -> dict:
    return make_proposal(tool="docs_search", impact="read", intent="Search docs")
