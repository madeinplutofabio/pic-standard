# Contributing to the PIC Standard

Thank you for helping us build a more accountable future for AI. 🛡️

## 🛠️ How to Contribute

### 1. Proposing a New Impact Class
If your domain (e.g., Healthcare, Legal) requires specific risk controls:
1. Use the **New Impact Class** issue template.
2. Define the risk levels and required **Evidence Requirements**.

### 2. Requirements for Acceptable Contributions

- All code must pass the existing test suite and conformance tests (`pytest` + `conformance.yml` workflow).
- Python code should follow PEP 8 style.
- Pull requests must include a clear description of the change and reference any related issue or discussion.
- For SDK changes, all Pydantic models must validate successfully.

### 3. Implementation & SDKs
We are currently focusing on the Python Reference SDK. If you wish to contribute:
1. Fork the repository.
2. Ensure all Pydantic models in `sdk-python/` pass validation.
3. Submit a PR with a clear description of changes.

## ⚖️ Governance Model
The PIC Standard is consensus-driven. Major changes to the core `spec/` or `schemas/` must be initiated in the **GitHub Discussions** tab before a Pull Request is opened.

## 📜 Code of Conduct
Please be professional and inclusive. We follow the Contributor Covenant.
