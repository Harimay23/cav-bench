"""The harness-owned deterministic benchmark environment.

``BenchmarkEnvironment`` is the *only* component allowed to create a
``side_effect_commit`` event or append to the side-effect ledger. It owns
authoritative state, the fault scheduler, and the canonical trace. Execution
adapters never touch this class directly -- they see only
:class:`cavbench.runtime.tools.ToolFacade`.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Mapping

from cavbench.runtime.faults import FaultScheduler
from cavbench.runtime.ledger import SideEffect, SideEffectLedger
from cavbench.runtime.state import VersionedStateStore
from cavbench.runtime.trace import EpisodeTrace, TraceEvent
from cavbench.scenarios.models import InjectionSpec, JSONValue, ScenarioDefinition


class BenchmarkEnvironment:
    def __init__(self, scenario: ScenarioDefinition, *, seed: int = 0, run_id: str = "run") -> None:
        self.scenario = scenario
        self.seed = seed
        self.run_id = run_id
        self.state = VersionedStateStore(scenario.initial_state)
        self.ledger = SideEffectLedger()
        self.faults = FaultScheduler(scenario.injections)

        self._events: list[TraceEvent] = []
        self._seq = 0
        self._forced_failures: dict[str, str] = {}
        self._effect_by_key: dict[str, SideEffect] = {}

        self._record(
            "user_input",
            source="scenario",
            metadata={"text": scenario.view.user_request},
        )

    # -- trace plumbing ---------------------------------------------------

    def _record(self, event_type: str, *, source: str = "environment", **kwargs: JSONValue) -> TraceEvent:
        event = TraceEvent(seq=self._seq, logical_time=self._seq, event_type=event_type, source=source, **kwargs)
        self._seq += 1
        self._events.append(event)
        return event

    def _fire(self, hook: str) -> tuple[InjectionSpec, ...]:
        fired = self.faults.trigger(hook)
        for injection in fired:
            self._apply_injection(injection)
        return fired

    def _apply_injection(self, injection: InjectionSpec) -> None:
        if injection.mode == "external_mutation":
            namespace = injection.payload["namespace"]
            resource_id = injection.payload["resource_id"]
            changes = injection.payload["changes"]
            before = self.state.get(namespace, resource_id)
            result = self.state.mutate(namespace, resource_id, changes)
            self._record(
                "external_mutation",
                resource_refs=[f"{namespace}:{resource_id}"],
                versions_before={f"{namespace}:{resource_id}": before.get("version")},
                versions_after={f"{namespace}:{resource_id}": result.after.get("version")},
                fault_id=injection.fault_id,
                response_status=injection.mode,
                metadata={"changes": dict(changes)},
            )
        elif injection.mode in ("downstream_failure", "compensation_failure"):
            # `affects_step` lets an earlier step's completion sabotage a
            # later one; when omitted, the hook is step-scoped
            # ("before_commit_step:<step_id>") and targets itself.
            affected_step = injection.payload.get("affects_step") or injection.hook.split(":", 1)[1]
            self._forced_failures[affected_step] = injection.mode
            self._record(
                "fault",
                fault_id=injection.fault_id,
                response_status=injection.mode,
                metadata={"affects_step": affected_step},
            )
        elif injection.mode == "ambiguous_response":
            self._record("fault", fault_id=injection.fault_id, response_status=injection.mode, metadata={})
        else:
            self._record("fault", fault_id=injection.fault_id, response_status=injection.mode, metadata=dict(injection.payload))

    # -- reads --------------------------------------------------------------

    def read(self, namespace: str, resource_id: str, *, tool_name: str) -> dict[str, JSONValue]:
        value = self.state.get(namespace, resource_id)
        self._record(
            "tool_read",
            tool_name=tool_name,
            args={"resource_id": resource_id},
            resource_refs=[f"{namespace}:{resource_id}"],
            versions_before={f"{namespace}:{resource_id}": value.get("version")},
            response_status="OK",
            metadata={"result": deepcopy(value)},
        )
        self._fire(f"after_read:{namespace}:{resource_id}")
        return value

    # -- writes / consequential commits --------------------------------------

    def commit(
        self,
        *,
        step_id: str,
        tool_name: str,
        effect_type: str,
        namespace: str,
        resource_id: str,
        changes: Mapping[str, JSONValue],
        logical_operation_id: str,
        idempotency_key: str | None,
        expected_version: int | None = None,
        args: Mapping[str, JSONValue] | None = None,
        compensation_for: str | None = None,
    ) -> dict[str, JSONValue]:
        args = dict(args or {})
        resource_ref = f"{namespace}:{resource_id}"

        before = self.state.get(namespace, resource_id)
        self._record(
            "tool_call_attempt",
            tool_name=tool_name,
            args=args,
            resource_refs=[resource_ref],
            versions_before={resource_ref: before.get("version")},
            logical_operation_id=logical_operation_id,
            idempotency_key=idempotency_key,
        )

        self._fire(f"before_commit_step:{step_id}")
        self._fire(f"before_commit:{tool_name}:{namespace}:{resource_id}")

        if step_id in self._forced_failures:
            reason = self._forced_failures.pop(step_id)
            self._record(
                "commit_rejected",
                tool_name=tool_name,
                args=args,
                resource_refs=[resource_ref],
                logical_operation_id=logical_operation_id,
                idempotency_key=idempotency_key,
                response_status="FAILED",
                metadata={"reason": reason},
            )
            return {"status": "FAILED", "committed": False}

        current = self.state.get(namespace, resource_id)
        current_version = current.get("version")

        if expected_version is not None and current_version != expected_version:
            self._record(
                "commit_rejected",
                tool_name=tool_name,
                args=args,
                resource_refs=[resource_ref],
                logical_operation_id=logical_operation_id,
                idempotency_key=idempotency_key,
                response_status="CONFLICT",
                metadata={"expected_version": expected_version, "actual_version": current_version},
            )
            return {"status": "CONFLICT", "committed": False, "state": current}

        if idempotency_key and idempotency_key in self._effect_by_key:
            self._record(
                "commit_rejected",
                tool_name=tool_name,
                args=args,
                resource_refs=[resource_ref],
                logical_operation_id=logical_operation_id,
                idempotency_key=idempotency_key,
                response_status="IDEMPOTENT_REPLAY",
                metadata={},
            )
            return {"status": "IDEMPOTENT_REPLAY", "committed": False, "state": current}

        result = self.state.mutate(namespace, resource_id, changes)
        effect = SideEffect(
            effect_id=f"eff-{self.ledger.next_seq()}",
            seq=self._seq,
            effect_type=effect_type,
            logical_operation_id=logical_operation_id,
            idempotency_key=idempotency_key,
            resource_ref=resource_ref,
            payload=args,
            compensation_for=compensation_for,
        )
        _, appended = self.ledger.append(effect)
        if idempotency_key and appended:
            self._effect_by_key[idempotency_key] = effect

        self._record(
            "side_effect_commit",
            tool_name=tool_name,
            args=args,
            resource_refs=[resource_ref],
            versions_before={resource_ref: current_version},
            versions_after={resource_ref: result.after.get("version")},
            logical_operation_id=logical_operation_id,
            idempotency_key=idempotency_key,
            response_status="COMMITTED",
            metadata={"effect_id": effect.effect_id, "effect_type": effect_type},
        )

        self._fire(f"after_commit_step:{step_id}")
        self._fire(f"after_commit:{tool_name}:{namespace}:{resource_id}")
        ambiguous = bool(self._fire(f"after_commit_before_response:{tool_name}:{namespace}:{resource_id}"))
        if ambiguous:
            return {
                "status": "AMBIGUOUS",
                "committed": True,
                "logical_operation_id": logical_operation_id,
                "idempotency_key": idempotency_key,
                "state": result.after,
            }
        return {"status": "COMMITTED", "committed": True, "state": result.after}

    def status_check(self, *, idempotency_key: str, tool_name: str = "get_operation_status") -> dict[str, JSONValue]:
        effect = self._effect_by_key.get(idempotency_key)
        found = effect is not None
        self._record(
            "operation_status_read",
            tool_name=tool_name,
            args={"idempotency_key": idempotency_key},
            idempotency_key=idempotency_key,
            response_status="COMMITTED" if found else "NOT_FOUND",
            metadata={"effect_id": effect.effect_id} if effect else {},
        )
        return {"status": "COMMITTED" if found else "NOT_FOUND", "found": found}

    def escalate(self, reason: str, *, logical_operation_id: str) -> None:
        effect = SideEffect(
            effect_id=f"eff-{self.ledger.next_seq()}",
            seq=self._seq,
            effect_type="escalate_case",
            logical_operation_id=logical_operation_id,
            idempotency_key=logical_operation_id,
            resource_ref=f"case:{self.scenario.id}",
            payload={"reason": reason},
        )
        self.ledger.append(effect)
        self._record(
            "escalation",
            tool_name="escalate_case",
            args={"reason": reason},
            resource_refs=[f"case:{self.scenario.id}"],
            logical_operation_id=logical_operation_id,
            response_status="CREATED",
            metadata={"effect_id": effect.effect_id},
        )

    def clarify(self, question: str) -> None:
        self._record("clarification", metadata={"question": question})

    def run_error(self, message: str) -> None:
        self._record("run_error", response_status="ERROR", metadata={"message": message})

    # -- finalize -------------------------------------------------------------

    def finalize(self, adapter_report: Mapping[str, JSONValue]) -> EpisodeTrace:
        return EpisodeTrace(
            schema_version="1.0",
            scenario_id=self.scenario.id,
            run_id=self.run_id,
            seed=self.seed,
            adapter_name=str(adapter_report.get("adapter_name", "unknown")),
            adapter_version=str(adapter_report.get("adapter_version", "0.0.0")),
            events=tuple(self._events),
            final_state=self.state.snapshot(),
            side_effects=self.ledger.as_dicts(),
            adapter_report=dict(adapter_report),
        )
