# Governance

This document describes the governance model for the **PIC Standard** project (Provenance & Intent Contracts).

## Principles

- **Open participation.** Anyone can contribute, report issues, or propose changes.
- **Transparent decision-making.** Architectural decisions are discussed publicly via GitHub Issues, Discussions, and Pull Requests.
- **Merit-based advancement.** Maintainer roles are earned through sustained, high-quality contributions.
- **Multi-organization stewardship goal.** The project is actively working toward maintainership from contributors at multiple organizations, reducing long-term dependency on any single contributor or company.
- **Local-first, operator-controlled.** The project's technical principles (no mandatory cloud dependencies, operator-controlled trust roots, fail-closed defaults) extend to governance: decisions and processes are visible to and reviewable by the community.

## Roles

### Contributor

Anyone who submits a pull request, files an issue, or participates in discussions. Contributors agree to the project's [Code of Conduct](CODE_OF_CONDUCT.md) and sign off on their commits per the Developer Certificate of Origin (see [CONTRIBUTING.md](CONTRIBUTING.md)).

### Reviewer

Contributors who have demonstrated familiarity with a specific area of the codebase and consistently provide constructive reviews. Reviewers can approve PRs in their area but cannot merge without maintainer approval.

**Path to Reviewer:** 3+ merged PRs in a specific area (e.g., a specific integration, canonicalization, evidence verification, conformance vectors), and active participation in issue triage or code review over 1+ months.

### Maintainer

Maintainers have write access to the repository, can merge PRs, and participate in architectural decisions. Maintainers are responsible for the project's technical direction, release management, and community health.

**Path to Maintainer:** Sustained contribution over 2+ months, including 5+ merged PRs of substance, active issue triage, and demonstrated understanding of the project's architecture and governance scope. Nomination by the Project Lead (or, once additional maintainers are added, by an existing maintainer), confirmed by consensus among current maintainers.

### Project Lead

The Project Lead sets overall technical direction, resolves disputes when consensus cannot be reached, and represents the project in external standards bodies and foundation interactions.

PIC Standard was initiated by **Fabio Marcello Salvadori** (@madeinplutofabio), with current stewardship and infrastructure support from **MadeInPluto** (https://madeinpluto.com), the Project Lead's agentic AI practice. Governance authority is exercised at the project level, not as a private-company right. MadeInPluto's role is current stewardship — providing engineering time and infrastructure — not permanent control over the project's direction. If PIC Standard is accepted into a foundation program, this governance model may be revised to align with that foundation's technical charter and onboarding requirements while preserving the project's open, local-first, action-boundary verification principles.

## Current Maintainers

See [MAINTAINERS.md](MAINTAINERS.md) for the full list of current maintainers, their areas of ownership, and affiliation details.

The project is actively recruiting co-maintainers. High-leverage open areas include reference verifier implementations, normative specification drafts, conformance vectors, evidence verification, and integration stewardship across agent/tool runtimes. If you are interested in becoming a maintainer, start by contributing in one of these areas and engaging with the project on GitHub.

## Decision-Making

### Day-to-day decisions

Pull requests require approval from at least one maintainer before merge. Maintainers use their judgment on routine changes (bug fixes, documentation, test additions, dependency bumps).

### Significant changes

Changes that affect the project's architecture, wire format, public API surface, security model, normative semantics, or governance scope are discussed publicly via GitHub Issues before implementation. Any maintainer or contributor can raise a concern. The goal is rough consensus among maintainers.

### Disputes

If maintainers cannot reach consensus, the Project Lead makes the final decision after considering all perspectives. The rationale is documented in the relevant GitHub Issue.

### Conflict of Interest

Maintainers must disclose any financial or employment relationship that could influence their decisions on project direction, dependency choices, or vendor integrations. A maintainer with a conflict of interest on a specific decision must recuse themselves from voting on that decision. Disclosures are noted in the relevant GitHub Issue or PR.

### Voting Thresholds

| Decision type | Required votes | Quorum |
|---|---|---|
| Routine PR merge | 1 maintainer approval | N/A |
| Architecture / wire-format / normative-semantics change | Rough consensus among maintainers | 50% of maintainers |
| New maintainer nomination | Consensus among current maintainers | 50% of maintainers |
| Governance document change | 2 maintainer approvals | N/A |
| Project Lead succession | Supermajority (2/3) of maintainers | 75% of maintainers |

**Transitional note (single-maintainer phase):** Until a second maintainer is appointed, the Project Lead is responsible for final decisions after public discussion. Once there are two or more maintainers, the voting and escalation rules above apply. Non-trivial decisions are documented in GitHub Issues regardless of phase, to preserve the transparency principle. During the single-maintainer phase, governance document changes specifically follow the transitional process: Project Lead approval after a 7-day public comment period via GitHub Issue, as also stated in the "Changes to Governance" section below.

## Releases

Releases follow [Semantic Versioning](https://semver.org/). Any maintainer can propose a release. The release process is documented in [RELEASING.md](RELEASING.md), including the cryptographically-signed release pipeline (PEP 740 attestations on PyPI artifacts + Ed25519-signed git tags) introduced in v0.8.1.1.

## Standards-Track Engagement

The project may engage with standards, interoperability, and open-source governance bodies where relevant, including AAIF, LF AI & Data, OpenSSF, IETF-style processes, and adjacent agent-governance vocabulary efforts. Specific engagements are tracked publicly on GitHub via Issues, PRs, and external proposal threads.

Standards-track decisions affecting wire format or normative semantics follow the "significant changes" decision-making path above.

## Code of Conduct

All participants are expected to follow the project's [Code of Conduct](CODE_OF_CONDUCT.md) (Contributor Covenant 2.1). Violations can be reported using the contact path listed in [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md). If no separate conduct contact is listed, reports may be sent to the Project Lead using the project contact listed in [SECURITY.md](SECURITY.md).

## Security

Security vulnerabilities should be reported via the process documented in [SECURITY.md](SECURITY.md), not through public issues.

## Changes to Governance

Changes to this document require a pull request with approval from at least two maintainers (or, in the single-maintainer phase, by the Project Lead with a 7-day public comment period via GitHub Issue). Significant governance changes (e.g., adding new roles, changing decision processes) should be discussed in a GitHub Issue first.

## Foundation Onboarding

If PIC Standard is accepted by a hosting foundation or formal open-governance program, this document will be revised to align with that program's required governance framework while preserving the principles and processes stated above. Foundation onboarding requires a PR amending this document with approval per the "Changes to Governance" process.
