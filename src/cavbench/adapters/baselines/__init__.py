"""The five canonical controlled architecture baselines.

These are deterministic architecture profiles, not LLM outputs. Each
implements :class:`cavbench.adapters.protocol.ExecutionAdapter` via the same
shared, capability-parameterized engine (see ``_engine.py``) so the evaluator
never special-cases by profile name.
"""

from __future__ import annotations

from cavbench.adapters.baselines.commit_guarded import commit_guarded_executor
from cavbench.adapters.baselines.direct import direct_executor
from cavbench.adapters.baselines.full_lifecycle import full_lifecycle_executor
from cavbench.adapters.baselines.policy_gated import policy_gated_executor
from cavbench.adapters.baselines.reconciled import reconciled_executor
from cavbench.adapters.protocol import ExecutionAdapter

BASELINE_PROFILES: dict[str, ExecutionAdapter] = {
    "direct": direct_executor,
    "policy_gated": policy_gated_executor,
    "commit_guarded": commit_guarded_executor,
    "reconciled": reconciled_executor,
    "full_lifecycle": full_lifecycle_executor,
}

CANONICAL_PROFILE_ORDER: tuple[str, ...] = (
    "direct",
    "policy_gated",
    "commit_guarded",
    "reconciled",
    "full_lifecycle",
)

__all__ = ["BASELINE_PROFILES", "CANONICAL_PROFILE_ORDER", "ExecutionAdapter"]
