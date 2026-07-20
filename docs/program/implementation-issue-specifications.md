# Implementation Issue Specifications

Status: Recorded — not yet filed

This document contains **ready-to-create GitHub issue specifications**
for the six future-workstream implementation milestones. No GitHub issue
is created by this document or by the pull request that carries it, per
repository practice for this documentation package. These specifications
are intended to be used, one at a time, to open real GitHub issues after
this approval PR merges — each issue mirrors the corresponding entry in
[`implementation-manifest.md`](implementation-manifest.md).

Only the first three specifications (`M-GPI-1`, `M-COM-V1`, `M-IVT-1`) are
marked **approved for implementation**, reflecting the recorded design
approvals in [`approvals/`](approvals/). The last three (`M-HFA-1`,
`M-IET-1`, `M-REL-NEXT`) are marked **proposed / not executable** and must
not be treated as authorizing any implementation work.

Opening any of these issues does not, by itself, authorize implementation
beyond what the corresponding design-approval record and manifest entry
already permit; the issue is a tracking artifact, not a new authorization.

---

## 1. M-GPI-1 — Generic protocol integration

- **Issue title:** `[M-GPI-1] Implement generic protocol gateway core with REST frontend`
- **milestone_id:** `M-GPI-1`
- **Design link:** [`docs/design/generic-protocol-integration.md`](../design/generic-protocol-integration.md)
- **Approval record link:** [`docs/program/approvals/M-GPI-1.md`](approvals/M-GPI-1.md) — `approved_with_conditions`
- **Status:** Approved for implementation
- **Scope:** A shared, transport-independent protocol gateway core plus a
  REST transport frontend, mediating between a candidate protocol client
  and the existing `ToolFacade → BenchmarkEnvironment` commit path, with a
  deterministic reference candidate client for local/CI use.
- **Deliverables:** common protocol envelope (schema + docs); shared
  gateway core (session binding, 1:1 request-to-`ToolFacade` mapping,
  response normalization, redaction, session logging, capability
  advertisement, final-report intake); REST frontend; deterministic
  reference candidate client; candidate-facing mapping documentation; CI
  example job (loopback-only).
- **Acceptance criteria:**
  1. Core package installs and imports with no protocol extras present.
  2. Reference-candidate integration runs are deterministic across two
     consecutive CI runs (artifact-hash comparison).
  3. The adversarial forged-report contract test shows no evaluation
     improvement from candidate-side assertions; neutrality tests show
     exact 1:1 request↔attempt correspondence including under ambiguity
     and retry storms.
  4. A reviewer can trace one ambiguous-retry episode
     wire → trace → ledger → evaluation using only run artifacts.
- **Required tests:** envelope/normalization unit tests; identity
  pass-through (no mutation) tests; redaction tests; adversarial
  forged-final-report contract test; gateway neutrality tests; malformed-
  request tests (no benchmark attempt created); reference-candidate
  integration tests over the four hazard patterns in guarded and flawed
  configurations; double-run determinism check; extras-isolation import
  test; full repository quality gate (`pytest`, `ruff check .`,
  `mypy src/cavbench`, `python -m build`, `git diff --check`).
- **Dependencies:** none in this queue; requires the recorded design
  approval (satisfied) and a `DECISION_LOG.md` entry at implementation
  time recording the approved topology and transport order (approval
  Condition 1).
- **External prerequisites:** external technical review of the envelope
  and both frontend mappings before the integration is represented
  publicly as externally usable or validated; no official REST/MCP/
  framework/community support is implied.
- **Branch name:** `feat/generic-protocol-integration`
- **PR title:** `feat: add generic protocol gateway core with REST frontend`
- **Stop conditions:** protocol conformance would require the gateway to
  break behavioral neutrality, add a commit path, or treat candidate
  claims as truth; any requirement for evaluator, core-v1, or schema
  changes; any adapter-supplied commit truth; any external execution
  mirrored into the benchmark.
