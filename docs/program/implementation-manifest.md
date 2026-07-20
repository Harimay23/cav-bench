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
**Three milestones — `M-GPI-1`, `M-COM-V1`, and `M-IVT-1` — are now
`APPROVED_FOR_IMPLEMENTATION`**, per the recorded human design-approval
records in [`approvals/`](approvals/) (see each entry below for its
record link). No implementation has begun under any of these approvals.
`M-HFA-1`, `M-IET-1`, and `M-REL-NEXT` remain unapproved. The manifest may
carry multiple `APPROVED_FOR_IMPLEMENTATION` entries at once; the work
selection algorithm in
[`fable-execution-contract.md`](fable-execution-contract.md) still
chooses exactly one earliest-eligible milestone at a time — multiple
approved entries do not authorize parallel or out-of-order execution.
Branch names and PR titles are proposed per
[`pr-and-branch-strategy.md`](pr-and-branch-strategy.md) and become fixed
at design approval. Issue references are placeholders until issues are
opened.

Statuses in this file change only through commits that record the
authorizing evidence per `gate-state.md` — never silently.

## Queue overview

**Intended implementation order** (also the section order below):
`M-GPI-1` → `M-COM-V1` → `M-IVT-1` → `M-HFA-1` → `M-IET-1` → `M-REL-NEXT`.
This ordering, together with each entry's dependency and eligibility
state, is what the Fable execution contract's selection algorithm reads
to pick the next milestone: as of this document, **`M-GPI-1` is the
first eligible milestone** (`APPROVED_FOR_IMPLEMENTATION`, no unresolved
dependency milestones, no pending external prerequisite gating entry into
`IMPLEMENTING`).

| milestone_id | Title | Current status | Depends on |
|---|---|---|---|
| `M-GPI-1` | Generic protocol integration (shared core + first transport) | `APPROVED_FOR_IMPLEMENTATION` | design approval (recorded, [`approvals/M-GPI-1.md`](approvals/M-GPI-1.md)) |
| `M-COM-V1` | Commerce-v1 profile implementation | `APPROVED_FOR_IMPLEMENTATION` | design approval (recorded, [`approvals/M-COM-V1.md`](approvals/M-COM-V1.md)); external scope review (unresolved — gates `APPROVED`/`MERGED`/`COMPLETE`, not `IMPLEMENTING`; see entry below) |
| `M-IVT-1` | Independent-validation tooling | `APPROVED_FOR_IMPLEMENTATION` (tooling scope; see note below) | design approval (recorded, [`approvals/M-IVT-1.md`](approvals/M-IVT-1.md)); tooling is independently buildable — see manifest entry |
| `M-HFA-1` | Hidden-failure analysis tooling | `PROPOSED` | `M-IVT-1` bundle format; an executable integration |
| `M-IET-1` | Improvement/retest evidence tooling | `PROPOSED` | `M-HFA-1` finding-record format |
| `M-REL-NEXT` | Versioned follow-up release | `PROPOSED` (effectively blocked) | approved, merged scope + external evidence |

