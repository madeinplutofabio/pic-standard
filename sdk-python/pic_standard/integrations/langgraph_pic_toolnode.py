from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, Optional

from importlib import resources
from jsonschema import validate as js_validate, ValidationError

from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.tools import BaseTool

from pic_standard.verifier import ActionProposal

PIC_ARG_KEY = "__pic"  # tool_calls[i]["args"]["__pic"] = {... PIC proposal ...}


def _load_packaged_schema() -> dict:
    """Load PIC proposal schema from the installed package data."""
    schema_text = (
        resources.files("pic_standard")
        .joinpath("schemas/proposal_schema.json")
        .read_text(encoding="utf-8")
    )
    return json.loads(schema_text)


def _clean_pydantic_error(e: Exception) -> str:
    """
    Pydantic wraps validator ValueErrors into a ValidationError with noisy formatting.
    Extract the real error message for clean UX.
    """
    if hasattr(e, "errors"):
        try:
            errs = e.errors()
            if errs and isinstance(errs, list) and "msg" in errs[0]:
                return errs[0]["msg"]
        except Exception:
            pass
    return str(e)


def verify_pic_proposal(
    proposal: Dict[str, Any],
    *,
    expected_tool_name: Optional[str] = None,
) -> ActionProposal:
    """
    Verify proposal in 2 layers (+ context when available):
      1) JSON Schema validation
      2) Reference verifier (pydantic + PIC rules)

    Tool binding is enforced ONLY at integration boundaries (LangGraph/MCP),
    via ActionProposal.verify_with_context(expected_tool=...).

    Raises ValueError with clean messages on failure.
    """
    schema = _load_packaged_schema()

    try:
        js_validate(instance=proposal, schema=schema)
    except ValidationError as e:
        raise ValueError(f"PIC schema validation failed: {e.message}") from e

    try:
        ap = ActionProposal(**proposal)
    except Exception as e:
        raise ValueError(f"PIC blocked: {_clean_pydantic_error(e)}") from e

    if expected_tool_name is not None:
        # Canonical tool binding lives in verifier; integrations provide runtime context.
        try:
            ap.verify_with_context(expected_tool=expected_tool_name)
        except Exception as e:
            # Keep the message clean and deterministic.
            msg = str(e) or "tool binding failed"
            raise ValueError(f"PIC blocked: {msg}") from e

    return ap


@dataclass
class PICToolNode:
    """
    PIC-enforced tool execution node compatible with LangGraph-style "messages state".

    Requires each tool call to include:
        args["__pic"] = {...proposal...}

    Enforces:
      - schema validation
      - verifier rules
      - tool binding via ActionProposal.verify_with_context(expected_tool=...)

    Then executes the tool and returns ToolMessages.
    """

    tools: list[BaseTool]

    def __post_init__(self) -> None:
        self._tools_by_name: Dict[str, BaseTool] = {t.name: t for t in self.tools}

    def invoke(self, state: Dict[str, Any]) -> Dict[str, Any]:
        messages = state.get("messages", [])
        if not messages:
            raise ValueError("PICToolNode expects state['messages'] to contain at least one message.")

        last = messages[-1]
        if not isinstance(last, AIMessage):
            raise ValueError("PICToolNode expects the last message to be an AIMessage with tool_calls.")

        tool_calls = getattr(last, "tool_calls", None) or []
        if not tool_calls:
            return {"messages": []}

        results: list[ToolMessage] = []

        for tc in tool_calls:
            name = tc.get("name")
            if not name:
                raise ValueError("Tool call missing 'name'.")

            tool = self._tools_by_name.get(name)
            if tool is None:
                raise ValueError(f"Unknown tool '{name}'. Available: {list(self._tools_by_name.keys())}")

            args = dict(tc.get("args") or {})

            if PIC_ARG_KEY not in args:
                raise ValueError(
                    f"PIC missing: tool call '{name}' must include args['{PIC_ARG_KEY}'] with the PIC proposal."
                )

            proposal = args.pop(PIC_ARG_KEY)

            if not isinstance(proposal, dict):
                raise ValueError(
                    f"PIC invalid: args['{PIC_ARG_KEY}'] must be a dict (parsed JSON), got {type(proposal)}."
                )

            # Enforce PIC BEFORE calling the tool (includes tool binding via verify_with_context)
            verify_pic_proposal(proposal, expected_tool_name=name)

            # Execute tool
            observation = tool.invoke(args)

            tool_call_id = tc.get("id") or "tool_call"
            results.append(ToolMessage(content=str(observation), tool_call_id=tool_call_id))

        return {"messages": results}