- **Explicit non-claims:** no MCP-specification conformance certification;
  no official support or endorsement by any protocol steward; the gateway
  is not a production API gateway or monitoring system; remote-candidate
  results are not reproducible benchmarks.

---

## 2. M-COM-V1 — Commerce-v1 profile implementation

- **Issue title:** `[M-COM-V1] Implement commerce-v1 scenario pack (initial subset)`
- **milestone_id:** `M-COM-V1`
- **Design link:** [`docs/design/commerce-v1-profile.md`](../design/commerce-v1-profile.md)
- **Approval record link:** [`docs/program/approvals/M-COM-V1.md`](approvals/M-COM-V1.md) — `approved_with_conditions`
- **Status:** Approved for implementation — **eligible to start now**
  against the approved proposed five-scenario working subset; **not
  eligible to merge or be marked complete** until the external scope
  review below is recorded (see Dependencies and Acceptance criteria).
- **Scope:** A self-contained `commerce-v1` scenario pack implementing an
  initial subset (4–6 scenarios, proposed: C-01, C-03, C-06, C-08, C-17)
  plus happy-path controls, loadable via the existing pack loader with no
  schema, evaluator, runtime, or `core-v1` changes.
- **Deliverables:** approved initial subset scenarios + happy-path
  controls; `pack.json` + digest; adoption-facing control mapping
  documentation; pack golden ablation expectations.
- **Acceptance criteria:**
  1. External review of the candidate set completed and the subset
     confirmed or amended (Gate-2 scope validation). **This gates
     merge/completion, not the start of implementation** — see
     Dependencies.
  2. Implemented subset passes the full quality gate and its own golden
     expectations; `core-v1` goldens byte-identical before/after.
  3. Guarded vs. flawed behavior separation visible in the pack's
     ablation (full_lifecycle passes what direct fails, per scenario
     design).
  4. An architect unfamiliar with evaluator internals can read a
     scenario's report and name the missing control — checked by
     external review.
- **Required tests:** schema validation of every scenario; pack-loading
  and digest tests; per-scenario deterministic execution tests across all
  five baselines; oracle-boundary contract tests (no oracle leakage into
  views); invariant unit tests for monetary/quantity predicates; golden
  expectations for the pack's ablation table; a docs test that every
  scenario's declared dimensions/`CMF-*` codes appear in the control-
  mapping documentation; full repository quality gate.
- **Dependencies:** none in this queue (uses existing runtime); requires
  the recorded design approval (satisfied). The external scope review
  named in the design (Gate-2 scope validation, unresolved) does **not**
  block opening this issue or starting implementation against the
  approved proposed five-scenario working subset — it blocks the PR from
  reaching `APPROVED`/`MERGED`/`COMPLETE`. If the review changes the
  subset, amend the implementation PR on the same branch rather than
  restarting.
- **External prerequisites:** external review of the candidate set and
  initial subset for Gate-2 scope validation — required before merge,
  not before starting work; implementation completion does not
  constitute external adoption or domain validation.
- **Branch name:** `feat/commerce-v1-profile`
- **PR title:** `feat: add commerce-v1 scenario pack initial subset`
- **Stop conditions:** any candidate requires schema or evaluator
  changes; any `core-v1` golden deviates.
- **Explicit non-claims:** no production transaction platform, real
  payment-provider integration, or real PII; no claim these scenarios
  represent any real merchant's incident history; commerce is the first
  applied profile, not CAV-Bench's identity or limit.

---

## 3. M-IVT-1 — Independent-validation tooling

- **Issue title:** `[M-IVT-1] Build independent-validation run tooling and runner kit`
- **milestone_id:** `M-IVT-1`
- **Design link:** [`docs/design/independent-validation-run.md`](../design/independent-validation-run.md)
- **Approval record link:** [`docs/program/approvals/M-IVT-1.md`](approvals/M-IVT-1.md) — `approved_with_conditions` (tooling scope only)
- **Status:** Approved for implementation (tooling scope only)
- **Scope:** Validation-run manifest schema, runner-attestation template,
  checksum-manifest and detached bundle-root generation/verification
  implementing the non-recursive integrity model, bundle packager and
  verifier, no-unlisted-files and path-safety checks, runner quick-start,
  reproducibility-review checklist, and a maintainer `project_self_run`
  rehearsal. No real external run is in scope.