The LangGraph milestone (PR #6 design brief, PR #8 four-scenario runtime)
is **not** in this queue: it predates this manifest, is in flight under
its own PRs, and must not be modified by executors working this queue.

---

## M-GPI-1 — Generic protocol integration

- **milestone_id:** `M-GPI-1`
- **title:** Implement the benchmark-owned protocol gateway (shared core + first transport frontend) and reference candidate client
- **design document:** [`../design/generic-protocol-integration.md`](../design/generic-protocol-integration.md)
- **design-approval record:** [`approvals/M-GPI-1.md`](approvals/M-GPI-1.md)
  (`approved_with_conditions`, reviewed commit
  `38c5e1e8590e17c2798618c0490db7958d7f739d` — the proposed
  gateway-mediated topology and REST-first transport order are confirmed
  by the record)
- **issue placeholder:** `ISSUE-TBD-GPI-1`
- **branch name (proposed):** `feat/generic-protocol-integration`
- **PR title (proposed):** `feat: add generic protocol integration core with first transport`
- **dependency milestones:** none in this queue; design approval is now
  recorded, including confirmation of the proposed gateway-mediated
  topology and REST-first transport order; a `DECISION_LOG.md` entry at
  implementation time recording both remains required (per `AGENTS.md`
  scope discipline and approval Condition 1).
- **current status:** `APPROVED_FOR_IMPLEMENTATION`
- **allowed actions:** new optional-extra modules for the gateway core
  and first transport frontend; deterministic reference candidate client
  (examples-adjacent); CI example job; documentation; changelog +
  decision-log entries.
- **prohibited actions:** changes to evaluator/runtime semantics; core
  (non-extra) dependencies; any commit path outside
  `ToolFacade → BenchmarkEnvironment`; deriving any ledger entry from a
  candidate claim; gateway-side retries, identity repair, or
  reconciliation on the candidate's behalf; network egress beyond
  loopback in benchmark mode.
- **implementation deliverables:** envelope schema + docs; shared
  gateway core (session binding, 1:1 request-to-ToolFacade mapping,
  session log); first transport frontend; reference candidate client;
  candidate-facing mapping documentation; CI example.
- **required tests:** envelope/normalization unit tests; identity
  pass-through (no mutation) tests; redaction tests; adversarial
  forged-final-report contract test; gateway neutrality tests (exact 1:1
  request↔attempt correspondence, no unrequested reconciliation or
  retries); malformed-request tests (no benchmark attempt created);
  reference-candidate integration tests over the four hazard patterns in
  guarded and flawed configurations; determinism (double-run hash)
  check; extras-isolation import test; full quality gate.
- **required external input:** design approval; transport-order
  confirmation; external technical review before the integration is
  represented as usable.
- **stop condition:** protocol conformance would require the gateway to
  break behavioral neutrality, add a commit path, or treat candidate
  claims as truth — pause and escalate.
- **merge prerequisites:** human PR review and approval; CI green
  including the new example job.
- **completion evidence:** merged PR; deterministic CI example passing;
  recorded external technical review of the envelope and gateway
  mappings (external input — until it exists, the milestone stops at
  `VALIDATING`).

---

## M-COM-V1 — Commerce-v1 profile implementation

- **milestone_id:** `M-COM-V1`
- **title:** Implement the commerce-v1 scenario pack initial subset
- **design document:** [`../design/commerce-v1-profile.md`](../design/commerce-v1-profile.md)
- **design-approval record:** [`approvals/M-COM-V1.md`](approvals/M-COM-V1.md)
  (`approved_with_conditions`, reviewed commit
  `38c5e1e8590e17c2798618c0490db7958d7f739d`)
- **issue placeholder:** `ISSUE-TBD-COM-V1` (open before implementation)
- **branch name (proposed):** `feat/commerce-v1-profile`
- **PR title (proposed):** `feat: add commerce-v1 scenario pack (initial subset)`
- **dependency milestones:** none in this queue (uses existing runtime);
  design approval is now recorded. The external scope review named in the
  design (Gate-2 scope validation) is an unresolved external prerequisite,
  but it **gates the approval/merge boundary, not eligibility to start**:
  see [Eligibility](#eligibility-com-v1) below.
- **current status:** `APPROVED_FOR_IMPLEMENTATION` — eligible to enter
  `IMPLEMENTING` now, against the approved proposed five-scenario working
  subset (approval Condition 2); not eligible to cross into `APPROVED` or
  `MERGED` until the external scope review is recorded (approval
  Condition 1).
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
- **required external input:** design approval (recorded); external
  review of the candidate subset (unresolved — required before
  `APPROVED`/`MERGED`/`COMPLETE`, not before `IMPLEMENTING`).
- **stop condition:** any candidate requires schema or evaluator changes;
  any `core-v1` golden deviates.
- <a id="eligibility-com-v1"></a>**eligibility (`gate-state.md` /
  `fable-execution-contract.md`):** `M-COM-V1` is eligible for the
  executor to select and enter `IMPLEMENTING` now, working against the
  approved proposed five-scenario subset, with its proposed status
  preserved in all adopter-facing material throughout implementation. The
  milestone is **not** eligible to reach `AWAITING_REVIEW → APPROVED` or
  `MERGED → COMPLETE` until the external scope review (Gate-2 scope
  validation) is recorded as evidence per `gate-state.md`. If that review
  changes the subset, the implementation PR is amended on the same
  branch — dropping, replacing, or narrowing a scenario — rather than
  restarted; the PR must not be opened for `APPROVED`/merge until the
  review is recorded.
- **merge prerequisites:** human PR review and approval; CI green;
  external scope review (Gate-2 scope validation) recorded.
- **completion evidence:** merged PR; pack goldens recorded; `core-v1`
  goldens byte-identical pre/post (CI-verified); external scope review
  recorded. No external adoption or domain validation is required for
  `COMPLETE`, but the scope review itself is required — see
  [Eligibility](#eligibility-com-v1) above.

---

## M-IVT-1 — Independent-validation tooling

- **milestone_id:** `M-IVT-1`
- **title:** Build the validation-run bundle tooling and runner documentation
- **design document:** [`../design/independent-validation-run.md`](../design/independent-validation-run.md)
- **design-approval record:** [`approvals/M-IVT-1.md`](approvals/M-IVT-1.md)
  (`approved_with_conditions`, reviewed commit
  `38c5e1e8590e17c2798618c0490db7958d7f739d` — **tooling scope only**)
- **issue placeholder:** `ISSUE-TBD-IVT-1`
- **branch name (proposed):** `feat/independent-validation-tooling`
- **PR title (proposed):** `feat: add independent-validation run tooling and runner kit`
- **dependency milestones:** the *tooling* (manifest/attestation
  templates, checksum/bundle-root generator and verifier, runner
  quick-start, reproducibility-review checklist, maintainer dry run) is
  independently buildable now — a baseline-profile validation run needs
  only the released v1.0.0 package, so tooling implementation does not
  require the LangGraph runtime or `M-GPI-1` to merge first. Any
  documentation the tooling ships that advertises a framework-specific or
  protocol-specific runner path (e.g. a LangGraph or generic-protocol-
  integration run) still requires the corresponding executable
  integration to be merged before that path is presented as usable. The
  milestone's `independent_external` outcome remains blocked by external
  evidence regardless of tooling completion.
- **current status:** `APPROVED_FOR_IMPLEMENTATION` (tooling scope)
- **allowed actions:** manifest/attestation templates and (if approved in
  design review) machine schemas; bundle packager; checksum-manifest and
  detached-bundle-root generator/verifier implementing the non-recursive
  integrity model; runner quick-start docs; tests; changelog.
- **prohibited actions:** anything that lets project tooling alter or
  regenerate runner evidence; claims that a run occurred.
- **implementation deliverables:** validation-run manifest template,
  integrity tooling (`checksums.sha256` + `bundle-root.sha256`
  generation and full verification order), attestation template, runner
  quick-start, reproducibility-review checklist.
- **required tests:** packaging round-trip on a real `cavbench ablate`
  output; canonical-manifest determinism test (two independent
  generations over the same tree are byte-identical); tamper-detection
  negative tests for every verification step (root mismatch, format
  violation, per-file mismatch, unlisted file); template/schema
  validation; full quality gate.
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
- **dependency milestones:** `M-IVT-1` (reuses the bundle format and
  non-recursive integrity model); an executable integration for real
  candidates.
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
- **required tests:** per-class predicate unit tests (`validity_gap`,
  `hidden_invalid_commit`, `false_success_report`, `recovery_failure`)
  and fixed-precedence `primary_class` computation tests covering every
  co-occurrence combination; a test that `reviewer_emphasis` never
  appears in classifier output nor affects eligibility computation;
  classifier-immutability contract test;
  end-to-end pipeline test over a Validity-Gap-producing baseline run
  asserting correct class assignment; false-positive and misclassed
  fixture tests; full quality gate.
- **required external input:** design approval; later, candidate-owner
  consent for any real evaluation.
- **stop condition:** correct classification would require evaluator
  changes or adapter-supplied assertions — pause and escalate.
- **merge prerequisites:** human PR review and approval; CI green.
- **completion evidence:** merged PR + passing synthetic demonstration.
  **A hidden-failure discovery is evidence-complete only with a
  `validated`, `reproduced` finding of
  `primary_class: hidden_invalid_commit` against a real external
  candidate, with preserved evidence** (HFD-FR-006a; other finding
  classes are reportable but do not satisfy the roadmap outcome) — the
  milestone parks at `VALIDATING` / `BLOCKED_EXTERNAL_INPUT` until that
  exists.

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
  bundle verification-order failure tests (root mismatch and per-file
  mismatch both abort the comparison); hypothesis-ordering warning test;
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
