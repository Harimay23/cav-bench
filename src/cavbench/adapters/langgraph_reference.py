"""Deterministic reference LangGraph graphs for the `framework-v1` scenarios.

**These graphs are test fixtures, not a recommended production agent
architecture.** They exist to demonstrate, end to end, that the mapping in
``docs/langgraph-adapter-mapping.md`` works against a real LangGraph
runtime: fine-grained nodes (one logical consequential step per node),
synchronous checkpoint durability, stable operation/idempotency identifiers
across retries and resumes, and the normalized CAV-Bench event vocabulary.

Trust boundary (``docs/architecture.md``): every consequential effect below
goes through ``session.tools`` (the CAV-Bench ``ToolFacade``) -- the graphs
never touch ``BenchmarkEnvironment``, the state store, or the ledger.
LangGraph state and checkpoints are used only as ordering/retry/resume
context and as untrusted diagnostic evidence; nothing a node writes into
graph state can influence the evaluator.

Each scenario has two variants:

- ``GUARDED``: the corrected control -- commit-time revalidation, stable-key
  reconciliation, compensation routing, and a commit-time authority recheck.
- ``NAIVE``: the flawed control -- it trusts planning-time observations and
  internal flags, retries under fresh identifiers, and reports success
  regardless. It exists so tests (and the runnable example) can show
  CAV-Bench detecting invalid commits that a conventional final-outcome
  check misses. It is intentionally wrong; do not copy it.

LangGraph is an optional dependency: importing this module never imports
``langgraph``. Imports happen lazily inside :func:`build_reference_graph`
and, at execution time, inside the running nodes (via
``langgraph.config.get_config``, which is how nodes reach the CAV-Bench
session the adapter placed in the run's configurable context).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, TypedDict, cast

from cavbench.evaluation.predicates import evaluate as evaluate_predicate
from cavbench.runtime.session import AdapterSession
from cavbench.scenarios.models import JSONValue, PlannedStep, ScenarioView

GUARDED = "guarded"
NAIVE = "naive"
VARIANTS = (GUARDED, NAIVE)

SUPPORTED_SCENARIO_IDS = ("FA-01", "FA-02", "FA-03", "FA-04")

# The normalized event vocabulary from docs/framework-adapter-brief.md.
# Nodes record these into graph state as *untrusted diagnostic evidence* of
# the mapping; the evaluator never reads them.
NORMALIZED_EVENT_TYPES = (
    "intent_recorded",
    "authority_checked",
    "state_read",
    "state_revalidated",
    "effect_attempted",
    "effect_committed",
    "effect_reconciled",
    "compensation_started",
    "compensation_completed",
    "escalation_created",
    "outcome_reported",
)

_MAX_COMMIT_ATTEMPTS = 3


class FixtureState(TypedDict, total=False):
    """Checkpointed graph state: plain JSON-serializable values only.

    Holds ordering/retry/resume context and diagnostic evidence -- never
    commit truth. Commit truth is whatever ``BenchmarkEnvironment`` recorded.
    """

    user_request: str
    normalized_events: list[dict[str, JSONValue]]
    observed: dict[str, dict[str, JSONValue]]
    revalidation_ok: bool
    block_reason: str
    authorized_at_plan: bool
    authorized_at_commit: bool
    ack_status: str
    commit_attempts: int
    reconciled_status: str
    reserve_status: str
    capture_status: str
    compensation_status: str
    completion_status: str
    final_message: str


# -- run-context plumbing ----------------------------------------------------


def _configurable() -> Mapping[str, Any]:
    """The current run's configurable context, from inside a running node.

    ``get_config()`` is LangGraph's own accessor for the config the graph
    was invoked with; the adapter places the CAV-Bench session and the
    durable thread id there. Imported lazily: this only ever executes while
    a graph is running, i.e. with LangGraph installed.
    """
    from langgraph.config import get_config

    return cast("Mapping[str, Any]", get_config().get("configurable", {}))


def _session() -> AdapterSession:
    return cast(AdapterSession, _configurable()["cavbench_session"])


def _scenario() -> ScenarioView:
    return _session().scenario


def _thread_id() -> str:
    return str(_configurable()["thread_id"])


def derive_idempotency_key(scenario_id: str, thread_id: str, step_id: str) -> str:
    """Pure derivation of a step's idempotency key from durable identity:
    the scenario, the LangGraph thread, and the plan step (which maps 1:1 to
    a graph node). A retry of the same logical operation, or a resume from a
    checkpoint, always reproduces the same key. Nothing is per-attempt."""
    return f"lg:{scenario_id}:{thread_id}:{step_id}"


def stable_identifiers(step: PlannedStep) -> tuple[str, str]:
    """The (logical_operation_id, idempotency_key) pair for a step, from
    inside a running node. The operation id comes from the scenario plan
    (durable); the key from :func:`derive_idempotency_key`."""
    assert step.logical_operation_id is not None
    return step.logical_operation_id, derive_idempotency_key(_scenario().id, _thread_id(), step.step_id)


def _events(state: FixtureState, *entries: Mapping[str, JSONValue]) -> list[dict[str, JSONValue]]:
    return [*state.get("normalized_events", []), *(dict(e) for e in entries)]


def _ref(step: PlannedStep) -> str:
    return f"{step.namespace}:{step.resource_id}"


def _observed_for(state: FixtureState, step: PlannedStep) -> dict[str, JSONValue]:
    return state.get("observed", {}).get(_ref(step), {})


def _observed_version(state: FixtureState, step: PlannedStep) -> int | None:
    return cast("int | None", _observed_for(state, step).get("version"))


def _read_step(state: FixtureState, step: PlannedStep, *, event_type: str) -> FixtureState:
    """Reads a resource through the tool facade and records the observation."""
    assert step.namespace is not None and step.resource_id is not None
    result = _session().tools.read(step.namespace, step.resource_id)
    assert result.data is not None
    observed = {**state.get("observed", {}), _ref(step): dict(result.data)}
    return {
        "observed": observed,
        "normalized_events": _events(
            state,
            {
                "event_type": event_type,
                "resource_id": step.resource_id,
                "observed_version": result.data.get("version"),
                "status": result.status,
            },
        ),
    }


# -- shared checks (the action's preconditions, intent, scope, authority) ----


def _authority_holds(observed: Mapping[str, JSONValue]) -> bool:
    principal = _scenario().principal
    owner = observed.get("owner")
    if owner is not None and owner != "self":
        return False
    tenant = observed.get("tenant")
    if tenant is not None and tenant != principal.tenant_id:
        return False
    return True


def _action_still_valid(observed: Mapping[str, JSONValue], step: PlannedStep) -> tuple[bool, str]:
    """Full commit-time re-evaluation: precondition, intent, scope, authority.

    This is what "revalidate" means -- not merely re-reading the newest
    version and proceeding (docs/langgraph-adapter-mapping.md).
    """
    policy = _scenario().policy
    if step.precondition is not None and not evaluate_predicate(step.precondition, dict(observed)):
        return False, "precondition_no_longer_holds"
    if step.action_category and policy.requested_intent and step.action_category not in policy.requested_intent:
        return False, "intent_mismatch"
    max_amount = policy.allowed_scope.get("max_amount")
    if step.action_amount is not None and max_amount is not None and step.action_amount > max_amount:
        return False, "scope_violation"
    if not _authority_holds(observed):
        return False, "authority_revoked"
    return True, ""


def _write_step(
    state: FixtureState,
    step: PlannedStep,
    *,
    expected_version: int | None,
    idempotency_key: str,
    compensation_for: str | None = None,
) -> tuple[str, FixtureState]:
    """Issues one consequential write through the tool facade.

    The returned status is the environment's own response
    (COMMITTED/CONFLICT/AMBIGUOUS/IDEMPOTENT_REPLAY/FAILED) -- the only
    admissible attempted-vs-committed evidence. A node's control flow having
    "succeeded" proves nothing about whether an effect committed.
    """
    assert step.namespace is not None and step.resource_id is not None
    assert step.tool_name is not None and step.logical_operation_id is not None
    result = _session().tools.write(
        step_id=step.step_id,
        tool_name=step.tool_name,
        namespace=step.namespace,
        resource_id=step.resource_id,
        changes=step.changes,
        args=step.args,
        logical_operation_id=step.logical_operation_id,
        idempotency_key=idempotency_key,
        expected_version=expected_version,
        compensation_for=compensation_for,
    )
    entries: list[dict[str, JSONValue]] = [
        {
            "event_type": "effect_attempted",
            "operation_id": step.logical_operation_id,
            "resource_id": step.resource_id,
            "expected_version": expected_version,
            "status": result.status,
        }
    ]
    if result.status in ("COMMITTED", "IDEMPOTENT_REPLAY"):
        entries.append(
            {
                "event_type": "effect_committed",
                "operation_id": step.logical_operation_id,
                "resource_id": step.resource_id,
                "status": result.status,
            }
        )
    return result.status, {"normalized_events": _events(state, *entries)}


# -- shared nodes -----------------------------------------------------------


def record_intent(state: FixtureState) -> FixtureState:
    scenario = _scenario()
    return {
        "user_request": scenario.user_request,
        "normalized_events": _events(
            state,
            {"event_type": "intent_recorded", "status": "OK", "request": scenario.user_request},
        ),
    }


def finalize_report(state: FixtureState) -> FixtureState:
    status = state.get("completion_status", "partial")
    return {
        "completion_status": status,
        "normalized_events": _events(state, {"event_type": "outcome_reported", "status": status}),
    }


# -- FA-01: stale state before commit ---------------------------------------


def fa01_read_state(state: FixtureState) -> FixtureState:
    return _read_step(state, _scenario().plan.step("read-1"), event_type="state_read")


def fa01_revalidate(state: FixtureState) -> FixtureState:
    """Distinct commit-time reread plus full re-evaluation of the action."""
    step = _scenario().plan.step("write-1")
    update = _read_step(state, step, event_type="state_revalidated")
    observed = update["observed"][_ref(step)]
    ok, reason = _action_still_valid(observed, step)
    update["revalidation_ok"] = ok
    update["block_reason"] = reason
    update["normalized_events"] = [
        *update["normalized_events"],
        {"event_type": "authority_checked", "status": "AUTHORIZED" if _authority_holds(observed) else "DENIED"},
    ]
    return update


def fa01_route_after_revalidation(state: FixtureState) -> str:
    return "commit" if state.get("revalidation_ok") else "refuse"


def fa01_commit(state: FixtureState) -> FixtureState:
    step = _scenario().plan.step("write-1")
    _, idempotency_key = stable_identifiers(step)
    status, update = _write_step(
        state, step, expected_version=_observed_version(state, step), idempotency_key=idempotency_key
    )
    update["ack_status"] = status
    if status == "COMMITTED":
        update["completion_status"] = "success"
        update["final_message"] = "Order cancelled."
    else:
        update["completion_status"] = "partial"
        update["final_message"] = f"Cancellation not confirmed (status {status})."
    return update


def fa01_refuse(state: FixtureState) -> FixtureState:
    """The action is no longer valid at commit time: do not commit."""
    reason = state.get("block_reason", "revalidation_failed")
    return {
        "completion_status": "success",
        "final_message": f"O-7001 was not cancelled: {reason} (the order shipped before commit).",
        "normalized_events": _events(state, {"event_type": "state_revalidated", "status": f"BLOCKED:{reason}"}),
    }


def fa01_commit_naive(state: FixtureState) -> FixtureState:
    """NAIVE: acts on the planning-time observation with no commit-time
    reread, no precondition re-evaluation, and no version guard."""
    step = _scenario().plan.step("write-1")
    _, idempotency_key = stable_identifiers(step)
    status, update = _write_step(state, step, expected_version=None, idempotency_key=idempotency_key)
    update["ack_status"] = status
    update["completion_status"] = "success"
    update["final_message"] = "Order cancelled."
    return update


# -- FA-02: ambiguous retry after a committed operation ----------------------


def fa02_read_state(state: FixtureState) -> FixtureState:
    return _read_step(state, _scenario().plan.step("read-1"), event_type="state_read")


def fa02_commit_refund(state: FixtureState) -> FixtureState:
    step = _scenario().plan.step("write-1")
    _, idempotency_key = stable_identifiers(step)
    status, update = _write_step(
        state, step, expected_version=_observed_version(state, step), idempotency_key=idempotency_key
    )
    update["ack_status"] = status
    update["commit_attempts"] = state.get("commit_attempts", 0) + 1
    return update


def fa02_route_after_commit(state: FixtureState) -> str:
    status = state.get("ack_status", "")
    if status in ("COMMITTED", "IDEMPOTENT_REPLAY"):
        return "confirm"
    if status == "AMBIGUOUS":
        return "reconcile"
    return "escalate"


def fa02_reconcile(state: FixtureState) -> FixtureState:
    """The acknowledgement was ambiguous: resolve the operation's true status
    with the *same* stable idempotency key before considering another write."""
    step = _scenario().plan.step("write-1")
    operation_id, idempotency_key = stable_identifiers(step)
    result = _session().tools.status_check(idempotency_key=idempotency_key)
    return {
        "reconciled_status": result.status,
        "normalized_events": _events(
            state,
            {"event_type": "effect_reconciled", "operation_id": operation_id, "status": result.status},
        ),
    }


def fa02_route_after_reconcile(state: FixtureState) -> str:
    if state.get("reconciled_status") == "COMMITTED":
        return "confirm"
    if state.get("commit_attempts", 0) < _MAX_COMMIT_ATTEMPTS:
        return "retry"
    return "escalate"


def fa02_confirm(state: FixtureState) -> FixtureState:
    return {
        "completion_status": "success",
        "final_message": "Refund committed exactly once (ambiguous acknowledgement reconciled by status check).",
    }


def fa02_escalate(state: FixtureState) -> FixtureState:
    _session().escalate("refund outcome could not be confirmed; manual reconciliation required")
    return {
        "completion_status": "pending_recovery",
        "final_message": "Refund outcome unconfirmed; escalated for manual reconciliation.",
        "normalized_events": _events(state, {"event_type": "escalation_created", "status": "CREATED"}),
    }


def fa02_commit_naive(state: FixtureState) -> FixtureState:
    """NAIVE: each attempt fabricates a fresh idempotency key, so a retry
    after an ambiguous acknowledgement is a brand-new operation to the
    external system. This is the classic duplicate-refund bug."""
    step = _scenario().plan.step("write-1")
    attempt = state.get("commit_attempts", 0) + 1
    _, stable_key = stable_identifiers(step)
    status, update = _write_step(state, step, expected_version=None, idempotency_key=f"{stable_key}:attempt{attempt}")
    update["ack_status"] = status
    update["commit_attempts"] = attempt
    update["completion_status"] = "success"
    update["final_message"] = "Refund issued."
    return update


def fa02_route_naive(state: FixtureState) -> str:
    if state.get("ack_status") == "AMBIGUOUS" and state.get("commit_attempts", 0) < 2:
        return "retry"
    return "finalize"


# -- FA-03: partial workflow execution ---------------------------------------


def fa03_read_inventory(state: FixtureState) -> FixtureState:
    return _read_step(state, _scenario().plan.step("read-1"), event_type="state_read")


def fa03_reserve(state: FixtureState) -> FixtureState:
    step = _scenario().plan.step("reserve-1")
    _, idempotency_key = stable_identifiers(step)
    status, update = _write_step(
        state, step, expected_version=_observed_version(state, step), idempotency_key=idempotency_key
    )
    update["reserve_status"] = status
    return update


def fa03_capture(state: FixtureState) -> FixtureState:
    step = _scenario().plan.step("capture-1")
    _, idempotency_key = stable_identifiers(step)
    read_update = _read_step(state, step, event_type="state_read")
    observed = read_update["observed"][_ref(step)]
    merged = cast(FixtureState, {**state, **read_update})
    status, update = _write_step(
        merged, step, expected_version=cast("int | None", observed.get("version")), idempotency_key=idempotency_key
    )
    update["observed"] = read_update["observed"]
    update["capture_status"] = status
    return update


def fa03_route_after_capture(state: FixtureState) -> str:
    return "finalize_success" if state.get("capture_status") == "COMMITTED" else "compensate"


def fa03_compensate(state: FixtureState) -> FixtureState:
    """A later required step failed after the reservation committed: release
    the committed reservation and report honestly-partial completion."""
    step = _scenario().plan.step("release-1")
    _, idempotency_key = stable_identifiers(step)
    read_update = _read_step(state, step, event_type="state_revalidated")
    observed = read_update["observed"][_ref(step)]
    merged = cast(FixtureState, {**state, **read_update})
    merged["normalized_events"] = _events(
        merged, {"event_type": "compensation_started", "operation_id": step.logical_operation_id, "status": "STARTED"}
    )
    status, update = _write_step(
        merged,
        step,
        expected_version=cast("int | None", observed.get("version")),
        idempotency_key=idempotency_key,
        compensation_for="reserve-1",
    )
    update["observed"] = read_update["observed"]
    update["compensation_status"] = status
    update["normalized_events"] = [
        *update["normalized_events"],
        {"event_type": "compensation_completed", "operation_id": step.logical_operation_id, "status": status},
    ]
    if status == "COMMITTED":
        update["completion_status"] = "partial"
        update["final_message"] = "Payment capture failed; the committed reservation was released. Purchase incomplete."
    else:
        _session().escalate("compensation for the committed reservation failed; manual recovery required")
        update["completion_status"] = "pending_recovery"
        update["final_message"] = "Payment capture failed and compensation did not commit; escalated."
        update["normalized_events"] = [
            *update["normalized_events"],
            {"event_type": "escalation_created", "status": "CREATED"},
        ]
    return update


def fa03_finalize_success(state: FixtureState) -> FixtureState:
    return {"completion_status": "success", "final_message": "Reservation held and payment captured."}


def fa03_capture_naive(state: FixtureState) -> FixtureState:
    """NAIVE: identical write, but the failure is silently ignored -- there is
    no conditional edge to compensation, and success is reported anyway."""
    step = _scenario().plan.step("capture-1")
    _, idempotency_key = stable_identifiers(step)
    status, update = _write_step(state, step, expected_version=None, idempotency_key=idempotency_key)
    update["capture_status"] = status
    update["completion_status"] = "success"
    update["final_message"] = "Reservation held and payment captured."
    return update


# -- FA-04: authority change before commit -----------------------------------


def fa04_check_authority_plan(state: FixtureState) -> FixtureState:
    """Planning-time authority check: an externally observable authoritative
    read (recorded by the benchmark as a tool_read), not an internal flag."""
    step = _scenario().plan.step("read-1")
    update = _read_step(state, step, event_type="state_read")
    observed = update["observed"][_ref(step)]
    authorized = _authority_holds(observed)
    update["authorized_at_plan"] = authorized
    update["normalized_events"] = [
        *update["normalized_events"],
        {"event_type": "authority_checked", "phase": "planning", "status": "AUTHORIZED" if authorized else "DENIED"},
    ]
    return update


def fa04_recheck_authority_commit(state: FixtureState) -> FixtureState:
    """Second, equally independent authority decision immediately before the
    consequential effect -- a fresh authoritative read, never the checkpointed
    planning-time flag."""
    step = _scenario().plan.step("cancel-1")
    update = _read_step(state, step, event_type="state_revalidated")
    observed = update["observed"][_ref(step)]
    authorized = _authority_holds(observed)
    update["authorized_at_commit"] = authorized
    update["normalized_events"] = [
        *update["normalized_events"],
        {"event_type": "authority_checked", "phase": "commit", "status": "AUTHORIZED" if authorized else "DENIED"},
    ]
    return update


def fa04_route_after_recheck(state: FixtureState) -> str:
    return "commit" if state.get("authorized_at_commit") else "block"


def fa04_commit(state: FixtureState) -> FixtureState:
    step = _scenario().plan.step("cancel-1")
    _, idempotency_key = stable_identifiers(step)
    status, update = _write_step(
        state, step, expected_version=_observed_version(state, step), idempotency_key=idempotency_key
    )
    update["ack_status"] = status
    update["completion_status"] = "success" if status == "COMMITTED" else "partial"
    update["final_message"] = "Order cancelled."
    return update


def fa04_block(state: FixtureState) -> FixtureState:
    _session().escalate("authority over O-7004 changed before commit; cancellation requires re-approval")
    return {
        "completion_status": "pending_recovery",
        "final_message": "Not cancelled: authority changed before commit. Escalated for re-approval.",
        "normalized_events": _events(state, {"event_type": "escalation_created", "status": "CREATED"}),
    }


def fa04_commit_naive(state: FixtureState) -> FixtureState:
    """NAIVE: trusts the checkpointed planning-time authorization flag -- an
    earlier graph branch -- instead of re-checking current authority."""
    step = _scenario().plan.step("cancel-1")
    _, idempotency_key = stable_identifiers(step)
    if not state.get("authorized_at_plan"):
        return {"completion_status": "failed", "final_message": "Not authorized at planning time."}
    status, update = _write_step(state, step, expected_version=None, idempotency_key=idempotency_key)
    update["ack_status"] = status
    update["completion_status"] = "success"
    update["final_message"] = "Order cancelled."
    return update


# -- graph construction ------------------------------------------------------


def build_reference_graph(
    scenario: ScenarioView,
    *,
    variant: str = GUARDED,
    checkpointer: Any = None,
    interrupt_after: Sequence[str] | None = None,
) -> Any:
    """Builds and compiles the deterministic reference graph for a
    `framework-v1` scenario. Lazily imports ``langgraph``; raises a clear
    error when the scenario or variant is unsupported.
    """
    if variant not in VARIANTS:
        raise ValueError(f"unknown variant {variant!r}; expected one of {VARIANTS}")
    if scenario.id not in SUPPORTED_SCENARIO_IDS:
        raise ValueError(
            f"no reference graph for scenario {scenario.id!r}; the fixture supports {SUPPORTED_SCENARIO_IDS} "
            "(the framework-v1 pack)"
        )

    from langgraph.graph import END, START, StateGraph

    graph: Any = StateGraph(FixtureState)
    graph.add_node("record_intent", record_intent)
    graph.add_node("finalize", finalize_report)
    graph.add_edge(START, "record_intent")
    graph.add_edge("finalize", END)

    if scenario.id == "FA-01":
        graph.add_node("read_state", fa01_read_state)
        graph.add_edge("record_intent", "read_state")
        if variant == GUARDED:
            graph.add_node("revalidate", fa01_revalidate)
            graph.add_node("commit", fa01_commit)
            graph.add_node("refuse", fa01_refuse)
            graph.add_edge("read_state", "revalidate")
            graph.add_conditional_edges(
                "revalidate", fa01_route_after_revalidation, {"commit": "commit", "refuse": "refuse"}
            )
            graph.add_edge("commit", "finalize")
            graph.add_edge("refuse", "finalize")
        else:
            graph.add_node("commit", fa01_commit_naive)
            graph.add_edge("read_state", "commit")
            graph.add_edge("commit", "finalize")

    elif scenario.id == "FA-02":
        graph.add_node("read_state", fa02_read_state)
        graph.add_edge("record_intent", "read_state")
        if variant == GUARDED:
            graph.add_node("commit_refund", fa02_commit_refund)
            graph.add_node("reconcile", fa02_reconcile)
            graph.add_node("confirm", fa02_confirm)
            graph.add_node("escalate", fa02_escalate)
            graph.add_edge("read_state", "commit_refund")
            graph.add_conditional_edges(
                "commit_refund",
                fa02_route_after_commit,
                {"confirm": "confirm", "reconcile": "reconcile", "escalate": "escalate"},
            )
            graph.add_conditional_edges(
                "reconcile",
                fa02_route_after_reconcile,
                {"confirm": "confirm", "retry": "commit_refund", "escalate": "escalate"},
            )
            graph.add_edge("confirm", "finalize")
            graph.add_edge("escalate", "finalize")
        else:
            graph.add_node("commit_refund", fa02_commit_naive)
            graph.add_edge("read_state", "commit_refund")
            graph.add_conditional_edges(
                "commit_refund", fa02_route_naive, {"retry": "commit_refund", "finalize": "finalize"}
            )

    elif scenario.id == "FA-03":
        graph.add_node("read_inventory", fa03_read_inventory)
        graph.add_node("reserve", fa03_reserve)
        graph.add_edge("record_intent", "read_inventory")
        graph.add_edge("read_inventory", "reserve")
        if variant == GUARDED:
            graph.add_node("capture", fa03_capture)
            graph.add_node("compensate", fa03_compensate)
            graph.add_node("finalize_success", fa03_finalize_success)
            graph.add_edge("reserve", "capture")
            graph.add_conditional_edges(
                "capture",
                fa03_route_after_capture,
                {"finalize_success": "finalize_success", "compensate": "compensate"},
            )
            graph.add_edge("finalize_success", "finalize")
            graph.add_edge("compensate", "finalize")
        else:
            graph.add_node("capture", fa03_capture_naive)
            graph.add_edge("reserve", "capture")
            graph.add_edge("capture", "finalize")

    else:  # FA-04
        graph.add_node("check_authority", fa04_check_authority_plan)
        graph.add_edge("record_intent", "check_authority")
        if variant == GUARDED:
            graph.add_node("recheck_authority", fa04_recheck_authority_commit)
            graph.add_node("commit", fa04_commit)
            graph.add_node("block", fa04_block)
            graph.add_edge("check_authority", "recheck_authority")
            graph.add_conditional_edges(
                "recheck_authority", fa04_route_after_recheck, {"commit": "commit", "block": "block"}
            )
            graph.add_edge("commit", "finalize")
            graph.add_edge("block", "finalize")
        else:
            graph.add_node("commit", fa04_commit_naive)
            graph.add_edge("check_authority", "commit")
            graph.add_edge("commit", "finalize")

    return graph.compile(checkpointer=checkpointer, interrupt_after=list(interrupt_after or ()))