- **Deliverables:** validation-run manifest template, integrity tooling
  (`checksums.sha256` + `bundle-root.sha256` generation and full
  verification order), attestation template, runner quick-start,
  reproducibility-review checklist.
- **Acceptance criteria:**
  1. A maintainer dry run produces a conforming bundle end-to-end using
     only public documentation.
  2. The rubric classifies the dry run as `project_self_run` without
     judgment calls.
  3. Review of the dry-run bundle passes the full verification order
     (root, manifest, per-file, no unlisted files) and re-derives summary
     metrics from `evaluations.jsonl`.
  4. An external reviewer of the design can state what they would have to
     do to conduct an independent run, without asking clarifying
     questions.
- **Required tests:** packaging round-trip on a real `cavbench ablate`
  output; canonical-manifest determinism test (two independent
  generations over the same tree are byte-identical); tamper-detection
  negative tests for every verification step (root mismatch, format
  violation, per-file mismatch, unlisted file); template/schema
  validation; full repository quality gate.
- **Dependencies:** the tooling is independently buildable now (a
  baseline-profile run needs only released v1.0.0); the design approval
  is satisfied. A merged executable integration is required only before
  any framework/protocol-specific runner path the tooling documents is
  presented as usable.
- **External prerequisites:** a real external runner; independently
  conducted execution; runner-authored attestation; reproducibility
  review; disclosure and attribution permission. None of these may be
  simulated or fabricated.
- **Branch name:** `feat/independent-validation-tooling`
- **PR title:** `feat: add independent-validation run tooling and runner kit`
- **Stop conditions:** the workflow cannot be completed by a maintainer
  dry run in reasonable time (design rework needed).
- **Explicit non-claims:** no claim that an independent external run has
  occurred; no claim of external validation, adoption, or runner
  endorsement; a maintainer rehearsal is always `project_self_run`, never
  `assisted_external` or `independent_external`.

---

## 4. M-HFA-1 — Hidden-failure analysis tooling

- **Issue title:** `[M-HFA-1] Build hidden-failure evidence correlation and finding tooling`
- **milestone_id:** `M-HFA-1`
- **Design link:** [`docs/design/hidden-failure-discovery.md`](../design/hidden-failure-discovery.md)
- **Approval record link:** not approved
- **Status:** Proposed / not executable
- **Scope:** Evidence correlator, classifier, and finding-record tooling
  for identifying hidden failures in real candidate systems, strictly
  downstream of the (unchanged) evaluator.
- **Deliverables:** correlator, classifier, finding-record
  schema/templates, false-positive review checklist, synthetic
  demonstration.
- **Acceptance criteria:** not applicable — implementation not authorized.
- **Required tests (planned, not run):** per-class predicate unit tests
  (`validity_gap`, `hidden_invalid_commit`, `false_success_report`,
  `recovery_failure`) and fixed-precedence `primary_class` computation
  tests; a test that `reviewer_emphasis` never appears in classifier
  output nor affects eligibility; classifier-immutability contract test;
  end-to-end pipeline test over a Validity-Gap-producing baseline run;
  false-positive and misclassed fixture tests; full quality gate.
- **Dependencies:** `M-IVT-1` (bundle format and integrity model); an
  executable integration for real candidates; **its own design approval
  (not yet recorded)**.
- **External prerequisites:** design approval; later, candidate-owner
  consent for any real evaluation.
- **Branch name (proposed):** `feat/hidden-failure-analysis`
- **PR title (proposed):** `feat: add hidden-failure evidence correlation and finding tooling`
- **Stop conditions:** correct classification would require evaluator
  changes or adapter-supplied assertions.
