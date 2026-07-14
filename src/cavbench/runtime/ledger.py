"""Append-only side-effect ledger.

The ledger is benchmark truth for execution integrity: it records every
committed external effect independently of normalized object state, so that
e.g. two committed refunds remain visible even if the final payment object
collapses them into a single ``refunded`` total.

Only :mod:`cavbench.runtime.environment` may construct and append effects.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

from cavbench.scenarios.models import JSONValue
from cavbench.util import thaw as _thaw


@dataclass(frozen=True)
class SideEffect:
    effect_id: str
    seq: int
    effect_type: str
    logical_operation_id: str
    idempotency_key: str | None
    resource_ref: str
    payload: Mapping[str, JSONValue] = field(default_factory=dict)
    compensation_for: str | None = None

    def to_dict(self) -> dict[str, JSONValue]:
        return {
            "effect_id": self.effect_id,
            "seq": self.seq,
            "effect_type": self.effect_type,
            "logical_operation_id": self.logical_operation_id,
            "idempotency_key": self.idempotency_key,
            "resource_ref": self.resource_ref,
            "payload": _thaw(self.payload),
            "compensation_for": self.compensation_for,
        }


class SideEffectLedger:
    """Append-only for the lifetime of a single benchmark session.

    Idempotency is enforced on ``idempotency_key``: appending a second effect
    with a key already present returns the original effect and does not
    record a new one. Effects without an idempotency key are always appended,
    so callers that omit one (a naive execution strategy) can produce visible
    duplicates -- which is the point.
    """

    def __init__(self) -> None:
        self._effects: list[SideEffect] = []
        self._idempotency_index: dict[str, SideEffect] = {}
        self._next_seq = 0

    def append(self, effect: SideEffect) -> tuple[SideEffect, bool]:
        if effect.idempotency_key:
            existing = self._idempotency_index.get(effect.idempotency_key)
            if existing is not None:
                return existing, False
            self._idempotency_index[effect.idempotency_key] = effect
        self._effects.append(effect)
        return effect, True

    def effects(self) -> tuple[SideEffect, ...]:
        return tuple(self._effects)

    def as_dicts(self) -> tuple[dict[str, JSONValue], ...]:
        return tuple(e.to_dict() for e in self._effects)

    def count(
        self,
        *,
        effect_type: str | None = None,
        logical_operation_id: str | None = None,
        resource_ref: str | None = None,
    ) -> int:
        return sum(
            1
            for effect in self._effects
            if (effect_type is None or effect.effect_type == effect_type)
            and (logical_operation_id is None or effect.logical_operation_id == logical_operation_id)
            and (resource_ref is None or effect.resource_ref == resource_ref)
        )

    def next_seq(self) -> int:
        value = self._next_seq
        self._next_seq += 1
        return value

