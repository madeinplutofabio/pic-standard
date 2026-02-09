---
events: ["tool_result_persist"]
priority: 200
---

# pic-audit — PIC Post-Execution Audit Trail

Fires after every tool execution via `tool_result_persist`. Logs a
structured audit record capturing the PIC verification outcome for
the tool call that just completed.

## Behavior

- Logs structured JSON audit entries at info level
- Records: tool name, whether PIC was present, verification result
- Never modifies the tool result
- Never throws
