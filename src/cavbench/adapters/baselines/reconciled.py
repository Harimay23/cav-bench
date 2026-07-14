"""A3 -- Commit-Guarded + Reconciliation.

Adds stable idempotency keys and operation-status reconciliation for
ambiguous or delayed operation results on top of the commit guard.
"""

from __future__ import annotations

from cavbench.adapters.baselines._engine import BaselineEngine, Capabilities

reconciled_executor = BaselineEngine(
    "reconciled",
    "1.0.0",
    Capabilities(
        intent_authority_gate=True,
        commit_time_state_guard=True,
        idempotency_reconciliation=True,
    ),
)
