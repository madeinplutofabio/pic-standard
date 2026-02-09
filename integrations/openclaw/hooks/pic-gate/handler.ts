/**
 * pic-gate — PIC Standard pre-execution gate for OpenClaw.
 *
 * Hook: before_tool_call (priority 100)
 *
 * Sends the tool call (including any __pic proposal in params) to the PIC
 * HTTP bridge for verification.
 *
 * - allowed  → strips __pic from params, tool proceeds
 * - blocked  → returns { block: true, blockReason } — NEVER throws
 * - bridge unreachable → blocked (fail-closed)
 */

import { verifyToolCall } from "../../lib/pic-client.js";
import type { PICPluginConfig } from "../../lib/types.js";
import { DEFAULT_CONFIG } from "../../lib/types.js";

/**
 * Load plugin config from the OpenClaw plugin context.
 *
 * Falls back to DEFAULT_CONFIG when no user configuration is present.
 */
function loadConfig(ctx: Record<string, unknown>): PICPluginConfig {
    const pluginCfg = (ctx?.pluginConfig ?? {}) as Partial<PICPluginConfig>;
    return {
        bridge_url: pluginCfg.bridge_url ?? DEFAULT_CONFIG.bridge_url,
        bridge_timeout_ms: pluginCfg.bridge_timeout_ms ?? DEFAULT_CONFIG.bridge_timeout_ms,
        log_level: pluginCfg.log_level ?? DEFAULT_CONFIG.log_level,
    };
}

/**
 * before_tool_call handler.
 *
 * @param event - { toolName: string, params: Record<string, unknown> }
 * @param ctx   - OpenClaw hook context (includes pluginConfig if set)
 *
 * @returns { block, blockReason } on denial; { params } on approval.
 */
export default async function handler(
    event: { toolName: string; params: Record<string, unknown> },
    ctx: Record<string, unknown>,
): Promise<
    | { block: true; blockReason: string }
    | { params: Record<string, unknown> }
    | void
> {
    const config = loadConfig(ctx);

    // Defensive: ensure params is an object (fail-closed if malformed event)
    const params = event.params ?? {};
    if (typeof params !== "object" || params === null) {
        return { block: true, blockReason: "PIC gate: malformed event (params not an object)" };
    }

    // Defensive: ensure toolName is a non-empty string
    const toolName = event.toolName;
    if (typeof toolName !== "string" || toolName.trim() === "") {
        return { block: true, blockReason: "PIC gate: malformed event (toolName missing or empty)" };
    }

    // ── Verify against PIC bridge ──────────────────────────────────────
    const result = await verifyToolCall(toolName, params, config);

    // ── Blocked ────────────────────────────────────────────────────────
    if (!result.allowed) {
        const reason =
            result.error?.message ?? "PIC contract violation (no details)";

        if (config.log_level === "debug" || config.log_level === "info") {
            console.log(
                `[pic-gate] BLOCKED tool=${toolName} reason="${reason}"`,
            );
        }

        return { block: true, blockReason: reason };
    }

    // ── Allowed — strip __pic metadata before tool executes ────────────
    const { __pic, __pic_request_id, ...cleanParams } = params as Record<
        string,
        unknown
    > & { __pic?: unknown; __pic_request_id?: unknown };

    if (config.log_level === "debug") {
        console.debug(
            `[pic-gate] ALLOWED tool=${toolName} eval_ms=${result.eval_ms}`,
        );
    }

    return { params: cleanParams };
}
