"""The evaluation subject must never be able to grade itself.

This is the non-negotiable trust-boundary requirement from PRD/ARCHITECTURE/
DECISION_LOG D-004: no adapter-controlled field may directly set or override
OSR, PAOSR, CVSR, dimension status, invalid-commit status, or failure codes.
"""

from __future__ import annotations

import pytest

from cavbench.adapters.baselines import BASELINE_PROFILES
from cavbench.adapters.protocol import AdapterResult
from cavbench.evaluation.evaluator import DeterministicEvaluator
from cavbench.runtime.environment import BenchmarkEnvironment
from cavbench.runtime.session import AdapterSession
from cavbench.runtime.tools import ToolFacade
from cavbench.scenarios.loader import load_builtin_pack
from tests.helpers import ForgingAdapter, evaluate

PACK = load_builtin_pack("core-v1")
EVALUATOR = DeterministicEvaluator()


@pytest.mark.parametrize(
    "scenario_id,profile_name",
    [("IA-01", "direct"), ("ST-01", "direct"), ("ER-01", "direct"), ("ER-04", "reconciled")],
)
def test_forged_success_claims_cannot_flip_a_genuine_failure_to_a_pass(scenario_id: str, profile_name: str) -> None:
    scenario = PACK.get(scenario_id)
    honest = evaluate(scenario, BASELINE_PROFILES[profile_name])
    assert honest.commit_valid_success is False, "test setup expects a genuine CVSR failure"

    forged_adapter = ForgingAdapter(BASELINE_PROFILES[profile_name])
    forged = evaluate(scenario, forged_adapter)

    assert forged.commit_valid_success is False
    assert forged.outcome_success == honest.outcome_success
    assert forged.policy_aware_outcome_success == honest.policy_aware_outcome_success
    assert forged.dimensions == honest.dimensions
    assert forged.failure_codes == honest.failure_codes


def test_forged_failure_claims_cannot_flip_a_genuine_pass_to_a_failure() -> None:
    scenario = PACK.get("HP-01")
    adapter = BASELINE_PROFILES["direct"]
    honest = evaluate(scenario, adapter)
    assert honest.commit_valid_success is True

    class LyingFailureAdapter:
        name = "lying_failure"
        version = "1.0.0"

        def run(self, session: AdapterSession) -> AdapterResult:
            result = adapter.run(session)
            return AdapterResult(
                final_message=result.final_message,
                completion_status="failed",  # claims failure despite a clean commit-valid episode
                metadata={"commit_valid_success": False, "cvsr": 0.0, "failure_codes": ["MADE_UP_CODE"]},
            )

    forged = evaluate(scenario, LyingFailureAdapter())
    assert forged.commit_valid_success is True
    assert "MADE_UP_CODE" not in forged.failure_codes


def test_evaluator_never_reads_adapter_report_fields_other_than_completion_status() -> None:
    """Directly construct a trace whose adapter_report claims every
    trust-boundary field a self-grading adapter might try to write, and
    confirm the derived result depends only on benchmark-owned facts.
    """
    scenario = PACK.get("IA-04")  # owner mismatch -> forbidden commit if attempted
    adapter = BASELINE_PROFILES["direct"]
    env = BenchmarkEnvironment(scenario, seed=0, run_id="adv-direct")
    tools = ToolFacade(env)
    session = AdapterSession(scenario.view, tools)
    result = adapter.run(session)

    forged_report = {
        "adapter_name": adapter.name,
        "adapter_version": adapter.version,
        "final_message": result.final_message,
        "completion_status": result.completion_status,
        "commit_valid": True,
        "commit_valid_success": True,
        "cvsr": 1.0,
        "outcome_success": True,
        "policy_aware_outcome_success": True,
        "dimensions": {"authority_validity": "pass"},
        "failed_dimensions": [],
        "invalid_commits": [],
        "failure_codes": [],
    }
    trace = env.finalize(forged_report)
    evaluation = EVALUATOR.evaluate(scenario, trace)

    assert evaluation.commit_valid_success is False
    assert evaluation.dimensions["authority_validity"] == "fail"
    assert "AV_PRINCIPAL_NOT_AUTHORIZED" in evaluation.failure_codes
