"""Capability-enforcement adversarial tests (M-GPI-1 review follow-up).

Before the fix, the gateway forwarded an arbitrary candidate-supplied
`tool_name`/`namespace`/`resource_id` straight to `ToolFacade`. These
tests prove that every operation is now checked against
`GatewaySession.capabilities()` for the current scenario *before* any
`ToolFacade` call, and that a rejection here creates zero benchmark
attempts, exactly like a malformed envelope or an authentication failure.

Scenario reference (`core-v1`, `ER-04` -- "Inventory reservation succeeds
but payment step fails"): `reserve-1` is a `write` step (tool
`reserve_inventory`, namespace `inventory`); `capture-1` is a `write` step
(tool `capture_payment`, namespace `payment`); `release-1` is the only
genuine `compensate`-kind step in this scenario (tool
`release_inventory`, namespace `inventory`, `compensates: "reserve-1"`).
`reserve_inventory` and `release_inventory` share a namespace but are
advertised under different actions -- the pair this suite uses to prove
write/compensate tools are not interchangeable.
"""

from __future__ import annotations

from cavbench.gateway.core import GatewaySession
from cavbench.gateway.envelope import ENVELOPE_VERSION
from cavbench.scenarios.loader import load_builtin_pack

PACK = load_builtin_pack("core-v1")


def _envelope(session: GatewaySession, **overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "envelope_version": ENVELOPE_VERSION,
        "session_token": session.run_token,
        "operation_id": "op-1",
        "correlation_id": "corr-1",
        "actor_id": "candidate",
        "action": "read",
        "resource": {"namespace": "order", "resource_id": "O-1"},
    }
    base.update(overrides)
    return base


def test_capabilities_advertise_reserve_as_write_and_release_as_compensate() -> None:
    scenario = PACK.get("ER-04")
    session = GatewaySession.start(scenario, seed=0, run_id="capdisc")
    ops = session.capabilities()["operations"]
    by_tool = {op["tool_name"]: op["action"] for op in ops if "tool_name" in op}
    assert by_tool["reserve_inventory"] == "write"
    assert by_tool["release_inventory"] == "compensate"


def test_unadvertised_tool_name_is_rejected_with_zero_tool_facade_calls() -> None:
    scenario = PACK.get("ER-04")
    session = GatewaySession.start(scenario, seed=0, run_id="cap-unadvertised")
    outcome = session.handle(
        _envelope(
            session,
            action="write",
            resource={"namespace": "inventory", "resource_id": "SKU-4004", "tool_name": "detonate_warehouse"},
            idempotency_key="idem-1",
        )
    )
    assert not outcome.accepted
    assert outcome.rejection is not None
    assert outcome.rejection.reason == "capability_violation"
    assert session.log.tool_facade_call_count() == 0


def test_valid_tool_with_wrong_namespace_is_rejected() -> None:
    scenario = PACK.get("ER-04")
    session = GatewaySession.start(scenario, seed=0, run_id="cap-wrong-namespace")
    outcome = session.handle(
        _envelope(
            session,
            action="write",
            # reserve_inventory is real, but it's advertised under "inventory", not "payment"
            resource={"namespace": "payment", "resource_id": "SKU-4004", "tool_name": "reserve_inventory"},
            idempotency_key="idem-1",
        )
    )
    assert not outcome.accepted
    assert outcome.rejection is not None
    assert outcome.rejection.reason == "capability_violation"
    assert session.log.tool_facade_call_count() == 0


def test_valid_tool_with_wrong_action_is_rejected() -> None:
    """capture_payment is advertised as `write`; requesting it as
    `compensate` must be rejected even though the tool name is real."""
    scenario = PACK.get("ER-04")
    session = GatewaySession.start(scenario, seed=0, run_id="cap-wrong-action")
    outcome = session.handle(
        _envelope(
            session,
            action="compensate",
            resource={"namespace": "payment", "resource_id": "P-4004", "tool_name": "capture_payment"},
            idempotency_key="idem-1",
        )
    )
    assert not outcome.accepted
    assert outcome.rejection is not None
    assert outcome.rejection.reason == "capability_violation"
    assert session.log.tool_facade_call_count() == 0


