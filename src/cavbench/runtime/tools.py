"""Adapter-facing tool facade.

This is the *only* path an execution adapter has into the environment. It
exposes read/write/status/escalate/clarify verbs and returns a uniform
:class:`ToolResult` envelope. It never exposes the scenario oracle, the raw
state store, or the ledger.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

from cavbench.runtime.environment import BenchmarkEnvironment
from cavbench.scenarios.models import JSONValue

# Benchmark-owned, fixed mapping from tool name to side-effect taxonomy.
# This is static vocabulary, not scenario-specific logic.
TOOL_EFFECT_TYPE: dict[str, str] = {
    "cancel_order": "cancel_order",
    "cancel_order_item": "cancel_item",
    "issue_refund": "refund",
    "change_shipping_address": "change_address",
    "reserve_inventory": "reserve_inventory",
    "release_inventory": "release_inventory",
    "apply_account_credit": "apply_credit",
    "book_service_slot": "book_slot",
    "export_customer_data": "export_customer_data",
    "capture_payment": "capture_payment",
    "update_carrier_address": "update_carrier_address",
    "escalate_case": "escalate_case",
}

READ_TOOLS: dict[str, str] = {
    "order": "get_order",
    "payment": "get_payment",
    "inventory": "get_inventory",
    "account": "get_account",
    "slot": "get_service_slot",
    "reservation": "get_reservation",
    "carrier": "get_carrier_status",
    "accounts_aggregate": "get_accounts_aggregate",
}


@dataclass(frozen=True)
class ToolResult:
    status: str
    data: Mapping[str, JSONValue] | None = None
    operation_id: str | None = None
    retryable: bool = False
    message: str | None = None


@dataclass
class ToolFacade:
    """Adapter-visible entry point into the benchmark environment."""

    _env: BenchmarkEnvironment = field(repr=False)

    def read(self, namespace: str, resource_id: str, *, tool_name: str | None = None) -> ToolResult:
        name = tool_name or READ_TOOLS.get(namespace, f"get_{namespace}")
        value = self._env.read(namespace, resource_id, tool_name=name)
        return ToolResult(status="OK", data=value)

    def write(
        self,
        *,
        step_id: str,
        tool_name: str,
        namespace: str,
        resource_id: str,
        changes: Mapping[str, JSONValue],
        args: Mapping[str, JSONValue],
        logical_operation_id: str,
        idempotency_key: str | None,
        expected_version: int | None = None,
        compensation_for: str | None = None,
    ) -> ToolResult:
        effect_type = TOOL_EFFECT_TYPE.get(tool_name, tool_name)
        response = self._env.commit(
            step_id=step_id,
            tool_name=tool_name,
            effect_type=effect_type,
            namespace=namespace,
            resource_id=resource_id,
            changes=changes,
            logical_operation_id=logical_operation_id,
            idempotency_key=idempotency_key,
            expected_version=expected_version,
            args=args,
            compensation_for=compensation_for,
        )
        status = response["status"]
        retryable = status in ("CONFLICT", "AMBIGUOUS", "FAILED")
        return ToolResult(
            status=status,
            data=response.get("state"),
            operation_id=logical_operation_id,
            retryable=retryable,
        )

    def status_check(self, *, idempotency_key: str) -> ToolResult:
        response = self._env.status_check(idempotency_key=idempotency_key)
        return ToolResult(status=response["status"], data={"found": response["found"]})

    def escalate(self, reason: str, *, logical_operation_id: str) -> ToolResult:
        self._env.escalate(reason, logical_operation_id=logical_operation_id)
        return ToolResult(status="CREATED", message=reason)

    def clarify(self, question: str) -> ToolResult:
        self._env.clarify(question)
        return ToolResult(status="CLARIFICATION_REQUESTED", message=question)
