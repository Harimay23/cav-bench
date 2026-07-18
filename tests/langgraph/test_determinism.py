"""Repeated LangGraph scenario runs must be bit-for-bit deterministic.

Same scenario, same variant, same seed, same run id => identical canonical
trace (every event, version, identifier) and identical evaluation. This is
what makes the outcome-pass vs. commit-valid-fail demonstration
reproducible rather than anecdotal.
"""

from __future__ import annotations

import pytest

from tests.langgraph.helpers import SCENARIO_IDS, run_reference_episode


@pytest.mark.parametrize("scenario_id", SCENARIO_IDS)
@pytest.mark.parametrize("variant", ["guarded", "naive"])
def test_repeated_runs_produce_identical_traces_and_evaluations(scenario_id: str, variant: str) -> None:
    run_id = f"{scenario_id}-{variant}-determinism"
    trace_a, evaluation_a = run_reference_episode(scenario_id, variant, run_id=run_id)
    trace_b, evaluation_b = run_reference_episode(scenario_id, variant, run_id=run_id)

    assert trace_a.to_dict() == trace_b.to_dict()
    assert evaluation_a == evaluation_b


def test_canonical_core_pack_is_untouched_by_the_langgraph_integration() -> None:
    """The framework-v1 pack and the LangGraph adapter must not perturb the
    canonical core-v1 corpus: its scenario ids and content digest are
    unchanged. (The full canonical ablation golden test runs in
    tests/golden/ regardless of whether langgraph is installed.)"""
    from cavbench.scenarios.loader import load_builtin_pack

    core = load_builtin_pack("core-v1")
    assert len(core) == 40
    assert not any(sid.startswith("FA-") for sid in core.scenario_ids)