def test_compensation_tool_sent_as_write_is_rejected() -> None:
    scenario = PACK.get("ER-04")
    session = GatewaySession.start(scenario, seed=0, run_id="cap-comp-as-write")
    outcome = session.handle(
        _envelope(
            session,
            action="write",
            resource={"namespace": "inventory", "resource_id": "SKU-4004", "tool_name": "release_inventory"},
            idempotency_key="idem-1",
        )
    )
    assert not outcome.accepted
    assert outcome.rejection is not None
    assert outcome.rejection.reason == "capability_violation"
    assert "interchangeable" in outcome.rejection.detail
    assert session.log.tool_facade_call_count() == 0


def test_write_tool_sent_as_compensation_is_rejected() -> None:
    scenario = PACK.get("ER-04")
    session = GatewaySession.start(scenario, seed=0, run_id="cap-write-as-comp")
    outcome = session.handle(
        _envelope(
            session,
            action="compensate",
            resource={"namespace": "inventory", "resource_id": "SKU-4004", "tool_name": "reserve_inventory"},
            idempotency_key="idem-1",
        )
    )
    assert not outcome.accepted
    assert outcome.rejection is not None
    assert outcome.rejection.reason == "capability_violation"
    assert "interchangeable" in outcome.rejection.detail
    assert session.log.tool_facade_call_count() == 0


def test_arbitrary_read_namespace_is_rejected() -> None:
    scenario = PACK.get("ER-04")
    session = GatewaySession.start(scenario, seed=0, run_id="cap-arbitrary-read")
    outcome = session.handle(
        _envelope(
            session,
            action="read",
            resource={"namespace": "internal_admin_secrets", "resource_id": "anything"},
        )
    )
    assert not outcome.accepted
    assert outcome.rejection is not None
    assert outcome.rejection.reason == "capability_violation"
    assert session.log.tool_facade_call_count() == 0


def test_scenario_visible_read_namespace_is_allowed() -> None:
    scenario = PACK.get("ER-04")
    session = GatewaySession.start(scenario, seed=0, run_id="cap-visible-read")
    outcome = session.handle(
        _envelope(session, action="read", resource={"namespace": "inventory", "resource_id": "SKU-4004"})
    )
    assert outcome.accepted
    assert session.log.tool_facade_call_count() == 1


def test_valid_write_and_compensate_operations_are_accepted() -> None:
    scenario = PACK.get("ER-04")
    session = GatewaySession.start(scenario, seed=0, run_id="cap-valid-both")

    write_outcome = session.handle(
        _envelope(
            session,
            action="write",
            resource={"namespace": "inventory", "resource_id": "SKU-4004", "tool_name": "reserve_inventory"},
            idempotency_key="idem-write",
        )
    )
    assert write_outcome.accepted

    compensate_outcome = session.handle(
        _envelope(
            session,
            action="compensate",
            operation_id="op-2",
            resource={"namespace": "inventory", "resource_id": "SKU-4004", "tool_name": "release_inventory"},
            idempotency_key="idem-compensate",
            parameters={"compensation_for": "reserve-1"},
        )
    )
    assert compensate_outcome.accepted
    assert session.log.tool_facade_call_count() == 2


def test_unavailable_scenario_operation_is_rejected() -> None:
    """A tool that exists in the repository's static effect-type
    vocabulary (`cavbench.runtime.tools.TOOL_EFFECT_TYPE`) but is simply
    not part of *this* scenario's plan must still be rejected -- being a
    real tool name elsewhere in the system does not make it available
    here."""
    scenario = PACK.get("ER-04")  # this scenario's plan never mentions export_customer_data
    session = GatewaySession.start(scenario, seed=0, run_id="cap-unavailable-op")
    outcome = session.handle(
        _envelope(
            session,
            action="write",
            resource={"namespace": "account", "resource_id": "ACC-1", "tool_name": "export_customer_data"},
            idempotency_key="idem-1",
        )
    )
    assert not outcome.accepted
    assert outcome.rejection is not None
    assert outcome.rejection.reason == "capability_violation"
    assert session.log.tool_facade_call_count() == 0
