# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project uses schema-versioned scenario/trace/evaluation contracts
(currently `1.0`) documented in `docs/scenario-authoring.md`.

## [Unreleased]

### Added

- Executable LangGraph integration (the next milestone from Issue #5, stacked on the PR #6 design-stage skeleton):
  - `LangGraphAdapter` now actually runs a compiled LangGraph graph against an `AdapterSession` (checkpointer, durable `thread_id`, `durability="sync"`), mapping terminal graph state to an untrusted `AdapterResult`. LangGraph stays an optional, lazily-imported dependency; a missing install raises a clear invocation-time error naming `cav-bench[langgraph]`.
  - Optional `langgraph` extra in `pyproject.toml` (`langgraph>=0.6,<2`; CI continuously tests the declared floor, `langgraph==0.6.0`, and the range's latest resolved release — see `docs/langgraph-adapter-mapping.md#local-vs-ci-validation`).
  - `framework-v1` builtin scenario pack: the four framework-adapter scenarios from `docs/framework-adapter-brief.md` (FA-01 stale state before commit, FA-02 ambiguous retry, FA-03 partial execution, FA-04 authority change before commit), kept separate from the frozen `core-v1` corpus (see DECISION_LOG D-020).
  - Deterministic reference LangGraph graphs (`cavbench.adapters.langgraph_reference`) — test fixtures, not a production design — in `guarded` and deliberately-flawed `naive` variants, with stable `operation_id`/`idempotency_key` derivation from durable scenario/thread/step identity.
  - `tests/langgraph/`: runtime tests for all four scenarios, adversarial trust-boundary tests (graph/adapter success claims cannot alter evaluator output), identifier stability across retry and checkpoint resume, safe idempotent replay, and bit-for-bit determinism; `tests/contract/test_langgraph_adapter_contract.py` covers dependency isolation without langgraph installed.
  - `examples/langgraph_adapter.py`: runnable outcome-pass vs. commit-valid-fail demonstration (naive run passes a conventional outcome check but fails commit validity on `TS_STALE_WITNESS`; the guarded control adds one revalidation node and becomes commit-valid).
  - CI (`.github/workflows/ci.yml`): a new `langgraph` job (matrix: `langgraph==0.6.0` and the latest resolved release) actually runs `tests/langgraph/`, the runnable example, and `cavbench validate --pack framework-v1` against the real dependency on every push/PR — previously the executable LangGraph suite silently skipped in CI (`pytest.importorskip`) because only the base `.[dev]` extra was installed. A new `wheel-smoke-test-langgraph` job additionally installs the *built wheel* with its `[langgraph]` extra and re-runs the same validation, so the packaged optional extra is verified, not only the source tree. The existing Python 3.11/3.12/3.13 `test` matrix is unchanged and continues to run without the extra, which is what continuously verifies dependency isolation and the missing-dependency error path.
- `cavbench list packs` now lists both builtin packs.

### Documentation

- Rewrote `docs/langgraph-adapter-mapping.md` to distinguish design decisions inherited from PR #6 from implemented runtime behavior, and to document authority evidence, state-read vs. commit-time revalidation, attempted-vs-committed evidence, reconciliation behavior, identifier derivation, synchronous durability, fixture limitations, local-vs-CI validation, and installation/minimal-execution instructions. No official LangChain/LangGraph support, endorsement, adoption, certification, or validation is claimed.

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
