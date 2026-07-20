"""Unit tests for the canonical capability model
(`cavbench.gateway.capabilities`), the single source of truth shared by
`GatewaySession.capabilities()` (advertisement) and
`GatewaySession._check_capability()` (enforcement) -- see the module
docstring for why a single model matters.

`core-v1` itself never reuses one tool name across distinct actions,
namespaces, or resource IDs within a scenario, so the "same tool name,
distinct descriptor" cases are exercised here against a small
hand-built `ScenarioView` rather than a real pack scenario.
"""

from __future__ import annotations

from cavbench.gateway.capabilities import (
    OperationDescriptor,
    derive_operations,
    operations_by_action_and_tool,
    readable_resources,
)
from cavbench.scenarios.models import (
    ActionPlan,
    PlannedStep,
    PolicyContext,
    PrincipalContext,
    ScenarioView,
)


def _view(steps: list[PlannedStep]) -> ScenarioView:
    return ScenarioView(
        id="SYN-01",
        family="synthetic",
        title="Synthetic capability-model fixture",
        user_request="n/a",
        principal=PrincipalContext(principal_id="p1", tenant_id="t1", roles=("member",)),
        toolset=("relabel_item",),
        policy=PolicyContext(requested_intent=()),
        plan=ActionPlan(steps=tuple(steps)),
    )


def test_same_tool_name_under_different_actions_are_distinct_descriptors() -> None:
    view = _view(
        [
            PlannedStep(step_id="s1", kind="write", tool_name="relabel_item", namespace="ns", resource_id="R-1"),
            PlannedStep(step_id="s2", kind="compensate", tool_name="relabel_item", namespace="ns", resource_id="R-1"),
        ]
    )
    ops = derive_operations(view)
    # 1 synthesized read (both steps target the same resource) + write + compensate
    assert len(ops) == 3
    assert OperationDescriptor("read", "ns", "R-1") in ops
    assert OperationDescriptor("write", "ns", "R-1", "relabel_item") in ops
    assert OperationDescriptor("compensate", "ns", "R-1", "relabel_item") in ops


def test_same_tool_name_under_different_namespaces_are_distinct_descriptors() -> None:
    view = _view(
        [
            PlannedStep(step_id="s1", kind="write", tool_name="relabel_item", namespace="ns-a", resource_id="R-1"),
            PlannedStep(step_id="s2", kind="write", tool_name="relabel_item", namespace="ns-b", resource_id="R-1"),
        ]
    )
    ops = derive_operations(view)
    # 2 synthesized reads (distinct namespaces) + 2 writes
    assert len(ops) == 4
    write_ops = [op for op in ops if op.action == "write"]
    assert len(write_ops) == 2
    namespaces = {op.namespace for op in write_ops}
    assert namespaces == {"ns-a", "ns-b"}


def test_same_tool_name_under_different_resource_ids_are_distinct_descriptors() -> None:
    view = _view(
        [
            PlannedStep(step_id="s1", kind="write", tool_name="relabel_item", namespace="ns", resource_id="R-1"),
            PlannedStep(step_id="s2", kind="write", tool_name="relabel_item", namespace="ns", resource_id="R-2"),
            PlannedStep(step_id="s3", kind="write", tool_name="relabel_item", namespace="ns", resource_id="R-3"),
        ]
    )
    ops = derive_operations(view)
    # 3 synthesized reads + 3 writes
    assert len(ops) == 6
    write_ops = [op for op in ops if op.action == "write"]
    resource_ids = {op.resource_id for op in write_ops}
    assert resource_ids == {"R-1", "R-2", "R-3"}

    r2_only = operations_by_action_and_tool(ops, action="write", tool_name="relabel_item")
    assert len(r2_only) == 3  # all three are the same (action, tool_name); resource_id still distinguishes them


def test_deduplication_is_by_full_descriptor_not_by_tool_name_alone() -> None:
    """An identical (action, tool_name, namespace, resource_id) tuple
    appearing twice (e.g. two plan steps that happen to target the same
    operation) collapses to one descriptor; anything that differs in any
    field does not."""
    view = _view(
        [
            PlannedStep(step_id="s1", kind="write", tool_name="relabel_item", namespace="ns", resource_id="R-1"),
            PlannedStep(step_id="s2", kind="write", tool_name="relabel_item", namespace="ns", resource_id="R-1"),
            PlannedStep(step_id="s3", kind="write", tool_name="relabel_item", namespace="ns", resource_id="R-2"),
        ]
    )
    ops = derive_operations(view)
    # reads: R-1 (from s1/s2, collapsed) + R-2 (from s3) = 2; writes: s1/s2 collapse, s3 distinct = 2
    assert len(ops) == 4
    write_ops = [op for op in ops if op.action == "write"]
    assert len(write_ops) == 2  # s1/s2 collapse; s3 is distinct


def test_read_visibility_includes_write_and_compensate_targeted_resources() -> None:
    """A resource targeted only by a `write` step (no explicit `read` step)
    is still read-visible -- a well-behaved candidate reads before it
    writes."""
    view = _view(
        [PlannedStep(step_id="s1", kind="write", tool_name="relabel_item", namespace="ns", resource_id="R-1")]
    )
    ops = derive_operations(view)
    assert ("ns", "R-1") in readable_resources(ops)


def test_operations_by_action_and_tool_returns_empty_for_unknown_pair() -> None:
    view = _view(
        [PlannedStep(step_id="s1", kind="write", tool_name="relabel_item", namespace="ns", resource_id="R-1")]
    )
    ops = derive_operations(view)
    assert operations_by_action_and_tool(ops, action="compensate", tool_name="relabel_item") == ()
    assert operations_by_action_and_tool(ops, action="write", tool_name="nonexistent_tool") == ()
