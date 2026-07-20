"""The protocol-neutral gateway core (M-GPI-1).

Implements the approved topology from
``docs/design/generic-protocol-integration.md`` and
``docs/program/approvals/M-GPI-1.md``:

    Candidate (protocol client)
      -> GatewaySession.handle() [this module]
        -> ToolFacade (existing, unchanged)
          -> BenchmarkEnvironment + SideEffectLedger (sole effect executor
             and sole commit authority)
        -> authoritative ToolResult
      -> normalized ResponseEnvelope back to the candidate

Transport frontends (``cavbench.gateway.rest``) are thin: they only
translate wire bytes into a dict, call :meth:`GatewaySession.handle`, and
translate the returned outcome back into wire bytes. All protocol-neutral
behavior -- envelope validation, authentication, capability enforcement,
the request-to-``ToolFacade`` mapping, response normalization, redaction,
session logging, capability advertisement, and final-report intake -- lives
here, once.

**The request-to-attempt invariant:** every *accepted tool-operation*
request (``read``, ``write``, ``compensate``, ``status_check``,
``escalate``, ``clarify``) maps to exactly one ``ToolFacade`` invocation.
Final-report submission (``report``) is an accepted *non-tool* request and
maps to zero ``ToolFacade`` invocations by design -- it only sets the
input to a later :meth:`GatewaySession.finalize` call. A request rejected
at the gateway level (malformed envelope, authentication failure, unknown
action, or a capability violation) is not "accepted" in this sense and
therefore also maps to zero ``ToolFacade`` invocations.
"""

from __future__ import annotations

import copy
import hmac
import secrets
from collections.abc import Mapping
from dataclasses import dataclass, field

from cavbench.gateway.capabilities import (
    OperationDescriptor,
    derive_operations,
    operations_by_action_and_tool,
    readable_resources,
)
from cavbench.gateway.envelope import (
    ENVELOPE_VERSION,
    STATUS_ACCEPTED,
    STATUS_CREATED,
    STATUS_NOT_FOUND,
    STATUS_OK,
    GatewayRejection,
    RequestEnvelope,
    ResponseEnvelope,
)
from cavbench.gateway.errors import (
    AuthenticationError,
    CapabilityViolationError,
    EnvelopeError,
    UnknownOperationError,
)
from cavbench.gateway.session_log import GatewaySessionLog
from cavbench.runtime.environment import BenchmarkEnvironment
from cavbench.runtime.tools import ToolFacade, ToolResult
from cavbench.runtime.trace import EpisodeTrace
from cavbench.scenarios.models import JSONValue, ScenarioDefinition

# Non-write actions the gateway understands beyond a bare tool name. A
# `write`/`compensate` action's actual tool name comes from
# `resource.tool_name` and must appear in `ScenarioView.toolset` (capability
# discovery already advertised only those names -- see `capabilities()`).
ACTION_READ = "read"
ACTION_WRITE = "write"
ACTION_COMPENSATE = "compensate"
ACTION_STATUS_CHECK = "status_check"
ACTION_ESCALATE = "escalate"
ACTION_CLARIFY = "clarify"
ACTION_REPORT = "report"

KNOWN_ACTIONS = (
    ACTION_READ,
    ACTION_WRITE,
    ACTION_COMPENSATE,
    ACTION_STATUS_CHECK,
    ACTION_ESCALATE,
    ACTION_CLARIFY,
    ACTION_REPORT,
)

# ToolResult.status -> normalized benchmark-level outcome status
# (GPI-FR-004). `ambiguous` is emitted only when the environment's own
# deterministic fault hooks produced it -- the gateway never invents or
# resolves it (it just relays the ToolResult it received).
_WRITE_STATUS_MAP: Mapping[str, str] = {
    "COMMITTED": "committed",
    "AMBIGUOUS": "ambiguous",
    "FAILED": "failed",
    "CONFLICT": "rejected",
    "IDEMPOTENT_REPLAY": "rejected",
}


@dataclass(frozen=True)
class GatewayOutcome:
    """What :meth:`GatewaySession.handle` produced for one wire request."""

    accepted: bool  # False => gateway-level rejection, zero ToolFacade calls
    response: ResponseEnvelope | None = None
    rejection: GatewayRejection | None = None
    http_hint: str = "ok"  # "ok" | "conflict" | "failed" | "ambiguous" | "bad_request" | "unauthorized" | "not_found"


