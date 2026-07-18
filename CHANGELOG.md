# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project uses schema-versioned scenario/trace/evaluation contracts
(currently `1.0`) documented in `docs/scenario-authoring.md`.

## [Unreleased]

### Documentation

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
