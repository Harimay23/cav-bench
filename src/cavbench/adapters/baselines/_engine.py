"""Shared, capability-parameterized execution engine for the five baseline
architecture profiles.

Every baseline (direct, policy_gated, commit_guarded, reconciled,
full_lifecycle) is the *same* generic engine, configured with a different
:class:`Capabilities` flag set. None of them special-case a scenario ID: they
only react to the scenario's adapter-visible ``policy`` envelope and
``plan``, plus the tool responses the environment actually returns. This is
what makes them controlled architecture baselines rather than a lookup table
of pre-baked outcomes.
"""

from __future__ import annotations

from dataclasses import dataclass

from cavbench.adapters.protocol import AdapterResult
from cavbench.evaluation.predicates import evaluate as evaluate_predicate
from cavbench.runtime.session import AdapterSession
from cavbench.scenarios.models import JSONValue, PlannedStep

MAX_WRITE_ATTEMPTS = 2


@dataclass(frozen=True)
class Capabilities:
    intent_authority_gate: bool = False
    commit_time_state_guard: bool = False
    idempotency_reconciliation: bool = False
    recovery_coordinator: bool = False


class BaselineEngine:
    def __init__(self, name: str, version: str, capabilities: Capabilities) -> None:
        self._name = name
        self._version = version
        self._caps = capabilities

    @property
    def name(self) -> str:
        return self._name

    @property
    def version(self) -> str:
        return self._version

    def run(self, session: AdapterSession) -> AdapterResult:
        return _Run(session, self._caps, self._name, self._version).execute()


