/**
 * pic-audit — PIC post-execution audit trail for OpenClaw.
 *
 * Hook: tool_result_persist (priority 200)
 *
 * Fires after a tool call completes. Logs a structured audit record.
 * This provides an audit trail for compliance and debugging.
 *
 * This hook is read-only — it never modifies the tool result or blocks
 * execution. It runs at priority 200 (after all functional hooks).
 *
 * IMPORTANT: This hook is SYNCHRONOUS ONLY — async handlers are rejected
 * by the OpenClaw hook runner.
 *
 * LIMITATION: The real tool_result_persist event contains
 * { toolName?, toolCallId?, message, isSynthetic? } — it does NOT include
 * params or __pic metadata (pic-gate strips __pic before execution, and
 * the persist event receives the result message, not the original call).
 */

import type { PICPluginConfig } from "../../lib/types.js";
import { DEFAULT_CONFIG } from "../../lib/types.js";

/** Real shape of tool_result_persist event (from OpenClaw src/plugins/types.ts). */
interface ToolResultPersistEvent {
    toolName?: string;
    toolCallId?: string;
    message: Record<string, unknown>;
    isSynthetic?: boolean;
}

/** Real shape of tool_result_persist context. */
interface ToolResultPersistContext {
    agentId?: string;
    sessionKey?: string;
    toolName?: string;
    toolCallId?: string;
}

/** Structured audit entry written to console. */
interface PICAuditEntry {
    timestamp: string;
    event: "tool_result_persist";
    tool: string;
    toolCallId?: string;
    isSynthetic: boolean;
}

/**
 * Resolve plugin config from captured pluginConfig (closure from register()).
 */
function resolveConfig(pluginConfig: Record<string, unknown>): PICPluginConfig {
    return {
        bridge_url:
            typeof pluginConfig.bridge_url === "string"
                ? pluginConfig.bridge_url
                : DEFAULT_CONFIG.bridge_url,
        bridge_timeout_ms:
            typeof pluginConfig.bridge_timeout_ms === "number"
                ? pluginConfig.bridge_timeout_ms
                : DEFAULT_CONFIG.bridge_timeout_ms,
        log_level:
            pluginConfig.log_level === "debug" || pluginConfig.log_level === "info" || pluginConfig.log_level === "warn"
                ? pluginConfig.log_level
                : DEFAULT_CONFIG.log_level,
    };
}

/**
 * Factory: creates the tool_result_persist handler with captured plugin config.
 */
export function createPicAuditHandler(
    pluginConfig: Record<string, unknown>,
): (event: ToolResultPersistEvent, ctx: ToolResultPersistContext) => void {
    return function handler(
        event: ToolResultPersistEvent,
        ctx: ToolResultPersistContext,
    ): void {
        const config = resolveConfig(pluginConfig);

        const toolName = event.toolName ?? ctx.toolName ?? "unknown";

        const entry: PICAuditEntry = {
            timestamp: new Date().toISOString(),
            event: "tool_result_persist",
            tool: toolName,
            toolCallId: event.toolCallId ?? ctx.toolCallId,
            isSynthetic: event.isSynthetic ?? false,
        };

        // ── Log ────────────────────────────────────────────────────────────
        if (config.log_level === "debug") {
            console.debug(`[pic-audit] ${JSON.stringify(entry)}`);
        } else if (config.log_level === "info") {
            console.log(
                `[pic-audit] tool=${entry.tool} callId=${entry.toolCallId ?? "n/a"} ` +
                `synthetic=${entry.isSynthetic}`,
            );
        }
    };
}
