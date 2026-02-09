/**
 * pic-init — PIC awareness injection for OpenClaw.
 *
 * Hook: before_agent_start (priority 50)
 *
 * Pushes a system-level message into the session that informs the agent
 * about PIC governance requirements, so it includes __pic proposals in
 * high-impact tool calls.
 *
 * Also performs an early health check against the PIC bridge to surface
 * connectivity issues at session start rather than at first tool call.
 */

import type { PICPluginConfig } from "../../lib/types.js";
import { DEFAULT_CONFIG } from "../../lib/types.js";

const PIC_AWARENESS_MESSAGE = `\
[PIC Standard] This session is governed by Provenance & Intent Contracts.

For high-impact tool calls (file writes, money transfers, irreversible
actions), you MUST include a __pic field in the tool parameters containing:
  - intent: why this action is needed
  - impact: array of impact classes (MONEY, IRREVERSIBLE, PRIVACY, etc.)
  - provenance: { source, trust_level } identifying the instruction origin
  - claims: array of verifiable assertions
  - action: { tool, params_hash } binding the proposal to a specific call

Tool calls without valid __pic proposals will be BLOCKED for high-impact
operations. Low-impact tools may proceed without __pic.

Refer to the PIC Standard documentation for the full contract schema.`;

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
 * before_agent_start handler.
 *
 * @param event - { messages: string[] } — push strings to inject context
 * @param ctx   - OpenClaw hook context
 */
export default async function handler(
    event: { messages: string[] },
    ctx: Record<string, unknown>,
): Promise<void> {
    const config = loadConfig(ctx);

    // ── Inject PIC awareness ───────────────────────────────────────────
    event.messages.push(PIC_AWARENESS_MESSAGE);

    // ── Early health check (best-effort, never blocks) ─────────────────
    const controller = new AbortController();
    const timeout = setTimeout(
        () => controller.abort(),
        config.bridge_timeout_ms,
    );

    try {
        const resp = await fetch(`${config.bridge_url}/health`, {
            signal: controller.signal,
        });

        if (!resp.ok) {
            console.warn(
                `[pic-init] PIC bridge health check failed: HTTP ${resp.status}`,
            );
        } else if (config.log_level === "debug") {
            console.debug("[pic-init] PIC bridge is healthy");
        }
    } catch {
        console.warn(
            `[pic-init] PIC bridge unreachable at ${config.bridge_url} — ` +
            "tool calls will be blocked (fail-closed) until the bridge is started.",
        );
    } finally {
        clearTimeout(timeout);
    }

    if (config.log_level === "debug" || config.log_level === "info") {
        console.log("[pic-init] PIC awareness injected into session");
    }
}
