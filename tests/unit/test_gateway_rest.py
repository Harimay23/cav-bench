"""REST frontend request/response mapping tests (M-GPI-1)."""

from __future__ import annotations

import json
import urllib.error
import urllib.request

from cavbench.gateway.core import GatewaySession
from cavbench.gateway.envelope import ENVELOPE_VERSION
from cavbench.gateway.rest import GatewayRestServer
from cavbench.scenarios.loader import load_builtin_pack

PACK = load_builtin_pack("core-v1")


def _post(url: str, token: str | None, body: dict[str, object]) -> tuple[int, dict[str, object]]:
    headers = {"Content-Type": "application/json"}
    if token is not None:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST", headers=headers)
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.load(resp)
    except urllib.error.HTTPError as exc:
        return exc.code, json.load(exc)


def test_capabilities_endpoint_requires_no_authentication_and_leaks_no_oracle() -> None:
    scenario = PACK.get("HP-01")
    session = GatewaySession.start(scenario, seed=0, run_id="rest-caps")
    with GatewayRestServer(session) as server:
        with urllib.request.urlopen(server.base_url + "/capabilities") as resp:
            assert resp.status == 200
            body = json.load(resp)
    assert body["scenario_id"] == "HP-01"
    assert "goal_predicates" not in json.dumps(body)


def test_committed_write_returns_200() -> None:
    scenario = PACK.get("HP-06")
    write_step = next(s for s in scenario.view.plan.steps if s.kind == "write")
    session = GatewaySession.start(scenario, seed=0, run_id="rest-committed")
    with GatewayRestServer(session) as server:
        status, body = _post(
            server.base_url + "/operations",
            server.run_token,
            {
                "envelope_version": ENVELOPE_VERSION,
                "operation_id": write_step.logical_operation_id or write_step.step_id,
                "correlation_id": "corr-1",
                "actor_id": "candidate",
                "action": "write",
                "resource": {
                    "namespace": write_step.namespace,
                    "resource_id": write_step.resource_id,
                    "tool_name": write_step.tool_name,
                },
                "parameters": {"step_id": write_step.step_id, "changes": dict(write_step.changes)},
                "idempotency_key": "idem-1",
            },
        )
    assert status == 200
    assert body["status"] == "committed"


def test_stale_expected_version_returns_409() -> None:
    scenario = PACK.get("ST-01")
    write_step = scenario.view.plan.steps[1]
    session = GatewaySession.start(scenario, seed=0, run_id="rest-conflict")
    with GatewayRestServer(session) as server:
        status, body = _post(
            server.base_url + "/operations",
            server.run_token,
            {
                "envelope_version": ENVELOPE_VERSION,
                "operation_id": write_step.logical_operation_id or write_step.step_id,
                "correlation_id": "corr-1",
                "actor_id": "candidate",
                "action": "write",
                "resource": {
                    "namespace": write_step.namespace,
                    "resource_id": write_step.resource_id,
                    "tool_name": write_step.tool_name,
                },
                "parameters": {"step_id": write_step.step_id, "changes": dict(write_step.changes)},
                "idempotency_key": "idem-1",
                "expected_version": 999999,
            },
        )
    assert status == 409
    assert body["status"] == "rejected"


def test_ambiguous_write_returns_deterministic_504() -> None:
    scenario = PACK.get("ER-03")
    write_step = scenario.view.plan.steps[1]
    session = GatewaySession.start(scenario, seed=0, run_id="rest-ambiguous")
    with GatewayRestServer(session) as server:
        status, body = _post(
            server.base_url + "/operations",
            server.run_token,
            {
                "envelope_version": ENVELOPE_VERSION,
                "operation_id": write_step.logical_operation_id or write_step.step_id,
                "correlation_id": "corr-1",
                "actor_id": "candidate",
                "action": "write",
                "resource": {
                    "namespace": write_step.namespace,
                    "resource_id": write_step.resource_id,
                    "tool_name": write_step.tool_name,
                },
                "parameters": {"step_id": write_step.step_id, "changes": dict(write_step.changes)},
                "idempotency_key": "idem-1",
            },
        )
    assert status == 504
    assert body["status"] == "ambiguous"


def test_malformed_json_body_returns_400_without_touching_tool_facade() -> None:
    scenario = PACK.get("HP-01")
    session = GatewaySession.start(scenario, seed=0, run_id="rest-malformed-json")
    with GatewayRestServer(session) as server:
        req = urllib.request.Request(
            server.base_url + "/operations", data=b"{not json", method="POST",
            headers={"Authorization": f"Bearer {session.run_token}"},
        )
        try:
            urllib.request.urlopen(req)
            raised = False
        except urllib.error.HTTPError as exc:
            raised = True
            assert exc.code == 400
        assert raised
    assert session.log.tool_facade_call_count() == 0


def test_missing_authorization_header_is_treated_as_unauthenticated() -> None:
    scenario = PACK.get("HP-01")
    session = GatewaySession.start(scenario, seed=0, run_id="rest-no-auth")
    with GatewayRestServer(session) as server:
        status, body = _post(
            server.base_url + "/operations",
            None,
            {
                "envelope_version": ENVELOPE_VERSION,
                "operation_id": "op-1",
                "correlation_id": "corr-1",
                "actor_id": "candidate",
                "action": "read",
                "resource": {"namespace": "order", "resource_id": "O-2001"},
            },
        )
    # a missing Authorization header fails either schema validation (empty
    # session_token) or the token comparison, depending on the empty-string
    # edge case; either way it is a gateway-level rejection with zero
    # ToolFacade calls, never treated as authenticated.
    assert status in (400, 401)
    assert session.log.tool_facade_call_count() == 0


def test_reconciliation_get_route_maps_to_status_check() -> None:
    scenario = PACK.get("ER-03")
    write_step = scenario.view.plan.steps[1]
    session = GatewaySession.start(scenario, seed=0, run_id="rest-reconcile")
    with GatewayRestServer(session) as server:
        operation_id = write_step.logical_operation_id or write_step.step_id
        _post(
            server.base_url + "/operations",
            server.run_token,
            {
                "envelope_version": ENVELOPE_VERSION,
                "operation_id": operation_id,
                "correlation_id": "corr-1",
                "actor_id": "candidate",
                "action": "write",
                "resource": {
                    "namespace": write_step.namespace,
                    "resource_id": write_step.resource_id,
                    "tool_name": write_step.tool_name,
                },
                "parameters": {"step_id": write_step.step_id, "changes": dict(write_step.changes)},
                "idempotency_key": "idem-1",
            },
        )
        req = urllib.request.Request(
            f"{server.base_url}/operations/{operation_id}",
            headers={"Authorization": f"Bearer {server.run_token}"},
        )
        with urllib.request.urlopen(req) as resp:
            status = resp.status
            body = json.load(resp)
    assert status == 200
    assert body["status"] == "ok"
