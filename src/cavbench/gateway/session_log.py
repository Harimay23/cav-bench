"""The redacted, append-only gateway/session log (GPI-FR-011, design's
"Observability and audit evidence").

The session log is deliberately *not* the benchmark trace: it records every
wire exchange (including gateway-level rejections, which never touch
`ToolFacade` and therefore never appear in the trace), joined by
`correlation_id`/`operation_id` so a reviewer can reconcile
wire -> trace -> ledger -> evaluation using only run artifacts.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from cavbench.gateway.redaction import redact


@dataclass(frozen=True)
class SessionLogEntry:
    seq: int
    kind: str  # "request" | "rejection"
    action: str | None
    correlation_id: str | None
    operation_id: str | None
    normalized_status: str | None
    tool_facade_call: bool
    detail: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "seq": self.seq,
            "kind": self.kind,
            "action": self.action,
            "correlation_id": self.correlation_id,
            "operation_id": self.operation_id,
            "normalized_status": self.normalized_status,
            "tool_facade_call": self.tool_facade_call,
            "detail": dict(self.detail),
        }


@dataclass
class GatewaySessionLog:
    session_id: str
    entries: list[SessionLogEntry] = field(default_factory=list)
    _seq: int = 0

    def record_request(
        self,
        *,
        action: str,
        correlation_id: str | None,
        operation_id: str | None,
        normalized_status: str,
        tool_facade_call: bool,
        raw_envelope: dict[str, Any],
        response: dict[str, Any],
    ) -> SessionLogEntry:
        entry = SessionLogEntry(
            seq=self._seq,
            kind="request",
            action=action,
            correlation_id=correlation_id,
            operation_id=operation_id,
            normalized_status=normalized_status,
            tool_facade_call=tool_facade_call,
            detail=redact({"request": raw_envelope, "response": response}),
        )
        self._seq += 1
        self.entries.append(entry)
        return entry

    def record_rejection(
        self,
        *,
        reason: str,
        correlation_id: str | None,
        raw_envelope: dict[str, Any],
    ) -> SessionLogEntry:
        entry = SessionLogEntry(
            seq=self._seq,
            kind="rejection",
            action=None,
            correlation_id=correlation_id,
            operation_id=None,
            normalized_status=None,
            tool_facade_call=False,
            detail=redact({"reason": reason, "request": raw_envelope}),
        )
        self._seq += 1
        self.entries.append(entry)
        return entry

    def record_discovery(self, *, advertisement: dict[str, Any]) -> SessionLogEntry:
        """Record one capability-discovery call (GPI-FR-009). Never a
        `ToolFacade` call. `advertisement` is exactly what was returned to
        the candidate, so this entry's `detail.advertisement` equals the
        wire response byte-for-byte (after redaction, which is a no-op
        here since capability advertisements never carry a run token or
        oracle content by construction)."""
        entry = SessionLogEntry(
            seq=self._seq,
            kind="discovery",
            action="discover_capabilities",
            correlation_id=None,
            operation_id=None,
            normalized_status=None,
            tool_facade_call=False,
            detail=redact({"advertisement": advertisement}),
        )
        self._seq += 1
        self.entries.append(entry)
        return entry

    def tool_facade_call_count(self) -> int:
        return sum(1 for entry in self.entries if entry.tool_facade_call)

    def to_list(self) -> list[dict[str, Any]]:
        return [entry.to_dict() for entry in self.entries]
