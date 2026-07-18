"""The LangGraph integration must not open any self-grading path.

Adversarial requirement (AGENTS.md, docs/architecture.md): LangGraph state,
node output, graph completion, and adapter metadata may claim whatever they
like -- the evaluator follows only benchmark-controlled evidence: the
environment's canonical trace, authoritative state versions, and the
side-effect ledger.
"""

from __future__ import annotations

import inspect

import pytest

from cavbench.adapters import langgraph as langgraph_module
from cavbench.adapters import langgraph_reference
from cavbench.adapters.langgraph import LangGraphAdapter
from cavbench.runtime.environment import BenchmarkEnvironment
from cavbench.runtime.session import AdapterSession
from cavbench.runtime.tools import ToolFacade, ToolResult
from tests.helpers import ForgingAdapter, evaluate
from tests.langgraph.helpers import EVALUATOR, PACK, SCENARIO_IDS, events_of, run_reference_episode


def test_naive_graph_claims_success_but_evaluator_follows_stale_state_evidence() -> None:
    """FA-01 adversarial case: the graph's terminal state, node outputs, and
    normalized-event diagnostics all claim a clean success, and the
    conventional outcome check agrees -- but the environment's recorded
    versions prove the commit was stale, and the evaluator follows that."""
    trace, evaluation = run_reference_episode("FA-01", "naive")

    # The graph/adapter side genuinely claims success...
    assert trace.adapter_report["completion_status"] == "success"
    claimed = [e for e in trace.adapter_report["normalized_events"] if e["event_type"] == "effect_committed"]
    assert claimed, "the naive graph believes (and reports) that its effect committed cleanly"

    # ...and the outcome check passes; but benchmark evidence rules.
    assert evaluation.outcome_success is True
    assert evaluation.commit_valid_success is False
    assert evaluation.dimensions["temporal_state_validity"] == "fail"
    assert "TS_STALE_WITNESS" in evaluation.failure_codes


def test_naive_graph_claims_success_but_evaluator_follows_authority_evidence() -> None:
    """FA-04 adversarial case: the graph trusted its checkpointed
    planning-time authorization flag; the ledger shows a commit the current
    authority did not permit."""
    trace, evaluation = run_reference_episode("FA-04", "naive")

    assert trace.adapter_report["completion_status"] == "success"
    assert evaluation.outcome_success is True
    assert evaluation.policy_aware_outcome_success is False
    assert evaluation.commit_valid_success is False
    assert evaluation.dimensions["authority_validity"] == "fail"
    assert "AV_PRINCIPAL_NOT_AUTHORIZED" in evaluation.failure_codes


@pytest.mark.parametrize("scenario_id", SCENARIO_IDS)
def test_forged_trust_boundary_metadata_cannot_alter_evaluator_output(scenario_id: str) -> None:
    """Wrapping the naive adapter in ForgingAdapter (which smuggles
    commit_valid/cvsr/dimension claims into adapter_report metadata) must
    change nothing about the derived evaluation."""
    scenario = PACK.get(scenario_id)
    honest = evaluate(scenario, LangGraphAdapter(variant="naive"))
    forged = evaluate(scenario, ForgingAdapter(LangGraphAdapter(variant="naive")))

    assert forged.commit_valid_success == honest.commit_valid_success is False
    assert forged.outcome_success == honest.outcome_success
    assert forged.dimensions == honest.dimensions
    assert forged.failure_codes == honest.failure_codes


@pytest.mark.parametrize("scenario_id", SCENARIO_IDS)
@pytest.mark.parametrize("variant", ["guarded", "naive"])
def test_every_consequential_write_goes_through_the_tool_facade(scenario_id: str, variant: str) -> None:
    """Counts facade write() calls with a spy and matches them 1:1 against
    the environment's recorded attempts, and matches non-escalation ledger
    entries against writes the environment acknowledged as committed."""
    calls: list[str] = []

    class SpyFacade(ToolFacade):
        def write(self, **kwargs: object) -> ToolResult:
            result = super().write(**kwargs)  # type: ignore[arg-type]
            calls.append(result.status)
            return result

    scenario = PACK.get(scenario_id)
    adapter = LangGraphAdapter(variant=variant)
    env = BenchmarkEnvironment(scenario, seed=0, run_id=f"{scenario_id}-{variant}-spy")
    session = AdapterSession(scenario.view, SpyFacade(env))
    result = adapter.run(session)
    trace = env.finalize(
        {
            "adapter_name": adapter.name,
            "adapter_version": adapter.version,
            "final_message": result.final_message,
            "completion_status": result.completion_status,
        }
    )

    attempts = events_of(trace, "tool_call_attempt")
    assert len(attempts) == len(calls), "every recorded attempt must correspond to a facade write() call"
    committed_via_facade = sum(1 for status in calls if status in ("COMMITTED", "AMBIGUOUS"))
    non_escalation_effects = [e for e in trace.side_effects if e.get("effect_type") != "escalate_case"]
    assert len(non_escalation_effects) == committed_via_facade, (
        "every non-escalation ledger entry must come from a facade write the environment acknowledged"
    )


def test_state_mutations_match_recorded_commits_and_injected_mutations() -> None:
    """No hidden mutation path: for a run with real commits, every version
    change in final authoritative state is accounted for by a recorded
    side_effect_commit or a recorded (benchmark-owned) external_mutation."""
    trace, _ = run_reference_episode("FA-03", "guarded")
    recorded: dict[str, int] = {}
    for event in trace.events:
        if event.event_type in ("side_effect_commit", "external_mutation"):
            for ref, version in (event.versions_after or {}).items():
                recorded[ref] = max(recorded.get(ref, 0), version)
    scenario = PACK.get("FA-03")
    for namespace, resources in trace.final_state.items():
        for resource_id, value in resources.items():
            ref = f"{namespace}:{resource_id}"
            initial = scenario.initial_state[namespace][resource_id]["version"]
            final = value["version"]
            if final != initial:
                assert recorded.get(ref) == final, f"unexplained version change on {ref}"


def test_fixture_and_adapter_sources_never_touch_benchmark_internals() -> None:
    """Static guard: the integration code has no reference to the
    harness-owned components adapters must never touch directly."""
    for module in (langgraph_module, langgraph_reference):
        source = inspect.getsource(module)
        for forbidden in (
            "BenchmarkEnvironment(",
            "VersionedStateStore",
            "SideEffectLedger",
            "FaultScheduler",
            "ScenarioOracle",
            "._env",
            ".ledger",
            ".state.mutate",
        ):
            assert forbidden not in source, f"{module.__name__} must not reference {forbidden!r}"


def test_evaluator_output_is_identical_for_direct_trace_and_adapter_metadata_claims() -> None:
    """Belt-and-braces: evaluating the same benchmark-owned trace with the
    adapter_report stripped of all metadata yields the identical result --
    i.e. nothing the LangGraph side reports feeds the evaluation. (The one
    deliberate exception in the architecture is completion_status, which is
    only ever compared against a derived floor to catch overclaims.)"""
    trace, evaluation = run_reference_episode("FA-02", "naive")
    stripped = trace.__class__(
        **{
            **{f: getattr(trace, f) for f in trace.__dataclass_fields__},
            "adapter_report": {
                "completion_status": trace.adapter_report["completion_status"],
            },
        }
    )
    assert EVALUATOR.evaluate(PACK.get("FA-02"), stripped) == evaluation
