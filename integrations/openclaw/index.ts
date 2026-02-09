/**
 * PIC Standard plugin for OpenClaw.
 *
 * Entry point — registers all hooks from the hooks/ directory.
 */

import type { PluginAPI } from "openclaw";
import { registerPluginHooksFromDir } from "openclaw";
import { fileURLToPath } from "url";
import path from "path";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

export default function activate(api: PluginAPI): void {
    // Point to source hooks/ directory (not dist/hooks/) so HOOK.md files are found.
    // At runtime __dirname is dist/, so we go up one level to reach hooks/.
    registerPluginHooksFromDir(api, path.join(__dirname, "..", "hooks"));
}
