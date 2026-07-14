from __future__ import annotations

from cavbench.adapters.baselines import BASELINE_PROFILES
from cavbench.evaluation.evaluator import DeterministicEvaluator
from cavbench.runtime.trace import EpisodeTrace
from cavbench.scenarios.loader import load_builtin_pack
from tests.helpers import run_episode

PACK = load_builtin_pack("core-v1")


def test_replaying_a_serialized_trace_reproduces_the_original_evaluation() -> None:
    evaluator = DeterministicEvaluator()
    scenario = PACK.get("ER-06")
    adapter = BASELINE_PROFILES["full_lifecycle"]

    trace = run_episode(scenario, adapter, seed=0)
    original = evaluator.evaluate(scenario, trace)

    # Round-trip through JSON exactly as the CLI/report writer would.
    serialized = trace.to_dict()
    reloaded_trace = EpisodeTrace.from_dict(serialized)
    replayed = evaluator.evaluate(scenario, reloaded_trace)

    assert replayed.to_dict() == original.to_dict()
