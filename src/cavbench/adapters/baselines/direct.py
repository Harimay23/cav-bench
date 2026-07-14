"""A0 -- Direct Tool Executor.

Executes tool actions without a dedicated intent/authority gate,
commit-time state guard, ambiguous-result reconciliation, or recovery
coordinator.
"""

from __future__ import annotations

from cavbench.adapters.baselines._engine import BaselineEngine, Capabilities

direct_executor = BaselineEngine("direct", "1.0.0", Capabilities())
