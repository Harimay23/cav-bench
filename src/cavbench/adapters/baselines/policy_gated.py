"""A1 -- Policy-Gated Executor.

Adds deterministic intent and authority checks before consequential tool
calls, but does not protect against state changes between observation and
commit.
"""

from __future__ import annotations

from cavbench.adapters.baselines._engine import BaselineEngine, Capabilities

policy_gated_executor = BaselineEngine(
    "policy_gated", "1.0.0", Capabilities(intent_authority_gate=True)
)
