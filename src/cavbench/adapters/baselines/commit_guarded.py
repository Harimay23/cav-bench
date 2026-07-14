"""A2 -- Commit-Guarded Executor.

Adds version-aware commit-time validation against authoritative state on top
of the policy gate.
"""

from __future__ import annotations

from cavbench.adapters.baselines._engine import BaselineEngine, Capabilities

commit_guarded_executor = BaselineEngine(
    "commit_guarded",
    "1.0.0",
    Capabilities(intent_authority_gate=True, commit_time_state_guard=True),
)
