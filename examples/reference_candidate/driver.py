"""The deterministic reference candidate client (M-GPI-1, GPI-FR-014).

This is a **scripted test subject**, not measurement infrastructure and not
a production client library: it is project-authored, deterministic, and
exists so the gateway and its REST mapping can be exercised end-to-end in
tests and CI without any real external candidate. Its determinism claims
apply only to itself -- see
``docs/design/generic-protocol-integration.md`` ("Reference candidate vs.
candidate system").

It mirrors the shape of ``cavbench.adapters.baselines._engine`` (the same
four generic guard capabilities: ``intent_authority_gate``,
``commit_time_state_guard``, ``idempotency_reconciliation``,
``recovery_coordinator``) but drives the scenario entirely over the wire,
through :class:`~examples.reference_candidate.client.RestGatewayClient`,
never touching ``ToolFacade`` directly. It never repairs or regenerates the
identity fields it sends -- a "flawed" configuration blind-retries with a
*fresh* ``idempotency_key`` deliberately, to exercise the duplicate-effect
hazard the benchmark exists to measure.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from cavbench.scenarios.models import PlannedStep, ScenarioView
from examples.reference_candidate.client import RestGatewayClient

MAX_WRITE_ATTEMPTS = 4


@dataclass(frozen=True)
class CandidateCapabilities:
    """Same vocabulary as ``cavbench.adapters.baselines._engine.Capabilities``,
    parameterizing the reference candidate's wire behavior."""

    intent_authority_gate: bool = False
    commit_time_state_guard: bool = False
    idempotency_reconciliation: bool = False
    recovery_coordinator: bool = False


GUARDED = CandidateCapabilities(
    intent_authority_gate=True,
    commit_time_state_guard=True,
    idempotency_reconciliation=True,
    recovery_coordinator=True,
)
FLAWED = CandidateCapabilities()


@dataclass(frozen=True)
class CandidateRunResult:
    final_status: str  # "success" | "partial" | "pending_recovery" | "failed"
    step_status: dict[str, str]
    notes: tuple[str, ...]


