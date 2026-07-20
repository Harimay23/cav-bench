"""The canonical scenario-visible capability model (M-GPI-1 review
follow-up).

Both `GatewaySession.capabilities()` (advertisement, GPI-FR-009) and
`GatewaySession._check_capability()` (enforcement, before any `ToolFacade`
call) must agree on exactly what operations a scenario makes visible to a
candidate. Before this module existed, advertisement and enforcement were
two separately-written, tool-name-keyed lookups that could silently
diverge and did not consider `resource_id` at all. This module is now the
single source of truth: one function, `derive_operations`, walks the
adapter-visible `ScenarioView.plan` once and produces the full set of
`OperationDescriptor`s. Everything else -- advertisement, enforcement,
tests, docs -- reads from it.

Deliberately **not** deduplicated by `tool_name` alone: two descriptors
are the same operation only if `(action, tool_name, namespace,
resource_id)` all match. The same tool name can validly appear more than
once with distinct descriptors -- under a different action, a different
namespace, or a different `resource_id` -- and each combination is
tracked and enforced independently. Write and compensate descriptors are
*not* claimed to be disjoint "by construction": nothing prevents a future
scenario pack from declaring the same tool name as both a `write` and a
`compensate` operation (over different resources, say); what makes them
non-interchangeable is that enforcement matches on the full descriptor
tuple, not that the two action buckets can never share a name.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from cavbench.scenarios.models import ScenarioView

ACTION_READ = "read"
ACTION_WRITE = "write"
ACTION_COMPENSATE = "compensate"

# Plan-step kinds that describe a resource-scoped operation the gateway
# advertises and enforces at the (action, tool_name, namespace,
# resource_id) level. Other kinds (`escalate`, `clarify`, `status_check`,
# `respond`) are session/case-level facilities handled generically -- see
# `GatewaySession.capabilities()`.
_RESOURCE_SCOPED_KINDS = {"read", ACTION_WRITE, ACTION_COMPENSATE}


@dataclass(frozen=True)
class OperationDescriptor:
    """One scenario-visible, resource-scoped operation.

    `tool_name` is `None` only for `read` (a read is not tool-scoped the
    way a write/compensate is -- `ToolFacade.read` takes no tool name).
    """

    action: str
    namespace: str
    resource_id: str
    tool_name: str | None = None

    def key(self) -> tuple[str, str | None, str, str]:
        """The full identity of this descriptor -- used for deduplication
        and lookup. Never `tool_name` alone."""
        return (self.action, self.tool_name, self.namespace, self.resource_id)

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "action": self.action,
            "namespace": self.namespace,
            "resource_id": self.resource_id,
        }
        if self.tool_name is not None:
            payload["tool_name"] = self.tool_name
        return payload


def derive_operations(view: ScenarioView) -> tuple[OperationDescriptor, ...]:
    """Derive every resource-scoped `OperationDescriptor` this scenario
    makes visible, from the adapter-visible plan alone -- never the
    oracle. Order is the plan's step order; duplicates (by the full
    descriptor key) are dropped, first occurrence wins."""
    seen: set[tuple[str, str | None, str, str]] = set()
    operations: list[OperationDescriptor] = []
    for step in view.plan.steps:
        if step.kind not in _RESOURCE_SCOPED_KINDS or not step.namespace or not step.resource_id:
            continue
        if step.kind == "read":
            descriptor = OperationDescriptor(action=ACTION_READ, namespace=step.namespace, resource_id=step.resource_id)
        else:
            if not step.tool_name:
                continue
            action = ACTION_WRITE if step.kind == "write" else ACTION_COMPENSATE
            descriptor = OperationDescriptor(
                action=action, namespace=step.namespace, resource_id=step.resource_id, tool_name=step.tool_name
            )
        key = descriptor.key()
        if key not in seen:
            seen.add(key)
            operations.append(descriptor)
    return tuple(operations)


def readable_resources(operations: tuple[OperationDescriptor, ...]) -> frozenset[tuple[str, str]]:
    """Every `(namespace, resource_id)` pair scenario-visible for `read`.

    A well-behaved candidate reads a resource before acting on it (as the
    reference candidate and every baseline profile do), so a resource is
    read-visible if *any* operation -- `read`, `write`, or `compensate`
    -- targets it, not only an explicit `read`-kind plan step."""
    return frozenset((op.namespace, op.resource_id) for op in operations)


def operations_by_action_and_tool(
    operations: tuple[OperationDescriptor, ...], *, action: str, tool_name: str
) -> tuple[OperationDescriptor, ...]:
    """All descriptors matching this exact `(action, tool_name)` pair --
    there may be more than one if the same tool is visible against
    multiple resources or namespaces under this action."""
    return tuple(op for op in operations if op.action == action and op.tool_name == tool_name)
