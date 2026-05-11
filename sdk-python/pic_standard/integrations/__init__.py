"""PIC Standard integrations — lazy-loaded to avoid pulling optional dependencies."""

from typing import TYPE_CHECKING

# Safe re-exports (no optional deps)
from ..pipeline import (
    PICEvaluateLimits,
    PipelineOptions,
    PipelineResult,
    verify_proposal,
)

__all__ = [
    "PICEvaluateLimits",
    "PICToolNode",
    "PipelineOptions",
    "PipelineResult",
    "guard_mcp_tool",
    "guard_mcp_tool_async",
    "start_bridge",
    "verify_proposal",
]

if TYPE_CHECKING:
    from .http_bridge import start_bridge
    from .langgraph_pic_toolnode import PICToolNode
    from .mcp_pic_guard import guard_mcp_tool, guard_mcp_tool_async


def __getattr__(name: str):
    if name == "PICToolNode":
        from .langgraph_pic_toolnode import PICToolNode

        return PICToolNode
    if name in ("guard_mcp_tool", "guard_mcp_tool_async"):
        from .mcp_pic_guard import guard_mcp_tool, guard_mcp_tool_async

        return guard_mcp_tool if name == "guard_mcp_tool" else guard_mcp_tool_async
    if name == "start_bridge":
        from .http_bridge import start_bridge

        return start_bridge
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__():
    return sorted(set(globals()) | set(__all__))
