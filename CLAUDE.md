# CLAUDE.md — CAV-Bench

Full agent operating instructions live in `AGENTS.md` — read that first.

## The one rule that overrides everything else

The system under evaluation must never be able to grade itself. No
adapter/agent/trace-supplied field may set or influence OSR, PAOSR, CVSR,
dimension status, or failure codes. See `docs/architecture.md` and
`tests/contract/test_evaluator_independence.py`.

## Quick reference

```bash
pytest                    # full test suite
ruff check .               # lint
mypy src/cavbench           # types
python -m build               # wheel + sdist
cavbench doctor                # sanity-check an install
cavbench ablate                 # reproduce the canonical table (docs/reproducibility.md)
```

Do not modify `tests/golden/test_canonical_ablation.py`'s expected values to
make a change pass — see `DECISION_LOG.md` D-018 and `AGENTS.md`.
