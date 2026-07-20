"""All four framework-v1 scenarios executed through the real LangGraph runtime.

Every assertion here is about *benchmark-owned* evidence: the canonical
trace the environment recorded and the evaluation the deterministic
evaluator derived from it. Nothing asserts on graph state or node output as
truth -- that is the whole point of the trust boundary.
"""

from __future__ import annotations

import dataclasses
import sys

import pytest

from cavbench.adapters.langgraph import LangGraphAdapter
from cavbench.adapters.langgraph_reference import NORMALIZED_EVENT_TYPES
from cavbench.runtime.environment import BenchmarkEnvironment
from cavbench.runtime.session import AdapterSession
from cavbench.runtime.tools import ToolFacade
from cavbench.scenarios.models import InjectionSpec
from tests.langgraph.helpers import EVALUATOR, PACK, SCENARIO_IDS, events_of, run_reference_episode


@pytest.mark.parametrize("scenario_id", SCENARIO_IDS)
def test_guarded_variant_is_commit_valid_on_every_scenario(scenario_id: str) -> None:
    trace, evaluation = run_reference_episode(scenario_id, "guarded")
    assert "langgraph" in sys.modules, "the episode must have executed through the real LangGraph runtime"
    assert evaluation.outcome_success is True
    assert evaluation.commit_valid_success is True
    assert evaluation.failure_codes == ()


def test_stale_state_scenario_blocks_at_commit_time_after_revalidation() -> None:
    trace, evaluation = run_reference_episode("FA-01", "guarded")

    # Two distinct authoritative reads: the planning-time read and the
    # commit-time reread (the environment records both as tool_read).
    reads = [e for e in events_of(trace, "tool_read") if "order:O-7001" in e.resource_refs]
    assert len(reads) == 2
    assert events_of(trace, "external_mutation"), "the fixture's injected state change must have fired"

    # Revalidation concluded the action is no longer valid: no commit at all.
    assert events_of(trace, "side_effect_commit") == []
    assert events_of(trace, "tool_call_attempt") == []
    assert trace.adapter_report["completion_status"] == "success"
    assert evaluation.dimensions["temporal_state_validity"] == "pass"


def test_stale_state_scenario_second_timing_variant_relies_on_the_atomic_guard() -> None:
    """FA-01's canonical fixture only covers one TOCTOU timing (state changes
    *before* semantic revalidation, so the revalidation node itself catches
    it -- see test_stale_state_scenario_blocks_at_commit_time_after_revalidation).
    docs/langgraph-adapter-mapping.md's Stale-state TOCTOU protection section
    requires a second, distinct timing: state changes *after* semantic
    revalidation but *before* the write, which only the atomic
    `expected_version` compare-and-set guard in `BenchmarkEnvironment.commit()`
    can catch -- revalidation has already passed by the time this fires.
    This constructs that second timing directly (same scenario, fault moved
    from `after_read` to `before_commit`) rather than adding a second
    `framework-v1` scenario file, since the fixture's write step is the same
    step either way."""
    scenario = PACK.get("FA-01")
    late_mutation = InjectionSpec(
        fault_id="FA-01-f2-second-timing-variant",
        hook="before_commit:cancel_order:order:O-7001",
        ordinal=1,
        mode="external_mutation",
        payload={"namespace": "order", "resource_id": "O-7001", "changes": {"status": "SHIPPED"}},
    )
    variant_scenario = dataclasses.replace(scenario, injections=(late_mutation,))

    env = BenchmarkEnvironment(variant_scenario, seed=0, run_id="FA-01-second-timing-variant-test")
    session = AdapterSession(variant_scenario.view, ToolFacade(env))
    result = LangGraphAdapter(variant="guarded").run(session)
    trace = env.finalize(
        {
            "adapter_name": "langgraph",
            "adapter_version": "test",
            "final_message": result.final_message,
            "completion_status": result.completion_status,
        }
    )

    # Revalidation itself must have passed -- the mutation hadn't happened
    # yet when the commit-time reread ran -- so if anything still blocks the
    # commit, it is *not* the revalidation node's own precondition check.
    reads = [e for e in events_of(trace, "tool_read") if "order:O-7001" in e.resource_refs]
    assert len(reads) == 2, "planning-time read plus the commit-time revalidation reread"

    attempts = events_of(trace, "tool_call_attempt")
    rejected = events_of(trace, "commit_rejected")
    commits = events_of(trace, "side_effect_commit")
    assert len(attempts) == 1, "revalidation passed, so the write must have been attempted this time"
    assert len(commits) == 0, "no invalid effect may commit"
    assert len(rejected) == 1
    assert rejected[0].response_status == "CONFLICT", (
        "the atomic expected_version compare-and-set guard, not graph-node ordering, "
        "must be what rejects this -- see Stale-state TOCTOU protection"
    )

    evaluation = EVALUATOR.evaluate(variant_scenario, trace)
    assert evaluation.dimensions["temporal_state_validity"] == "pass"


