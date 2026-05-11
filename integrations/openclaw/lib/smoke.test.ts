/**
 * Smoke tests — OpenClaw plugin surface contracts.
 *
 * These verify that the TypeScript types and runtime values used by the
 * pic-guard plugin match what the plugin code depends on.  They exist so
 * Dependabot PRs that bump openclaw (peer dep) or vitest/typescript will
 * fail CI if the API surface changes.
 *
 * Real `tsc --noEmit` catches type-level drift; these vitests validate
 * runtime contracts and the real plugin registration path.
 */

import { describe, it, expect, vi } from "vitest";
import { DEFAULT_CONFIG } from "./types.js";
import type { PICPluginConfig, PICVerifyResponse } from "./types.js";
import register from "../index.js";

// ---------------------------------------------------------------------------
// Type + runtime contracts
// ---------------------------------------------------------------------------

describe("types runtime contracts", () => {
    it("DEFAULT_CONFIG has correct PICPluginConfig shape", () => {
        expect(DEFAULT_CONFIG.bridge_url).toBe("http://127.0.0.1:7580");
        expect(DEFAULT_CONFIG.bridge_timeout_ms).toBe(500);
        expect(DEFAULT_CONFIG.log_level).toBe("info");
    });

    it("PICPluginConfig covers all config keys from openclaw.plugin.json", () => {
        const requiredKeys: (keyof PICPluginConfig)[] = [
            "bridge_url",
            "bridge_timeout_ms",
            "log_level",
        ];
        for (const key of requiredKeys) {
            expect(DEFAULT_CONFIG).toHaveProperty(key);
        }
    });

    it("PICVerifyResponse discriminated union is well-formed", () => {
        const allowed: PICVerifyResponse = { allowed: true, error: null, eval_ms: 5 };
        expect(allowed.allowed).toBe(true);
        expect(allowed.eval_ms).toBe(5);

        const denied: PICVerifyResponse = {
            allowed: false,
            error: { code: "PIC_VERIFIER_FAILED", message: "Denied" },
            eval_ms: 3,
        };
        expect(denied.allowed).toBe(false);
        expect(denied.error?.code).toBe("PIC_VERIFIER_FAILED");
    });
});

// ---------------------------------------------------------------------------
// Real plugin entrypoint smoke tests
// ---------------------------------------------------------------------------

describe("plugin registration", () => {
    it("register() hooks into the expected lifecycle events", () => {
        const hookNames: string[] = [];

        const mockApi = {
            id: "pic-guard",
            name: "PIC Standard Guard",
            source: "test",
            config: {},
            pluginConfig: {},
            on: vi.fn((hookName: string, _handler: unknown, _opts?: unknown) => {
                hookNames.push(hookName);
            }),
            registerHook: vi.fn(),
            getConfig: vi.fn(),
            log: vi.fn(),
            resolvePath: vi.fn((s: string) => s),
        };

        register(mockApi as any);

        expect(mockApi.on).toHaveBeenCalledTimes(3);
        expect(mockApi.registerHook).not.toHaveBeenCalled();

        expect(hookNames.sort()).toEqual(
            ["before_agent_start", "before_tool_call", "tool_result_persist"].sort()
        );
    });

    it("register() passes handlers as functions (not undefined)", () => {
        const handlers: unknown[] = [];

        const mockApi = {
            id: "pic-guard",
            name: "PIC Standard Guard",
            source: "test",
            config: {},
            pluginConfig: {},
            on: vi.fn((_hookName: string, handler: unknown) => {
                handlers.push(handler);
            }),
            registerHook: vi.fn(),
            getConfig: vi.fn(),
            log: vi.fn(),
            resolvePath: vi.fn((s: string) => s),
        };

        register(mockApi as any);

        expect(handlers).toHaveLength(3);
        for (const h of handlers) {
            expect(typeof h).toBe("function");
        }
    });
});
