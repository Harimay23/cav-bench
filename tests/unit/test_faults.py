from __future__ import annotations

from cavbench.runtime.faults import FaultScheduler
from cavbench.scenarios.models import InjectionSpec


def _mutation_injection(fault_id: str = "f1", *, ordinal: int = 1) -> InjectionSpec:
    return InjectionSpec(
        fault_id=fault_id, hook="after_read:order:O-1", ordinal=ordinal, mode="external_mutation", payload={}
    )


def test_fault_fires_only_on_matching_hook() -> None:
    scheduler = FaultScheduler((_mutation_injection(),))
    assert scheduler.trigger("unrelated_hook") == ()
    fired = scheduler.trigger("after_read:order:O-1")
    assert [f.fault_id for f in fired] == ["f1"]


def test_fault_fires_only_once() -> None:
    scheduler = FaultScheduler((_mutation_injection(),))
    scheduler.trigger("after_read:order:O-1")
    second_fire = scheduler.trigger("after_read:order:O-1")
    assert second_fire == ()
    assert scheduler.triggered == ["f1"]


def test_fault_trigger_order_is_deterministic_by_ordinal_then_id() -> None:
    scheduler = FaultScheduler(
        (
            InjectionSpec(fault_id="f-b", hook="h", ordinal=2, mode="external_mutation", payload={}),
            InjectionSpec(fault_id="f-a", hook="h", ordinal=1, mode="external_mutation", payload={}),
        )
    )
    fired = scheduler.trigger("h")
    assert [f.fault_id for f in fired] == ["f-a", "f-b"]
