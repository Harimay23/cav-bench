# Design Approval — M-IVT-1

Status: Recorded

This is a **design-approval record** in the format defined by
[`../gate-state.md`](../gate-state.md#design-approval-record-format). It
approves one specific design document at one specific reviewed commit for
one bounded implementation milestone, and that milestone's scope is
**tooling only**. It is not a PR approval, not a merge authorization, and
not external validation — see
[Scope of this record](#scope-of-this-record).

| Field | Value |
|---|---|
| `milestone_id` | `M-IVT-1` |
| `design_path` | [`../../design/independent-validation-run.md`](../../design/independent-validation-run.md) |
| `reviewed_commit` | `38c5e1e8590e17c2798618c0490db7958d7f739d` |
| `merged_main_commit` | `6aee17723c53cc9fc56f2e40a793c5ffc1d8b6ce` |
| `decision` | `approved_with_conditions` |
| `approver` | Nixalkumar Patel (GitHub: `Harimay23`) |
| `timestamp` | 2026-07-19T18:59:44Z |

## Approved scope — tooling only

- The validation-run manifest schema implementation (`validation-run-v1`).
- The runner-attestation template.
- Canonical `checksums.sha256` generation.
- Detached `bundle-root.sha256` generation and verification.
- The optional detached-signature support boundary (`checksums.sha256.sig`).
- The bundle packager and verifier.
- The no-unlisted-files check.
- Path-safety checks for archive extraction.
- The runner quick-start documentation.
- The reproducibility-review checklist.
- A maintainer `project_self_run` rehearsal (dry run).
- Proposed branch: `feat/independent-validation-tooling`.
- Proposed PR: `feat: add independent-validation run tooling and runner kit`.

## Explicitly unapproved scope

- Any claim that an independent external run occurred.
- Any claim that an external party validated the benchmark.
- Any claim that the benchmark was adopted.
- Any claim that a runner endorsed the project.
- A real `independent_external` outcome — this is a separate
  external-evidence gate and cannot be marked complete by automation
  (see [Unresolved external prerequisites](#unresolved-external-prerequisites)).

## Conditions

1. Approval covers tooling and a maintainer dry run only.
2. It does not authorize any claim listed in
   [Explicitly unapproved scope](#explicitly-unapproved-scope).
3. A project-maintainer rehearsal must always be classified
   `project_self_run` — never `assisted_external` or `independent_external`.
4. The tooling must preserve the exact non-recursive integrity model
   defined in the design: `checksums.sha256` excludes itself,
   `bundle-root.sha256`, and detached signature files; the bundle root
   hashes the canonical checksum manifest; verification checks the
   externally recorded root first when available; no unlisted files are
   permitted beyond the defined exclusions; broken bundles are never
   repaired in place.
5. A real `independent_external` outcome remains a separate
   external-evidence gate and cannot be marked complete by automation.

## Unresolved external prerequisites

Implementation may not treat these as satisfied by this approval:

- A real external runner.
- Independently conducted execution.
- Runner-authored attestation.
- Reproducibility review of a real external bundle.
- Disclosure and attribution permission from a real external runner.

## Manifest-eligibility note

Per the implementation manifest, `M-IVT-1`'s dependency was recorded as
"a merged, usable executable integration for the run classes the kit
advertises." This approval confirms that **tooling** may proceed as an
independently buildable milestone ahead of a real external run: a
baseline-profile validation run needs only the released v1.0.0 package,
so the tooling, templates, and maintainer dry run do not require the
LangGraph runtime or `M-GPI-1` to merge first. Any advertised
framework-specific or protocol-specific runner path within the tooling's
documentation still requires the corresponding executable integration to
be merged before that path is presented as usable; the milestone's
`independent_external` outcome remains blocked by external evidence
regardless of tooling completion.

## Evidence references

- [Pull request #9](https://github.com/Harimay23/cav-bench/pull/9)
  (merged), which carried the reviewed design text at commit
  `38c5e1e8590e17c2798618c0490db7958d7f739d`.
- Human approver decision recorded directly in this repository via
  [`docs/approve-initial-workstreams`](../../../CHANGELOG.md), the PR that
  introduces this record.

## Scope of this record

This record approves **this design, at this reviewed commit, for this
milestone's tooling scope** — nothing more. It is not approval of any
implementation PR that will later claim to satisfy `M-IVT-1` (that PR
requires its own human review and approval per `gate-state.md`); it is
not a merge authorization for anything; and it is not external validation
of CAV-Bench or evidence that any independent run has occurred. If
`independent-validation-run.md` changes materially after
`38c5e1e8590e17c2798618c0490db7958d7f739d`, this record becomes **stale**
and a new review and record are required before implementation may
proceed (typo-level fixes are exempt at the approver's recorded
discretion).
