"""The small, stable public Python API.

Internal state-mutation helpers, the environment, and the raw state store are
deliberately not exported here.
"""

from __future__ import annotations

from cavbench.adapters.baselines import BASELINE_PROFILES, CANONICAL_PROFILE_ORDER
from cavbench.adapters.protocol import AdapterResult, ExecutionAdapter
from cavbench.config import RunConfig
from cavbench.evaluation.evaluator import DeterministicEvaluator
from cavbench.evaluation.results import EvaluationResult, MetricSummary
from cavbench.runner import BenchmarkRunner, CompletedRun
from cavbench.runtime.session import AdapterSession
from cavbench.runtime.tools import ToolFacade, ToolResult
from cavbench.scenarios.loader import load_builtin_pack, load_pack_from_directory
from cavbench.scenarios.models import ScenarioDefinition, ScenarioOracle, ScenarioPack, ScenarioView

__all__ = [
    "AdapterResult",
    "AdapterSession",
    "BASELINE_PROFILES",
    "BenchmarkRunner",
    "CANONICAL_PROFILE_ORDER",
    "CompletedRun",
    "DeterministicEvaluator",
    "EvaluationResult",
    "ExecutionAdapter",
    "MetricSummary",
    "RunConfig",
    "ScenarioDefinition",
    "ScenarioOracle",
    "ScenarioPack",
    "ScenarioView",
    "ToolFacade",
    "ToolResult",
    "load_builtin_pack",
    "load_pack_from_directory",
]
