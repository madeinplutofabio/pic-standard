// ESLint v9+ flat config for the PIC OpenClaw plugin.
//
// References:
//   https://eslint.org/docs/latest/use/configure/configuration-files
//   https://typescript-eslint.io/getting-started/
//
// Design notes:
//   - Uses ESLint v9 flat config (the default since v9; `.eslintrc.json` is
//     deprecated). Configuration is an exported array of config objects.
//   - Uses ESLint core's `defineConfig` helper (from `eslint/config`) to
//     compose the array with type-aware autocomplete. The older
//     `tseslint.config(...)` helper from typescript-eslint is now
//     documented as deprecated in favor of this core helper.
//   - Uses the modern `typescript-eslint` meta-package (replaces the older
//     `@typescript-eslint/parser` + `@typescript-eslint/eslint-plugin` pair).
//     The `configs.recommended` preset is still imported from it; only the
//     helper-fn choice changed.
//   - Non-type-checked variant of typescript-eslint recommended: faster than
//     type-checked, doesn't require `parserOptions.project` setup. Upgrade
//     to type-checked variant in a focused follow-up if type-aware rules
//     become valuable.
//   - No stylistic rules — Prettier owns formatting; ESLint owns logic.
//     No `eslint-config-prettier` package is needed because the
//     typescript-eslint recommended set doesn't enable conflicting
//     stylistic rules.

import { defineConfig } from "eslint/config";
import js from "@eslint/js";
import tseslint from "typescript-eslint";

export default defineConfig(
    // Ignore generated and vendored output globally.
    {
        ignores: ["dist/**", "node_modules/**", "package-lock.json"],
    },

    // Apply ESLint's JavaScript recommended ruleset.
    js.configs.recommended,

    // Apply typescript-eslint's recommended ruleset (non-type-checked variant).
    ...tseslint.configs.recommended,

    // Project-specific overrides.
    {
        rules: {
            // The OpenClaw plugin SDK and the PIC HTTP bridge return JSON
            // bodies typed as `unknown` / `any` at the boundary. Suppressing
            // every legitimate `any` would force defensive type assertions
            // throughout the handlers; warn instead of error so genuine
            // `any`-creep is visible without breaking CI.
            "@typescript-eslint/no-explicit-any": "warn",

            // Reduce friction with the OpenClaw hook handler signatures,
            // which intentionally accept context objects with unused fields
            // for forward-compatibility. Standard convention: underscore
            // prefix on intentionally-unused args/vars.
            "@typescript-eslint/no-unused-vars": [
                "error",
                {
                    argsIgnorePattern: "^_",
                    varsIgnorePattern: "^_",
                },
            ],
        },
    },

    // The OpenClaw SDK declaration file (types/openclaw-plugin-sdk.d.ts)
    // intentionally declares signatures we don't all use; suppress
    // unused-vars there entirely (declarations aren't runtime code).
    {
        files: ["types/**/*.d.ts"],
        rules: {
            "@typescript-eslint/no-unused-vars": "off",
        },
    }
);
