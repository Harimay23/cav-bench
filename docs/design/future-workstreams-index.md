# Future Workstream Designs — Index

Status: Proposed

This index makes the future-workstream design package discoverable: six
workstream designs, six program execution-control documents, and four
shared diagrams. Approval is **per design, not per PR**: each design
requires its own design-approval record in the format defined in
`../program/gate-state.md` (design path, reviewed commit SHA, decision,
approver, timestamp, conditions, unresolved external prerequisites).
Generic approval or merging of the documentation pull request that
carried this package (PR #9) approved none of the six designs by itself.
Three designs — `generic-protocol-integration.md`, `commerce-v1-profile.md`,
and `independent-validation-run.md` (tooling scope) — have since received
such a record and are `Status: Approved for implementation with
conditions`; the remaining three (`hidden-failure-discovery.md`,
`improvement-case-study.md`, `follow-up-release.md`) remain `Status:
Proposed`, with no approval record and no implementation authorized. See
[Design approvals](#design-approvals) below for the current record set.
Implementation has occurred and merged for `M-GPI-1` (PR
[#12](https://github.com/Harimay23/cav-bench/pull/12), tracking issue
[#11](https://github.com/Harimay23/cav-bench/issues/11) closed); it
remains at the `VALIDATING` gate-state pending its recorded external
technical review — see
[`../program/implementation-manifest.md`](../program/implementation-manifest.md)
for the authoritative, current status of every milestone. No
implementation has occurred under the `M-COM-V1` or `M-IVT-1` approvals.

The package designs future work for the current 90-day program
(`../strategy/90-day-engineering-program.md`) beyond the LangGraph
milestone (PR #6 design brief, PR #8 four-scenario runtime), which are
now both merged to `main` and remain separate from, and unmodified by,
this package.

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

## Design approvals

Human design-approval records live at
[`../program/approvals/`](../program/approvals/README.md), one per
approved design (format defined in `../program/gate-state.md`). As of
this update, `M-GPI-1`, `M-COM-V1`, and `M-IVT-1` (tooling scope) carry
recorded `approved_with_conditions` records; `M-HFA-1`, `M-IET-1`, and
`M-REL-NEXT` remain unapproved and `Status: Proposed`. See the approvals
index for the full table, conditions, and unresolved external
prerequisites — an approval record is design-specific, not
implementation, PR approval, merge authorization, or external
validation.

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
