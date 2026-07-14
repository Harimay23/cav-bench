"""Shared test helpers: run a scenario through a real profile end to end."""

from __future__ import annotations

from cavbench.adapters.protocol import AdapterResult, ExecutionAdapter
from cavbench.evaluation.evaluator import DeterministicEvaluator
from cavbench.evaluation.results import EvaluationResult
from cavbench.runtime.environment import BenchmarkEnvironment
from cavbench.runtime.session import AdapterSession
from cavbench.runtime.tools import ToolFacade
from cavbench.runtime.trace import EpisodeTrace
from cavbench.scenarios.models import ScenarioDefinition

EVALUATOR = DeterministicEvaluator()


def run_episode(scenario: ScenarioDefinition, adapter: ExecutionAdapter, *, seed: int = 0) -> EpisodeTrace:
    env = BenchmarkEnvironment(scenario, seed=seed, run_id=f"{scenario.id}-{adapter.name}-test")
    tools = ToolFacade(env)
    session = AdapterSession(scenario.view, tools)
    result = adapter.run(session)
    adapter_report = {
        "adapter_name": adapter.name,
        "adapter_version": adapter.version,
        "final_message": result.final_message,
        "completion_status": result.completion_status,
        **{k: v for k, v in dict(result.metadata).items() if k not in ("adapter_name", "adapter_version")},
    }
    return env.finalize(adapter_report)


def evaluate(scenario: ScenarioDefinition, adapter: ExecutionAdapter, *, seed: int = 0) -> EvaluationResult:
    trace = run_episode(scenario, adapter, seed=seed)
    return EVALUATOR.evaluate(scenario, trace)


class ForgingAdapter:
    """Adversarial adapter: runs a real inner adapter, then tries to smuggle
    trust-boundary fields (pass/fail claims) into the trace via adapter_report
    metadata. Used to prove the evaluator ignores them.
    """

    def __init__(self, inner: ExecutionAdapter) -> None:
        self._inner = inner

    @property
    def name(self) -> str:
        return f"forging::{self._inner.name}"

    @property
    def version(self) -> str:
        return self._inner.version

    def run(self, session: AdapterSession) -> AdapterResult:
        result = self._inner.run(session)
        return AdapterResult(
            final_message=result.final_message,
            completion_status=result.completion_status,
            metadata={
                **dict(result.metadata),
                "commit_valid": True,
                "commit_valid_success": True,
                "cvsr": 1.0,
                "outcome_success": True,
                "policy_aware_outcome_success": True,
                "dimensions": {"intent_grounding": "pass", "authority_validity": "pass"},
                "failed_dimensions": [],
                "invalid_commits": [],
                "failure_codes": [],
            },
        )
