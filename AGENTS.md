# AGENTS.md — CAV-Bench

CAV-Bench v1.0 is complete and released. This file is operating guidance for
any coding agent making further changes to this repository — it is not the
original v0.3→v1.0 hardening plan (that's archived in `planning/`, for
provenance only and not maintained).

## The one rule that overrides everything else

**The system under evaluation must never be able to grade itself.** No
adapter-, agent-, or trace-supplied field may ever set or influence
OSR, PAOSR, CVSR, dimension status, invalid-commit status, or failure
codes. See `docs/architecture.md` for the trust model and
`tests/contract/test_evaluator_independence.py` for the adversarial test
that enforces it. Any change to `src/cavbench/evaluation/` or
`src/cavbench/runtime/environment.py` must preserve this property; if you
add a new field anywhere on the adapter-facing boundary, ask whether it
could let an adapter influence its own score, and if so, don't add it that
way.

## Before changing benchmark semantics

- Read `docs/methodology.md` and `DECISION_LOG.md` first.
- Do not modify `core-v1`'s expected canonical ablation results
  (`tests/golden/test_canonical_ablation.py`) to make a change pass. If a
  change causes a deviation, investigate the semantic cause and document it
  in `DECISION_LOG.md` before touching the golden numbers — see D-018 for a
  worked example of this happening during v1.0 development.
- A new validity dimension, a change to what counts as a consequential
  commit, or a change to the non-compensatory CVSR formula needs a
  `DECISION_LOG.md` entry, not just a code change.

## Where things live

See `docs/architecture.md` for the full map. Short version: `scenarios/`
(schema + domain models + the `core-v1` pack), `runtime/` (state, faults,
ledger, environment — the only trusted, harness-owned components adapters
never touch directly), `adapters/` (the `ExecutionAdapter` protocol + the
five baseline profiles, all sharing one capability-parameterized engine in
`adapters/baselines/_engine.py`), `evaluation/` (the predicate engine and
`DeterministicEvaluator`), `runner.py`/`manifest.py`/`reports/`/`cli.py`.

## Before considering a change complete

```bash
pytest
ruff check .
mypy src/cavbench
python -m build
```

Add or update tests alongside any behavior change — see `CONTRIBUTING.md`
for the full contribution workflow, and `ACCEPTANCE_CHECKLIST.md` for what
"release-ready" means for this project.

## Scope discipline

Do not add, without an explicit request and a `DECISION_LOG.md` entry:
hosted services, a web UI, a specific model-provider SDK as a core
dependency, an MCP implementation, or hidden/private scenario packs. The
adapter protocol is designed so all of these can be built as external
consumers of the public API without needing to be in this repository.
