"""Outcome-pass vs. commit-valid-fail, demonstrated through a real LangGraph runtime.

Runs the deterministic reference LangGraph graph (a test fixture, not a
production agent design) against scenario FA-01 from the `framework-v1`
pack, twice:

1. NAIVE control: reads the order, then commits the cancellation with no
   commit-time reread or revalidation. A conventional final-outcome check
   passes -- the goal predicate holds -- but the commit landed against state
   that changed after the read. CAV-Bench derives this from
   benchmark-controlled evidence (the versions the environment recorded at
   read time and at commit time), not from anything the graph reports.
2. GUARDED control: identical graph except for one added revalidation node
   that re-reads and re-evaluates the action's precondition, intent, scope,
   and authority immediately before commit -- and therefore refuses. The
   corrected run is commit-valid.

Both runs are deterministic and reproducible (run this file twice).

Requires the optional LangGraph extra:  pip install "cav-bench[langgraph]"
Run:  python examples/langgraph_adapter.py
"""

from __future__ import annotations

from cavbench.adapters.langgraph import LangGraphAdapter
from cavbench.evaluation.evaluator import DeterministicEvaluator
from cavbench.evaluation.results import EvaluationResult
from cavbench.runtime.environment import BenchmarkEnvironment
from cavbench.runtime.session import AdapterSession
from cavbench.runtime.tools import ToolFacade
from cavbench.scenarios.loader import load_builtin_pack

SCENARIO_ID = "FA-01"


def run_variant(variant: str) -> EvaluationResult:
    pack = load_builtin_pack("framework-v1")
    scenario = pack.get(SCENARIO_ID)
    adapter = LangGraphAdapter(variant=variant)
    env = BenchmarkEnvironment(scenario, seed=0, run_id=f"{SCENARIO_ID}-{variant}")
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
    return DeterministicEvaluator().evaluate(scenario, trace)


def main() -> None:
    naive = run_variant("naive")
    guarded = run_variant("guarded")

    print(f"Scenario {SCENARIO_ID}: the order ships between the read and the cancellation commit.\n")
    header = f"{'run':10s} {'outcome_success':>16s} {'commit_valid_success':>21s}  failure_codes"
    print(header)
    print("-" * len(header))
    for name, r in (("naive", naive), ("guarded", guarded)):
        print(f"{name:10s} {str(r.outcome_success):>16s} {str(r.commit_valid_success):>21s}  {list(r.failure_codes)}")

    print(
        "\nThe naive run looks successful to a final-outcome check (outcome_success=True)\n"
        "but committed against stale state; the evaluator derives TS_STALE_WITNESS from the\n"
        "versions the environment recorded, independent of anything the graph reported.\n"
        "The guarded run adds one commit-time revalidation node and becomes commit-valid."
    )

    assert naive.outcome_success and not naive.commit_valid_success
    assert "TS_STALE_WITNESS" in naive.failure_codes
    assert guarded.outcome_success and guarded.commit_valid_success

    # Determinism: repeating each run yields identical evaluator output.
    assert run_variant("naive") == naive
    assert run_variant("guarded") == guarded
    print("\nDeterminism check passed: repeated runs produce identical evaluations.")


if __name__ == "__main__":
    main()
