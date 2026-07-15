# Citing CAV-Bench

## DOI overview

- **Concept DOI:** [10.5281/zenodo.21364385](https://doi.org/10.5281/zenodo.21364385) — represents the CAV-Bench project as a whole, across all versions. It always resolves to the most recently archived release.
- **v1.0.0 DOI:** [10.5281/zenodo.21364386](https://doi.org/10.5281/zenodo.21364386) — represents the exact, immutable archive of the `v1.0.0` release: the specific source tree, scenario pack, and code that produced the canonical ablation results published in `README.md`.

## Which DOI should I use?

Use the **concept DOI** when:

- referring to CAV-Bench generally, e.g. "we evaluated using CAV-Bench";
- linking to the project from a website, talk, or survey where the specific version isn't load-bearing;
- you want the citation to keep resolving to whatever the latest release is, without updating it yourself later.

Use the **v1.0.0 DOI** when:

- citing or reproducing a specific result (e.g. the canonical ablation table, a specific scenario's behavior);
- your own work depends on the exact code, scenarios, or scoring logic of this release;
- you need the citation to point at content that will never change out from under you, even after CAV-Bench publishes v1.1.0 or later.

**Reproducibility claims must cite the exact release DOI, not the concept DOI.** The concept DOI is a moving target by design — it resolves to whatever the newest version is, so a reproducibility claim anchored to it can silently start pointing at different code and different scenarios after a future release. The v1.0.0 DOI is Zenodo's permanent archive of the exact artifact this README's canonical ablation table came from, and will still point at that same artifact regardless of what CAV-Bench does afterward. If you are citing this benchmark to support a reproducibility claim, cite `10.5281/zenodo.21364386`, not the concept DOI.

## APA

> Patel, N. (2026). *CAV-Bench: Commit-Time Action Validity Benchmark* (Version v1.0.0) [Computer software]. Zenodo. https://doi.org/10.5281/zenodo.21364386

## BibTeX

```bibtex
@software{patel_2026_cav_bench,
  author    = {Patel, Nixalkumar},
  title     = {CAV-Bench: Commit-Time Action Validity Benchmark},
  version   = {v1.0.0},
  year      = {2026},
  publisher = {Zenodo},
  doi       = {10.5281/zenodo.21364386},
  url       = {https://doi.org/10.5281/zenodo.21364386}
}
```

## Repository

[https://github.com/Harimay23/cav-bench](https://github.com/Harimay23/cav-bench)

Licensed under [Apache-2.0](../LICENSE).

## Reproducibility

The source archive Zenodo preserves under the v1.0.0 DOI is the exact artifact behind this repository's canonical ablation table:

| Profile | OSR | PAOSR | CVSR | VG |
|---|---:|---:|---:|---:|
| direct | 0.925 | 0.750 | 0.250 | 0.675 |
| policy_gated | 1.000 | 1.000 | 0.500 | 0.500 |
| commit_guarded | 1.000 | 1.000 | 0.750 | 0.250 |
| reconciled | 1.000 | 1.000 | 0.875 | 0.125 |
| full_lifecycle | 1.000 | 1.000 | 1.000 | 0.000 |

If you're reproducing or building on these specific numbers, cite the v1.0.0
DOI above, and see [`reproducibility.md`](reproducibility.md) for the exact
commands to regenerate this table from a clean checkout.

## Future releases

CAV-Bench is archived on Zenodo via GitHub's Zenodo integration, which mints
a new version-specific DOI automatically each time a new GitHub release is
published. The concept DOI above is unaffected and will simply resolve to
the newest one. When a future version is released:

- Its own version-specific DOI will be documented here and in `CITATION.cff`.
- Prior version DOIs (including `10.5281/zenodo.21364386` for v1.0.0) remain
  valid and continue to resolve to that exact archived release — they are
  never reassigned or overwritten.
- The concept DOI (`10.5281/zenodo.21364385`) never changes.

## Author identity

CAV-Bench was created and is maintained by Nixalkumar Patel.
A verified ORCID may be added in a future metadata update.
