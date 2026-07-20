"""Capability-discovery session-logging tests (M-GPI-1 review follow-up,
GPI-FR-009: "the advertisement is recorded in the session log").

Before this fix, `GET /capabilities` returned `session.capabilities()`
directly without ever touching the session log. `GatewaySession.
discover_capabilities()` is now the candidate-facing entry point: it
returns the same advertisement `capabilities()` always returns for this
session (computed once, cached -- see `_resource_scoped_operations()`)
and records exactly that advertisement in the log on every call.
"""

from __future__ import annotations

import json

from cavbench.gateway.core import GatewaySession
from cavbench.gateway.rest import GatewayRestServer
from cavbench.scenarios.loader import load_builtin_pack
from examples.reference_candidate.client import RestGatewayClient

PACK = load_builtin_pack("core-v1")


def test_discovery_is_logged() -> None:
    scenario = PACK.get("ER-04")
    session = GatewaySession.start(scenario, seed=0, run_id="disc-logged")
    session.discover_capabilities()
    discoveries = [e for e in session.log.entries if e.kind == "discovery"]
    assert len(discoveries) == 1
    assert discoveries[0].tool_facade_call == False  # noqa: E712 - explicit, readable assertion


def test_logged_advertisement_equals_returned_advertisement() -> None:
    scenario = PACK.get("ER-04")
    session = GatewaySession.start(scenario, seed=0, run_id="disc-equal")
    returned = session.discover_capabilities()
    logged = session.log.entries[-1].detail["advertisement"]
    assert logged == returned


def test_logged_advertisement_over_rest_matches_the_wire_response() -> None:
    scenario = PACK.get("ER-04")
    session = GatewaySession.start(scenario, seed=0, run_id="disc-rest")
    with GatewayRestServer(session) as server:
        client = RestGatewayClient(server.base_url, server.run_token)
        wire_response = client.capabilities()
    logged = session.log.entries[-1].detail["advertisement"]
    assert logged == wire_response


def test_run_token_is_absent_from_the_discovery_log_entry() -> None:
    scenario = PACK.get("ER-04")
    session = GatewaySession.start(scenario, seed=0, run_id="disc-no-token")
    session.discover_capabilities()
    serialized = json.dumps(session.log.entries[-1].to_dict())
    assert session.run_token not in serialized


def test_discovery_log_entry_carries_no_oracle_content() -> None:
    scenario = PACK.get("ER-04")
    session = GatewaySession.start(scenario, seed=0, run_id="disc-no-oracle")
    session.discover_capabilities()
    serialized = json.dumps(session.log.entries[-1].to_dict())
    for oracle_term in ("goal_predicates", "forbidden_effects", "required_effects", "policy_constraints"):
        assert oracle_term not in serialized


def test_discovery_log_entry_contains_required_fields() -> None:
    scenario = PACK.get("ER-04")
    session = GatewaySession.start(scenario, seed=0, run_id="disc-fields")
    session.discover_capabilities()
    advertisement = session.log.entries[-1].detail["advertisement"]
    assert advertisement["session_id"] == session.session_id
    assert advertisement["scenario_id"] == scenario.id
    assert advertisement["envelope_version"]
    actions = {op["action"] for op in advertisement["operations"]}
    assert {"read", "write", "compensate", "escalate", "clarify", "status_check", "report"} <= actions
    resource_scoped = [op for op in advertisement["operations"] if op["action"] in ("read", "write", "compensate")]
    assert resource_scoped, "expected at least one resource-scoped operation to be advertised"
    for op in resource_scoped:
        assert "namespace" in op
        assert "resource_id" in op
    write_ops = [op for op in resource_scoped if op["action"] in ("write", "compensate")]
    assert all("tool_name" in op for op in write_ops)


def test_repeated_discovery_is_deterministic_and_each_call_is_logged() -> None:
    """Option (a) from the requirement: each GET is recorded, and every
    recorded advertisement is byte-identical (the frozen advertisement),
    even though it produces a distinct log entry per call."""
    scenario = PACK.get("ER-04")
    session = GatewaySession.start(scenario, seed=0, run_id="disc-repeat")

    first = session.discover_capabilities()
    second = session.discover_capabilities()
    third = session.discover_capabilities()

    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True) == json.dumps(third, sort_keys=True)

    discoveries = [e for e in session.log.entries if e.kind == "discovery"]
    assert len(discoveries) == 3
    assert discoveries[0].seq != discoveries[1].seq != discoveries[2].seq
    for entry in discoveries:
        assert entry.detail["advertisement"] == first


def test_discovery_does_not_create_a_benchmark_attempt() -> None:
    scenario = PACK.get("ER-04")
    session = GatewaySession.start(scenario, seed=0, run_id="disc-no-attempt")
    session.discover_capabilities()
    session.discover_capabilities()
    assert session.log.tool_facade_call_count() == 0
