# Contributing to CAV-Bench

Thanks for considering a contribution. CAV-Bench is a methodology benchmark
first — changes that touch scoring semantics get more scrutiny than changes
that touch tooling.

## Before you start

- For anything beyond a small fix, open an issue describing what you want to
  change and why before writing code. This is especially true for anything
  touching `src/cavbench/evaluation/`, the scenario schema, or the canonical
  scenario pack — see [Changing benchmark semantics](#changing-benchmark-semantics)
  below.
- Read [`docs/architecture.md`](docs/architecture.md) for the trust model
  before touching runtime or evaluator code. The one rule that overrides
  everything else: **the system under evaluation must never be able to
  grade itself.** No adapter-, agent-, or trace-supplied field may ever be
  trusted for pass/fail truth.

## Development setup

```bash
git clone https://github.com/Harimay23/cav-bench
cd cav-bench
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest
ruff check .
mypy src/cavbench
```

## Making a change

1. Create a branch.
2. Write or update tests alongside any behavior change. A PR that changes
   evaluator or runtime behavior without a test change will be asked for one.
3. Run the full local gate before opening a PR:
   ```bash
   pytest
   ruff check .
   mypy src/cavbench
   python -m build
   ```
4. Update `CHANGELOG.md` under an `[Unreleased]` heading.
5. If the change is a material design decision (not just an implementation
   detail), add an entry to `DECISION_LOG.md` explaining what and why.

## Adding a scenario

See [`docs/scenario-authoring.md`](docs/scenario-authoring.md). New scenarios
go in a new or existing scenario pack under
`src/cavbench/scenarios/packs/<pack-id>/scenarios/`, must validate against
`scenario-v1.schema.json`, and must include a benchmark-private oracle that
is *never* derivable from data exposed to the adapter.

## Adding an adapter

See [`docs/adapter-authoring.md`](docs/adapter-authoring.md) and
[`examples/custom_adapter.py`](examples/custom_adapter.py). An adapter should
never require a change to `cavbench.evaluation` to be scored correctly — if
it does, that's very likely a trust-boundary bug in the adapter, not a
missing feature in the evaluator.

## Changing benchmark semantics

Do not:

- Modify `core-v1`'s expected canonical ablation results
  (`tests/golden/test_canonical_ablation.py`) to make a change pass. If your
  change causes a deviation, that's a signal to investigate the semantic
  cause first — see `DECISION_LOG.md` D-018 for an example of exactly this
  happening during v1.0 development, and how it was resolved (the
  implementation was fixed, not the golden numbers).
- Add a new validity dimension, change what counts as a consequential
  commit, or change the non-compensatory CVSR formula without opening an
  issue first and documenting the rationale in `DECISION_LOG.md`.
- Add a field that lets an adapter set or influence its own OSR/PAOSR/CVSR,
  dimension status, or failure codes, directly or indirectly.

## Code style

- Python 3.11+, type-annotated public APIs, `ruff` and `mypy --strict` clean.
- Prefer immutable (frozen) dataclasses for value objects in the domain model.
- No comments explaining *what* code does; comment only non-obvious *why*.

## Reporting a security issue

See [`SECURITY.md`](SECURITY.md) — please do not open a public issue for a
security concern.

## Code of conduct

This project follows [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md).
