from __future__ import annotations

import pytest

from cavbench.adapters.baselines import BASELINE_PROFILES, CANONICAL_PROFILE_ORDER
from cavbench.evaluation.results import EvaluationResult
from cavbench.scenarios.loader import load_builtin_pack
from cavbench.scenarios.models import DIMENSIONS
from tests.helpers import evaluate, run_episode

PACK = load_builtin_pack("core-v1")


@pytest.mark.parametrize("scenario_id", PACK.scenario_ids)
@pytest.mark.parametrize("profile_name", CANONICAL_PROFILE_ORDER)
def test_every_scenario_runs_cleanly_through_every_profile(scenario_id: str, profile_name: str) -> None:
    scenario = PACK.get(scenario_id)
    result = evaluate(scenario, BASELINE_PROFILES[profile_name])
    assert isinstance(result, EvaluationResult)
    assert set(result.dimensions) == set(DIMENSIONS)
    assert all(v in ("pass", "fail", "not_applicable") for v in result.dimensions.values())
    # CVSR is non-compensatory: never valid when outcome failed or any
    # applicable dimension failed or an invalid commit was recorded.
    if result.commit_valid_success:
        assert result.outcome_success is True
        assert not result.invalid_commits
        assert all(v != "fail" for v in result.dimensions.values())


@pytest.mark.parametrize("scenario_id", ["ST-01", "IA-05", "ER-01", "ER-09"])
def test_same_scenario_profile_seed_reproduces_the_same_result(scenario_id: str) -> None:
    scenario = PACK.get(scenario_id)
    adapter = BASELINE_PROFILES["full_lifecycle"]
    first = evaluate(scenario, adapter, seed=7)
    second = evaluate(scenario, adapter, seed=7)
    assert first.to_dict() == second.to_dict()


def test_same_scenario_profile_seed_reproduces_the_same_trace_events() -> None:
    scenario = PACK.get("ER-04")
    adapter = BASELINE_PROFILES["full_lifecycle"]
    first = run_episode(scenario, adapter, seed=3)
    second = run_episode(scenario, adapter, seed=3)
    assert [e.to_dict() for e in first.events] == [e.to_dict() for e in second.events]
    assert first.final_state == second.final_state
