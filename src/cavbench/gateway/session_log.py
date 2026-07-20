"""The redacted, append-only gateway/session log (GPI-FR-011, design's
"Observability and audit evidence").

The session log is deliberately *not* the benchmark trace: it records every
wire exchange (including gateway-level rejections, which never touch
`ToolFacade` and therefore never appear in the trace), joined by
`correlation_id`/`operation_id` so a reviewer can reconcile
wire -> trace -> ledger -> evaluation using only run artifacts.

Genuinely append-only and externally immutable: the only ways to add an
entry are `record_request`, `record_rejection`, and `record_discovery`.
Internal storage (`GatewaySessionLog._entries`) is never exposed; the
public `entries` property and `to_list()` both return fresh, fully
independent copies on every access, so nothing a caller does to a
previously returned entry, its `detail`, or a `to_list()` result can ever
reach back into what is actually stored.
"""

from __future__ import annotations

import copy
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from cavbench.gateway.redaction import redact


@dataclass(frozen=True)
class SessionLogEntry:
    seq: int
    kind: str  # "request" | "rejection" | "discovery"
    action: str | None
    correlation_id: str | None
    operation_id: str | None
    normalized_status: str | None
    tool_facade_call: bool
    detail: Mapping[str, Any] = field(default_factory=dict)

    def _copy(self) -> SessionLogEntry:
        """A new `SessionLogEntry` with an independently deep-copied
        `detail` -- `frozen=True` stops attribute *reassignment*, but does
        nothing to stop in-place mutation of a mutable `detail` a caller
        holds a direct reference to (`entry.detail["x"] = 1`), so a real
        defensive copy has to rebuild the container, not just the
        dataclass wrapper."""
        return SessionLogEntry(
            seq=self.seq,
            kind=self.kind,
            action=self.action,
            correlation_id=self.correlation_id,
            operation_id=self.operation_id,
            normalized_status=self.normalized_status,
            tool_facade_call=self.tool_facade_call,
            detail=copy.deepcopy(dict(self.detail)),
        )

    def to_dict(self) -> dict[str, Any]:
        """A fresh, independent deep copy of this entry as a plain dict.
        Mutating any nested container in the returned structure (e.g.
        `entry.to_dict()["detail"]["advertisement"]["operations"][0]`)
        can never reach back into the stored entry."""
        return {
            "seq": self.seq,
            "kind": self.kind,
            "action": self.action,
            "correlation_id": self.correlation_id,
            "operation_id": self.operation_id,
            "normalized_status": self.normalized_status,
            "tool_facade_call": self.tool_facade_call,
            "detail": copy.deepcopy(dict(self.detail)),
        }


@dataclass
class GatewaySessionLog:
    session_id: str
    _entries: list[SessionLogEntry] = field(default_factory=list, repr=False)
    _seq: int = 0

    @property
    def entries(self) -> tuple[SessionLogEntry, ...]:
        """A fresh tuple of defensive entry copies. Tuples cannot be
        cleared, appended to, or reordered in place, and each entry's
        `detail` is an independent deep copy -- so nothing obtained
        through this property can affect internal storage, a later call
        to `entries`, or any other previously returned entry."""
        return tuple(entry._copy() for entry in self._entries)  # noqa: SLF001 - same class, private helper

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
    ) -> None:
        self._append(
            kind="request",
            action=action,
            correlation_id=correlation_id,
            operation_id=operation_id,
            normalized_status=normalized_status,
            tool_facade_call=tool_facade_call,
            detail=redact({"request": raw_envelope, "response": response}),
        )

    def record_rejection(
        self,
        *,
        reason: str,
        correlation_id: str | None,
        raw_envelope: dict[str, Any],
    ) -> None:
        self._append(
            kind="rejection",
            action=None,
            correlation_id=correlation_id,
            operation_id=None,
            normalized_status=None,
            tool_facade_call=False,
            detail=redact({"reason": reason, "request": raw_envelope}),
        )

    def record_discovery(self, *, advertisement: dict[str, Any]) -> None:
        """Record one capability-discovery call (GPI-FR-009). Never a
        `ToolFacade` call. `advertisement` is exactly what was returned to
        the candidate, so this entry's `detail.advertisement` equals the
        wire response byte-for-byte (after redaction, which is a no-op
        here since capability advertisements never carry a run token or
        oracle content by construction)."""
        self._append(
            kind="discovery",
            action="discover_capabilities",
            correlation_id=None,
            operation_id=None,
            normalized_status=None,
            tool_facade_call=False,
            detail=redact({"advertisement": advertisement}),
        )

    def _append(
        self,
        *,
        kind: str,
        action: str | None,
        correlation_id: str | None,
        operation_id: str | None,
        normalized_status: str | None,
        tool_facade_call: bool,
        detail: dict[str, Any],
    ) -> None:
        """The single internal append path. `record_request`,
        `record_rejection`, and `record_discovery` are the only public
        entry points that reach it -- there is no other way to add,
        remove, or reorder an entry in `_entries`."""
        entry = SessionLogEntry(
            seq=self._seq,
            kind=kind,
            action=action,
            correlation_id=correlation_id,
            operation_id=operation_id,
            normalized_status=normalized_status,
            tool_facade_call=tool_facade_call,
            detail=detail,
        )
        self._seq += 1
        self._entries.append(entry)

    def tool_facade_call_count(self) -> int:
        return sum(1 for entry in self._entries if entry.tool_facade_call)

    def to_list(self) -> list[dict[str, Any]]:
        return [entry.to_dict() for entry in self._entries]
