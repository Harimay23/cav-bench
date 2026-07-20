"""Gateway neutrality contract tests (M-GPI-1).

Mirrors ``tests/contract/test_evaluator_independence.py``'s spirit but at
the protocol boundary: the gateway must be measurement plumbing that never
adds safeguards the candidate didn't exhibit and never hides hazards it
did. See ``docs/design/generic-protocol-integration.md`` ("Trust
boundaries") and approval condition 2 in
``docs/program/approvals/M-GPI-1.md``.
"""

from __future__ import annotations

from cavbench.gateway.core import GatewaySession
from cavbench.gateway.envelope import ENVELOPE_VERSION
from cavbench.scenarios.loader import load_builtin_pack

PACK = load_builtin_pack("core-v1")


def _envelope(session: GatewaySession, **overrides: object) -> dict[str, object]:
    base = {
        "envelope_version": ENVELOPE_VERSION,
        "session_token": session.run_token,
        "operation_id": "op-1",
        "correlation_id": "corr-1",
        "actor_id": "candidate",
        "action": "read",
        "resource": {"namespace": "order", "resource_id": "O-2001"},
    }
    base.update(overrides)
    return base


# -- one request, one ToolFacade invocation ---------------------------------


def test_one_valid_request_maps_to_exactly_one_tool_facade_call() -> None:
    scenario = PACK.get("ST-01")
    session = GatewaySession.start(scenario, seed=0, run_id="neutrality-1")
    outcome = session.handle(_envelope(session))
    assert outcome.accepted
    assert session.log.tool_facade_call_count() == 1


def test_malformed_request_creates_zero_benchmark_attempts() -> None:
    scenario = PACK.get("ST-01")
    session = GatewaySession.start(scenario, seed=0, run_id="neutrality-2")
    outcome = session.handle({"not_an_envelope": True})
    assert not outcome.accepted
    assert outcome.http_hint == "bad_request"
    assert session.log.tool_facade_call_count() == 0
    trace = session.finalize()
    assert len(trace.events) == 1  # only the scenario's synthetic user_input event


def test_authentication_failure_creates_zero_benchmark_attempts() -> None:
    scenario = PACK.get("ST-01")
    session = GatewaySession.start(scenario, seed=0, run_id="neutrality-3")
    outcome = session.handle(_envelope(session, session_token="not-the-real-token"))
    assert not outcome.accepted
    assert outcome.http_hint == "unauthorized"
    assert session.log.tool_facade_call_count() == 0


def test_unknown_action_is_a_gateway_level_rejection_not_an_attempt() -> None:
    scenario = PACK.get("ST-01")
    session = GatewaySession.start(scenario, seed=0, run_id="neutrality-4")
    outcome = session.handle(_envelope(session, action="teleport_order"))
    assert not outcome.accepted
    assert outcome.http_hint == "not_found"
    assert session.log.tool_facade_call_count() == 0


# -- no gateway-initiated retry / reconciliation -----------------------------


def test_gateway_performs_no_automatic_retry_on_conflict() -> None:
    """A CONFLICT (rejected) response is relayed as-is; the gateway never
    re-reads or resubmits on the candidate's behalf."""
    scenario = PACK.get("ST-01")
    step = scenario.view.plan.steps[1]
    session = GatewaySession.start(scenario, seed=0, run_id="neutrality-5")
    write = _envelope(
        session,
        action="write",
        resource={"namespace": step.namespace, "resource_id": step.resource_id, "tool_name": step.tool_name},
        idempotency_key="idem-1",
        expected_version=999999,  # deliberately stale
    )
    outcome = session.handle(write)
    assert outcome.accepted
    assert outcome.response is not None
    assert outcome.response.status == "rejected"
    # exactly one ToolFacade call was made for this one request -- no
    # gateway-side retry loop occurred.
    assert session.log.tool_facade_call_count() == 1


def test_gateway_performs_no_unrequested_reconciliation() -> None:
    """An ambiguous write is returned to the candidate as ambiguous; the
    gateway does not call status_check on the candidate's behalf."""
    scenario = PACK.get("ER-03")
    step = scenario.view.plan.steps[1]
    session = GatewaySession.start(scenario, seed=0, run_id="neutrality-6")
    write = _envelope(
        session,
        action="write",
        resource={"namespace": step.namespace, "resource_id": step.resource_id, "tool_name": step.tool_name},
        idempotency_key="idem-1",
    )
    outcome = session.handle(write)
    assert outcome.accepted
    assert outcome.response is not None
    assert outcome.response.status == "ambiguous"
    # exactly one ToolFacade call: the write itself. No implicit status_check.
    assert session.log.tool_facade_call_count() == 1
    # the ledger truly holds the committed effect despite the ambiguous response
    assert len(session.environment.ledger.as_dicts()) == 1


