"""The stable extension point for execution adapters.

Deterministic baselines, real LLM agents, agent frameworks, and a future MCP
adapter all implement this same protocol. The evaluator never special-cases
by adapter name or type.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Protocol, runtime_checkable

from cavbench.runtime.session import AdapterSession
from cavbench.scenarios.models import JSONValue

# Untrusted-by-construction: nothing in AdapterResult is read by the
# evaluator as ground truth. `completion_status` is only ever *compared*
# against benchmark-derived facts to detect an overclaim, never trusted.
COMPLETION_STATUSES = ("success", "partial", "pending_recovery", "failed")


@dataclass(frozen=True)
class AdapterResult:
    final_message: str
    completion_status: str = "success"
    metadata: Mapping[str, JSONValue] = field(default_factory=dict)


@runtime_checkable
class ExecutionAdapter(Protocol):
    @property
    def name(self) -> str: ...

    @property
    def version(self) -> str: ...

    def run(self, session: AdapterSession) -> AdapterResult: ...
