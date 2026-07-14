"""Adapter-facing session: scenario view + tool facade only.

This is deliberately the narrowest possible surface. It cannot reach the
scenario oracle, the raw state store, the ledger, or evaluator internals --
see ``cavbench.scenarios.models.ScenarioView`` for exactly what is visible.
"""

from __future__ import annotations

from dataclasses import dataclass

from cavbench.runtime.tools import ToolFacade
from cavbench.scenarios.models import ScenarioView


@dataclass
class AdapterSession:
    _scenario: ScenarioView
    _tools: ToolFacade

    @property
    def scenario(self) -> ScenarioView:
        return self._scenario

    @property
    def tools(self) -> ToolFacade:
        return self._tools

    def clarify(self, question: str) -> None:
        self._tools.clarify(question)

    def escalate(self, reason: str) -> None:
        self._tools.escalate(reason, logical_operation_id=f"escalate:{self._scenario.id}")
