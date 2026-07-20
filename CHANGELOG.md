# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project uses schema-versioned scenario/trace/evaluation contracts
(currently `1.0`) documented in `docs/scenario-authoring.md`.

## [Unreleased]

### Added

- **M-GPI-1: generic protocol gateway core with a REST frontend**
  (`cavbench.gateway`), implementing
  `docs/design/generic-protocol-integration.md` under
  `docs/program/approvals/M-GPI-1.md`. A benchmark-owned protocol gateway
  lets a REST-speaking candidate agent or service be evaluated without
  writing a Python `ExecutionAdapter`: the candidate is the protocol
  client; the gateway is the protocol server; `ToolFacade` and
  `BenchmarkEnvironment` remain the sole effect executor and sole commit
  authority, unchanged. One well-formed, authenticated candidate request
  maps to exactly one `ToolFacade` invocation; a malformed or
  unauthenticated request creates zero benchmark attempts. Adds: the
  common protocol envelope (`cavbench.gateway.envelope`, schema at
  `src/cavbench/gateway/schemas/envelope.schema.json`); the transport-
  neutral gateway core (`cavbench.gateway.core`); redaction and a
  redacted session log (`cavbench.gateway.redaction`,
  `cavbench.gateway.session_log`); a standard-library-only REST frontend
  (`cavbench.gateway.rest`, no new runtime dependency); a deterministic
  reference candidate client and REST client
  (`examples/reference_candidate/`, a scripted test fixture, not a
  production client library) exercising the four canonical hazard
  patterns (stale state before commit, ambiguous acknowledgement and
  retry, partial execution and recovery, authority change before commit)
  in guarded and flawed configurations; a runnable local example
  (`examples/gateway_rest_demo.py`); gateway documentation under
  `docs/program/gateway/` (architecture, envelope reference, REST
  mapping, candidate integration guide with limitations/non-claims); new
  CI jobs `gateway-core-installs-without-extras` and `gateway-example`
  (loopback-only, double-run determinism check), plus a REST-extra
  gateway smoke test folded into `wheel-smoke-test`; a `rest` optional
  extra (currently empty — the REST frontend needs no dependency beyond
  core). `cavbench.gateway` is never imported by importing plain
  `cavbench` (extras isolation, matching the existing `reporting`
  pattern). No evaluator, runtime, scenario-schema, or `core-v1` change;
  all canonical ablation goldens are byte-identical before and after.
  MCP transport is explicitly out of scope for this milestone (deferred,
  see `DECISION_LOG.md` D-020). External technical review of the
  envelope and REST mapping has not occurred; the gateway is not claimed
  as externally validated, adopted, or production-ready. Tracked by
  [issue #11](https://github.com/Harimay23/cav-bench/issues/11).

### Documentation

- Recorded human design approvals for three future-workstream milestones:
  `M-GPI-1` (generic protocol integration), `M-COM-V1` (commerce-v1
  profile), and `M-IVT-1` (independent-validation tooling, tooling scope
  only) — each `approved_with_conditions` by the repository owner, at
  reviewed commit `38c5e1e8590e17c2798618c0490db7958d7f739d` (PR #9's
  design head), with approval records at `docs/program/approvals/`
  (`M-GPI-1.md`, `M-COM-V1.md`, `M-IVT-1.md`, and an index `README.md`).
  Updated the three corresponding design documents' status to `Approved
  for implementation with conditions` and the implementation manifest's
  entries to `APPROVED_FOR_IMPLEMENTATION`. `M-HFA-1`, `M-IET-1`, and
  `M-REL-NEXT` remain unapproved and `Status: Proposed`; no implementation
  has begun for any milestone. Added
  `docs/program/implementation-issue-specifications.md`, ready-to-create
  GitHub issue specifications for all six milestones (three approved,
  three proposed/not executable), to be used after this PR merges. This
  is a documentation and governance change only: no evaluator, runtime,
  scenario, schema, dependency, or CI behavior changed, and nothing is
  merged or implemented by it.
- Added the future-workstream design package (`docs/design/`): proposed
  designs for an independent external validation run, hidden-failure
  discovery, a before-and-after improvement case, the commerce-v1
  consequential-action profile, generic MCP/REST protocol integration, and
  a versioned follow-up release, with an index. All designs are
  `Status: Proposed`; nothing is approved for implementation and no
  production behavior, evaluator semantics, scenario packs, dependencies,
  or version metadata changed.
- Added program execution-control documents (`docs/program/`): an
  implementation manifest (future execution queue), gate-state lifecycle,
  external-evidence policy, Fable execution contract, PR and branch
  strategy, and a resume-and-recovery protocol.
- Added shared program diagrams (`docs/diagrams/`): future system
  architecture, validation and evidence lifecycle, workstream dependency
  map, and release and adoption gates.
- Added Claude Code project guidance, a 90-day technical validation and
  adoption roadmap, a 14-day validation sprint, program and architecture
  diagrams, adoption and validation tracking guidance, and repository-ready
  GitHub issue templates. No benchmark behavior, scoring semantics, or
  evaluator logic changed.
- Added project-level and version-specific DOI guidance.
- Added complete APA and BibTeX citation examples.
- Clarified reproducibility citation for v1.0.0.
- Hardened repository citation and Zenodo metadata.
- Fixed repository URL inconsistencies (`nixalkumar/cav-bench` → `Harimay23/cav-bench`) across `README.md`, `CITATION.cff`, `CONTRIBUTING.md`, `pyproject.toml`, and `docs/`.

## [1.0.0] — 2026-07-14

Initial public hardening of the v0.3 research prototype into an installable,
deterministic, framework-neutral benchmark.

Archived on Zenodo: concept DOI [10.5281/zenodo.21364385](https://doi.org/10.5281/zenodo.21364385), version DOI [10.5281/zenodo.21364386](https://doi.org/10.5281/zenodo.21364386).

### Added

- `src/`-layout installable package `cavbench` (distribution name `cav-bench`), CLI entry point `cavbench`.
- Versioned JSON Schemas (`schema_version: "1.0"`) for scenarios, traces, and evaluation results.
- Immutable domain models with a hard split between `ScenarioView` (adapter-visible) and `ScenarioOracle` (benchmark-private, never exposed through any runtime API).
- All 40 `core-v1` scenarios migrated from the v0.3 prototype, each now declaring a real adapter-visible task plan and policy envelope alongside the private oracle.
- Deterministic runtime: versioned state store, hook-based fault scheduler, append-only side-effect ledger, harness-owned commit path, canonical trace recorder.
- `DeterministicEvaluator`: derives OSR, PAOSR, CVSR, VG, PAVG, and per-dimension status entirely from benchmark-owned facts (oracle, state, ledger, trace) — never from adapter-supplied labels.
- Five canonical baseline architecture profiles (`direct`, `policy_gated`, `commit_guarded`, `reconciled`, `full_lifecycle`), implemented as one shared, capability-parameterized `ExecutionAdapter` engine executing real tool calls against the environment.
- `BenchmarkRunner`, run manifest, and report writers producing the `runs/<run-id>/{manifest.json,traces/,evaluations.jsonl,summary.json,summary.md}` layout.
- CLI: `doctor`, `list`, `validate`, `run`, `ablate`, `replay`, `report`.
- Unit, contract, integration, golden, and CLI test suites, including an adversarial test proving the evaluator ignores forged trust-boundary metadata.
- Public documentation: methodology, architecture, scenario-authoring, adapter-authoring, reproducibility guides.
- Open-source release metadata: `LICENSE` (Apache-2.0), `CITATION.cff`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `SECURITY.md`.

### Changed from v0.3

- The v0.3 prototype selected between two hand-authored "good"/"bad" fixture traces per scenario per profile (`use_safe_trace`); v1.0 replaces this with real execution of the five profiles against a real environment. See `DECISION_LOG.md` D-014.
- `harness_checks` embedded in trace metadata, `explicit_invalid_dimension`, and adapter-reachable `goal_predicates_satisfied`/`recovery_obligation_satisfied` flags are removed from the runtime trust path entirely.

### Verified

- Running all 40 scenarios through all five baseline profiles reproduces the canonical ablation table from the v0.3 research specification exactly (see `tests/golden/test_canonical_ablation.py`).
