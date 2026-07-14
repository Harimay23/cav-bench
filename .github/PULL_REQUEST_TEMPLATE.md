## What and why

<!-- What does this change, and why. Link an issue if there is one. -->

## Checklist

- [ ] `pytest`, `ruff check .`, and `mypy src/cavbench` all pass locally
- [ ] Tests added/updated for any behavior change
- [ ] `CHANGELOG.md` updated under `[Unreleased]`
- [ ] If this changes benchmark semantics (evaluator, dimensions, scenario
      schema, CVSR formula): `DECISION_LOG.md` updated with the rationale
- [ ] If this changes `core-v1`'s expected results: the golden table in
      `tests/golden/test_canonical_ablation.py` was **not** edited to make
      the change pass without investigating and documenting why the
      semantics changed
