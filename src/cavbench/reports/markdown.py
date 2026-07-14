"""Human-readable Markdown summaries."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from cavbench.runner import CompletedRun

_INTERPRETATION_NOTE = (
    "> **Interpretation boundary:** this is a deterministic architecture ablation over five "
    "controlled execution-strategy baselines, not an LLM benchmark or a claim about frontier-model "
    "performance. See `docs/methodology.md` for what CAV-Bench does and does not evaluate."
)


def render_run_summary(run: "CompletedRun") -> str:
    m = run.manifest
    overall = run.metrics.overall.to_dict()
    lines = [
        f"# CAV-Bench run `{run.run_id}`",
        "",
        _INTERPRETATION_NOTE,
        "",
        "## Reproducibility",
        "",
        f"- cavbench version: `{m['cavbench_version']}`",
        f"- git commit: `{m.get('git_commit') or 'unknown'}`",
        f"- scenario pack: `{m['scenario_pack']['id']}` v`{m['scenario_pack']['version']}` (`{m['scenario_pack']['digest']}`)",
        f"- adapter/profile: `{m['adapter']['name']}` v`{m['adapter']['version']}`",
        f"- seed: `{m['seed']}`",
        f"- python: `{m['python_version']}` / platform: `{m['platform']}`",
        f"- command: `{m['command']}`",
        "",
        "## Overall",
        "",
        "| n | OSR | PAOSR | CVSR | VG | PAVG |",
        "|---:|---:|---:|---:|---:|---:|",
        f"| {overall['n']} | {overall['OSR']:.3f} | {overall['PAOSR']:.3f} | {overall['CVSR']:.3f} | {overall['VG']:.3f} | {overall['PAVG']:.3f} |",
        "",
        "## By family",
        "",
        "| Family | n | OSR | PAOSR | CVSR | VG | PAVG |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for family, rate in run.metrics.by_family.items():
        r = rate.to_dict()
        lines.append(f"| {family} | {r['n']} | {r['OSR']:.3f} | {r['PAOSR']:.3f} | {r['CVSR']:.3f} | {r['VG']:.3f} | {r['PAVG']:.3f} |")

    failing = [sid for sid, ev in run.evaluations.items() if not ev.commit_valid_success]
    if failing:
        lines += ["", "## Scenarios that failed CVSR", "", "| Scenario | OSR | PAOSR | CVSR | Failure codes |", "|---|---:|---:|---:|---|"]
        for sid in sorted(failing):
            ev = run.evaluations[sid]
            codes = ", ".join(ev.failure_codes) or "-"
            lines.append(f"| {sid} | {int(ev.outcome_success)} | {int(ev.policy_aware_outcome_success)} | {int(ev.commit_valid_success)} | {codes} |")

    return "\n".join(lines) + "\n"


def render_ablation_summary(runs: dict[str, "CompletedRun"], *, profile_order: tuple[str, ...]) -> str:
    lines = [
        "# CAV-Bench Controlled Architecture Ablation",
        "",
        _INTERPRETATION_NOTE,
        "",
        "## Overall results",
        "",
        "| Profile | OSR | PAOSR | CVSR | VG | PAVG |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for profile in profile_order:
        run = runs[profile]
        r = run.metrics.overall.to_dict()
        lines.append(f"| {profile} | {r['OSR']:.3f} | {r['PAOSR']:.3f} | {r['CVSR']:.3f} | {r['VG']:.3f} | {r['PAVG']:.3f} |")

    families = sorted({fam for run in runs.values() for fam in run.metrics.by_family})
    lines += ["", "## CVSR by family", "", "| Profile | " + " | ".join(families) + " |", "|---|" + "---:|" * len(families)]
    for profile in profile_order:
        run = runs[profile]
        cells = []
        for fam in families:
            rate = run.metrics.by_family.get(fam)
            cells.append(f"{rate.to_dict()['CVSR']:.3f}" if rate else "-")
        lines.append(f"| {profile} | " + " | ".join(cells) + " |")

    return "\n".join(lines) + "\n"
