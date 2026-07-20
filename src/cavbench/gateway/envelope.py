"""The common, transport-neutral protocol envelope (M-GPI-1, GPI-FR-002).

Schema at ``src/cavbench/gateway/schemas/envelope.schema.json``, documented
at ``docs/program/gateway/envelope.md``. Both REST (and any future
transport) frontends translate their wire format into a
:class:`RequestEnvelope` before handing it to
:class:`cavbench.gateway.core.GatewaySession`, and translate a
:class:`ResponseEnvelope` back out -- the envelope itself never depends on
any transport.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from importlib import resources
from typing import Any

import jsonschema

from cavbench.gateway.errors import EnvelopeError

ENVELOPE_VERSION = "1.0"

# Normalized benchmark-level outcome statuses (GPI-FR-004). These are the
# *only* statuses ever derived from an authoritative ToolResult; a gateway
# never invents or resolves "ambiguous" itself.
STATUS_COMMITTED = "committed"
STATUS_REJECTED = "rejected"
STATUS_FAILED = "failed"
STATUS_AMBIGUOUS = "ambiguous"
STATUS_OK = "ok"
STATUS_NOT_FOUND = "not_found"
STATUS_CREATED = "created"
STATUS_ACCEPTED = "accepted"

_SCHEMA: Mapping[str, Any] = json.loads(
    resources.files("cavbench.gateway.schemas").joinpath("envelope.schema.json").read_text()
)


def _load_schema() -> Mapping[str, Any]:
    return _SCHEMA


@dataclass(frozen=True)
class RequestEnvelope:
    """A candidate-issued request. Every field the candidate supplies is
    passed through to :class:`~cavbench.runtime.tools.ToolFacade`
    unmodified (GPI-FR-003): the gateway never generates, repairs, or
    regenerates ``operation_id``, ``idempotency_key``, or ``correlation_id``.
    """

    envelope_version: str
    session_token: str
    operation_id: str
    correlation_id: str
    actor_id: str
    action: str
    resource: Mapping[str, Any]
    idempotency_key: str | None = None
    parameters: Mapping[str, Any] = field(default_factory=dict)
    expected_version: int | None = None

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> RequestEnvelope:
        if not isinstance(data, Mapping):
            raise EnvelopeError("request envelope must be a JSON object")
        try:
            jsonschema.validate(instance=data, schema=_load_schema())
        except jsonschema.ValidationError as exc:
            raise EnvelopeError(f"envelope validation failed: {exc.message}") from exc
        if data["envelope_version"] != ENVELOPE_VERSION:
            raise EnvelopeError(
                f"unsupported envelope_version {data['envelope_version']!r} "
                f"(this gateway serves {ENVELOPE_VERSION!r})"
            )
        return cls(
            envelope_version=data["envelope_version"],
            session_token=data["session_token"],
            operation_id=data["operation_id"],
            correlation_id=data["correlation_id"],
            actor_id=data["actor_id"],
            action=data["action"],
            resource=dict(data["resource"]),
            idempotency_key=data.get("idempotency_key"),
            parameters=dict(data.get("parameters", {})),
            expected_version=data.get("expected_version"),
        )

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "envelope_version": self.envelope_version,
            "session_token": self.session_token,
            "operation_id": self.operation_id,
            "correlation_id": self.correlation_id,
            "actor_id": self.actor_id,
            "action": self.action,
            "resource": dict(self.resource),
        }
        if self.idempotency_key is not None:
            payload["idempotency_key"] = self.idempotency_key
        if self.parameters:
            payload["parameters"] = dict(self.parameters)
        if self.expected_version is not None:
            payload["expected_version"] = self.expected_version
        return payload


@dataclass(frozen=True)
class ResponseEnvelope:
    """The gateway's response to a benchmark-level (ToolFacade-backed)
    request. Always echoes ``correlation_id`` and the candidate-supplied
    ``operation_id`` unchanged (GPI-FR-003)."""

    envelope_version: str
    correlation_id: str
    operation_id: str
    status: str
    data: Mapping[str, Any] | None = None
    message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "envelope_version": self.envelope_version,
            "correlation_id": self.correlation_id,
            "operation_id": self.operation_id,
            "status": self.status,
            "data": dict(self.data) if self.data is not None else None,
            "message": self.message,
        }


@dataclass(frozen=True)
class GatewayRejection:
    """A gateway-level rejection: malformed envelope, unknown operation, or
    authentication failure. No :class:`~cavbench.runtime.tools.ToolFacade`
    call was made to produce this (GPI-FR-011)."""

    reason: str
    detail: str
    correlation_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "envelope_version": ENVELOPE_VERSION,
            "correlation_id": self.correlation_id,
            "reason": self.reason,
            "detail": self.detail,
        }
