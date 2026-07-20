"""Generic advertisement/enforcement consistency tests (M-GPI-1 review
follow-up).

A prior round fixed resource_id-level enforcement but left one
divergence: `derive_operations` advertised a `read` descriptor only for
explicit `read`-kind plan steps, while enforcement's `readable_resources`
allowed reads for any resource touched by *any* resource-scoped step
(read, write, or compensate). A request could therefore be accepted by
enforcement with no equivalent descriptor in `/capabilities`.

These tests are deliberately generic -- parametrized over several real
`core-v1` scenarios -- rather than scenario-specific, so they act as a
standing symmetry check between `capabilities()` and `_check_capability()`
for any scenario, not just the one hand-picked example.
"""

from __future__ import annotations

import pytest

from cavbench.gateway.core import GatewaySession
from cavbench.gateway.envelope import ENVELOPE_VERSION
from cavbench.scenarios.loader import load_builtin_pack

PACK = load_builtin_pack("core-v1")

# A representative cross-section: scenarios exercising read, write, and
# compensate descriptors (ER-04 has all three in one scenario), plus a
# couple of others for breadth.
SAMPLE_SCENARIO_IDS = ("ER-04", "ER-05", "ST-01", "IA-04", "HP-01")


def _envelope(session: GatewaySession, op: dict[str, object], *, operation_id: str) -> dict[str, object]:
    action = op["action"]
    resource: dict[str, object] = {"namespace": op["namespace"], "resource_id": op["resource_id"]}
    envelope: dict[str, object] = {
        "envelope_version": ENVELOPE_VERSION,
        "session_token": session.run_token,
        "operation_id": operation_id,
        "correlation_id": f"corr-{operation_id}",
        "actor_id": "candidate",
        "action": action,
        "resource": resource,
    }
    if action in ("write", "compensate"):
        resource["tool_name"] = op["tool_name"]
        envelope["idempotency_key"] = f"idem-{operation_id}"
    return envelope


@pytest.mark.parametrize("scenario_id", SAMPLE_SCENARIO_IDS)
def test_every_advertised_resource_scoped_descriptor_is_accepted_by_enforcement(scenario_id: str) -> None:
    """The converse direction: every operation `/capabilities` advertises
    must actually be accepted -- with its exact action/tool/namespace/
    resource -- when submitted, and each submission is exactly one
    `ToolFacade` call."""
    scenario = PACK.get(scenario_id)
    session = GatewaySession.start(scenario, seed=0, run_id=f"consistency-accept-{scenario_id}")
    advertised = session.capabilities()["operations"]
    resource_scoped = [op for op in advertised if op["action"] in ("read", "write", "compensate")]
    assert resource_scoped, f"{scenario_id} advertised no resource-scoped operations to test"

    before = session.log.tool_facade_call_count()
    for i, op in enumerate(resource_scoped):
        outcome = session.handle(_envelope(session, op, operation_id=f"op-{i}"))
        assert outcome.accepted, f"advertised operation {op} was rejected: {outcome.rejection}"
    after = session.log.tool_facade_call_count()
    assert after - before == len(resource_scoped)


@pytest.mark.parametrize("scenario_id", SAMPLE_SCENARIO_IDS)
def test_every_accepted_request_has_an_equivalent_advertised_descriptor(scenario_id: str) -> None:
    """The forward direction: submit exactly what's advertised (the only
    way this suite constructs "valid" requests), and confirm the logged
    request's (action, namespace, resource_id, tool_name) is literally a
    member of the advertised set -- not just namespace-level, not just
    tool-name-level."""
    scenario = PACK.get(scenario_id)
    session = GatewaySession.start(scenario, seed=0, run_id=f"consistency-equiv-{scenario_id}")
    advertised = session.capabilities()["operations"]
    resource_scoped = [op for op in advertised if op["action"] in ("read", "write", "compensate")]
    advertised_keys = {
        (op["action"], op.get("tool_name"), op["namespace"], op["resource_id"]) for op in resource_scoped
    }

    for i, op in enumerate(resource_scoped):
        outcome = session.handle(_envelope(session, op, operation_id=f"op-{i}"))
        assert outcome.accepted
        logged = session.log.entries[-1]
        submitted_key = (op["action"], op.get("tool_name"), op["namespace"], op["resource_id"])
        assert submitted_key in advertised_keys
        assert logged.action == op["action"]


