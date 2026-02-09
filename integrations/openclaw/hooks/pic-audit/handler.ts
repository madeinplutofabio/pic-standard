/**
 * pic-audit — PIC post-execution audit trail for OpenClaw.
 *
 * Hook: tool_result_persist (priority 200)
 *
 * Fires after a tool call completes. Logs a structured audit record
 * capturing the PIC governance outcome. This provides an audit trail
 * for compliance and debugging.
 *
 * This hook is read-only — it never modifies the tool result or blocks
 * execution. It runs at priority 200 (after all functional hooks).
 *
 * LIMITATION: The pic-gate hook strips __pic from params BEFORE execution.
 * Whether __pic is visible here depends on OpenClaw's event propagation.
 * If pic_present shows false for a tool that was gated, it means OpenClaw
 * passed the modified (stripped) params to the persist event.
 */

import type { PICPluginConfig } from "../../lib/types.js";
import { DEFAULT_CONFIG } from "../../lib/types.js";

/** Shape of the tool_result_persist event. */
interface ToolResultEvent {
    toolName: string;
    params: Record<string, unknown>;
    result: unknown;
    error?: string;
    durationMs?: number;
}

/** Trust levels per proposal_schema.json. */
type TrustLevel = "trusted" | "semi_trusted" | "untrusted";

/** Provenance entry per proposal_schema.json. */
interface ProvenanceEntry {
    id: string;
    trust: TrustLevel;
    source?: string;
}

/** Structured audit entry written to console. */
interface PICAuditEntry {
    timestamp: string;
    event: "tool_result_persist";
    tool: string;
    /** Whether __pic was present in params at persist time (may be stripped by pic-gate). */
    pic_in_params: boolean;
    pic_intent?: string;
    pic_impact?: unknown;
    /** Trust level from the FIRST provenance entry (primary source). */
    pic_trust_level?: TrustLevel;
    tool_error: boolean;
    duration_ms?: number;
}

/**
 * Load plugin config from the OpenClaw plugin context.
 */
function loadConfig(ctx: Record<string, unknown>): PICPluginConfig {
    const pluginCfg = (ctx?.pluginConfig ?? {}) as Partial<PICPluginConfig>;
    return {
        bridge_url: pluginCfg.bridge_url ?? DEFAULT_CONFIG.bridge_url,
        bridge_timeout_ms:
            pluginCfg.bridge_timeout_ms ?? DEFAULT_CONFIG.bridge_timeout_ms,
        log_level: pluginCfg.log_level ?? DEFAULT_CONFIG.log_level,
    };
}

/**
 * tool_result_persist handler.
 *
 * @param event - tool execution result event
 * @param ctx   - OpenClaw hook context
 */
export default async function handler(
    event: ToolResultEvent,
    ctx: Record<string, unknown>,
): Promise<void> {
    const config = loadConfig(ctx);

    // ── Extract PIC metadata (if present in original params) ───────────
    // Note: pic-gate strips __pic before execution. Whether this event
    // receives original or modified params depends on OpenClaw's pipeline.
    const pic = event.params?.__pic as
        | {
            intent?: string;
            impact?: unknown;
            provenance?: ProvenanceEntry[];
        }
        | undefined;

    const entry: PICAuditEntry = {
        timestamp: new Date().toISOString(),
        event: "tool_result_persist",
        tool: event.toolName,
        pic_in_params: pic !== undefined,
        tool_error: event.error !== undefined,
        duration_ms: event.durationMs,
    };

    // ── Enrich with PIC details when available ─────────────────────────
    if (pic) {
        entry.pic_intent = pic.intent;
        entry.pic_impact = pic.impact;
        // Get trust from first provenance entry (primary source)
        entry.pic_trust_level = pic.provenance?.[0]?.trust;
    }

    // ── Log ────────────────────────────────────────────────────────────
    if (config.log_level === "debug") {
        console.debug(`[pic-audit] ${JSON.stringify(entry)}`);
    } else if (config.log_level === "info") {
        console.log(
            `[pic-audit] tool=${entry.tool} pic_in_params=${entry.pic_in_params} ` +
            `error=${entry.tool_error} duration_ms=${entry.duration_ms ?? "n/a"}`,
        );
    }
}
