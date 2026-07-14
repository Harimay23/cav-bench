# CAV-Bench v1.0 Acceptance Checklist

## Product

- [ ] Public package name is `cav-bench` and import package is `cavbench`.
- [ ] Python 3.11, 3.12, and 3.13 are supported in CI.
- [ ] Core benchmark runs without external network access.
- [ ] All 40 `core-v1` scenarios are included and versioned.

## Trust boundary

- [ ] Adapter cannot access `ScenarioOracle` through public runtime API.
- [ ] Adapter metadata cannot set OSR/PAOSR/CVSR.
- [ ] Evaluator does not trust pre-labeled dimension validity.
- [ ] No normal runtime path uses `explicit_invalid_dimension`.
- [ ] No normal evaluator path uses adapter-supplied `goal_predicates_satisfied`.
- [ ] No normal evaluator path uses adapter-supplied `recovery_obligation_satisfied`.

## Runtime

- [ ] Versioned state store works.
- [ ] Stale expected version is rejected deterministically.
- [ ] Deterministic external mutations work.
- [ ] Deterministic fault injections work.
- [ ] Side-effect ledger is append-only.
- [ ] Duplicate logical effects are detectable.
- [ ] Compensation relationships are representable.
- [ ] Canonical trace schema validates.

## Evaluation

- [ ] Outcome success is derived from oracle predicates.
- [ ] Intent grounding is derived.
- [ ] Authority validity is derived.
- [ ] Temporal state validity is derived.
- [ ] Execution integrity is derived from trace/ledger facts.
- [ ] Recovery adequacy is derived.
- [ ] OSR is computed.
- [ ] PAOSR is computed.
- [ ] CVSR is computed.
- [ ] VG is computed.
- [ ] PAVG is computed.
- [ ] Overall and by-family summaries are produced.

## Profiles

- [ ] Direct profile works.
- [ ] Policy-gated profile works.
- [ ] Commit-guarded profile works.
- [ ] Reconciled profile works.
- [ ] Full-lifecycle profile works.
- [ ] All profiles implement the same adapter protocol.
- [ ] Evaluator has no profile-name-specific scoring logic.

## Canonical regression

- [ ] Direct: OSR 0.925, PAOSR 0.750, CVSR 0.250, VG 0.675.
- [ ] Policy-gated: OSR 1.000, PAOSR 1.000, CVSR 0.500, VG 0.500.
- [ ] Commit-guarded: OSR 1.000, PAOSR 1.000, CVSR 0.750, VG 0.250.
- [ ] Reconciled: OSR 1.000, PAOSR 1.000, CVSR 0.875, VG 0.125.
- [ ] Full lifecycle: OSR 1.000, PAOSR 1.000, CVSR 1.000, VG 0.000.

## CLI

- [ ] `cavbench doctor`
- [ ] `cavbench list scenarios`
- [ ] `cavbench list profiles`
- [ ] `cavbench validate --pack core-v1`
- [ ] `cavbench run --profile direct`
- [ ] `cavbench ablate`
- [ ] `cavbench replay`
- [ ] `cavbench report`
- [ ] Threshold-based non-zero exit code works.

## Reproducibility

- [ ] Run manifest includes package version.
- [ ] Run manifest includes git commit when available.
- [ ] Run manifest includes scenario pack version and digest.
- [ ] Run manifest includes profile/adapter name and version.
- [ ] Run manifest includes seed.
- [ ] Run manifest includes Python/platform information.
- [ ] Replaying a trace produces the same evaluation.

## Testing and quality

- [ ] Unit tests pass.
- [ ] Integration tests pass.
- [ ] Contract tests pass.
- [ ] Golden ablation test passes.
- [ ] CLI tests pass.
- [ ] `ruff check .` passes.
- [ ] `mypy src/cavbench` passes at configured strictness.
- [ ] `python -m build` succeeds.
- [ ] Wheel installs in clean environment.
- [ ] Sdist installs in clean environment.

## Documentation

- [ ] README quickstart works exactly as written.
- [ ] Methodology document exists.
- [ ] Architecture document exists.
- [ ] Scenario authoring guide exists.
- [ ] Adapter authoring guide exists.
- [ ] Reproducibility guide exists.
- [ ] Limitations and non-claims are explicit.
- [ ] Included result table is labeled as a deterministic architecture ablation, not an LLM benchmark.

## Open-source readiness

- [ ] `LICENSE`
- [ ] `CITATION.cff`
- [ ] `CHANGELOG.md`
- [ ] `CONTRIBUTING.md`
- [ ] `CODE_OF_CONDUCT.md`
- [ ] `SECURITY.md`
- [ ] `.gitignore`
- [ ] No secrets.
- [ ] No real customer/employer data.
- [ ] No tracked `__pycache__`.
- [ ] No unintended generated run artifacts.

## Release

- [ ] Clean checkout verification passes.
- [ ] Release notes prepared.
- [ ] `v1.0.0` tag candidate points to verified commit.
- [ ] GitHub release assets prepared.
- [ ] DOI metadata prepared for Zenodo.
- [ ] TDS article repository/DOI references prepared.
