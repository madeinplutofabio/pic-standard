/**
 * pic-init — PIC awareness injection for OpenClaw.
 *
 * Hook: before_agent_start (priority 50)
 *
 * Returns a prependContext string that informs the agent about PIC governance
 * requirements, so it includes __pic proposals in high-impact tool calls.
 *
 * Also performs an early health check against the PIC bridge to surface
 * connectivity issues at session start rather than at first tool call.
 */

import type { PICPluginConfig } from "../../lib/types.js";
import { DEFAULT_CONFIG } from "../../lib/types.js";

const PIC_AWARENESS_MESSAGE = `\
[PIC Standard] This session is governed by Provenance & Intent Contracts.

For high-impact tool calls (money transfers, data exports, irreversible
actions), you MUST include a __pic field in the tool parameters with:
  - intent: why this action is needed (string)
  - impact: impact class (e.g., "money", "privacy", "irreversible")
  - provenance: array of { id, trust } identifying instruction origins
  - claims: array of { text, evidence } — verifiable assertions
  - action: { tool, args } binding the proposal to the specific call

Example __pic structure:
{
  "intent": "Transfer funds for approved invoice",
  "impact": "money",
  "provenance": [{ "id": "user_request", "trust": "trusted" }],
  "claims": [{ "text": "Invoice verified", "evidence": ["invoice_hash"] }],
  "action": { "tool": "payments_send", "args": { "amount": 100 } }
}

Tool calls without valid __pic proposals will be BLOCKED for high-impact
operations. Low-impact tools may proceed without __pic.`;

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
 * Factory: creates the before_agent_start handler with captured plugin config.
 */
export function createPicInitHandler(
    pluginConfig: Record<string, unknown>,
): (event: { prompt: string; messages?: unknown[] }, ctx: Record<string, unknown>) => Promise<{ prependContext?: string }> {
    return async function handler(
        _event: { prompt: string; messages?: unknown[] },
        _ctx: Record<string, unknown>,
    ): Promise<{ prependContext?: string }> {
        const config = resolveConfig(pluginConfig);

        if (config.log_level === "debug") {
            console.debug("[pic-init] Injected awareness message:", PIC_AWARENESS_MESSAGE);
        }

        // ── Early health check (best-effort, never blocks) ─────────────────
        const controller = new AbortController();
        const timeout = setTimeout(() => controller.abort(), config.bridge_timeout_ms);

        try {
            const resp = await fetch(`${config.bridge_url}/health`, {
                signal: controller.signal,
            });

            if (!resp.ok) {
                console.warn(`[pic-init] PIC bridge health check failed: HTTP ${resp.status}`);
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

        return { prependContext: PIC_AWARENESS_MESSAGE };
    };
}
