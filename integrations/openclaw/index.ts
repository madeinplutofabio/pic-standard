/**
 * PIC Standard plugin for OpenClaw.
 *
 * Entry point — registers lifecycle hooks using api.on() for typed hook system.
 *
 * IMPORTANT: Use api.on() for lifecycle hooks (before_tool_call, etc.), NOT api.registerHook().
 * - api.registerHook() → internal hooks (old system, requires config flag)
 * - api.on() → typed hooks (new system, always active, used by hook runner)
 */

import type { OpenClawPluginApi } from "openclaw/plugin-sdk";
import picGateHandler from "./hooks/pic-gate/handler.js";
import picInitHandler from "./hooks/pic-init/handler.js";
import picAuditHandler from "./hooks/pic-audit/handler.js";

export default function register(api: OpenClawPluginApi): void {
    // pic-init: Inject PIC awareness at session start
    api.on("before_agent_start", picInitHandler, { priority: 50 });

    // pic-gate: Verify tool calls before execution (fail-closed)
    api.on("before_tool_call", picGateHandler, { priority: 100 });

    // pic-audit: Log verification outcomes after execution
    api.on("tool_result_persist", picAuditHandler, { priority: 200 });
}