class ReferenceCandidate:
    """Drives one scenario's adapter-visible plan against a gateway session
    over REST, using a fixed operation-id numbering scheme so two runs
    against the same scenario/capabilities produce byte-identical wire
    traffic (determinism, GPI-FR-015)."""

    def __init__(self, client: RestGatewayClient, view: ScenarioView, caps: CandidateCapabilities) -> None:
        self._client = client
        self._view = view
        self._caps = caps
        self._observed: dict[tuple[str, str], dict[str, Any]] = {}
        self._op_seq = 0
        self._notes: list[str] = []

    def _next_correlation_id(self, operation_id: str) -> str:
        self._op_seq += 1
        return f"{self._view.id}:{operation_id}:corr{self._op_seq}"

    def _envelope(
        self,
        *,
        action: str,
        operation_id: str,
        namespace: str,
        resource_id: str,
        tool_name: str | None = None,
        parameters: dict[str, Any] | None = None,
        idempotency_key: str | None = None,
        expected_version: int | None = None,
    ) -> dict[str, Any]:
        resource: dict[str, Any] = {"namespace": namespace, "resource_id": resource_id}
        if tool_name is not None:
            resource["tool_name"] = tool_name
        envelope: dict[str, Any] = {
            "envelope_version": "1.0",
            "operation_id": operation_id,
            "correlation_id": self._next_correlation_id(operation_id),
            "actor_id": self._view.principal.principal_id,
            "action": action,
            "resource": resource,
        }
        if parameters:
            envelope["parameters"] = parameters
        if idempotency_key is not None:
            envelope["idempotency_key"] = idempotency_key
        if expected_version is not None:
            envelope["expected_version"] = expected_version
        return envelope

    def _read(self, namespace: str, resource_id: str, *, operation_id: str) -> dict[str, Any]:
        envelope = self._envelope(
            action="read", operation_id=operation_id, namespace=namespace, resource_id=resource_id
        )
        response = self._client.submit(envelope)
        data = dict(response.body.get("data") or {})
        self._observed[(namespace, resource_id)] = data
        return data

    def _read_cached(self, namespace: str, resource_id: str, *, operation_id: str) -> dict[str, Any]:
        key = (namespace, resource_id)
        if key in self._observed:
            return self._observed[key]
        return self._read(namespace, resource_id, operation_id=operation_id)

    def _derive_key(self, logical_operation_id: str, attempt: int) -> str:
        if self._caps.idempotency_reconciliation:
            return f"{self._view.id}:{logical_operation_id}"
        return f"{self._view.id}:{logical_operation_id}:attempt{attempt}"

    def _apply_authority_gate(
        self, step: PlannedStep, observed: dict[str, Any]
    ) -> tuple[PlannedStep | None, str | None]:
        policy = self._view.policy
        principal = self._view.principal
        reasons: list[str] = []
        if policy.ambiguous_reference:
            reasons.append("ambiguous_reference")
        owner = observed.get("owner")
        if owner is not None and owner != "self":
            reasons.append("authority_violation")
        tenant = observed.get("tenant")
        if tenant is not None and tenant != principal.tenant_id:
            reasons.append("tenant_violation")
        max_amount = policy.allowed_scope.get("max_amount")
        if step.action_amount is not None and max_amount is not None and step.action_amount > max_amount:
            reasons.append("scope_violation")
        if not reasons:
            return step, None
        if step.narrowed is not None:
            return step.narrowed, None
        return None, reasons[0]

    def _write(self, step: PlannedStep) -> str:
        assert step.namespace is not None and step.resource_id is not None and step.logical_operation_id is not None
        observed = self._read_cached(step.namespace, step.resource_id, operation_id=step.logical_operation_id)
        acting_step = step

        if self._caps.intent_authority_gate:
            acting_step_or_none, reason = self._apply_authority_gate(step, observed)
            if acting_step_or_none is None:
                self._notes.append(f"{step.step_id} blocked: {reason}")
                return "blocked"
            if acting_step_or_none is not step:
                acting_step = acting_step_or_none
                observed = self._read(
                    acting_step.namespace, acting_step.resource_id, operation_id=step.logical_operation_id
                )

        # Capability enforcement requires a `compensate`-kind plan step to
        # be submitted as action="compensate" (never "write") -- the
        # gateway advertises write and compensate tools as disjoint,
        # non-interchangeable operations (docs/program/gateway/architecture.md
        # "Capability enforcement").
        action = "compensate" if acting_step.kind == "compensate" else "write"

        for attempt in range(1, MAX_WRITE_ATTEMPTS + 1):
            expected_version = observed.get("version") if self._caps.commit_time_state_guard else None
            idempotency_key = self._derive_key(acting_step.logical_operation_id or step.step_id, attempt)
            parameters: dict[str, Any] = {
                "step_id": acting_step.step_id,
                "changes": dict(acting_step.changes),
                "args": dict(acting_step.args),
            }
            if action == "compensate" and acting_step.compensates:
                parameters["compensation_for"] = acting_step.compensates
            envelope = self._envelope(
                action=action,
                operation_id=acting_step.logical_operation_id or step.step_id,
                namespace=acting_step.namespace or "",
                resource_id=acting_step.resource_id or "",
                tool_name=acting_step.tool_name,
                parameters=parameters,
                idempotency_key=idempotency_key,
                expected_version=expected_version,
            )
            response = self._client.submit(envelope)
            status = response.status

            if status == "committed":
                return "committed"
            if status == "rejected":
                if not self._caps.commit_time_state_guard:
                    return "blocked"
                observed = self._read(acting_step.namespace, acting_step.resource_id, operation_id=step.step_id)
                continue
            if status == "ambiguous":
                if self._caps.idempotency_reconciliation:
                    reconciled = self._client.reconcile(acting_step.logical_operation_id or step.step_id)
                    if reconciled.status == "ok":
                        return "committed"
                continue
            if status == "failed":
                return self._handle_failure(step)
        return "incomplete"

    def _handle_failure(self, step: PlannedStep) -> str:
        self._notes.append(f"{step.step_id} failed")
        if not self._caps.recovery_coordinator:
            return "failed"
        if step.compensation_step_id is None:
            envelope = self._envelope(
                action="escalate",
                operation_id=f"escalate:{step.step_id}",
                namespace="case",
                resource_id=self._view.id,
                parameters={"reason": f"{step.step_id} failed and cannot be compensated"},
            )
            self._client.submit(envelope)
            return "pending_recovery"
        comp_step = next((s for s in self._view.plan.steps if s.step_id == step.compensation_step_id), None)
        if comp_step is None:
            return "pending_recovery"
        result = self._write(comp_step)
        return "partial" if result == "committed" else "pending_recovery"

    def run(self) -> CandidateRunResult:
        step_status: dict[str, str] = {}
        for step in self._view.plan.steps:
            if step.kind == "compensate":
                continue
            if step.depends_on:
                dep_status = step_status.get(step.depends_on)
                if step.trigger == "on_dependency_success" and dep_status != "committed":
                    continue
                if step.trigger == "on_dependency_failure" and dep_status not in ("failed", "blocked"):
                    continue
            if step.kind == "read":
                self._read_cached(step.namespace or "", step.resource_id or "", operation_id=step.step_id)
                step_status[step.step_id] = "committed"
            elif step.kind == "write":
                step_status[step.step_id] = self._write(step)
            elif step.kind == "escalate":
                envelope = self._envelope(
                    action="escalate", operation_id=f"escalate:{step.step_id}", namespace="case",
                    resource_id=self._view.id, parameters={"reason": f"{step.step_id}: plan requires escalation"},
                )
                self._client.submit(envelope)
                step_status[step.step_id] = "escalated"
            elif step.kind == "clarify":
                envelope = self._envelope(
                    action="clarify", operation_id=f"clarify:{step.step_id}", namespace="case",
                    resource_id=self._view.id, parameters={"question": f"{step.step_id}: clarification required"},
                )
                self._client.submit(envelope)
                step_status[step.step_id] = "clarified"
            elif step.kind == "status_check":
                step_status[step.step_id] = "committed"

        severity = {"success": 0, "partial": 1, "pending_recovery": 2, "failed": 3}
        worst = "success"
        for status in step_status.values():
            mapped = {"committed": "success", "blocked": "success", "escalated": "pending_recovery",
                      "clarified": "partial", "partial": "partial", "pending_recovery": "pending_recovery",
                      "failed": "failed", "incomplete": "failed", "stale_blocked": "success"}.get(status, "success")
            if severity[mapped] > severity[worst]:
                worst = mapped

        report = {
            "adapter_name": "reference-protocol-candidate",
            "adapter_version": "0.1.0",
            "final_message": "Request completed." if worst == "success" else f"Request ended with status {worst}.",
            "completion_status": worst,
        }
        self._client.report(report)
        return CandidateRunResult(final_status=worst, step_status=step_status, notes=tuple(self._notes))
