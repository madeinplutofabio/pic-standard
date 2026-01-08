# 🛡️ PIC Standard: Provenance & Intent Contracts
**Bridging the "Causal Gap" in Agentic AI.**

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Status](https://img.shields.io/badge/Status-Draft_v0.1-orange.svg)]()

## The Problem: The Causal Gap
Current AI safety focuses on **Guardrails** (filtering what an agent says) or **Permissions** (what an agent can access). Both fail when an agent receives malicious instructions from an untrusted source (Indirect Prompt Injection).

## The Solution: The PIC Standard
The **PIC (Provenance & Intent Contract)** is a runtime governance protocol. It forces agents to generate a machine-verifiable contract before executing any high-impact action.

> **The Golden Rule:** Untrusted text can advise, but it cannot drive side effects.

---

## 🏗️ Core Architecture
The PIC Standard operates on three primitives:
1. **Provenance:** Every input is tagged by trust level (`trusted`, `semi_trusted`, `untrusted`).
2. **Impact Class:** Every tool is categorized by risk (`read`, `write`, `external`, `irreversible`, `money`).
3. **Intent:** A semantic justification for the action.

## 📂 Project Structure
- `/spec`: Technical specification and taxonomy definitions.
- `/schemas`: JSON Schema for the PIC Action Proposal.
- `/sdk-python`: Reference implementation using Pydantic.
- `/examples`: Real-world contract patterns for Marketing, Finance, and HR.

## 🚀 Quick Start (Python)
```bash
pip install -r sdk-python/requirements.txt
python sdk-python/pic_verifier.py

```

## 🤝 Community & Governance
The PIC Standard is an open-source movement. We are actively seeking:

- Security Researchers to stress-test causal logic.
- Framework Authors to build native PIC integrations.
- Enterprise Architects to define domain-specific Impact Classes.

Maintained by [![Linkedin](https://i.sstatic.net/gVE0j.png) @fmsalvadori](https://www.linkedin.com/in/fmsalvadori/)
&nbsp;
[![GitHub](https://i.sstatic.net/tskMh.png) MadeInPluto](https://github.com/madeinplutofabio)
