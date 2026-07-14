# Release process

## Before tagging a release

Run the full gate from a clean checkout (this is exactly what CI runs):

```bash
pytest
ruff check .
mypy src/cavbench
python -m build
```

Then, in a fresh virtual environment, install the built artifacts and
smoke-test them (this is what CI's `wheel-smoke-test` job automates):

```bash
python -m venv /tmp/cavbench-release-check
source /tmp/cavbench-release-check/bin/activate
pip install dist/cav_bench-*.whl
cavbench doctor
cavbench ablate --output /tmp/cavbench-release-check-runs
deactivate
```

Confirm:

- [ ] Every item in `ACCEPTANCE_CHECKLIST.md` passes.
- [ ] `CHANGELOG.md` has a dated entry for the release (move content out of
      `[Unreleased]`).
- [ ] `pyproject.toml` version matches the tag you're about to create.
- [ ] No `__pycache__`, `runs/`, or other generated artifacts are tracked
      (`git status` on a clean checkout should be empty).
- [ ] No secrets, credentials, or non-synthetic data anywhere in the tree.

## Tagging

```bash
git tag -a v1.0.0 -m "v1.0.0"
git push origin v1.0.0
```

Do not tag or push unless explicitly asked to — this repository's default
workflow keeps release actions manual and confirmed.

## Release notes template

```markdown
## cav-bench vX.Y.Z

### Highlights
- ...

### Breaking changes
- ... (schema_version bump, if any; migration notes)

### Canonical ablation (core-v1, seed 0)
| Profile | OSR | PAOSR | CVSR | VG |
|---|---:|---:|---:|---:|
| direct | 0.925 | 0.750 | 0.250 | 0.675 |
| policy_gated | 1.000 | 1.000 | 0.500 | 0.500 |
| commit_guarded | 1.000 | 1.000 | 0.750 | 0.250 |
| reconciled | 1.000 | 1.000 | 0.875 | 0.125 |
| full_lifecycle | 1.000 | 1.000 | 1.000 | 0.000 |

Reproduce: see `docs/reproducibility.md`.

Full changelog: https://github.com/nixalkumar/cav-bench/compare/vPREV...vX.Y.Z
```

## Publishing (only when explicitly requested)

This project does not auto-publish to PyPI or mint a Zenodo DOI as part of
the normal release flow (`PRD.md` §4 non-goals). If a maintainer explicitly
requests it:

```bash
python -m build
python -m twine upload dist/*
```

For a Zenodo DOI, use GitHub's Zenodo integration on the tagged release, or
upload the release tarball manually; update `CITATION.cff` with the minted
DOI afterward.
