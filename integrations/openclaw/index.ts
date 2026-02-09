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
    registerPluginHooksFromDir(api, path.join(__dirname, "hooks"));
}