- **Explicit non-claims:** no claim that a hidden failure has been
  discovered in any real system; no naming of any candidate system; no
  publication of any "finding" from synthetic demonstrations.

---

## 5. M-IET-1 — Improvement/retest evidence tooling

- **Issue title:** `[M-IET-1] Build before-and-after comparison and case-study evidence tooling`
- **milestone_id:** `M-IET-1`
- **Design link:** [`docs/design/improvement-case-study.md`](../design/improvement-case-study.md)
- **Approval record link:** not approved
- **Status:** Proposed / not executable
- **Scope:** Comparison engine, comparability checklist, and artifact
  templates (remediation plan, changed-system manifest, comparison
  report, disclosure record) for a future before-and-after improvement
  case, plus labeled process-rehearsal fixtures.
- **Deliverables:** comparison engine + templates + rehearsal, per the
  design's tooling phase.
- **Acceptance criteria:** not applicable — implementation not authorized.
- **Required tests (planned, not run):** diff unit tests (improve/
  regress/mixed/no-change); bundle verification-order failure tests (root
  mismatch and per-file mismatch both abort the comparison); hypothesis-
  ordering warning test; labeled two-profile rehearsal; full quality
  gate.
- **Dependencies:** `M-HFA-1` (consumes finding records); **its own design
  approval (not yet recorded)**.
- **External prerequisites:** design approval; a validated finding and a
  real retest for any actual improvement case (tooling alone does not
  satisfy this).
- **Branch name (proposed):** `feat/improvement-evidence-tooling`
- **PR title (proposed):** `feat: add before-and-after comparison and case-study evidence tooling`
- **Stop conditions:** comparability checklist proves unsatisfiable for
  real subjects (design rework, not in-flight loosening).
- **Explicit non-claims:** no claim of measured improvement; no
  publication of any case study without a recorded disclosure record; no
  alteration of frozen baselines.

---

## 6. M-REL-NEXT — Versioned follow-up release

- **Issue title:** `[M-REL-NEXT] Prepare and publish the versioned follow-up release`
- **milestone_id:** `M-REL-NEXT`
- **Design link:** [`docs/design/follow-up-release.md`](../design/follow-up-release.md)
- **Approval record link:** not approved
- **Status:** Proposed / not executable (effectively blocked)
- **Scope:** Release checklist, evidence manifest, release-candidate
  process, and eventual tag/publication for a versioned follow-up release
  bundling whichever approved, merged scope items exist at freeze time.
- **Deliverables:** release checklist, evidence manifest, RC(s), release
  notes, reproducibility package, review sign-offs, tag, GitHub release,
  post-release verification record, roadmap update.
- **Acceptance criteria:** not applicable — implementation not authorized;
  entry criteria in the design are the unlock.
- **Required tests (planned, not run):** full quality gate from clean
  checkout; wheel smoke test; extras and Python matrices; goldens; link
  validation; the four human reviews (security, docs, claims,
  attribution).
- **Dependencies:** every scope item it will contain, merged and
  gate-complete (`M-COM-V1`, `M-GPI-1`, `M-IVT-1` at minimum, plus the
  hardened LangGraph adapter from its own PR chain), and the external
  evidence its claims will cite; **its own design approval (not yet
  recorded)**.
- **External prerequisites:** all four review sign-offs; permission
  records for every attribution; the external evidence behind every
  externally-facing claim.
- **Branch name (proposed):** `release/follow-up-version`
- **PR title (proposed):** `release: follow-up version release candidate`
- **Stop conditions:** any claim cannot be substantiated → publication
  blocked.
- **Explicit non-claims:** no version number is selected before the
  freeze-time semver rule application; no tagging or publication until
  every prerequisite is met; no program outcome marked complete without
  evidence.

---

This file will be used, after this approval PR merges, to open the
corresponding GitHub issues one at a time — in dependency and manifest
order — never all at once, and never ahead of the recorded approval each
one requires.