@dataclass
class GatewaySession:
    """Binds one benchmark session (a scenario episode) to one protocol
    session (a run token + session id) -- GPI-FR-001."""

    session_id: str
    run_token: str
    scenario: ScenarioDefinition
    environment: BenchmarkEnvironment
    tools: ToolFacade
    log: GatewaySessionLog
    finalized: bool = False
    _final_report: dict[str, JSONValue] | None = field(default=None, repr=False)
    _idempotency_by_operation: dict[str, str] = field(default_factory=dict, repr=False)
    _trace: EpisodeTrace | None = field(default=None, repr=False)
    _operations_cache: tuple[OperationDescriptor, ...] | None = field(default=None, repr=False)
    _advertisement_cache: dict[str, JSONValue] | None = field(default=None, repr=False)

    @classmethod
    def start(cls, scenario: ScenarioDefinition, *, seed: int = 0, run_id: str | None = None) -> GatewaySession:
        run_id = run_id or f"gateway::{scenario.id}"
        environment = BenchmarkEnvironment(scenario, seed=seed, run_id=run_id)
        tools = ToolFacade(environment)
        session_id = f"sess-{secrets.token_hex(8)}"
        run_token = secrets.token_urlsafe(24)
        return cls(
            session_id=session_id,
            run_token=run_token,
            scenario=scenario,
            environment=environment,
            tools=tools,
            log=GatewaySessionLog(session_id=session_id),
        )

    # -- capability discovery (GPI-FR-009) --------------------------------

    def _resource_scoped_operations(self) -> tuple[OperationDescriptor, ...]:
        """The canonical, memoized capability model for this session's
        scenario -- see `cavbench.gateway.capabilities`. Computed once:
        the underlying `ScenarioView` is immutable for the session's
        lifetime, so every call is guaranteed to see the same frozen set
        of descriptors. Both `capabilities()` (advertisement) and
        `_check_capability()` (enforcement) read from this single source,
        so they cannot diverge."""
        if self._operations_cache is None:
            self._operations_cache = derive_operations(self.scenario.view)
        return self._operations_cache

    def _canonical_advertisement(self) -> dict[str, JSONValue]:
        """Build (once) and cache the canonical capability advertisement.
        This exact object is never handed to a caller -- `capabilities()`
        and `discover_capabilities()` each return their own independent
        deep copy of it, so no caller can mutate what any other caller
        (or the session log, or a later discovery call) sees."""
        if self._advertisement_cache is not None:
            return self._advertisement_cache

        view = self.scenario.view
        operations: list[dict[str, JSONValue]] = [
            {"action": ACTION_STATUS_CHECK, "description": "Reconcile an operation by idempotency_key."},
            {"action": ACTION_ESCALATE, "description": "Escalate the case for manual handling."},
            {"action": ACTION_CLARIFY, "description": "Request clarification."},
            {"action": ACTION_REPORT, "description": "Submit the untrusted final completion report."},
        ]
        for descriptor in self._resource_scoped_operations():
            payload = descriptor.to_dict()
            payload["description"] = (
                f"Read {descriptor.namespace}:{descriptor.resource_id}."
                if descriptor.action == ACTION_READ
                else f"{descriptor.action.capitalize()} operation {descriptor.tool_name!r} "
                f"on {descriptor.namespace}:{descriptor.resource_id}."
            )
            operations.append(payload)

        advertisement: dict[str, JSONValue] = {
            "envelope_version": ENVELOPE_VERSION,
            "session_id": self.session_id,
            "scenario_id": view.id,
            "scenario_title": view.title,
            "toolset": list(view.toolset),
            "operations": operations,
        }
        self._advertisement_cache = advertisement
        return advertisement

    def capabilities(self) -> dict[str, JSONValue]:
        """A fresh, independent deep copy of the operations available in
        this scenario, derived only from the adapter-visible
        `ScenarioView` -- never the oracle. Pure: does not touch the
        session log. Use `discover_capabilities()` to advertise *and* log
        (GPI-FR-009).

        Every call returns a brand-new structure: mutating the returned
        dict (or anything nested inside it) can never affect the
        canonical internal snapshot, any other call's return value, or
        anything already recorded in the session log."""
        return copy.deepcopy(self._canonical_advertisement())

    def discover_capabilities(self) -> dict[str, JSONValue]:
        """The candidate-facing capability-discovery operation
        (`GET /capabilities`): returns a fresh deep copy of the same
        frozen advertisement `capabilities()` always returns for this
        session, and records an independent deep copy of that same
        content in the session log every time it is called (GPI-FR-009).
        Repeated discovery is deterministic by construction: the
        advertisement is computed once and cached (see
        `_resource_scoped_operations`), so every logged entry's
        `advertisement` field is identical in *content*, while each call
        still gets its own log entry (auditable: a reviewer can see
        exactly how many times, and when, the candidate asked) and its
        own independent object (mutating what one call returned, or what
        one log entry stored, can never reach any other)."""
        canonical = self._canonical_advertisement()
        self.log.record_discovery(advertisement=copy.deepcopy(canonical))
        return copy.deepcopy(canonical)

    # -- capability enforcement (review follow-up: scenario-visible allowlist,
    # enforced before any ToolFacade call, never derived from the oracle,
    # and never a separate model from what capabilities() advertises) -----

    def _check_capability(self, envelope: RequestEnvelope) -> None:
        """Verify the requested operation is actually advertised by
        `capabilities()` for this scenario, before any `ToolFacade` call.
        `status_check`/`escalate`/`clarify` are session/case-level
        facilities every scenario advertises unconditionally (see
        `capabilities()`), so they carry no additional restriction here."""
        if envelope.action == ACTION_READ:
            self._check_read_capability(
                namespace=str(envelope.resource["namespace"]), resource_id=str(envelope.resource["resource_id"])
            )
        elif envelope.action in (ACTION_WRITE, ACTION_COMPENSATE):
            self._check_write_capability(
                action=envelope.action,
                tool_name=str(envelope.resource.get("tool_name", "")),
                namespace=str(envelope.resource["namespace"]),
                resource_id=str(envelope.resource["resource_id"]),
            )

    def _check_read_capability(self, *, namespace: str, resource_id: str) -> None:
        visible = readable_resources(self._resource_scoped_operations())
        if (namespace, resource_id) not in visible:
            raise CapabilityViolationError(
                f"resource {namespace}:{resource_id} is not scenario-visible for reading "
                f"(advertised resources: {sorted(f'{ns}:{rid}' for ns, rid in visible)!r})"
            )

    def _check_write_capability(self, *, action: str, tool_name: str, namespace: str, resource_id: str) -> None:
        operations = self._resource_scoped_operations()
        matching_action = operations_by_action_and_tool(operations, action=action, tool_name=tool_name)
        other_action = ACTION_COMPENSATE if action == ACTION_WRITE else ACTION_WRITE

        if not matching_action:
            matching_other = operations_by_action_and_tool(operations, action=other_action, tool_name=tool_name)
            if matching_other:
                raise CapabilityViolationError(
                    f"tool {tool_name!r} is advertised as a {other_action!r} operation, not {action!r} "
                    f"-- write and compensate operations are not interchangeable"
                )
            known_tools = sorted({op.tool_name for op in operations if op.action == action and op.tool_name})
            raise CapabilityViolationError(
                f"tool {tool_name!r} is not an advertised {action!r} operation for this scenario "
                f"(advertised {action} tools: {known_tools!r})"
            )

        if not any(op.namespace == namespace and op.resource_id == resource_id for op in matching_action):
            if any(op.namespace == namespace for op in matching_action):
                advertised_resources = sorted(op.resource_id for op in matching_action if op.namespace == namespace)
                raise CapabilityViolationError(
                    f"resource_id {resource_id!r} is not advertised for {action!r} tool {tool_name!r} "
                    f"under namespace {namespace!r} (advertised resource_id(s): {advertised_resources!r})"
                )
            advertised_namespaces = sorted({op.namespace for op in matching_action})
            raise CapabilityViolationError(
                f"tool {tool_name!r} is advertised under namespace(s) {advertised_namespaces!r} for {action!r}, "
                f"not {namespace!r}"
            )

    # -- request handling: the request-to-attempt boundary ------------------

    def handle(self, raw: Mapping[str, JSONValue]) -> GatewayOutcome:
        """Handle exactly one wire request.

        Every accepted tool-operation request maps to exactly one
        ``ToolFacade`` invocation. Final-report submission is an accepted
        non-tool request and maps to zero ``ToolFacade`` invocations by
        design (see module docstring). A malformed envelope, an
        authentication failure, an unknown action, or a capability
        violation (an unadvertised or mismatched tool/namespace/action) is
        rejected here without ever reaching ``ToolFacade``.
        """
        raw_dict = dict(raw) if isinstance(raw, Mapping) else {}
        correlation_id = raw_dict.get("correlation_id") if isinstance(raw_dict.get("correlation_id"), str) else None

        try:
            envelope = RequestEnvelope.from_dict(raw)
        except EnvelopeError as exc:
            self.log.record_rejection(reason="malformed_envelope", correlation_id=correlation_id, raw_envelope=raw_dict)
            return GatewayOutcome(
                accepted=False,
                rejection=GatewayRejection(reason="malformed_envelope", detail=str(exc), correlation_id=correlation_id),
                http_hint="bad_request",
            )

        try:
            self._authenticate(envelope)
        except AuthenticationError as exc:
            self.log.record_rejection(
                reason="authentication_failed", correlation_id=envelope.correlation_id, raw_envelope=raw_dict
            )
            return GatewayOutcome(
                accepted=False,
                rejection=GatewayRejection(
                    reason="authentication_failed", detail=str(exc), correlation_id=envelope.correlation_id
                ),
                http_hint="unauthorized",
            )

        if envelope.action not in KNOWN_ACTIONS:
            self.log.record_rejection(
                reason="unknown_operation", correlation_id=envelope.correlation_id, raw_envelope=raw_dict
            )
            return GatewayOutcome(
                accepted=False,
                rejection=GatewayRejection(
                    reason="unknown_operation",
                    detail=f"no such action {envelope.action!r}",
                    correlation_id=envelope.correlation_id,
                ),
                http_hint="not_found",
            )

        return self._dispatch(envelope, raw_dict)

    def _authenticate(self, envelope: RequestEnvelope) -> None:
        if not hmac.compare_digest(envelope.session_token, self.run_token):
            raise AuthenticationError("session_token does not match this session's issued run token")

    def _dispatch(self, envelope: RequestEnvelope, raw_dict: dict[str, JSONValue]) -> GatewayOutcome:
        action = envelope.action

        if action == ACTION_REPORT:
            # Untrusted subject claims: recorded for finalize(), never a
            # ToolFacade call and never influences any normalized status
            # (GPI-FR-010).
            self._final_report = dict(envelope.parameters)
            response = ResponseEnvelope(
                envelope_version=ENVELOPE_VERSION,
                correlation_id=envelope.correlation_id,
                operation_id=envelope.operation_id,
                status=STATUS_ACCEPTED,
                data=None,
            )
            self._log_request(envelope, raw_dict, response, tool_facade_call=False)
            return GatewayOutcome(accepted=True, response=response, http_hint="ok")

        try:
            self._check_capability(envelope)
        except CapabilityViolationError as exc:
            self.log.record_rejection(
                reason="capability_violation", correlation_id=envelope.correlation_id, raw_envelope=raw_dict
            )
            return GatewayOutcome(
                accepted=False,
                rejection=GatewayRejection(
                    reason="capability_violation", detail=str(exc), correlation_id=envelope.correlation_id
                ),
                http_hint="not_found",
            )

        result: ToolResult
        status: str
        http_hint = "ok"

        if action == ACTION_READ:
            namespace = str(envelope.resource["namespace"])
            resource_id = str(envelope.resource["resource_id"])
            result = self.tools.read(namespace, resource_id)
            status = STATUS_OK

        elif action in (ACTION_WRITE, ACTION_COMPENSATE):
            result, status, http_hint = self._dispatch_write(envelope)

        elif action == ACTION_STATUS_CHECK:
            idempotency_key = self._resolve_reconciliation_key(envelope)
            if idempotency_key is None:
                self.log.record_rejection(
                    reason="unknown_operation_id", correlation_id=envelope.correlation_id, raw_envelope=raw_dict
                )
                return GatewayOutcome(
                    accepted=False,
                    rejection=GatewayRejection(
                        reason="unknown_operation_id",
                        detail=f"no prior write is known for operation_id {envelope.operation_id!r}",
                        correlation_id=envelope.correlation_id,
                    ),
                    http_hint="not_found",
                )
            result = self.tools.status_check(idempotency_key=idempotency_key)
            status = STATUS_OK if result.status == "COMMITTED" else STATUS_NOT_FOUND

        elif action == ACTION_ESCALATE:
            reason = str(envelope.parameters.get("reason", "candidate-requested escalation"))
            result = self.tools.escalate(reason, logical_operation_id=envelope.operation_id)
            status = STATUS_CREATED

        elif action == ACTION_CLARIFY:
            question = str(envelope.parameters.get("question", ""))
            result = self.tools.clarify(question)
            status = "clarification_requested"

        else:  # pragma: no cover - guarded by the KNOWN_ACTIONS/toolset check in handle()
            raise UnknownOperationError(f"unhandled action {action!r}")

        response = ResponseEnvelope(
            envelope_version=ENVELOPE_VERSION,
            correlation_id=envelope.correlation_id,
            operation_id=envelope.operation_id,
            status=status,
            data=result.data,
            message=result.message,
        )
        self._log_request(envelope, raw_dict, response, tool_facade_call=True)
        return GatewayOutcome(accepted=True, response=response, http_hint=http_hint)

    def _dispatch_write(self, envelope: RequestEnvelope) -> tuple[ToolResult, str, str]:
        resource = envelope.resource
        namespace = str(resource["namespace"])
        resource_id = str(resource["resource_id"])
        tool_name = str(resource.get("tool_name", envelope.action))
        compensation_for = envelope.parameters.get("compensation_for") if envelope.action == ACTION_COMPENSATE else None

        result = self.tools.write(
            step_id=str(envelope.parameters.get("step_id", envelope.operation_id)),
            tool_name=tool_name,
            namespace=namespace,
            resource_id=resource_id,
            changes=envelope.parameters.get("changes", {}),
            args=envelope.parameters.get("args", {}),
            logical_operation_id=envelope.operation_id,
            idempotency_key=envelope.idempotency_key,
            expected_version=envelope.expected_version,
            compensation_for=compensation_for,
        )
        if envelope.idempotency_key:
            # Remember what the *candidate itself* supplied for this
            # operation_id, so a later explicit status_check can reconcile
            # by operation_id (GPI-FR-006) without the gateway generating or
            # repairing any identity.
            self._idempotency_by_operation[envelope.operation_id] = envelope.idempotency_key
        status = _WRITE_STATUS_MAP.get(result.status, "failed")
        http_hint = {"committed": "ok", "ambiguous": "ambiguous", "failed": "failed", "rejected": "conflict"}[status]
        return result, status, http_hint

    def _resolve_reconciliation_key(self, envelope: RequestEnvelope) -> str | None:
        if envelope.idempotency_key:
            return envelope.idempotency_key
        return self._idempotency_by_operation.get(envelope.operation_id)

    def _log_request(
        self,
        envelope: RequestEnvelope,
        raw_dict: dict[str, JSONValue],
        response: ResponseEnvelope,
        *,
        tool_facade_call: bool,
    ) -> None:
        self.log.record_request(
            action=envelope.action,
            correlation_id=envelope.correlation_id,
            operation_id=envelope.operation_id,
            normalized_status=response.status,
            tool_facade_call=tool_facade_call,
            raw_envelope=raw_dict,
            response=response.to_dict(),
        )

    # -- finalize -----------------------------------------------------------

    def finalize(self) -> EpisodeTrace:
        """Close the session and produce the canonical `EpisodeTrace`.

        The candidate's final report (if any was submitted via the
        `report` action) is carried through exactly as `AdapterResult`
        metadata is for every other integration -- untrusted comparison
        input, never commit truth (GPI-FR-010).
        """
        if self.finalized and self._trace is not None:
            return self._trace
        report = dict(self._final_report) if self._final_report is not None else {}
        report.setdefault("adapter_name", "generic-protocol-candidate")
        report.setdefault("adapter_version", "0.0.0")
        report.setdefault("final_message", report.get("final_message", ""))
        report.setdefault("completion_status", report.get("completion_status", "success"))
        trace = self.environment.finalize(report)
        self.finalized = True
        self._trace = trace
        return trace
