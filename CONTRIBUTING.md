# Contributing to the PIC Standard

Thank you for helping us build a more accountable future for AI. 🛡️

## 🛠️ How to Contribute

### 1. Proposing a New Impact Class
If your domain (e.g., Healthcare, Legal) requires specific risk controls:
1. Use the **New Impact Class** issue template.
2. Define the risk levels and required **Evidence Requirements**.

### 2. Requirements for Acceptable Contributions

- All code must pass the existing test suite and conformance tests (`pytest` + `conformance.yml` workflow).
- **Style is enforced by automated tools — CI blocks merge on violations.**
  - **Python** (Ruff): config in `pyproject.toml` (`[tool.ruff]`); rule set `E F W I N B SIM RUF`.
    Run locally before pushing:

    ```bash
    ruff check sdk-python/ tests/ conformance/
    ruff format --check sdk-python/ tests/ conformance/
    ```

  - **TypeScript** (ESLint v9 flat config + Prettier): config in `integrations/openclaw/{eslint.config.mjs, .prettierrc.json}`.
    Run locally before pushing:

    ```bash
    cd integrations/openclaw
    npm run lint
    npm run format:check
    ```

- **Statement coverage ≥80% (Python).** CI runs `coverage report --fail-under=80`. If a change drops coverage below the threshold, add tests or refactor. Config: `pyproject.toml` (`[tool.coverage.run]` / `[tool.coverage.report]`).
- Pull requests must include a clear description of the change and reference any related issue or discussion.
- For SDK changes, all Pydantic models must validate successfully.

### 3. Implementation & SDKs
We are currently focusing on the Python Reference SDK. If you wish to contribute:
1. Fork the repository.
2. Ensure all Pydantic models in `sdk-python/` pass validation.
3. Submit a PR with a clear description of changes.

## 4. Test Policy

Pull requests that add or change behavior MUST include automated tests
for that behavior. Specifically:

- New public APIs, new pipeline stages, new evidence types, new policy
  knobs, and new integrations MUST ship with unit tests under `tests/`.
- New verifier behavior MUST also ship with conformance vectors under
  `conformance/` where applicable.
- Bug fixes MUST include a regression test that fails before the fix
  and passes after.
- Documentation-only and refactor-only PRs (no behavior change) are
  exempt.

Maintainers will not merge PRs that add new functionality without
corresponding tests.

## ⚖️ Governance Model
The PIC Standard is consensus-driven. Major changes to the core `spec/` or `schemas/` must be initiated in the **GitHub Discussions** tab before a Pull Request is opened.

## 📜 Code of Conduct
Please be professional and inclusive. We follow the Contributor Covenant.
