"""Deterministic, hook-based fault and mutation scheduler.

Injections are declared on the scenario (benchmark-owned) and fire
automatically when the environment reaches the matching hook during
execution -- they are never hand-sequenced by an adapter or fixture author.
Trigger order is deterministic: hook, then ordinal, then fault_id. Each
injection fires at most once per episode.
"""

from __future__ import annotations

from collections import defaultdict

from cavbench.scenarios.models import InjectionSpec


class FaultScheduler:
    def __init__(self, injections: tuple[InjectionSpec, ...]) -> None:
        self._by_hook: dict[str, list[InjectionSpec]] = defaultdict(list)
        for injection in sorted(injections, key=lambda i: (i.hook, i.ordinal, i.fault_id)):
            self._by_hook[injection.hook].append(injection)
        self._fired: set[str] = set()
        self.triggered: list[str] = []

    def trigger(self, hook: str) -> tuple[InjectionSpec, ...]:
        fired: list[InjectionSpec] = []
        for injection in self._by_hook.get(hook, ()):
            if injection.fault_id in self._fired:
                continue
            self._fired.add(injection.fault_id)
            self.triggered.append(injection.fault_id)
            fired.append(injection)
        return tuple(fired)

    def pending_hooks(self) -> tuple[str, ...]:
        return tuple(sorted(self._by_hook.keys()))
