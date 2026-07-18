# Future Workstream Designs — Index

Status: Proposed

This index makes the future-workstream design package discoverable: six
workstream designs, six program execution-control documents, and four
shared diagrams. Every document in the package is **Proposed** — none is
approved for implementation; approval happens only through human review of
the documentation pull request and the gate process defined in
`../program/gate-state.md`. Merging this documentation approves nothing.

The package designs future work for the current 90-day program
(`../strategy/90-day-engineering-program.md`) beyond the in-flight
LangGraph milestone (PR #6 design brief, PR #8 four-scenario runtime,
which remain separate, unmerged, and unmodified by this package).

## Workstream designs

| Design | Roadmap outcome it serves | Requirement prefix |
|---|---|---|
| [Independent external validation run](independent-validation-run.md) | A benchmark run conducted outside the project team, with verifiable evidence | `IVR-FR` |
| [Hidden-failure discovery](hidden-failure-discovery.md) | A weakness found that ordinary outcome testing did not expose | `HFD-FR` |
| [Before-and-after improvement case](improvement-case-study.md) | A documented improvement and a controlled retest | `BAI-FR` |
| [Commerce-v1 consequential-action profile](commerce-v1-profile.md) | The first applied domain scenario pack | `COM-FR` |
| [Generic MCP or REST integration](generic-protocol-integration.md) | A generic protocol integration path | `GPI-FR` |
| [Versioned follow-up release](follow-up-release.md) | A versioned public release with reproducible artifacts | `REL-FR` |

Each design follows a common standard: executive summary through explicit
claims and non-claims, with stable requirement identifiers where they aid
review.

## Program execution-control documents

| Document | Purpose |
|---|---|
| [Implementation manifest](../program/implementation-manifest.md) | The authoritative future execution queue: one entry per implementation milestone, with dependencies, statuses, and stop conditions |
| [Gate state](../program/gate-state.md) | The milestone lifecycle states, allowed transitions, and who may authorize each |
| [External evidence policy](../program/external-evidence-policy.md) | What automation may prepare versus what must be real external evidence |
| [Fable execution contract](../program/fable-execution-contract.md) | The execution model a future master prompt will invoke to implement approved milestones one at a time |
| [PR and branch strategy](../program/pr-and-branch-strategy.md) | One branch and one focused PR per milestone; stacking, retargeting, and cleanup rules |
| [Resume and recovery protocol](../program/resume-and-recovery-protocol.md) | Execution-journal format and restart behavior after interruption |

## Diagrams

| Diagram | Shows |
|---|---|
| [Future system architecture](../diagrams/future-system-architecture.md) | How the designed components attach to the existing trusted core |
| [Validation and evidence lifecycle](../diagrams/validation-evidence-lifecycle.md) | How evidence is produced, classified, and permitted for publication |
| [Workstream dependency map](../diagrams/workstream-dependency-map.md) | Which workstreams gate which, from executable integration to release |
| [Release and adoption gates](../diagrams/release-and-adoption-gates.md) | The program gates and the release gate's blocking checks |

## Reading order

For review: start with the dependency map, then the six designs in table
order, then the program documents (manifest → gate state → evidence
policy → execution contract → branch strategy → recovery protocol).

## Standing constraints

All documents in this package are bound by the repository's operating
rules (`../../AGENTS.md`, `../../CLAUDE.md`): evaluator independence,
benchmark-owned commit truth, frozen `core-v1` semantics and golden
results, optional-dependency isolation, and the claim discipline of
`../strategy/adoption-and-validation-tracking.md`. Nothing here has
occurred yet: no independent run, no discovered hidden failure, no
measured improvement, no release scope or version.