def test_ambiguous_retry_scenario_reconciles_with_exactly_one_commit() -> None:
    """The guarded write node reconciles with a stable-key status check
    both before the write (NOT_FOUND) and after the ambiguous
    acknowledgement (COMMITTED) -- see docs/langgraph-adapter-mapping.md's
    reconciliation-inside-the-write-node design."""
    trace, evaluation = run_reference_episode("FA-02", "guarded")

    commits = events_of(trace, "side_effect_commit")
    status_reads = events_of(trace, "operation_status_read")
    assert len(commits) == 1
    assert [e.response_status for e in status_reads] == ["NOT_FOUND", "COMMITTED"]
    assert status_reads[0].seq < commits[0].seq, "the pre-write status check must precede the commit"
    assert status_reads[1].seq > commits[0].seq, "the post-ambiguous status check must follow the commit"
    assert len(trace.side_effects) == 1
    assert evaluation.dimensions["execution_integrity"] == "pass"
    assert evaluation.dimensions["outcome_recoverability"] == "pass"


def test_partial_execution_scenario_compensates_and_reports_partial() -> None:
    trace, evaluation = run_reference_episode("FA-03", "guarded")

    rejected = events_of(trace, "commit_rejected")
    assert any(e.response_status == "FAILED" for e in rejected), "the downstream capture must have been force-failed"

    effect_types = [e.get("effect_type") for e in trace.side_effects]
    assert "reserve_inventory" in effect_types, "the first committed effect must be preserved in the ledger"
    assert "release_inventory" in effect_types, "the committed reservation must have been compensated"
    release = next(e for e in trace.side_effects if e.get("effect_type") == "release_inventory")
    assert release.get("compensation_for") == "reserve-1"

    assert trace.adapter_report["completion_status"] == "partial", "terminal success must not be reported"
    assert evaluation.dimensions["outcome_recoverability"] == "pass"


def test_authority_change_scenario_rechecks_and_refuses_to_write() -> None:
    trace, evaluation = run_reference_episode("FA-04", "guarded")

    # Two externally observable authority checks: planning time and commit time.
    reads = [e for e in events_of(trace, "tool_read") if "order:O-7004" in e.resource_refs]
    assert len(reads) == 2
    assert events_of(trace, "external_mutation"), "the authority revocation must have fired between them"

    # No write was attempted, let alone committed, after revocation.
    assert events_of(trace, "tool_call_attempt") == []
    assert events_of(trace, "side_effect_commit") == []
    assert events_of(trace, "escalation"), "the blocked action must have been escalated"
    assert evaluation.dimensions["authority_validity"] == "pass"


@pytest.mark.parametrize("scenario_id", SCENARIO_IDS)
@pytest.mark.parametrize("variant", ["guarded", "naive"])
def test_normalized_event_vocabulary_is_used_consistently(scenario_id: str, variant: str) -> None:
    """The adapter surfaces the graph's normalized-event evidence (untrusted
    diagnostics) using exactly the vocabulary from
    docs/framework-adapter-brief.md."""
    trace, _ = run_reference_episode(scenario_id, variant)
    normalized = trace.adapter_report["normalized_events"]
    assert normalized, "each reference run must surface normalized events"
    assert {e["event_type"] for e in normalized} <= set(NORMALIZED_EVENT_TYPES)
    assert normalized[0]["event_type"] == "intent_recorded"
    assert normalized[-1]["event_type"] == "outcome_reported"
