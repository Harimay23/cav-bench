"""Immutable domain models for scenarios, oracles, and scenario packs.

These types are the boundary between scenario JSON documents and the rest of
the runtime. ``ScenarioView`` is everything an execution adapter is allowed to
see. ``ScenarioOracle`` is benchmark-private and must never be handed to an
adapter through a normal runtime API (see ``cavbench.runtime.session``).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from cavbench.util import freeze as _freeze
from cavbench.util import thaw as _thaw

JSONValue = Any

DIMENSIONS: tuple[str, ...] = (
    "intent_grounding",
    "authority_validity",
    "temporal_state_validity",
    "execution_integrity",
    "outcome_recoverability",
)


@dataclass(frozen=True)
class Predicate:
    """A small, deterministic, side-effect-free predicate over evaluation facts.

    Supported ops: eq, ne, lt, lte, gt, gte, in, not_in, exists, not_exists,
    count_eq, count_lte, count_gte, all, any, not.
    """

    op: str
    path: str | None = None
    value: JSONValue = None
    collection: str | None = None
    where: Mapping[str, JSONValue] = field(default_factory=dict)
    predicates: tuple[Predicate, ...] = ()
    description: str = ""
    dimension: str = ""
    failure_code: str = ""

    @classmethod
    def from_dict(cls, data: Mapping[str, JSONValue]) -> Predicate:
        return cls(
            op=data["op"],
            path=data.get("path"),
            value=data.get("value"),
            collection=data.get("collection"),
            where=_freeze(data.get("where", {})),
            predicates=tuple(cls.from_dict(p) for p in data.get("predicates", [])),
            description=data.get("description", ""),
            dimension=data.get("dimension", ""),
            failure_code=data.get("failure_code", ""),
        )

    def to_dict(self) -> dict[str, JSONValue]:
        payload: dict[str, JSONValue] = {"op": self.op}
        if self.path is not None:
            payload["path"] = self.path
        if self.value is not None:
            payload["value"] = self.value
        if self.collection is not None:
            payload["collection"] = self.collection
        if self.where:
            payload["where"] = _thaw(self.where)
        if self.predicates:
            payload["predicates"] = [p.to_dict() for p in self.predicates]
        if self.description:
            payload["description"] = self.description
        if self.dimension:
            payload["dimension"] = self.dimension
        if self.failure_code:
            payload["failure_code"] = self.failure_code
        return payload


@dataclass(frozen=True)
class PrincipalContext:
    principal_id: str
    tenant_id: str
    roles: tuple[str, ...]
    delegation: Mapping[str, JSONValue] | None = None

    @classmethod
    def from_dict(cls, data: Mapping[str, JSONValue]) -> PrincipalContext:
        delegation = data.get("delegation")
        return cls(
            principal_id=data["principal_id"],
            tenant_id=data["tenant_id"],
            roles=tuple(data.get("roles", ())),
            delegation=_freeze(delegation) if delegation is not None else None,
        )

    def to_dict(self) -> dict[str, JSONValue]:
        return {
            "principal_id": self.principal_id,
            "tenant_id": self.tenant_id,
            "roles": list(self.roles),
            "delegation": _thaw(self.delegation) if self.delegation is not None else None,
        }


@dataclass(frozen=True)
class PolicyContext:
    """Adapter-visible, mechanically-checkable statement of what the literal
    request authorizes. This is *not* the oracle: it describes what the
    request licenses, not whether any particular execution was valid.
    """

    requested_intent: tuple[str, ...]
    allowed_scope: Mapping[str, JSONValue] = field(default_factory=dict)
    ambiguous_reference: bool = False
    candidate_resources: tuple[str, ...] = ()
    on_block: str = "refuse"

    @classmethod
    def from_dict(cls, data: Mapping[str, JSONValue]) -> PolicyContext:
        return cls(
            requested_intent=tuple(data.get("requested_intent", ())),
            allowed_scope=_freeze(data.get("allowed_scope", {})),
            ambiguous_reference=bool(data.get("ambiguous_reference", False)),
            candidate_resources=tuple(data.get("candidate_resources", ())),
            on_block=data.get("on_block", "refuse"),
        )

    def to_dict(self) -> dict[str, JSONValue]:
        return {
            "requested_intent": list(self.requested_intent),
            "allowed_scope": _thaw(self.allowed_scope),
            "ambiguous_reference": self.ambiguous_reference,
            "candidate_resources": list(self.candidate_resources),
            "on_block": self.on_block,
        }


@dataclass(frozen=True)
class PlannedStep:
    """One adapter-visible candidate step of the task's mechanical action plan.

    This represents *what a request-following executor would attempt*, not
    whether it is valid to do so. Validity is derived independently by the
    evaluator from committed facts, never from this plan.
    """

    step_id: str
    kind: str  # read | write | escalate | clarify | status_check | compensate | respond
    tool_name: str | None = None
    namespace: str | None = None
    resource_id: str | None = None
    changes: Mapping[str, JSONValue] = field(default_factory=dict)
    args: Mapping[str, JSONValue] = field(default_factory=dict)
    action_category: str | None = None
    action_amount: float | None = None
    action_scope: Mapping[str, JSONValue] = field(default_factory=dict)
    logical_operation_id: str | None = None
    precondition: Predicate | None = None
    precondition_scope: str = "gate"
    narrowed: PlannedStep | None = None
    compensates: str | None = None
    compensation_step_id: str | None = None
    depends_on: str | None = None
    trigger: str = "always"
    on_failure: str = "compensate"

    @classmethod
    def from_dict(cls, data: Mapping[str, JSONValue]) -> PlannedStep:
        precondition = data.get("precondition")
        narrowed = data.get("narrowed")
        return cls(
            step_id=data["step_id"],
            kind=data["kind"],
            tool_name=data.get("tool_name"),
            namespace=data.get("namespace"),
            resource_id=data.get("resource_id"),
            changes=_freeze(data.get("changes", {})),
            args=_freeze(data.get("args", {})),
            action_category=data.get("action_category"),
            action_amount=data.get("action_amount"),
            action_scope=_freeze(data.get("action_scope", {})),
            logical_operation_id=data.get("logical_operation_id"),
            precondition=Predicate.from_dict(precondition) if precondition else None,
            precondition_scope=data.get("precondition_scope", "gate"),
            narrowed=cls.from_dict(narrowed) if narrowed else None,
            compensates=data.get("compensates"),
            compensation_step_id=data.get("compensation_step_id"),
            depends_on=data.get("depends_on"),
            trigger=data.get("trigger", "always"),
            on_failure=data.get("on_failure", "compensate"),
        )

    def to_dict(self) -> dict[str, JSONValue]:
        payload: dict[str, JSONValue] = {"step_id": self.step_id, "kind": self.kind}
        for attr in (
            "tool_name",
            "namespace",
            "resource_id",
            "action_category",
            "action_amount",
            "logical_operation_id",
            "compensates",
            "compensation_step_id",
            "depends_on",
        ):
            value = getattr(self, attr)
            if value is not None:
                payload[attr] = value
        if self.changes:
            payload["changes"] = _thaw(self.changes)
        if self.args:
            payload["args"] = _thaw(self.args)
        if self.action_scope:
            payload["action_scope"] = _thaw(self.action_scope)
        if self.precondition is not None:
            payload["precondition"] = self.precondition.to_dict()
            if self.precondition_scope != "gate":
                payload["precondition_scope"] = self.precondition_scope
        if self.narrowed is not None:
            payload["narrowed"] = self.narrowed.to_dict()
        if self.trigger != "always":
            payload["trigger"] = self.trigger
        if self.on_failure != "compensate":
            payload["on_failure"] = self.on_failure
        return payload


@dataclass(frozen=True)
class ActionPlan:
    steps: tuple[PlannedStep, ...]

    @classmethod
    def from_dict(cls, data: Mapping[str, JSONValue]) -> ActionPlan:
        return cls(steps=tuple(PlannedStep.from_dict(s) for s in data.get("steps", [])))

    def to_dict(self) -> dict[str, JSONValue]:
        return {"steps": [s.to_dict() for s in self.steps]}

    def step(self, step_id: str) -> PlannedStep:
        for s in self.steps:
            if s.step_id == step_id:
                return s
        raise KeyError(step_id)


@dataclass(frozen=True)
class ScenarioView:
    """Everything an execution adapter is allowed to see."""

    id: str
    family: str
    title: str
    user_request: str
    principal: PrincipalContext
    toolset: tuple[str, ...]
    policy: PolicyContext
    plan: ActionPlan

    def to_dict(self) -> dict[str, JSONValue]:
        return {
            "id": self.id,
            "family": self.family,
            "title": self.title,
            "user_request": self.user_request,
            "principal": self.principal.to_dict(),
            "toolset": list(self.toolset),
            "policy": self.policy.to_dict(),
            "plan": self.plan.to_dict(),
        }


@dataclass(frozen=True)
class RecoverySpec:
    """Recovery is conditionally applicable. When ``required`` is True, every
    predicate in ``obligations`` must hold against derived evaluation facts
    (default dimension: outcome_recoverability) for CVSR to pass.
    """

    required: bool = False
    obligations: tuple[Predicate, ...] = ()

    @classmethod
    def from_dict(cls, data: Mapping[str, JSONValue]) -> RecoverySpec:
        return cls(
            required=bool(data.get("required", False)),
            obligations=tuple(Predicate.from_dict(o) for o in data.get("obligations", [])),
        )

    def to_dict(self) -> dict[str, JSONValue]:
        return {"required": self.required, "obligations": [o.to_dict() for o in self.obligations]}


@dataclass(frozen=True)
class ScenarioOracle:
    """Benchmark-private evaluation configuration. Never exposed to adapters."""

    goal_predicates: tuple[Predicate, ...]
    forbidden_effects: tuple[Predicate, ...] = ()
    required_effects: tuple[Predicate, ...] = ()
    policy_constraints: tuple[Predicate, ...] = ()
    recovery: RecoverySpec = field(default_factory=RecoverySpec)
    dimension_focus: tuple[str, ...] = ()

    @classmethod
    def from_dict(cls, data: Mapping[str, JSONValue]) -> ScenarioOracle:
        return cls(
            goal_predicates=tuple(Predicate.from_dict(p) for p in data.get("goal_predicates", [])),
            forbidden_effects=tuple(Predicate.from_dict(p) for p in data.get("forbidden_effects", [])),
            required_effects=tuple(Predicate.from_dict(p) for p in data.get("required_effects", [])),
            policy_constraints=tuple(Predicate.from_dict(p) for p in data.get("policy_constraints", [])),
            recovery=RecoverySpec.from_dict(data.get("recovery", {})),
            dimension_focus=tuple(data.get("dimension_focus", ())),
        )

    def to_dict(self) -> dict[str, JSONValue]:
        return {
            "goal_predicates": [p.to_dict() for p in self.goal_predicates],
            "forbidden_effects": [p.to_dict() for p in self.forbidden_effects],
            "required_effects": [p.to_dict() for p in self.required_effects],
            "policy_constraints": [p.to_dict() for p in self.policy_constraints],
            "recovery": self.recovery.to_dict(),
            "dimension_focus": list(self.dimension_focus),
        }


@dataclass(frozen=True)
class InjectionSpec:
    fault_id: str
    hook: str
    ordinal: int
    mode: str
    payload: Mapping[str, JSONValue] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Mapping[str, JSONValue]) -> InjectionSpec:
        return cls(
            fault_id=data["fault_id"],
            hook=data["hook"],
            ordinal=int(data.get("ordinal", 1)),
            mode=data["mode"],
            payload=_freeze(data.get("payload", {})),
        )

    def to_dict(self) -> dict[str, JSONValue]:
        return {
            "fault_id": self.fault_id,
            "hook": self.hook,
            "ordinal": self.ordinal,
            "mode": self.mode,
            "payload": _thaw(self.payload),
        }


@dataclass(frozen=True)
class ScenarioDefinition:
    """Full internal representation of a scenario: adapter view + private oracle."""

    view: ScenarioView
    initial_state: Mapping[str, JSONValue]
    injections: tuple[InjectionSpec, ...]
    oracle: ScenarioOracle
    schema_version: str = "1.0"
    notes: str = ""

    @property
    def id(self) -> str:
        return self.view.id

    @property
    def family(self) -> str:
        return self.view.family

    @classmethod
    def from_dict(cls, data: Mapping[str, JSONValue]) -> ScenarioDefinition:
        task = data["task"]
        view = ScenarioView(
            id=data["id"],
            family=data["family"],
            title=data["title"],
            user_request=task["user_request"],
            principal=PrincipalContext.from_dict(task["principal"]),
            toolset=tuple(task.get("toolset", ())),
            policy=PolicyContext.from_dict(data.get("policy", {})),
            plan=ActionPlan.from_dict(data.get("plan", {})),
        )
        world = data["world"]
        return cls(
            view=view,
            initial_state=_freeze(world.get("initial_state", {})),
            injections=tuple(InjectionSpec.from_dict(i) for i in world.get("injections", [])),
            oracle=ScenarioOracle.from_dict(data["oracle"]),
            schema_version=data.get("schema_version", "1.0"),
            notes=data.get("notes", ""),
        )

    def to_dict(self) -> dict[str, JSONValue]:
        return {
            "schema_version": self.schema_version,
            "id": self.view.id,
            "family": self.view.family,
            "title": self.view.title,
            "task": {
                "user_request": self.view.user_request,
                "principal": self.view.principal.to_dict(),
                "toolset": list(self.view.toolset),
            },
            "policy": self.view.policy.to_dict(),
            "plan": self.view.plan.to_dict(),
            "world": {
                "initial_state": _thaw(self.initial_state),
                "injections": [i.to_dict() for i in self.injections],
            },
            "oracle": self.oracle.to_dict(),
            "notes": self.notes,
        }


@dataclass(frozen=True)
class ScenarioPack:
    pack_id: str
    pack_version: str
    schema_version: str
    description: str
    scenario_ids: tuple[str, ...]
    digest: str
    scenarios: Mapping[str, ScenarioDefinition]

    def __iter__(self) -> Any:
        return iter(self.scenarios[sid] for sid in self.scenario_ids)

    def __len__(self) -> int:
        return len(self.scenario_ids)

    def get(self, scenario_id: str) -> ScenarioDefinition:
        return self.scenarios[scenario_id]

    def families(self) -> Sequence[str]:
        seen: list[str] = []
        for sid in self.scenario_ids:
            fam = self.scenarios[sid].family
            if fam not in seen:
                seen.append(fam)
        return tuple(seen)