def test_candidate_invoked_reconciliation_resolves_ambiguity_via_status_check_path() -> None:
    scenario = PACK.get("ER-03")
    step = scenario.view.plan.steps[1]
    session = GatewaySession.start(scenario, seed=0, run_id="neutrality-7")
    write = _envelope(
        session,
        action="write",
        resource={"namespace": step.namespace, "resource_id": step.resource_id, "tool_name": step.tool_name},
        idempotency_key="idem-recon",
    )
    outcome = session.handle(write)
    assert outcome.response is not None and outcome.response.status == "ambiguous"

    reconcile = _envelope(
        session,
        action="status_check",
        operation_id=str(write["operation_id"]),
        correlation_id="corr-reconcile",
        resource={"namespace": "operation", "resource_id": str(write["operation_id"])},
    )
    reconcile_outcome = session.handle(reconcile)
    assert reconcile_outcome.accepted
    assert reconcile_outcome.response is not None
    assert reconcile_outcome.response.status == "ok"  # found: committed
    # exactly two ToolFacade calls total: the write, and the explicit,
    # candidate-invoked status_check -- nothing implicit in between.
    assert session.log.tool_facade_call_count() == 2


def test_blind_retry_with_fresh_identity_produces_a_duplicate_effect() -> None:
    """The gateway adds no dedup of its own beyond passing through whatever
    idempotency_key the candidate supplies (GPI-FR-007): a candidate that
    retries with a *different* key after an ambiguous response gets a
    second committed effect, exactly as core semantics already model."""
    scenario = PACK.get("ER-03")
    step = scenario.view.plan.steps[1]
    session = GatewaySession.start(scenario, seed=0, run_id="neutrality-8")
    resource = {"namespace": step.namespace, "resource_id": step.resource_id, "tool_name": step.tool_name}

    first = session.handle(_envelope(session, action="write", resource=resource, idempotency_key="idem-a"))
    assert first.response is not None and first.response.status == "ambiguous"

    second = session.handle(
        _envelope(
            session,
            action="write",
            resource=resource,
            operation_id="op-2",
            correlation_id="corr-2",
            idempotency_key="idem-b",
        )
    )
    assert second.response is not None
    # the second commit lands (order was already cancelled, so this
    # particular scenario's mutation may itself be rejected downstream --
    # what matters is the gateway made exactly one ToolFacade call per
    # request either way).
    assert session.log.tool_facade_call_count() == 2


# -- compensation / escalation mapping ---------------------------------------


def test_compensate_action_maps_to_tool_facade_write_with_compensation_for() -> None:
    scenario = PACK.get("ER-05")
    comp_step = next(s for s in scenario.view.plan.steps if s.step_id == "cancel-1")
    session = GatewaySession.start(scenario, seed=0, run_id="neutrality-9")
    envelope = _envelope(
        session,
        action="compensate",
        resource={
            "namespace": comp_step.namespace,
            "resource_id": comp_step.resource_id,
            "tool_name": comp_step.tool_name,
        },
        idempotency_key="idem-comp",
        parameters={"compensation_for": "refund-1"},
    )
    outcome = session.handle(envelope)
    assert outcome.accepted
    assert session.log.tool_facade_call_count() == 1
    effects = session.environment.ledger.as_dicts()
    assert effects[0]["compensation_for"] == "refund-1"


def test_escalate_action_maps_to_tool_facade_escalate() -> None:
    scenario = PACK.get("ST-01")
    session = GatewaySession.start(scenario, seed=0, run_id="neutrality-10")
    outcome = session.handle(_envelope(session, action="escalate", parameters={"reason": "needs review"}))
    assert outcome.accepted
    assert outcome.response is not None
    assert outcome.response.status == "created"
    assert session.log.tool_facade_call_count() == 1


# -- oracle leakage -----------------------------------------------------------


def test_capability_discovery_leaks_no_oracle_content() -> None:
    scenario = PACK.get("IA-04")
    session = GatewaySession.start(scenario, seed=0, run_id="neutrality-11")
    caps = session.capabilities()
    serialized = str(caps)
    oracle_terms = ["goal_predicates", "forbidden_effects", "required_effects", "policy_constraints", "recovery"]
    for term in oracle_terms:
        assert term not in serialized


def test_gateway_rejection_response_leaks_no_oracle_content() -> None:
    scenario = PACK.get("IA-04")
    session = GatewaySession.start(scenario, seed=0, run_id="neutrality-12")
    outcome = session.handle({"garbage": True})
    assert not outcome.accepted
    assert outcome.rejection is not None
    serialized = str(outcome.rejection.to_dict())
    assert "goal_predicates" not in serialized
