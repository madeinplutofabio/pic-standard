/**
 * Type stub for openclaw/plugin-sdk peer dependency.
 *
 * This stub allows TypeScript to compile the plugin in isolation.
 * At runtime in OpenClaw, the real module provides these exports.
 */
declare module "openclaw/plugin-sdk" {
    export interface PluginAPI {
        registerHook(hook: unknown): void;
        getConfig<T = unknown>(): T;
        log(level: string, message: string, meta?: Record<string, unknown>): void;
    }

    export function registerPluginHooksFromDir(api: PluginAPI, dir: string): void;
}
