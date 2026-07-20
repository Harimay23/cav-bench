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
from cavbench.runtime.tools import ToolFacade, ToolResult
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
    from a per-attempt value -- and must not issue a second write.

    The guarded write node reconciles twice in this run, both times with
    the identical key: once pre-write (NOT_FOUND, since nothing had
    committed yet) before the one real write, and once post-AMBIGUOUS
    (COMMITTED, found by the separate reconcile node) after resume."""
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
    assert [e.idempotency_key for e in status_reads] == [expected_key, expected_key], (
        "both the pre-write and post-AMBIGUOUS reconciliations must reuse the exact key of the write"
    )
    assert status_reads[0].response_status == "NOT_FOUND", "pre-write: nothing had committed yet"
    assert status_reads[1].response_status == "COMMITTED", "post-AMBIGUOUS: the write's own commit, now confirmed"
    assert status_reads[0].seq < attempts[0].seq <= commits[0].seq < status_reads[1].seq, (
        "pre-write reconciliation must precede the write, and post-AMBIGUOUS reconciliation must follow the commit"
    )

    evaluation = EVALUATOR.evaluate(PACK.get("FA-02"), trace)
    assert evaluation.commit_valid_success is True


def test_resume_from_pre_write_checkpoint_reconciles_hidden_prior_commit_before_reissuing() -> None:
    """Models the interleaving a separate preceding reconciliation node
    cannot catch: the checkpoint is taken *before* commit_refund ever
    runs, the external effect commits during what would have been
    commit_refund's own execution, but that execution's result is lost
    before LangGraph can checkpoint it (simulated here by committing
    directly through the tool facade, bypassing the graph entirely, then
    resuming from the pre-write checkpoint as if commit_refund's own
    invocation had never returned). The resumed commit_refund invocation
    must reconcile via its own pre-write status check before ever
    reissuing the write -- not rely on a separate node that will never run
    again on this resume."""
    env, session = _fa02_session()
    graph = build_reference_graph(
        PACK.get("FA-02").view, checkpointer=InMemorySaver(), interrupt_after=["read_state"]
    )
    config = _invoke_config(session)

    interrupted = graph.invoke({"user_request": session.scenario.user_request}, config=config, durability="sync")
    assert graph.get_state(config).next == ("commit_refund",), (
        "the checkpoint must precede commit_refund entirely -- it has no knowledge a write was ever attempted"
    )
    assert interrupted.get("ack_status") is None, "commit_refund has not run yet"

    # Simulate commit_refund's own (never-checkpointed) execution: the
    # external effect commits, but the fault mode returns AMBIGUOUS and
    # nothing about this call is written into LangGraph state.
    step = session.scenario.plan.step("write-1")
    idempotency_key = derive_idempotency_key("FA-02", THREAD_ID, "write-1")
    hidden_write = session.tools.write(
        step_id=step.step_id,
        tool_name=step.tool_name,
        namespace=step.namespace,
        resource_id=step.resource_id,
        changes=step.changes,
        args=step.args,
        logical_operation_id=step.logical_operation_id,
        idempotency_key=idempotency_key,
    )
    assert hidden_write.status == "AMBIGUOUS", "FA-02's injected fault must fire on this first write"
    assert len(env.ledger.as_dicts()) == 1, "the hidden write must have genuinely committed"

    resumed = graph.invoke(None, config=config, durability="sync")
    assert resumed.get("completion_status") == "success"

    normalized_events = resumed.get("normalized_events", [])
    trace = env.finalize(
        {
            "adapter_name": "langgraph",
            "adapter_version": "test",
            "completion_status": "success",
            "normalized_events": normalized_events,
        }
    )
    attempts = events_of(trace, "tool_call_attempt")
    commits = events_of(trace, "side_effect_commit")
    status_reads = events_of(trace, "operation_status_read")
    committed_diagnostics = [e for e in normalized_events if e["event_type"] == "effect_committed"]
    reconciled_diagnostics = [e for e in normalized_events if e["event_type"] == "effect_reconciled"]

    assert len(attempts) == 1, "only the hidden write attempted anything -- the resume must not reissue it"
    assert len(commits) == 1, "no duplicate commit"
    assert len(status_reads) == 1, "exactly one reconciliation: commit_refund's own pre-write status check"
    assert status_reads[0].idempotency_key == idempotency_key
    assert status_reads[0].seq > commits[0].seq, (
        "the status check must observe the hidden commit, which happened before the resume"
    )
    assert committed_diagnostics == [], (
        "no effect_committed diagnostic may be fabricated for a write the resumed invocation never issued"
    )
    assert reconciled_diagnostics and reconciled_diagnostics[-1]["status"] == "COMMITTED", (
        "the resumed invocation's pre-write reconciliation must observe and report the hidden commit"
    )

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
    """In the guarded run, the write node reconciles twice: once before the
    write (NOT_FOUND, nothing committed yet -- safe to proceed) and once
    after the AMBIGUOUS acknowledgement (COMMITTED, confirming the write
    that just happened). Never another write attempt after either check."""
    trace, _ = run_reference_episode("FA-02", "guarded")
    attempts = events_of(trace, "tool_call_attempt")
    status_reads = events_of(trace, "operation_status_read")
    assert len(attempts) == 1
    assert [e.response_status for e in status_reads] == ["NOT_FOUND", "COMMITTED"]
    later_attempts = [e for e in attempts if e.seq > status_reads[-1].seq]
    assert later_attempts == [], "no write may follow reconciliation of the ambiguous acknowledgement"
    earlier_attempts = [e for e in attempts if e.seq < status_reads[0].seq]
    assert earlier_attempts == [], "the pre-write reconciliation must precede the one write attempt"


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


class _ForcedIdempotentReplayFacade(ToolFacade):
    """Forces the one write for ``force_replay_key`` to report
    IDEMPOTENT_REPLAY and scripts the surrounding status_check calls to
    match, so the guarded write node's control-flow response to
    IDEMPOTENT_REPLAY can be tested directly. The deterministic FA-02
    fixture cannot naturally reach precheck=NOT_FOUND immediately followed
    by write=IDEMPOTENT_REPLAY for the same key now that the pre-write
    reconciliation closes that TOCTOU gap -- this proves the routing is
    correct regardless of how that response was reached."""

    def __init__(self, env: BenchmarkEnvironment, *, force_replay_key: str) -> None:
        super().__init__(env)
        self._force_replay_key = force_replay_key
        self._write_forced = False

    def write(self, **kwargs: object) -> ToolResult:
        if kwargs.get("idempotency_key") == self._force_replay_key and not self._write_forced:
            self._write_forced = True
            return ToolResult(status="IDEMPOTENT_REPLAY", operation_id=kwargs.get("logical_operation_id"))
        return super().write(**kwargs)  # type: ignore[arg-type]

    def status_check(self, *, idempotency_key: str) -> ToolResult:
        if idempotency_key == self._force_replay_key:
            found = self._write_forced
            return ToolResult(status="COMMITTED" if found else "NOT_FOUND", data={"found": found})
        return super().status_check(idempotency_key=idempotency_key)


def test_idempotent_replay_requires_explicit_reconciliation_not_direct_confirmation() -> None:
    """status_check -> NOT_FOUND, write -> IDEMPOTENT_REPLAY, status_check
    -> COMMITTED, confirm. The graph must not confirm immediately after
    IDEMPOTENT_REPLAY: an explicit second status check must occur, and no
    effect_committed normalized event may be emitted for the
    IDEMPOTENT_REPLAY write itself."""
    scenario = PACK.get("FA-02")
    env = BenchmarkEnvironment(scenario, seed=0, run_id="FA-02-idempotent-replay-test")
    idempotency_key = derive_idempotency_key("FA-02", THREAD_ID, "write-1")
    session = AdapterSession(scenario.view, _ForcedIdempotentReplayFacade(env, force_replay_key=idempotency_key))
    graph = build_reference_graph(scenario.view, checkpointer=InMemorySaver())

    final_state = graph.invoke(
        {"user_request": session.scenario.user_request}, config=_invoke_config(session), durability="sync"
    )
    assert final_state.get("completion_status") == "success"

    normalized = final_state.get("normalized_events", [])
    reconciled = [e for e in normalized if e["event_type"] == "effect_reconciled"]
    committed = [e for e in normalized if e["event_type"] == "effect_committed"]
    attempted = [e for e in normalized if e["event_type"] == "effect_attempted"]

    assert [e["status"] for e in reconciled] == ["NOT_FOUND", "COMMITTED"], (
        "pre-write NOT_FOUND, then an explicit second status check after IDEMPOTENT_REPLAY -- "
        "the graph must not treat IDEMPOTENT_REPLAY as direct confirmation"
    )
    assert [e["status"] for e in attempted] == ["IDEMPOTENT_REPLAY"]
    assert committed == [], "no effect_committed diagnostic may be emitted for an IDEMPOTENT_REPLAY write"

    # Ordering: reconcile(NOT_FOUND) < attempt(IDEMPOTENT_REPLAY) < reconcile(COMMITTED) < outcome.
    event_order = [e["event_type"] for e in normalized]
    assert event_order.index("effect_reconciled") < event_order.index("effect_attempted")
    assert event_order.count("effect_reconciled") == 2
    first_reconcile_idx = event_order.index("effect_reconciled")
    second_reconcile_idx = event_order.index("effect_reconciled", first_reconcile_idx + 1)
    assert event_order.index("effect_attempted") < second_reconcile_idx
    assert second_reconcile_idx < event_order.index("outcome_reported")
