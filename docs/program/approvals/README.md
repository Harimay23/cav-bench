# Design Approvals — Index

Status: Recorded

This directory holds **design-approval records**, one per approved design
document, in the format defined by
[`../gate-state.md`](../gate-state.md#design-approval-record-format). This
index lists every approval record currently on file.

## What an approval record means — and does not mean

- **Approval is design-specific.** One record approves one design
  document at one reviewed commit SHA, for one bounded implementation
  milestone. It does not approve any other document in the same
  documentation package.
- **Approval is not implementation.** No milestone approved here has been
  implemented; no scenario files, gateway code, adapters, schemas,
  tooling, dependencies, releases, or CI jobs are added by an approval
  record or by the pull request that carries it.
- **Approval is not PR approval.** A future implementation PR claiming to
  satisfy an approved milestone requires its own human review and
  approval per `../gate-state.md` — a design approval does not carry
  forward to that PR.
- **Approval is not merge authorization.** Nothing here authorizes
  merging anything, now or later.
- **Approval is not external validation.** No approval record here is
  evidence that an external party reviewed, endorsed, adopted, or
  validated CAV-Bench, any design, or any implementation.
- **Material design changes make an approval stale.** If a design
  document changes materially after its recorded `reviewed_commit`, the
  approval record is stale: a new review and record are required before
  implementation may proceed (typo-level fixes are exempt at the
  approver's recorded discretion).

## Approved records

Listed in intended implementation order (see
[`../implementation-manifest.md`](../implementation-manifest.md)):
`M-GPI-1` is currently the first eligible milestone.

| Milestone | Design | Decision | Reviewed commit | Conditions summary | Current execution status |
|---|---|---|---|---|---|
| [`M-GPI-1`](M-GPI-1.md) | [Generic MCP or REST integration](../../design/generic-protocol-integration.md) | `approved_with_conditions` | `38c5e1e8590e17c2798618c0490db7958d7f739d` | DECISION_LOG entry required at implementation; no MCP transport in this milestone; no new evaluator/commit-path/schema surface; stop if evaluator/core/schema changes needed. | `APPROVED_FOR_IMPLEMENTATION` — not started; first eligible milestone. |
| [`M-COM-V1`](M-COM-V1.md) | [Commerce-v1 consequential-action profile](../../design/commerce-v1-profile.md) | `approved_with_conditions` | `38c5e1e8590e17c2798618c0490db7958d7f739d` | Final scenario subset still subject to external scope review — this **gates the approval/merge/complete transitions, not the start of implementation**: the milestone is eligible to enter `IMPLEMENTING` now against the approved proposed 5-scenario working subset, but cannot reach `APPROVED`/`MERGED`/`COMPLETE` until the external scope review is recorded, and the implementation PR may need amendment (dropping, replacing, or narrowing a scenario) once that review lands; no `core-v1`/schema/evaluator/runtime changes; commerce remains an applied profile, not CAV-Bench's identity. | `APPROVED_FOR_IMPLEMENTATION` — not started; eligible to start, blocked from merge/completion pending external scope review. |
| [`M-IVT-1`](M-IVT-1.md) | [Independent external validation run](../../design/independent-validation-run.md) (tooling scope) | `approved_with_conditions` | `38c5e1e8590e17c2798618c0490db7958d7f739d` | Tooling and maintainer dry run only; dry run always classified `project_self_run`; no claim of external run, adoption, or endorsement; non-recursive integrity model preserved exactly. | `APPROVED_FOR_IMPLEMENTATION` — not started. |

## Not approved

The following designs remain `Status: Proposed` and have **no** approval
record in this directory. They must not be treated as eligible for
implementation:

| Milestone | Design | Why unapproved |
|---|---|---|
| `M-HFA-1` | [Hidden-failure discovery](../../design/hidden-failure-discovery.md) | Depends on `M-IVT-1`'s bundle format and a real executable integration; not yet reviewed for approval. |
| `M-IET-1` | [Before-and-after improvement case](../../design/improvement-case-study.md) | Depends on `M-HFA-1`'s finding-record format; not yet reviewed for approval. |
| `M-REL-NEXT` | [Versioned follow-up release](../../design/follow-up-release.md) | Depends on merged, gate-complete scope from every milestone it will contain, plus the external evidence its claims will cite; effectively blocked. |

## Adding a new record

See [`../gate-state.md`](../gate-state.md#design-approval-record-format)
for the required fields and rules. Each new record gets its own file,
`<milestone_id>.md`, and a row in the tables above.
