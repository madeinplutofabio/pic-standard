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

// TODO: Future enhancement — make awareness message configurable via plugin
// config or environment variable for i18n or custom agent instructions.

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

    if (config.log_level === "debug") {
        console.debug("[pic-init] Injected awareness message:", PIC_AWARENESS_MESSAGE);
    }

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

