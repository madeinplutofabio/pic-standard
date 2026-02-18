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
import { createPicAuditHandler } from "./hooks/pic-audit/handler.js";
import { createPicGateHandler } from "./hooks/pic-gate/handler.js";
import { createPicInitHandler } from "./hooks/pic-init/handler.js";

export default function register(api: OpenClawPluginApi): void {
    const pluginConfig = (api.pluginConfig ?? {}) as Record<string, unknown>;

    // pic-init: Inject PIC awareness at session start
    api.on("before_agent_start", createPicInitHandler(pluginConfig), { priority: 50 });

    // pic-gate: Verify tool calls before execution (fail-closed)
    api.on("before_tool_call", createPicGateHandler(pluginConfig), { priority: 100 });

    // pic-audit: Log verification outcomes after execution
    api.on("tool_result_persist", createPicAuditHandler(pluginConfig), { priority: 200 });
}
