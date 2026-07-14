"""Canonical episode trace types.

``EpisodeTrace`` keeps a hard boundary between benchmark-owned facts
(``events``, ``final_state``, ``side_effects``) and the untrusted
``adapter_report``. Only benchmark-owned facts may be used by the evaluator to
derive scores; ``adapter_report`` exists so the evaluator can *compare*
adapter claims against derived truth (e.g. to detect a false success report),
never so it can *trust* them.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

from cavbench.scenarios.models import JSONValue
from cavbench.util import freeze as _freeze

EVENT_TYPES: tuple[str, ...] = (
    "user_input",
    "tool_read",
    "external_mutation",
    "tool_call_attempt",
    "commit_rejected",
    "side_effect_commit",
    "operation_status_read",
    "retry",
    "compensation_attempt",
    "compensation_result",
    "clarification",
    "escalation",
    "agent_message",
    "fault",
    "run_error",
)


@dataclass(frozen=True)
class TraceEvent:
    seq: int
    logical_time: int
    event_type: str
    source: str
    tool_name: str | None = None
    args: Mapping[str, JSONValue] | None = None
    resource_refs: tuple[str, ...] = ()
    versions_before: Mapping[str, int] = field(default_factory=dict)
    versions_after: Mapping[str, int] = field(default_factory=dict)
    logical_operation_id: str | None = None
    idempotency_key: str | None = None
    response_status: str | None = None
    fault_id: str | None = None
    metadata: Mapping[str, JSONValue] = field(default_factory=dict)

    def to_dict(self) -> dict[str, JSONValue]:
        return {
            "seq": self.seq,
            "logical_time": self.logical_time,
            "event_type": self.event_type,
            "source": self.source,
            "tool_name": self.tool_name,
            "args": dict(self.args) if self.args is not None else None,
            "resource_refs": list(self.resource_refs),
            "versions_before": dict(self.versions_before),
            "versions_after": dict(self.versions_after),
            "logical_operation_id": self.logical_operation_id,
            "idempotency_key": self.idempotency_key,
            "response_status": self.response_status,
            "fault_id": self.fault_id,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, JSONValue]) -> "TraceEvent":
        return cls(
            seq=data["seq"],
            logical_time=data.get("logical_time", data["seq"]),
            event_type=data["event_type"],
            source=data.get("source", "environment"),
            tool_name=data.get("tool_name"),
            args=_freeze(data.get("args")) if data.get("args") is not None else None,
            resource_refs=tuple(data.get("resource_refs", ())),
            versions_before=_freeze(data.get("versions_before", {})),
            versions_after=_freeze(data.get("versions_after", {})),
            logical_operation_id=data.get("logical_operation_id"),
            idempotency_key=data.get("idempotency_key"),
            response_status=data.get("response_status"),
            fault_id=data.get("fault_id"),
            metadata=_freeze(data.get("metadata", {})),
        )


@dataclass(frozen=True)
class EpisodeTrace:
    schema_version: str
    scenario_id: str
    run_id: str
    seed: int
    adapter_name: str
    adapter_version: str
    events: tuple[TraceEvent, ...]
    final_state: Mapping[str, JSONValue]
    side_effects: tuple[Mapping[str, JSONValue], ...]
    adapter_report: Mapping[str, JSONValue] = field(default_factory=dict)

    def to_dict(self) -> dict[str, JSONValue]:
        return {
            "schema_version": self.schema_version,
            "scenario_id": self.scenario_id,
            "run_id": self.run_id,
            "seed": self.seed,
            "adapter_name": self.adapter_name,
            "adapter_version": self.adapter_version,
            "events": [e.to_dict() for e in self.events],
            "final_state": dict(self.final_state),
            "side_effects": [dict(e) for e in self.side_effects],
            "adapter_report": dict(self.adapter_report),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, JSONValue]) -> "EpisodeTrace":
        return cls(
            schema_version=data.get("schema_version", "1.0"),
            scenario_id=data["scenario_id"],
            run_id=data["run_id"],
            seed=data["seed"],
            adapter_name=data.get("adapter_name", "unknown"),
            adapter_version=data.get("adapter_version", "0.0.0"),
            events=tuple(TraceEvent.from_dict(e) for e in data["events"]),
            final_state=_freeze(data["final_state"]),
            side_effects=tuple(_freeze(e) for e in data.get("side_effects", ())),
            adapter_report=_freeze(data.get("adapter_report", {})),
        )
