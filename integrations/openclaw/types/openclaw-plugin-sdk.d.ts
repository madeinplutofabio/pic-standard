/**
 * Type stub for openclaw/plugin-sdk peer dependency.
 *
 * This stub allows TypeScript to compile the plugin in isolation.
 * At runtime in OpenClaw, the real module provides these exports.
 *
 * CRITICAL: Use api.on() for lifecycle hooks, NOT api.registerHook()!
 * - api.registerHook() → internal hooks (old system, requires config flag)
 * - api.on() → typed hooks (new system, always active, used by hook runner)
 */
declare module "openclaw/plugin-sdk" {
    // Hook event types (from OpenClaw src/plugins/types.ts)
    export type PluginHookName =
        | "before_agent_start"
        | "agent_end"
        | "before_compaction"
        | "after_compaction"
        | "message_received"
        | "message_sending"
        | "message_sent"
        | "before_tool_call"
        | "after_tool_call"
        | "tool_result_persist"
        | "session_start"
        | "session_end"
        | "gateway_start"
        | "gateway_stop";

    // Handler type - uses 'any' since each hook has specific event/ctx shapes
    export type PluginHookHandler = (
        event: any,
        ctx: Record<string, unknown>
    ) => unknown | Promise<unknown>;

    export interface OpenClawPluginApi {
        id: string;
        name: string;
        version?: string;
        description?: string;
        source: string;
        config: Record<string, unknown>;
        pluginConfig?: Record<string, unknown>;

        /** Register a typed lifecycle hook - USE THIS for before_tool_call etc. */
        on<K extends PluginHookName>(
            hookName: K,
            handler: PluginHookHandler,
            opts?: { priority?: number }
        ): void;

        /** Register an internal hook - DO NOT USE for lifecycle hooks */
        registerHook(
            events: string | string[],
            handler: PluginHookHandler,
            opts?: { name?: string; priority?: number }
        ): void;

        getConfig<T = unknown>(): T;
        log(level: string, message: string, meta?: Record<string, unknown>): void;
        resolvePath(input: string): string;
    }

    // Legacy alias for backwards compatibility
    export type PluginAPI = OpenClawPluginApi;
}
