"""Evaluator-owned result types. Nothing in this module is ever constructed
from adapter-supplied data -- every field is derived by
:class:`cavbench.evaluation.evaluator.DeterministicEvaluator`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

from cavbench.scenarios.models import DIMENSIONS, JSONValue


@dataclass(frozen=True)
class EvaluationResult:
    scenario_id: str
    outcome_success: bool
    policy_aware_outcome_success: bool
    commit_valid_success: bool
    dimensions: Mapping[str, str]
    invalid_commits: tuple[Mapping[str, JSONValue], ...] = ()
    failure_codes: tuple[str, ...] = ()
    diagnostics: Mapping[str, JSONValue] = field(default_factory=dict)

    def to_dict(self) -> dict[str, JSONValue]:
        return {
            "scenario_id": self.scenario_id,
            "outcome_success": self.outcome_success,
            "policy_aware_outcome_success": self.policy_aware_outcome_success,
            "commit_valid_success": self.commit_valid_success,
            "dimensions": {d: self.dimensions.get(d, "not_applicable") for d in DIMENSIONS},
            "invalid_commits": [dict(c) for c in self.invalid_commits],
            "failure_codes": list(self.failure_codes),
            "diagnostics": dict(self.diagnostics),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, JSONValue]) -> "EvaluationResult":
        return cls(
            scenario_id=data["scenario_id"],
            outcome_success=data["outcome_success"],
            policy_aware_outcome_success=data["policy_aware_outcome_success"],
            commit_valid_success=data["commit_valid_success"],
            dimensions=dict(data.get("dimensions", {})),
            invalid_commits=tuple(data.get("invalid_commits", ())),
            failure_codes=tuple(data.get("failure_codes", ())),
            diagnostics=dict(data.get("diagnostics", {})),
        )


@dataclass(frozen=True)
class RateSummary:
    n: int
    osr: float
    paosr: float
    cvsr: float
    vg: float
    pavg: float

    def to_dict(self) -> dict[str, JSONValue]:
        return {
            "n": self.n,
            "OSR": round(self.osr, 4),
            "PAOSR": round(self.paosr, 4),
            "CVSR": round(self.cvsr, 4),
            "VG": round(self.vg, 4),
            "PAVG": round(self.pavg, 4),
        }


@dataclass(frozen=True)
class MetricSummary:
    overall: RateSummary
    by_family: Mapping[str, RateSummary]

    def to_dict(self) -> dict[str, JSONValue]:
        return {
            "overall": self.overall.to_dict(),
            "by_family": {family: rate.to_dict() for family, rate in self.by_family.items()},
        }
