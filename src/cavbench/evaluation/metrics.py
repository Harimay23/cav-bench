"""Metrics aggregation: OSR, PAOSR, CVSR, VG, PAVG, overall and by family."""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Iterable

from cavbench.evaluation.results import EvaluationResult, MetricSummary, RateSummary
from cavbench.scenarios.models import ScenarioDefinition


def _rates(counter: Counter) -> RateSummary:
    n = counter["n"]
    if n == 0:
        return RateSummary(n=0, osr=0.0, paosr=0.0, cvsr=0.0, vg=0.0, pavg=0.0)
    osr = counter["outcome_success"] / n
    paosr = counter["policy_aware_outcome_success"] / n
    cvsr = counter["commit_valid_success"] / n
    return RateSummary(n=n, osr=osr, paosr=paosr, cvsr=cvsr, vg=osr - cvsr, pavg=paosr - cvsr)


def aggregate(rows: Iterable[tuple[ScenarioDefinition, EvaluationResult]]) -> MetricSummary:
    totals: Counter = Counter()
    by_family: dict[str, Counter] = defaultdict(Counter)
    for scenario, result in rows:
        totals["n"] += 1
        family_counter = by_family[scenario.family]
        family_counter["n"] += 1
        for key in ("outcome_success", "policy_aware_outcome_success", "commit_valid_success"):
            value = int(getattr(result, key))
            totals[key] += value
            family_counter[key] += value

    return MetricSummary(
        overall=_rates(totals),
        by_family={family: _rates(counter) for family, counter in sorted(by_family.items())},
    )
