# Implementation Manifest — Future Execution Queue

Status: Proposed

This manifest is the **authoritative future execution queue** for the
designed workstreams
([`../design/future-workstreams-index.md`](../design/future-workstreams-index.md)).
An executor operating under the
[`fable-execution-contract.md`](fable-execution-contract.md) selects work
**only** from this manifest, only in dependency order, and only when the
entry's status and merge prerequisites permit. Statuses use
[`gate-state.md`](gate-state.md).

Initial statuses below reflect real dependencies as of this document.
**No milestone is approved for implementation.** Branch names and PR
titles are proposed per
[`pr-and-branch-strategy.md`](pr-and-branch-strategy.md) and become fixed
at design approval. Issue references are placeholders until issues are
opened.

Statuses in this file change only through commits that record the
authorizing evidence per `gate-state.md` — never silently.

## Queue overview

| milestone_id | Title | Initial status | Depends on |
|---|---|---|---|
| `M-COM-V1` | Commerce-v1 profile implementation | `AWAITING_DESIGN_REVIEW` | design approval; external scope review |
| `M-GPI-1` | Generic protocol integration (shared core + first transport) | `AWAITING_DESIGN_REVIEW` | design approval |
| `M-IVT-1` | Independent-validation tooling | `PROPOSED` | a merged, usable executable integration |
| `M-HFA-1` | Hidden-failure analysis tooling | `PROPOSED` | `M-IVT-1` bundle format; an executable integration |
| `M-IET-1` | Improvement/retest evidence tooling | `PROPOSED` | `M-HFA-1` finding-record format |
| `M-REL-NEXT` | Versioned follow-up release | `PROPOSED` (effectively blocked) | approved, merged scope + external evidence |

