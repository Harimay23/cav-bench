from __future__ import annotations

from cavbench.runtime.ledger import SideEffect, SideEffectLedger


def effect(seq: int, *, idempotency_key: str | None, logical_operation_id: str = "op-1") -> SideEffect:
    return SideEffect(
        effect_id=f"eff-{seq}",
        seq=seq,
        effect_type="refund",
        logical_operation_id=logical_operation_id,
        idempotency_key=idempotency_key,
        resource_ref="payment:P-1",
        payload={"amount": 10},
    )


def test_append_is_visible_and_ordered() -> None:
    ledger = SideEffectLedger()
    ledger.append(effect(0, idempotency_key="k1"))
    ledger.append(effect(1, idempotency_key="k2"))
    assert [e.effect_id for e in ledger.effects()] == ["eff-0", "eff-1"]


def test_same_idempotency_key_does_not_append_a_second_effect() -> None:
    ledger = SideEffectLedger()
    first, appended_first = ledger.append(effect(0, idempotency_key="same-key"))
    second, appended_second = ledger.append(effect(1, idempotency_key="same-key"))
    assert appended_first is True
    assert appended_second is False
    assert second is first
    assert ledger.count(logical_operation_id="op-1") == 1


def test_different_idempotency_keys_allow_a_harmful_duplicate_to_be_recorded() -> None:
    ledger = SideEffectLedger()
    ledger.append(effect(0, idempotency_key="k1"))
    ledger.append(effect(1, idempotency_key="k2"))
    # The ledger does not silently collapse distinct logical commits -- that
    # is exactly the fact the evaluator's execution-integrity check needs.
    assert ledger.count(logical_operation_id="op-1") == 2


def test_effects_without_idempotency_key_always_append() -> None:
    ledger = SideEffectLedger()
    ledger.append(effect(0, idempotency_key=None))
    ledger.append(effect(1, idempotency_key=None))
    assert ledger.count(logical_operation_id="op-1") == 2
