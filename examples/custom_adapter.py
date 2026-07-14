"""A minimal custom execution adapter, runnable without modifying anything
in cavbench itself.

Run: python examples/custom_adapter.py
"""

from __future__ import annotations

from cavbench.adapters.protocol import AdapterResult
from cavbench.evaluation.evaluator import DeterministicEvaluator
from cavbench.runtime.environment import BenchmarkEnvironment
from cavbench.runtime.session import AdapterSession
from cavbench.runtime.tools import ToolFacade
from cavbench.scenarios.loader import load_builtin_pack


class AlwaysEscalateAdapter:
    """Never attempts a write; always escalates for human review instead.

    This demonstrates the minimum an ExecutionAdapter needs to implement --
    it doesn't use the shared baseline engine at all.
    """

    name = "always_escalate"
    version = "0.1.0"

    def run(self, session: AdapterSession) -> AdapterResult:
        session.escalate("custom adapter always escalates for review")
        return AdapterResult(
            final_message="This request has been escalated for manual review.",
            completion_status="pending_recovery",
        )


def main() -> None:
    pack = load_builtin_pack("core-v1")
    adapter = AlwaysEscalateAdapter()
    evaluator = DeterministicEvaluator()

    scenario = pack.get("HP-01")
    env = BenchmarkEnvironment(scenario, seed=0, run_id=f"{scenario.id}-{adapter.name}")
    session = AdapterSession(scenario.view, ToolFacade(env))
    result = adapter.run(session)
    trace = env.finalize(
        {
            "adapter_name": adapter.name,
            "adapter_version": adapter.version,
            "final_message": result.final_message,
            "completion_status": result.completion_status,
        }
    )
    evaluation = evaluator.evaluate(scenario, trace)
    print(
        f"{scenario.id}: outcome_success={evaluation.outcome_success} "
        f"commit_valid_success={evaluation.commit_valid_success}"
    )
    print("(Expected: both False -- the order was never cancelled, so the goal predicate does not hold.)")


if __name__ == "__main__":
    main()
