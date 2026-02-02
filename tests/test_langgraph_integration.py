import pytest
from langchain_core.messages import AIMessage
from langchain_core.tools import tool

from pic_standard.integrations import PICToolNode


@tool
def payments_send(amount: int) -> str:
    """Send a payment of the given amount (test tool)."""
    return f"sent ${amount}"


def make_money_proposal(trust: str) -> dict:
    prov_id = "invoice_123" if trust == "trusted" else "random_web"
    return {
        "protocol": "PIC/1.0",
        "intent": "Send payment",
        "impact": "money",
        "provenance": [{"id": prov_id, "trust": trust, "source": "unit-test"}],
        "claims": [{"text": "Pay $500", "evidence": [prov_id]}],
        "action": {"tool": "payments_send", "args": {"amount": 500}},
    }


def test_pic_toolnode_blocks_untrusted_money():
    node = PICToolNode([payments_send])
    state = {
        "messages": [
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "payments_send",
                        "args": {"amount": 500, "__pic": make_money_proposal("untrusted")},
                        "id": "1",
                    }
                ],
            )
        ]
    }
    with pytest.raises(ValueError):
        node.invoke(state)


def test_pic_toolnode_allows_trusted_money():
    node = PICToolNode([payments_send])
    state = {
        "messages": [
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "payments_send",
                        "args": {"amount": 500, "__pic": make_money_proposal("trusted")},
                        "id": "2",
                    }
                ],
            )
        ]
    }
    out = node.invoke(state)
    assert out["messages"][0].content == "sent $500"


def test_pic_toolnode_blocks_tool_binding_mismatch():
    """
    Integration must block when the actual tool call name doesn't match
    proposal.action.tool. This should be enforced via ActionProposal.verify_with_context(...).
    """
    node = PICToolNode([payments_send])

    proposal = make_money_proposal("trusted")
    proposal["action"]["tool"] = "some_other_tool"  # mismatch on purpose

    state = {
        "messages": [
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "payments_send",  # actual tool being called
                        "args": {"amount": 500, "__pic": proposal},
                        "id": "3",
                    }
                ],
            )
        ]
    }

    with pytest.raises(ValueError) as e:
        node.invoke(state)

    # Don't assert the exact string (too brittle), but require clear intent.
    msg = str(e.value).lower()
    assert "tool" in msg and ("binding" in msg or "mismatch" in msg)

