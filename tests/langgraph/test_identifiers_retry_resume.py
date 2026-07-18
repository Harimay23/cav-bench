"""Stable operation_id / idempotency_key behavior across retries and resumes.

The requirement (docs/langgraph-adapter-mapping.md, Issue #5): both
identifiers are derived from durable identity -- scenario, thread, and plan
step -- never freshly generated per attempt, so a LangGraph retry or a
checkpoint resume is recognizable to the environment as the *same* logical
operation.
"""

from __future__ import annotations

from langgraph.checkpoint.memory import InMemorySaver

from cavbench.adapters.langgraph_reference import build_reference_graph, derive_idempotency_key
from cavbench.runtime.environment import BenchmarkEnvironment
from cavbench.runtime.session import AdapterSession
from cavbench.runtime.tools import ToolFacade
from tests.langgraph.helpers import EVALUATOR, PACK, events_of, run_reference_episode

THREAD_ID = "resume-thread"


def _fa02_session() -> tuple[BenchmarkEnvironment, AdapterSession]:
    scenario = PACK.get("FA-02")
    env = BenchmarkEnvironment(scenario, seed=0, run_id="FA-02-resume-test")
    return env, AdapterSession(scenario.view, ToolFacade(env))


def _invoke_config(session: AdapterSession) -> dict:
    return {"configurable": {"thread_id": THREAD_ID, "cavbench_session": session}}


def test_identifier_derivation_is_a_pure_function_of_durable_identity() -> None:
    key = derive_idempotency_key("FA-02", THREAD_ID, "write-1")
    assert key == derive_idempotency_key("FA-02", THREAD_ID, "write-1"), "no per-invocation freshness"
    assert "attempt" not in key
    # Distinct durable identity -> distinct key.
    assert key != derive_idempotency_key("FA-02", THREAD_ID, "read-1")
    assert key != derive_idempotency_key("FA-02", "other-thread", "write-1")


def test_checkpoint_resume_reuses_the_same_identifiers_and_reconciles_before_writing() -> None:
    """Interrupts the FA-02 graph right after the (genuinely committed but
    ambiguously acknowledged) write, then resumes from the checkpoint with
    durability="sync". The resumed run must reconcile using the *same*
    idempotency key -- derived again from durable identity, not replayed
    from a per-attempt value -- and must not issue a second write."""
    env, session = _fa02_session()
    graph = build_reference_graph(
        PACK.get("FA-02").view, checkpointer=InMemorySaver(), interrupt_after=["commit_refund"]
    )
    config = _invoke_config(session)

    interrupted = graph.invoke({"user_request": session.scenario.user_request}, config=config, durability="sync")
    assert interrupted.get("ack_status") == "AMBIGUOUS"
    assert graph.get_state(config).next == ("reconcile",), "the graph must be paused before reconciliation"

    resumed = graph.invoke(None, config=config, durability="sync")
    assert resumed.get("completion_status") == "success"

    trace = env.finalize({"adapter_name": "langgraph", "adapter_version": "test", "completion_status": "success"})
    attempts = events_of(trace, "tool_call_attempt")
    status_reads = events_of(trace, "operation_status_read")
    commits = events_of(trace, "side_effect_commit")
    expected_key = derive_idempotency_key("FA-02", THREAD_ID, "write-1")

    assert len(attempts) == 1, "the resume must not re-execute the checkpointed write node"
    assert len(commits) == 1
    assert attempts[0].idempotency_key == expected_key
    assert attempts[0].logical_operation_id == "issue_refund:P-7002:30"
    assert [e.idempotency_key for e in status_reads] == [expected_key], (
        "reconciliation must reuse the exact key of the ambiguous write"
    )
    assert status_reads[0].seq > commits[0].seq

    evaluation = EVALUATOR.evaluate(PACK.get("FA-02"), trace)
    assert evaluation.commit_valid_success is True


def test_safe_replay_with_the_stable_key_is_deduplicated_not_recommitted() -> None:
    """Even if a resumed run *did* re-issue the write (e.g. resuming from a
    checkpoint taken before the write node), the stable key makes the replay
    safe: the environment answers IDEMPOTENT_REPLAY and the ledger does not
    grow."""
    env, session = _fa02_session()
    graph = build_reference_graph(PACK.get("FA-02").view, checkpointer=InMemorySaver())
    graph.invoke({"user_request": session.scenario.user_request}, config=_invoke_config(session), durability="sync")
    assert len(env.ledger.as_dicts()) == 1

    step = session.scenario.plan.step("write-1")
    replay = session.tools.write(
        step_id=step.step_id,
        tool_name=step.tool_name,
        namespace=step.namespace,
        resource_id=step.resource_id,
        changes=step.changes,
        args=step.args,
        logical_operation_id=step.logical_operation_id,
        idempotency_key=derive_idempotency_key("FA-02", THREAD_ID, "write-1"),
    )
    assert replay.status == "IDEMPOTENT_REPLAY"
    assert len(env.ledger.as_dicts()) == 1, "safe replay must not produce a duplicate committed effect"


def test_operation_id_stays_stable_across_retries_even_in_the_naive_variant() -> None:
    """The naive FA-02 variant retries under a *fresh idempotency key* (its
    deliberate bug) -- but the logical operation id still comes from the
    durable plan, which is exactly why the ledger can prove the two commits
    are the same logical operation duplicated."""
    trace, evaluation = run_reference_episode("FA-02", "naive")
    attempts = events_of(trace, "tool_call_attempt")
    assert len(attempts) == 2
    assert attempts[0].logical_operation_id == attempts[1].logical_operation_id
    assert attempts[0].idempotency_key != attempts[1].idempotency_key, "the naive bug: per-attempt keys"

    assert len(trace.side_effects) == 2
    assert "EI_DUPLICATE_LOGICAL_EFFECT" in evaluation.failure_codes
    assert evaluation.commit_valid_success is False


def test_ambiguous_acknowledgement_is_reconciled_before_any_possible_second_write() -> None:
    """In the guarded run, after the AMBIGUOUS acknowledgement the next
    operation against the environment is the status check -- never another
    write attempt."""
    trace, _ = run_reference_episode("FA-02", "guarded")
    attempts = events_of(trace, "tool_call_attempt")
    status_reads = events_of(trace, "operation_status_read")
    assert len(attempts) == 1 and len(status_reads) == 1
    later_attempts = [e for e in attempts if e.seq > status_reads[0].seq]
    assert later_attempts == [], "no write may precede reconciliation of the ambiguous acknowledgement"


def test_attempted_and_committed_evidence_remain_distinct() -> None:
    """tool_call_attempt (attempted) and side_effect_commit (committed) are
    separate benchmark-owned event types, and an attempt only pairs with a
    commit when the environment actually committed: FA-03's failed capture
    leaves an attempt with a commit_rejected, not a side_effect_commit."""
    trace, _ = run_reference_episode("FA-03", "guarded")
    attempts = events_of(trace, "tool_call_attempt")
    commits = events_of(trace, "side_effect_commit")
    rejected = events_of(trace, "commit_rejected")

    assert len(attempts) == 3  # reserve, capture (failed), release
    assert len(commits) == 2  # reserve, release
    assert len(rejected) == 1 and rejected[0].response_status == "FAILED"
    committed_ops = {e.logical_operation_id for e in commits}
    assert rejected[0].logical_operation_id == "capture_payment:P-7003"
    assert "capture_payment:P-7003" not in committed_ops