The LangGraph milestone (PR #6 design brief, PR #8 four-scenario runtime)
is **not** in this queue: it predates this manifest, is in flight under
its own PRs, and must not be modified by executors working this queue.

---

## M-COM-V1 — Commerce-v1 profile implementation

- **milestone_id:** `M-COM-V1`
- **title:** Implement the commerce-v1 scenario pack initial subset
- **design document:** [`../design/commerce-v1-profile.md`](../design/commerce-v1-profile.md)
- **issue placeholder:** `ISSUE-TBD-COM-V1` (open before implementation)
- **branch name (proposed):** `feat/commerce-v1-profile`
- **PR title (proposed):** `feat: add commerce-v1 scenario pack (initial subset)`
- **dependency milestones:** none in this queue (uses existing runtime);
  requires design approval **and** the external scope review named in the
  design (Gate-2 scope validation).
- **initial status:** `AWAITING_DESIGN_REVIEW`
- **allowed actions:** create pack files under
  `src/cavbench/scenarios/packs/commerce-v1/`; profile documentation;
  pack-specific tests and golden expectations; changelog entry.
- **prohibited actions:** any change to `core-v1`, schemas, `runtime/`,
  `evaluation/`, `adapters/`; new dependencies; new validity dimensions
  or failure semantics; editing any existing golden results.
- **implementation deliverables:** approved initial subset scenarios +
  happy-path controls; `pack.json` + digest; adoption-facing control
  mapping docs; pack golden ablation expectations.
- **required tests:** schema validation, pack loading/digest,
  deterministic per-scenario execution across all five baselines,
  oracle-boundary contract tests, invariant unit tests, pack goldens;
  full repository quality gate.
- **required external input:** design approval; external review of the
  candidate subset.
- **stop condition:** any candidate requires schema or evaluator changes;
  any `core-v1` golden deviates.
- **merge prerequisites:** human PR review and approval; CI green.
- **completion evidence:** merged PR; pack goldens recorded; `core-v1`
  goldens byte-identical pre/post (CI-verified). No external validation
  required for `COMPLETE`, but applied use is tracked separately.

---

## M-GPI-1 — Generic protocol integration

- **milestone_id:** `M-GPI-1`
- **title:** Implement the shared integration core, first transport, and reference server
- **design document:** [`../design/generic-protocol-integration.md`](../design/generic-protocol-integration.md)
- **issue placeholder:** `ISSUE-TBD-GPI-1`
- **branch name (proposed):** `feat/generic-protocol-integration`
- **PR title (proposed):** `feat: add generic protocol integration core with first transport`
- **dependency milestones:** none in this queue; requires design
  approval, including confirmation of the proposed REST-first transport
  order, and a `DECISION_LOG.md` entry at implementation time (per
  `AGENTS.md` scope discipline).
- **initial status:** `AWAITING_DESIGN_REVIEW`
- **allowed actions:** new optional-extra modules for the connector core
  and first transport; deterministic reference server (examples-adjacent);
  CI example job; documentation; changelog + decision-log entries.
- **prohibited actions:** changes to evaluator/runtime semantics; core
  (non-extra) dependencies; trusting wire-supplied status as commit
  truth; network egress beyond loopback in benchmark mode.
- **implementation deliverables:** envelope schema + docs; normalized
  execution adapter; first transport connector; reference server;
  transport mapping documentation; CI example.
- **required tests:** envelope/normalization unit tests; identity-under-
  retry tests; redaction tests; adversarial forged-commit-claim contract
  test; reference-server integration tests over the four hazard
  patterns; determinism (double-run hash) check; extras-isolation import
  test; full quality gate.
- **required external input:** design approval; transport-order
  confirmation; external technical review before the integration is
  represented as usable.
- **stop condition:** faithful translation would require evaluator
  changes or adapter-supplied truth — pause and escalate.
- **merge prerequisites:** human PR review and approval; CI green
  including the new example job.
- **completion evidence:** merged PR; deterministic CI example passing;
  recorded external technical review of the mappings (external input —
  until it exists, the milestone stops at `VALIDATING`).

---

## M-IVT-1 — Independent-validation tooling

- **milestone_id:** `M-IVT-1`
- **title:** Build the validation-run bundle tooling and runner documentation
- **design document:** [`../design/independent-validation-run.md`](../design/independent-validation-run.md)
- **issue placeholder:** `ISSUE-TBD-IVT-1`
- **branch name (proposed):** `feat/independent-validation-tooling`
- **PR title (proposed):** `feat: add independent-validation run tooling and runner kit`
- **dependency milestones:** a merged, usable executable integration for
  the run classes the kit advertises — baseline-profile runs need only
  released v1.0.0, but the roadmap's independent-run outcome anticipates
  framework/protocol runs, so this milestone should follow the LangGraph
  runtime merge (outside this queue) or `M-GPI-1`.
- **initial status:** `PROPOSED`
- **allowed actions:** manifest/attestation templates and (if approved in
  design review) machine schemas; bundle packager + checksum
  generator/verifier; runner quick-start docs; tests; changelog.
- **prohibited actions:** anything that lets project tooling alter or
  regenerate runner evidence; claims that a run occurred.
- **implementation deliverables:** validation-run manifest template,
  integrity-manifest tooling, attestation template, runner quick-start,
  reproducibility-review checklist.
- **required tests:** packaging round-trip on a real `cavbench ablate`
  output; tamper-detection negative test; template/schema validation;
  full quality gate.
- **required external input:** design approval. (The *tooling* completes
  without an external run; the roadmap *outcome* additionally requires a
  real `independent_external` bundle — tracked on this entry's
  `VALIDATING` note, not conflated with tooling completion.)
- **stop condition:** the workflow cannot be completed by a maintainer
  dry run in reasonable time (design rework needed).
- **merge prerequisites:** human PR review and approval; CI green;
  maintainer dry run recorded as `project_self_run`.
- **completion evidence:** merged PR + recorded dry-run bundle passing
  review. The **independent-run outcome** remains open until a real
  `independent_external` bundle passes review — external evidence that
  must never be simulated.

---

## M-HFA-1 — Hidden-failure analysis tooling

- **milestone_id:** `M-HFA-1`
- **title:** Build the evidence correlator, classifier, and finding-record tooling
- **design document:** [`../design/hidden-failure-discovery.md`](../design/hidden-failure-discovery.md)
- **issue placeholder:** `ISSUE-TBD-HFA-1`
- **branch name (proposed):** `feat/hidden-failure-analysis`
- **PR title (proposed):** `feat: add hidden-failure evidence correlation and finding tooling`
- **dependency milestones:** `M-IVT-1` (reuses the bundle/integrity
  format); an executable integration for real candidates.
- **initial status:** `PROPOSED`
- **allowed actions:** analysis-layer modules (placement per design
  review), finding-record templates, pipeline tests, synthetic
  demonstration fixtures (clearly labeled), docs, changelog.
- **prohibited actions:** any write path from classifier to evaluator
  output; new validity dimensions; publishing any "finding" from
  synthetic demonstrations; naming any candidate system.
- **implementation deliverables:** correlator, classifier, finding-record
  schema/templates, false-positive review checklist, synthetic
  demonstration.
- **required tests:** classifier predicate unit tests (incl. all causal
  attributions); classifier-immutability contract test; end-to-end
  pipeline test over a Validity-Gap-producing baseline run;
  false-positive fixture test; full quality gate.
- **required external input:** design approval; later, candidate-owner
  consent for any real evaluation.
- **stop condition:** correct classification would require evaluator
  changes or adapter-supplied assertions — pause and escalate.
- **merge prerequisites:** human PR review and approval; CI green.
- **completion evidence:** merged PR + passing synthetic demonstration.
  **A hidden-failure discovery is evidence-complete only with a
  `validated`, `reproduced` finding against a real external candidate,
  with preserved evidence** — the milestone parks at `VALIDATING` /
  `BLOCKED_EXTERNAL_INPUT` until that exists.

---

## M-IET-1 — Improvement/retest evidence tooling

- **milestone_id:** `M-IET-1`
- **title:** Build the baseline-freeze, comparison, and case-study evidence tooling
- **design document:** [`../design/improvement-case-study.md`](../design/improvement-case-study.md)
- **issue placeholder:** `ISSUE-TBD-IET-1`
- **branch name (proposed):** `feat/improvement-evidence-tooling`
- **PR title (proposed):** `feat: add before-and-after comparison and case-study evidence tooling`
- **dependency milestones:** `M-HFA-1` (consumes finding records).
- **initial status:** `PROPOSED`
- **allowed actions:** comparison engine, comparability checklist,
  artifact templates (remediation plan, changed-system manifest,
  comparison report, disclosure record), process-rehearsal fixtures
  (labeled), tests, docs, changelog.
- **prohibited actions:** altering frozen baselines; producing a "case
  study" from rehearsal fixtures; publication without a recorded
  disclosure record.
- **implementation deliverables:** comparison engine + templates +
  rehearsal, per the design's tooling phase.
- **required tests:** diff unit tests (improve/regress/mixed/no-change);
  checksum-mismatch failure test; hypothesis-ordering warning test;
  labeled two-profile rehearsal; full quality gate.
- **required external input:** design approval. The tooling is buildable
  once approved; **an improvement case remains externally blocked until a
  validated finding and a real retest exist** — that half of the
  workstream sits at `BLOCKED_EXTERNAL_INPUT` regardless of tooling
  status.
- **stop condition:** comparability checklist proves unsatisfiable for
  real subjects (design rework, not in-flight loosening).
- **merge prerequisites:** human PR review and approval; CI green.
- **completion evidence:** merged PR + recorded rehearsal. The
  before-and-after **case** outcome requires the full external chain
  (finding → real change → comparable retest → reviewed determination →
  permission) and is tracked as external evidence, never tool output.

---

## M-REL-NEXT — Versioned follow-up release

- **milestone_id:** `M-REL-NEXT`
- **title:** Prepare and publish the versioned follow-up release
- **design document:** [`../design/follow-up-release.md`](../design/follow-up-release.md)
- **issue placeholder:** `ISSUE-TBD-REL-NEXT`
- **branch name (proposed):** `release/follow-up-version` (RC branch at
  freeze; checklist/template work may land earlier via `docs/` or
  `chore/` branches).
- **PR title (proposed):** `release: follow-up version release candidate`
- **dependency milestones:** every scope item it will contain, merged and
  gate-complete (`M-COM-V1`, `M-GPI-1`, `M-IVT-1` at minimum, plus the
  hardened LangGraph adapter from its own PR chain), **and** the external
  evidence its claims will cite.
- **initial status:** `PROPOSED` — and effectively **blocked until
  approved artifacts exist**; entry criteria in the design are the
  unlock.
- **allowed actions (pre-entry):** author the release checklist and
  evidence-manifest template; rehearsal without tags or publication.
- **prohibited actions:** selecting/changing version numbers before the
  freeze-time rule application; tagging; publishing; any claim not
  referenced in the evidence manifest; marking program outcomes complete
  without evidence.
- **implementation deliverables:** release checklist, evidence manifest,
  RC(s), release notes, reproducibility package, review sign-offs, tag,
  GitHub release, post-release verification record, roadmap update.
- **required tests:** full quality gate from clean checkout; wheel smoke
  test; extras and Python matrices; goldens; link validation; the four
  human reviews (security, docs, claims, attribution).
- **required external input:** all four review sign-offs; permission
  records for every attribution; the external evidence behind every
  externally-facing claim.
- **stop condition:** any claim cannot be substantiated → publication
  blocked (this is the release gate working as designed).
- **merge prerequisites:** human approval at every step; tagging, release
  publication, and any PyPI upload are human acts.
- **completion evidence:** published release; minted version DOI with
  concept DOI unchanged; post-release verification record; updated
  roadmap/tracker.

---

## Manifest change rules

- Adding a milestone requires a design document and a
  `AWAITING_DESIGN_REVIEW`-at-most initial status.
- Status changes cite their authorizing evidence in the commit that makes
  them.
- Dependencies may be added by maintainers; removed only with a recorded
  reason.
- The executor never edits this file except to record authorized status
  transitions and journal-linked progress notes.
