# Reproducibility

## Supported environments

Python 3.11, 3.12, or 3.13. Core benchmark execution requires no network
access. CI runs the full matrix on every push (`.github/workflows/ci.yml`).

## Reproduce from a clean checkout

```bash
git clone https://github.com/nixalkumar/cav-bench
cd cav-bench
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest
ruff check .
mypy src/cavbench
python -m build
cavbench doctor
cavbench validate --pack core-v1
cavbench ablate --output runs/ablation
```

## Expected output

`cavbench validate --pack core-v1` should print:

```
OK: pack 'core-v1' v1.0.0 -- 40 scenarios valid, digest sha256:...
```

The digest is a stable SHA-256 over the canonicalized scenario documents; it
changes if and only if scenario content changes. It is recorded in every
run manifest.

`cavbench ablate` should print the canonical table (also asserted byte-for-byte
in `tests/golden/test_canonical_ablation.py`):

| Profile | OSR | PAOSR | CVSR | VG |
|---|---:|---:|---:|---:|
| direct | 0.925 | 0.750 | 0.250 | 0.675 |
| policy_gated | 1.000 | 1.000 | 0.500 | 0.500 |
| commit_guarded | 1.000 | 1.000 | 0.750 | 0.250 |
| reconciled | 1.000 | 1.000 | 0.875 | 0.125 |
| full_lifecycle | 1.000 | 1.000 | 1.000 | 0.000 |

## What every run records

`runs/<run-id>/manifest.json`:

```json
{
  "run_id": "...",
  "cavbench_version": "1.0.0",
  "git_commit": "...",
  "python_version": "3.12.4",
  "platform": "...",
  "scenario_pack": {"id": "core-v1", "version": "1.0.0", "digest": "sha256:..."},
  "adapter": {"name": "direct", "version": "1.0.0"},
  "seed": 0,
  "command": "cavbench run --profile direct --seed 0 --output runs",
  "started_at": "2026-07-14T00:00:00+00:00"
}
```

Reproduce any past run by matching all seven of: cavbench version, code
commit, scenario-pack id/version/digest, adapter name/version, seed, and
Python/platform. `git_commit` is best-effort (`None` outside a git checkout
or if `git` isn't on `PATH`) and never affects scoring.

## Determinism guarantees

- Same scenario + same profile + same seed ⇒ byte-identical trace events
  and identical evaluation result. `tests/integration/test_full_matrix_and_determinism.py`
  asserts this directly.
- Fault injections fire in `(hook, ordinal, fault_id)` order and at most
  once per episode — no wall-clock timing affects any baseline result.
- `cavbench replay --trace <path> --scenario <id>` re-evaluates a
  previously written trace without re-running the adapter, and reproduces
  the original evaluation exactly (`tests/integration/test_replay_equivalence.py`).

## If your results don't match

1. Confirm `cavbench validate --pack core-v1` reports the same digest shown
   above (from a from a clean checkout of the tagged release).
2. Confirm you're running an actual Python 3.11–3.13 interpreter — the
   evaluator has no external dependencies that would drift between patch
   versions, but confirm `python --version` matches a supported line.
3. If the deviation is in the canonical ablation table specifically: per
   `AGENTS.md`/`CLAUDE.md`, this project's policy is to investigate the
   semantic cause and document it in `DECISION_LOG.md`, not to update the
   expected numbers to match. Please open an issue with your exact
   `manifest.json` and `summary.json` attached.