class _Run:
    def __init__(self, session: AdapterSession, caps: Capabilities, name: str, version: str) -> None:
        self._session = session
        self._caps = caps
        self._name = name
        self._version = version
        self._scenario = session.scenario
        self._plan = session.scenario.plan
        self._status: dict[str, str] = {}
        self._notes: list[str] = []
        self._worst = "success"  # success > partial > pending_recovery > failed (severity order below)

    _SEVERITY = {"success": 0, "partial": 1, "pending_recovery": 2, "failed": 3}

    def _downgrade(self, status: str) -> None:
        if self._SEVERITY[status] > self._SEVERITY[self._worst]:
            self._worst = status

    def execute(self) -> AdapterResult:
        for step in self._plan.steps:
            if step.kind == "compensate":
                continue  # only invoked reactively from a failure handler
            if step.depends_on:
                dep_status = self._status.get(step.depends_on)
                if step.trigger == "on_dependency_success" and dep_status != "committed":
                    continue
                if step.trigger == "on_dependency_failure" and dep_status not in ("failed", "blocked"):
                    continue

            if step.kind == "read":
                self._read(step.namespace, step.resource_id)
                self._status[step.step_id] = "committed"
            elif step.kind == "write":
                self._status[step.step_id] = self._write_step(step)
            elif step.kind == "escalate":
                self._session.escalate(f"{step.step_id}: escalation required by task plan")
                self._status[step.step_id] = "escalated"
            elif step.kind == "clarify":
                self._session.clarify(f"{step.step_id}: clarification required by task plan")
                self._status[step.step_id] = "clarified"
            elif step.kind == "status_check":
                self._status[step.step_id] = "committed"

        return AdapterResult(
            final_message=self._final_message(),
            completion_status=self._worst,
            metadata={"adapter_name": self._name, "adapter_version": self._version, "notes": tuple(self._notes)},
        )

    def _final_message(self) -> str:
        if self._worst == "success":
            return "Request completed."
        if self._worst == "partial":
            return "Request partially completed; see diagnostics for unresolved items."
        if self._worst == "pending_recovery":
            return "Request could not be fully completed; escalated for manual recovery."
        return "Request could not be completed."

    def _read(self, namespace: str | None, resource_id: str | None) -> dict[str, JSONValue]:
        assert namespace is not None and resource_id is not None
        result = self._session.tools.read(namespace, resource_id)
        assert result.data is not None
        return dict(result.data)

    # -- policy gate ----------------------------------------------------

    def _apply_policy_gate(self, step: PlannedStep, observed: dict[str, JSONValue]) -> tuple[PlannedStep | None, str | None]:
        policy = self._scenario.policy
        principal = self._scenario.principal
        reasons: list[str] = []

        if policy.ambiguous_reference:
            reasons.append("ambiguous_reference")
        if step.action_category and policy.requested_intent and step.action_category not in policy.requested_intent:
            reasons.append("intent_mismatch")
        if step.precondition is not None and not evaluate_predicate(step.precondition, observed):
            reasons.append("precondition_failed")

        scope_violation = False
        max_amount = policy.allowed_scope.get("max_amount")
        if step.action_amount is not None and max_amount is not None and step.action_amount > max_amount:
            scope_violation = True
        wanted_items = step.action_scope.get("item_ids") if step.action_scope else None
        allowed_items = policy.allowed_scope.get("item_ids")
        if wanted_items and allowed_items is not None and not set(wanted_items).issubset(set(allowed_items)):
            scope_violation = True
        if scope_violation:
            reasons.append("scope_violation")

        owner = observed.get("owner")
        if owner is not None and owner != "self":
            reasons.append("authority_violation")
        tenant = observed.get("tenant")
        if tenant is not None and tenant != principal.tenant_id:
            reasons.append("tenant_violation")

        delegation_limit = principal.delegation.get("max_amount") if principal.delegation else None
        if step.action_amount is not None and delegation_limit is not None and step.action_amount > delegation_limit:
            reasons.append("delegation_limit")

        if not reasons:
            return step, None

        narrowable = {"scope_violation", "authority_violation", "tenant_violation", "delegation_limit"}
        if step.narrowed is not None and set(reasons) <= narrowable:
            return step.narrowed, None
        return None, reasons[0]

    def _apply_block_behavior(self, step: PlannedStep, reason: str | None) -> None:
        on_block = self._scenario.policy.on_block
        self._notes.append(f"{step.step_id} blocked: {reason}")
        if on_block == "escalate":
            self._session.escalate(f"{step.step_id} blocked ({reason}); requires approval")
            self._downgrade("pending_recovery")
        elif on_block == "clarify":
            self._session.clarify(f"{step.step_id} is ambiguous ({reason}); please clarify")
            self._downgrade("partial")
        # "respond_only" and "refuse" perform no further action: the step is
        # simply not executed, which is itself the correct behavior.

    # -- write execution --------------------------------------------------

    def _write_step(self, step: PlannedStep) -> str:
        assert step.namespace is not None and step.resource_id is not None
        observed = self._read(step.namespace, step.resource_id)
        acting_step = step

        if self._caps.intent_authority_gate:
            acting_step_or_none, reason = self._apply_policy_gate(step, observed)
            if acting_step_or_none is None:
                self._apply_block_behavior(step, reason)
                return "blocked"
            if acting_step_or_none is not step:
                acting_step = acting_step_or_none
                observed = self._read(acting_step.namespace, acting_step.resource_id)

        return self._commit_with_retries(acting_step, observed)

    def _derive_key(self, logical_operation_id: str, attempt: int) -> str:
        if self._caps.idempotency_reconciliation:
            return f"{self._scenario.id}:{logical_operation_id}"
        return f"{self._scenario.id}:{logical_operation_id}:attempt{attempt}"

    def _commit_with_retries(self, step: PlannedStep, observed: dict[str, JSONValue]) -> str:
        assert step.namespace is not None and step.resource_id is not None and step.logical_operation_id is not None
        for attempt in range(1, MAX_WRITE_ATTEMPTS + 1):
            expected_version = observed.get("version") if self._caps.commit_time_state_guard else None
            idempotency_key = self._derive_key(step.logical_operation_id, attempt)
            result = self._session.tools.write(
                step_id=step.step_id,
                tool_name=step.tool_name or "unknown_tool",
                namespace=step.namespace,
                resource_id=step.resource_id,
                changes=step.changes,
                args=step.args,
                logical_operation_id=step.logical_operation_id,
                idempotency_key=idempotency_key,
                expected_version=expected_version,
            )
            if result.status in ("COMMITTED", "IDEMPOTENT_REPLAY"):
                return "committed"
            if result.status == "CONFLICT":
                if not self._caps.commit_time_state_guard:
                    return "blocked"
                observed = self._read(step.namespace, step.resource_id)
                if step.precondition is not None and not evaluate_predicate(step.precondition, observed):
                    self._notes.append(f"{step.step_id} precondition false at commit time; not retried")
                    return "stale_blocked"
                continue
            if result.status == "AMBIGUOUS":
                if self._caps.idempotency_reconciliation:
                    status = self._session.tools.status_check(idempotency_key=idempotency_key)
                    if status.status == "COMMITTED":
                        return "committed"
                continue
            if result.status == "FAILED":
                return self._handle_downstream_failure(step)
        return "incomplete"

    # -- failure recovery ---------------------------------------------------

    def _handle_downstream_failure(self, step: PlannedStep) -> str:
        self._notes.append(f"{step.step_id} failed")
        if not self._caps.recovery_coordinator:
            # Naive profiles do not notice or react to the downstream
            # failure; they will go on to (falsely) report success.
            return "failed"

        if step.on_failure == "report_partial":
            self._downgrade("partial")
            return "partial"

        if step.on_failure == "escalate":
            self._session.escalate(f"{step.step_id} failed and requires manual resolution")
            self._downgrade("pending_recovery")
            return "pending_recovery"

        comp_step = next((s for s in self._plan.steps if s.compensates == step.step_id), None)
        if comp_step is None:
            self._session.escalate(f"{step.step_id} failed and cannot be compensated")
            self._downgrade("pending_recovery")
            return "pending_recovery"

        comp_result = self._commit_with_retries(comp_step, self._read(comp_step.namespace, comp_step.resource_id))
        if comp_result == "committed":
            self._downgrade("partial")
            return "partial"

        self._session.escalate(f"Compensation for {step.step_id} failed")
        self._downgrade("pending_recovery")
        return "pending_recovery"
