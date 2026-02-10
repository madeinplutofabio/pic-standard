---
name: pic-init
description: PIC awareness injection — informs the agent about PIC governance at session start
metadata:
  openclaw:
    events: ["before_agent_start"]
    priority: 50
---

# pic-init — PIC Awareness Injection

Fires once at session start via `before_agent_start`. Pushes a system
message that tells the agent about PIC governance so it knows to include
`__pic` proposals in tool calls.

## Behavior

- Pushes a concise PIC awareness message into `event.messages`
- Checks bridge health to warn early if the bridge is unreachable
- Never blocks, never throws