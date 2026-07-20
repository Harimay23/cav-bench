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

**Implicit read rule:** a scenario's plan rarely declares an explicit
`read`-kind step for every resource a candidate legitimately needs to
read (a well-behaved candidate reads a resource before writing or
compensating it, exactly as the reference candidate and every baseline
profile do). Rather than advertise a narrower set of reads than
enforcement actually allows -- the divergence a prior review caught --
`derive_operations` synthesizes exactly one `read` descriptor for every
unique `(namespace, resource_id)` referenced by *any* resource-scoped
step (`read`, `write`, or `compensate`), deduplicated by
`(action="read", namespace, resource_id)`. There is no separate,
broader "readable" allowlist anywhere else: the synthesized `read`
descriptors returned by this function *are* both the advertisement and
the enforcement boundary for reads.
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
    oracle.

    Two passes over the plan, in step order:

    1. Every unique `(namespace, resource_id)` touched by any
       resource-scoped step (`read`, `write`, or `compensate`) gets
       exactly one synthesized `read` descriptor -- see "Implicit read
       rule" in the module docstring. This is the *only* place read
       visibility is decided; there is no separate broader allowlist.
    2. Every `write`/`compensate` step contributes its own descriptor,
       deduplicated by the full `(action, tool_name, namespace,
       resource_id)` key -- first occurrence wins.

    Read descriptors are listed first (in first-touched order), followed
    by write/compensate descriptors in plan order.
    """
    read_seen: set[tuple[str, str]] = set()
    read_operations: list[OperationDescriptor] = []
    write_seen: set[tuple[str, str | None, str, str]] = set()
    write_operations: list[OperationDescriptor] = []

    for step in view.plan.steps:
        if step.kind not in _RESOURCE_SCOPED_KINDS or not step.namespace or not step.resource_id:
            continue

        resource_key = (step.namespace, step.resource_id)
        if resource_key not in read_seen:
            read_seen.add(resource_key)
            read_operations.append(
                OperationDescriptor(action=ACTION_READ, namespace=step.namespace, resource_id=step.resource_id)
            )

        if step.kind in (ACTION_WRITE, ACTION_COMPENSATE) and step.tool_name:
            action = ACTION_WRITE if step.kind == "write" else ACTION_COMPENSATE
            descriptor = OperationDescriptor(
                action=action, namespace=step.namespace, resource_id=step.resource_id, tool_name=step.tool_name
            )
            key = descriptor.key()
            if key not in write_seen:
                write_seen.add(key)
                write_operations.append(descriptor)

    return tuple(read_operations) + tuple(write_operations)


def readable_resources(operations: tuple[OperationDescriptor, ...]) -> frozenset[tuple[str, str]]:
    """Every `(namespace, resource_id)` pair scenario-visible for `read` --
    exactly the resources carrying a synthesized `read` descriptor in
    `operations` (see `derive_operations`' "Implicit read rule"). This is
    read *enforcement's* boundary, and it is definitionally identical to
    what is *advertised*, since both come from the same `read` descriptors."""
    return frozenset((op.namespace, op.resource_id) for op in operations if op.action == ACTION_READ)


def operations_by_action_and_tool(
    operations: tuple[OperationDescriptor, ...], *, action: str, tool_name: str
) -> tuple[OperationDescriptor, ...]:
    """All descriptors matching this exact `(action, tool_name)` pair --
    there may be more than one if the same tool is visible against
    multiple resources or namespaces under this action."""
    return tuple(op for op in operations if op.action == action and op.tool_name == tool_name)
