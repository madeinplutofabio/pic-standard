"""Smoke tests — LangGraph / langchain_core API surface.

These verify the upstream classes and attributes that
``pic_standard.integrations.langgraph_pic_toolnode`` relies on.
They do NOT test PIC logic; they exist so Dependabot PRs that bump
langchain-core will fail CI if the API surface changes.

The final two tests exercise the real PICToolNode integration path
to confirm end-to-end compatibility.
"""
from __future__ import annotations

import pytest
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.tools import BaseTool, tool

from conftest import make_proposal


# ---------------------------------------------------------------------------
# Upstream API shape checks
# ---------------------------------------------------------------------------

def test_ai_message_has_tool_calls():
    """PICToolNode reads ``last.tool_calls`` (line 44)."""
    msg = AIMessage(content="hi")
    assert hasattr(msg, "tool_calls"), "AIMessage must expose tool_calls"


def test_tool_message_accepts_content_and_tool_call_id():
    """PICToolNode constructs ToolMessage(content=..., tool_call_id=...) (line 84)."""
    tm = ToolMessage(content="ok", tool_call_id="tc_1")
    assert tm.content == "ok"
    assert tm.tool_call_id == "tc_1"


def test_base_tool_instance_has_name_and_invoke():
    """PICToolNode indexes tools by ``.name`` and calls ``.invoke()`` (lines 33, 81)."""

    @tool
    def probe_tool(x: str) -> str:
        """A probe tool."""
        return x

    assert hasattr(probe_tool, "name"), "BaseTool instance must have name"
    assert probe_tool.name == "probe_tool"
    assert callable(getattr(probe_tool, "invoke", None)), "BaseTool instance must have invoke"


def test_tool_decorator_produces_base_tool():
    """PICToolNode accepts ``list[BaseTool]``; @tool must produce one."""

    @tool
    def dummy_tool(x: str) -> str:
        """A dummy tool."""
        return x

    assert isinstance(dummy_tool, BaseTool), "@tool must produce a BaseTool instance"


# ---------------------------------------------------------------------------
# Real integration-path smoke tests
# ---------------------------------------------------------------------------

def test_pic_toolnode_smoke_allows_trusted_call():
    """Full PICToolNode.invoke() path: trusted proposal → tool executes → ToolMessage."""
    from pic_standard.integrations.langgraph_pic_toolnode import PICToolNode

    @tool
    def greet(name: str) -> str:
        """Say hello."""
        return f"Hello, {name}!"

    proposal = make_proposal(
        tool="greet", impact="read", intent="Greet the user",
        args={"name": "Alice"},
    )

    node = PICToolNode(tools=[greet])
    state = {
        "messages": [
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "id": "call_1",
                        "name": "greet",
                        "args": {"name": "Alice", "__pic": proposal},
                    }
                ],
            )
        ]
    }

    result = node.invoke(state)

    msgs = result["messages"]
    assert len(msgs) == 1
    assert isinstance(msgs[0], ToolMessage)
    assert msgs[0].content == "Hello, Alice!"
    assert msgs[0].tool_call_id == "call_1"


def test_pic_toolnode_smoke_blocks_untrusted_money():
    """Full PICToolNode.invoke() path: untrusted money → ValueError raised."""
    from pic_standard.integrations.langgraph_pic_toolnode import PICToolNode

    @tool
    def pay(amount: int) -> str:
        """Send payment."""
        return f"Paid {amount}"

    proposal = make_proposal(
        tool="pay", impact="money", trust="untrusted", prov_id="web_page",
        args={"amount": 100},
    )

    node = PICToolNode(tools=[pay])
    state = {
        "messages": [
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "id": "call_2",
                        "name": "pay",
                        "args": {"amount": 100, "__pic": proposal},
                    }
                ],
            )
        ]
    }

    with pytest.raises(ValueError) as exc:
        node.invoke(state)
    assert "PIC blocked" in str(exc.value)
