# CAV-Bench v1.0 Implementation Plan

This plan is ordered. The coding agent should complete each gate before moving to the next phase.

---

## Phase 0 — Establish the clean repository baseline

### Tasks

- Unpack the v0.3 prototype.
- Initialize/confirm git repository.
- Create a working branch for v1.0 hardening.
- Remove generated `__pycache__` and local output artifacts from tracked source.
- Add `.gitignore`.
- Preserve the v0.3 package as a migration reference, not as the final structure.
- Create the `src/cavbench` layout.
- Add baseline `pyproject.toml`.

### Gate

- `python -m build` produces installable artifacts.
- Package imports in a clean virtual environment.

---

## Phase 1 — Lock schemas and domain models

### Tasks

- Add versioned scenario, trace, and evaluation JSON Schemas.
- Implement immutable domain models.
- Split `ScenarioView` from `ScenarioOracle`.
- Implement scenario-pack metadata and digest.
- Migrate all 40 scenarios into `core-v1`.
- Add schema and semantic validation.

### Gate

- All 40 scenarios validate.
- Adapter-facing objects contain no oracle fields.
- Scenario-pack digest is stable across repeated loads.

---

## Phase 2 — Rebuild deterministic runtime boundaries

### Tasks

- Port versioned state store.
- Port deterministic fault/mutation scheduler.
- Port append-only side-effect ledger.
- Implement canonical trace recorder.
- Implement tool facade.
- Ensure only environment code can create `side_effect_commit` events.

### Gate

- State mutation and stale-write tests pass.
- Fault ordering tests pass.
- Duplicate side effects remain visible in the ledger.
- Trace schema validates.

---

## Phase 3 — Harden evaluator

### Tasks

- Implement predicate engine.
- Derive outcome success from oracle predicates and final world facts.
- Derive intent grounding.
- Derive authority validity.
- Derive temporal state validity.
- Derive execution integrity from ledger and trace.
- Derive recovery adequacy.
- Compute OSR/PAOSR/CVSR and failure codes.
- Remove prototype reliance on `harness_checks`, explicit invalid labels, or goal-success flags.

### Gate

- A deliberately forged adapter metadata field cannot change scores.
- Replaying the same canonical trace yields the same result.
- Evaluator has no network/model dependency.

---

## Phase 4 — Implement adapter protocol and five baselines

### Tasks

- Define `ExecutionAdapter`.
- Define adapter-facing session and tool interfaces.
- Port the five architecture profiles.
- Ensure profiles create behavior, not pass/fail labels.
- Version each built-in profile.

### Gate

- All profiles run through the same public adapter interface.
- Evaluator code contains no special-case branch by profile name.

---

## Phase 5 — Implement runner, manifest, and output contracts

### Tasks

- Add `BenchmarkRunner`.
- Add run configuration.
- Add run manifest generation.
- Add per-scenario trace persistence.
- Add evaluation result persistence.
- Add aggregate metrics.
- Add replay support.

### Gate

- One command can run a profile over all 40 scenarios.
- Artifacts are schema-valid.
- Run manifest captures reproducibility metadata.

---

## Phase 6 — Build the CLI

### Tasks

Implement:

- `doctor`
- `list`
- `validate`
- `run`
- `ablate`
- `replay`
- `report`

Add stable exit codes and actionable error messages.

### Gate

A clean install can execute the full quickstart from README.

---

## Phase 7 — Reporting and canonical ablation

### Tasks

- Generate JSON and Markdown summaries from core runtime.
- Add optional CSV/chart export under reporting extras.
- Reproduce canonical five-profile ablation.
- Commit expected aggregate results as a golden regression artifact.

### Gate

Computed results match the canonical table or any deviation is documented as a correctness fix with evidence.

---

## Phase 8 — Testing and CI hardening

### Tasks

- Unit tests.
- Contract tests.
- Integration tests.
- Golden ablation test.
- CLI smoke tests.
- Python 3.11/3.12/3.13 CI matrix.
- Ruff.
- Mypy.
- Build and wheel smoke test.

### Gate

All CI jobs pass without external secrets.

---

## Phase 9 — Open-source repository readiness

### Tasks

- Rewrite public README.
- Add methodology docs.
- Add scenario-authoring guide.
- Add adapter-authoring guide.
- Add reproduction guide.
- Add `CONTRIBUTING.md`.
- Add `CODE_OF_CONDUCT.md`.
- Add `SECURITY.md`.
- Add `CHANGELOG.md`.
- Add `CITATION.cff`.
- Add recommended license after confirmation.
- Add issue and pull-request templates if useful.

### Gate

A technically competent external user can understand, install, run, and extend the benchmark from repository documentation alone.

---

## Phase 10 — Release candidate verification

### Tasks

- Build wheel and sdist from clean checkout.
- Install each into clean environment.
- Run `cavbench doctor`.
- Run all tests.
- Run canonical ablation.
- Compare results.
- Verify package data.
- Verify no confidential data or secrets.
- Verify citation metadata.
- Generate release notes.

### Gate

`ACCEPTANCE_CHECKLIST.md` is fully satisfied.

---

## Phase 11 — Public release preparation

Do not automatically publish unless explicitly requested.

Prepare:

- tag candidate `v1.0.0`;
- release notes;
- final repository description;
- topics/tags;
- DOI-ready metadata;
- TDS article repository reference text.

---

## Implementation discipline

### Do

- preserve scenario semantics;
- write tests before changing evaluator behavior;
- keep the evaluator provider-neutral;
- keep core runs network-free;
- maintain explicit schema versions;
- record decisions in `DECISION_LOG.md`.

### Do not

- modify expected metrics just to satisfy tests;
- add model APIs to v1.0 core;
- expose private oracle objects to adapters;
- let adapters emit trusted validity labels;
- turn the CLI into a framework-specific interface;
- add a web app.
