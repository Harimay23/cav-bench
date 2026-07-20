"""Shared plumbing for the LangGraph runtime tests."""

from __future__ import annotations

from cavbench.evaluation.evaluator import DeterministicEvaluator
from cavbench.evaluation.results import EvaluationResult
from cavbench.runtime.environment import BenchmarkEnvironment
from cavbench.runtime.session import AdapterSession
from cavbench.runtime.tools import ToolFacade
from cavbench.runtime.trace import EpisodeTrace, TraceEvent
from cavbench.scenarios.loader import load_builtin_pack
from cavbench.scenarios.models import ScenarioDefinition

PACK = load_builtin_pack("framework-v1")
EVALUATOR = DeterministicEvaluator()
SCENARIO_IDS = ("FA-01", "FA-02", "FA-03", "FA-04")


def run_reference_episode(
    scenario_id: str, variant: str, *, seed: int = 0, run_id: str | None = None
) -> tuple[EpisodeTrace, EvaluationResult]:
    """Runs a framework-v1 scenario through LangGraphAdapter's reference
    graph and returns the benchmark-owned trace plus the independently
    derived evaluation."""
    from cavbench.adapters.langgraph import LangGraphAdapter

    scenario: ScenarioDefinition = PACK.get(scenario_id)
    adapter = LangGraphAdapter(variant=variant)
    env = BenchmarkEnvironment(scenario, seed=seed, run_id=run_id or f"{scenario_id}-{variant}-test")
    session = AdapterSession(scenario.view, ToolFacade(env))
    result = adapter.run(session)
    trace = env.finalize(
        {
            "adapter_name": adapter.name,
            "adapter_version": adapter.version,
            "final_message": result.final_message,
            "completion_status": result.completion_status,
            **{k: v for k, v in dict(result.metadata).items()},
        }
    )
    return trace, EVALUATOR.evaluate(scenario, trace)


def events_of(trace: EpisodeTrace, event_type: str) -> list[TraceEvent]:
    return [e for e in trace.events if e.event_type == event_type]
