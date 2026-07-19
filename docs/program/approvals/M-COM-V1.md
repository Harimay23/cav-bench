# Design Approval — M-COM-V1

Status: Recorded

This is a **design-approval record** in the format defined by
[`../gate-state.md`](../gate-state.md#design-approval-record-format). It
approves one specific design document at one specific reviewed commit for
one bounded implementation milestone. It is not a PR approval, not a merge
authorization, and not external validation — see
[Scope of this record](#scope-of-this-record).

| Field | Value |
|---|---|
| `milestone_id` | `M-COM-V1` |
| `design_path` | [`../../design/commerce-v1-profile.md`](../../design/commerce-v1-profile.md) |
| `reviewed_commit` | `38c5e1e8590e17c2798618c0490db7958d7f739d` |
| `merged_main_commit` | `6aee17723c53cc9fc56f2e40a793c5ffc1d8b6ce` |
| `decision` | `approved_with_conditions` |
| `approver` | Nixalkumar Patel (GitHub: `Harimay23`) |
| `timestamp` | 2026-07-19T18:59:44Z |

## Approved scope

- `commerce-v1` as the first applied domain profile, plugging in through
  the existing `ScenarioPack` extension point.
- Implementation as a wholly separate pack (`packs/commerce-v1/`); no
  changes to `core-v1`, evaluator semantics, runtime semantics, or
  schemas.
- The proposed fixture model (namespaces and authoritative records:
  `orders`, `inventory`, `pricing`, `payments`, `fulfillment`, `credits`,
  `escalations`), the profile taxonomy (domain / core family /
  dimensions), the domain failure codes (`CMF-*`), and the
  safeguard/control mapping table, as designed.
- Implementation of an initial subset of 4–6 scenarios (the design's
  proposed 5-scenario subset — C-01, C-03, C-06, C-08, C-17 — may be used
  as the working implementation scope, per the conditions below).
- Proposed branch: `feat/commerce-v1-profile`.
- Proposed PR: `feat: add commerce-v1 scenario pack initial subset`.

## Explicitly unapproved scope

- The exact final scenario subset — remains subject to external scope
  review (Condition 1).
- The remaining twelve implementation candidates beyond the initial
  subset — proposed future work, not authorized by this record.
- Any change to `core-v1`, schemas, `runtime/`, `evaluation/`, or
  `adapters/`.

## Conditions

1. The exact initial scenario subset remains subject to external scope
   review; this approval does not fix it as final.
2. Before implementation begins, the executor may use the proposed
   five-scenario subset (C-01 duplicate order, C-03 stale stock, C-06
   discount limit, C-08 capture after void, C-17 divergent cancellation)
   as the working implementation scope, but must:
   - preserve its proposed status in adopter-facing claims;
   - document why each selected scenario is implementable under the
     existing schema without schema changes;
   - stop and escalate if any selected scenario requires schema,
     evaluator, runtime, or core-v1 changes.
3. The implementation must include: happy-path controls; deterministic
   golden expectations for `commerce-v1` only (never co-edited with
   `core-v1` goldens); no edits to `core-v1` goldens; all five
   baseline-profile runs; oracle-boundary tests; domain control mapping
   documentation.
4. Commerce remains an applied profile, not the identity or exclusive
   scope of CAV-Bench, in all adoption-facing material produced by the
   implementation.

## Eligibility: what the external scope review gates, and what it does not

This condition is stated precisely so the eligibility of `M-COM-V1` under
`gate-state.md`/`fable-execution-contract.md` is decidable without
ambiguity:

- The pending external scope review **does not block starting
  implementation.** `M-COM-V1` is eligible to enter `IMPLEMENTING` now,
  against the approved proposed five-scenario working subset, under
  Condition 2 above.
- The pending review **does block treating the subset as final or as
  externally validated.** Nothing produced under this approval — code,
  docs, PR body, adoption-facing material — may describe the five-
  scenario subset as confirmed, final, or reviewed; it must be described
  as proposed and pending review throughout implementation.
- The pending review **must be recorded before the milestone can be
  approved (as a PR), merged, or marked `COMPLETE`.** Per `gate-state.md`,
  `AWAITING_REVIEW → APPROVED` and `MERGED → COMPLETE` both require their
  own recorded evidence; for `M-COM-V1` that evidence set includes the
  external scope review record (Gate-2 scope validation) in addition to
  ordinary PR review. A PR opened against the working subset without that
  review recorded may reach `PR_OPEN` / `AWAITING_REVIEW` but may not
  cross into `APPROVED` or `MERGED`.
- The review's outcome **may require amendment of the implementation PR
  before merge** — e.g. dropping, replacing, or narrowing a scenario from
  the five-scenario working subset. The implementation PR must be written
  so that such an amendment is a normal follow-up commit on the same
  branch, not a restart.

In short: **eligible to start now under the working subset; not eligible
to cross the approval/merge gate until the external scope review is
recorded.**

## Unresolved external prerequisites

Implementation may not treat these as satisfied by this approval:

- External review of the candidate set and initial subset remains
  required for Gate-2 scope validation (per the design's acceptance
  criteria) — required before `APPROVED`/`MERGED`/`COMPLETE`, not before
  `IMPLEMENTING` (see [Eligibility](#eligibility-what-the-external-scope-review-gates-and-what-it-does-not)
  above).
- Implementation completion does not constitute external adoption or
  domain validation of the profile.

## Evidence references

- [Pull request #9](https://github.com/Harimay23/cav-bench/pull/9)
  (merged), which carried the reviewed design text at commit
  `38c5e1e8590e17c2798618c0490db7958d7f739d`.
- [Pull request #10](https://github.com/Harimay23/cav-bench/pull/10)
  (`docs/approve-initial-workstreams`) introduces and records this human
  approval decision. Additional provenance: PR #10 branch head at commit
  `617f6f0be6600a0bf7d2ceccef141e45959040e9` as of the decision above;
  the PR head advances with subsequent corrections to this documentation
  package, which does not itself reopen the approval.

## Scope of this record

This record approves **this design, at this reviewed commit, for this
milestone** — nothing more. It is not approval of any implementation PR
that will later claim to satisfy `M-COM-V1` (that PR requires its own
human review and approval per `gate-state.md`); it is not a merge
authorization for anything; and it is not external validation of the
commerce-v1 profile or of CAV-Bench generally. If
`commerce-v1-profile.md` changes materially after
`38c5e1e8590e17c2798618c0490db7958d7f739d`, this record becomes **stale**
and a new review and record are required before implementation may
proceed (typo-level fixes are exempt at the approver's recorded
discretion).