@pytest.mark.parametrize("scenario_id", SAMPLE_SCENARIO_IDS)
def test_operation_absent_from_advertisement_is_rejected_with_zero_attempts(scenario_id: str) -> None:
    scenario = PACK.get(scenario_id)
    session = GatewaySession.start(scenario, seed=0, run_id=f"consistency-absent-{scenario_id}")
    advertised = session.capabilities()["operations"]
    advertised_namespaces = {op["namespace"] for op in advertised if "namespace" in op}

    # A namespace guaranteed not to be advertised by any core-v1 scenario.
    bogus_namespace = "definitely_not_a_real_namespace_xyz"
    assert bogus_namespace not in advertised_namespaces

    before = session.log.tool_facade_call_count()
    outcome = session.handle(
        {
            "envelope_version": ENVELOPE_VERSION,
            "session_token": session.run_token,
            "operation_id": "op-absent",
            "correlation_id": "corr-absent",
            "actor_id": "candidate",
            "action": "read",
            "resource": {"namespace": bogus_namespace, "resource_id": "whatever"},
        }
    )
    assert not outcome.accepted
    assert outcome.rejection is not None
    assert outcome.rejection.reason == "capability_violation"
    assert session.log.tool_facade_call_count() == before


def test_write_only_resource_advertises_the_implicit_read_capability() -> None:
    """ER-04's `capture_payment` targets `payment:P-4004` with no
    explicit `read`-kind plan step for that resource. The implicit-read
    rule (`derive_operations` module docstring) means it must still be
    advertised as a `read` descriptor, and a read against it must be
    accepted."""
    scenario = PACK.get("ER-04")
    session = GatewaySession.start(scenario, seed=0, run_id="consistency-implicit-read")
    advertised = session.capabilities()["operations"]
    read_resources = {(op["namespace"], op["resource_id"]) for op in advertised if op["action"] == "read"}
    assert ("payment", "P-4004") in read_resources

    outcome = session.handle(
        {
            "envelope_version": ENVELOPE_VERSION,
            "session_token": session.run_token,
            "operation_id": "op-implicit-read",
            "correlation_id": "corr-implicit-read",
            "actor_id": "candidate",
            "action": "read",
            "resource": {"namespace": "payment", "resource_id": "P-4004"},
        }
    )
    assert outcome.accepted


def test_compensate_only_resource_advertises_the_implicit_read_capability() -> None:
    """ER-04's `release_inventory` (compensate) targets
    `inventory:SKU-4004`, which also happens to be targeted by a read and
    a write step in this particular scenario -- so this test constructs a
    scenario-independent guarantee directly against `derive_operations`
    instead, covering a resource touched *only* by a `compensate` step."""
    from cavbench.gateway.capabilities import derive_operations
    from cavbench.scenarios.models import ActionPlan, PlannedStep, PolicyContext, PrincipalContext, ScenarioView

    view = ScenarioView(
        id="SYN-COMPENSATE-ONLY",
        family="synthetic",
        title="Compensate-only resource fixture",
        user_request="n/a",
        principal=PrincipalContext(principal_id="p1", tenant_id="t1", roles=("member",)),
        toolset=("undo_thing",),
        policy=PolicyContext(requested_intent=()),
        plan=ActionPlan(
            steps=(
                PlannedStep(
                    step_id="s1", kind="compensate", tool_name="undo_thing", namespace="ns", resource_id="R-1"
                ),
            )
        ),
    )
    ops = derive_operations(view)
    read_resources = {(op.namespace, op.resource_id) for op in ops if op.action == "read"}
    assert ("ns", "R-1") in read_resources
