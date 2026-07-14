from __future__ import annotations

from cavbench.evaluation.metrics import aggregate
from cavbench.evaluation.results import EvaluationResult
from cavbench.scenarios.loader import load_builtin_pack

PACK = load_builtin_pack("core-v1")


def make_result(scenario_id: str, *, osr: bool, paosr: bool, cvsr: bool) -> EvaluationResult:
    return EvaluationResult(
        scenario_id=scenario_id,
        outcome_success=osr,
        policy_aware_outcome_success=paosr,
        commit_valid_success=cvsr,
        dimensions={},
    )


def test_aggregate_overall_rates() -> None:
    rows = [
        (PACK.get("HP-01"), make_result("HP-01", osr=True, paosr=True, cvsr=True)),
        (PACK.get("HP-02"), make_result("HP-02", osr=True, paosr=False, cvsr=False)),
    ]
    summary = aggregate(rows)
    assert summary.overall.n == 2
    assert summary.overall.osr == 1.0
    assert summary.overall.paosr == 0.5
    assert summary.overall.cvsr == 0.5
    assert summary.overall.vg == 0.5
    assert summary.overall.pavg == 0.0


def test_aggregate_by_family() -> None:
    rows = [
        (PACK.get("HP-01"), make_result("HP-01", osr=True, paosr=True, cvsr=True)),
        (PACK.get("ST-01"), make_result("ST-01", osr=True, paosr=True, cvsr=False)),
    ]
    summary = aggregate(rows)
    assert summary.by_family["stable_happy_path"].cvsr == 1.0
    assert summary.by_family["state_mutation"].cvsr == 0.0
