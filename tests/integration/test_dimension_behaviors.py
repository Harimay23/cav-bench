"""Targeted integration tests for each named failure/recovery behavior class
called out in TECHNICAL_DESIGN.md's testing strategy.
"""

from __future__ import annotations

from cavbench.adapters.baselines import BASELINE_PROFILES
from cavbench.scenarios.loader import load_builtin_pack
from tests.helpers import evaluate

PACK = load_builtin_pack("core-v1")


def test_authority_failure_is_detected_and_fixed_by_the_gate() -> None:
    scenario = PACK.get("IA-04")  # order belongs to another account
    naive = evaluate(scenario, BASELINE_PROFILES["direct"])
    assert naive.commit_valid_success is False
    assert naive.dimensions["authority_validity"] == "fail"
    assert "AV_PRINCIPAL_NOT_AUTHORIZED" in naive.failure_codes

    gated = evaluate(scenario, BASELINE_PROFILES["policy_gated"])
    assert gated.commit_valid_success is True
    assert gated.dimensions["authority_validity"] == "pass"


def test_intent_boundary_failure_is_detected_and_fixed_by_the_gate() -> None:
    scenario = PACK.get("IA-01")  # read-only request must not trigger a write
    naive = evaluate(scenario, BASELINE_PROFILES["direct"])
    assert naive.commit_valid_success is False
    assert naive.dimensions["intent_grounding"] == "fail"

    gated = evaluate(scenario, BASELINE_PROFILES["policy_gated"])
    assert gated.commit_valid_success is True


def test_commit_time_stale_state_is_rejected_only_by_the_commit_guard() -> None:
    scenario = PACK.get("ST-01")
    for profile_name in ("direct", "policy_gated"):
        result = evaluate(scenario, BASELINE_PROFILES[profile_name])
        assert result.commit_valid_success is False, profile_name
        assert result.dimensions["temporal_state_validity"] == "fail", profile_name

    for profile_name in ("commit_guarded", "reconciled", "full_lifecycle"):
        result = evaluate(scenario, BASELINE_PROFILES[profile_name])
        assert result.commit_valid_success is True, profile_name
        assert result.dimensions["temporal_state_validity"] == "pass", profile_name


def test_ambiguous_timeout_is_reconciled_without_a_duplicate_effect() -> None:
    scenario = PACK.get("ER-01")
    for profile_name in ("direct", "policy_gated", "commit_guarded"):
        result = evaluate(scenario, BASELINE_PROFILES[profile_name])
        assert result.commit_valid_success is False, profile_name
        assert "EI_DUPLICATE_LOGICAL_EFFECT" in result.failure_codes, profile_name

    for profile_name in ("reconciled", "full_lifecycle"):
        result = evaluate(scenario, BASELINE_PROFILES[profile_name])
        assert result.commit_valid_success is True, profile_name
        assert result.dimensions["execution_integrity"] != "fail", profile_name


def test_partial_workflow_recovery_requires_the_full_lifecycle_profile() -> None:
    scenario = PACK.get("ER-04")  # reservation succeeds, payment capture force-fails
    for profile_name in ("direct", "policy_gated", "commit_guarded", "reconciled"):
        result = evaluate(scenario, BASELINE_PROFILES[profile_name])
        assert result.commit_valid_success is False, profile_name
        assert result.dimensions["outcome_recoverability"] == "fail", profile_name

    result = evaluate(scenario, BASELINE_PROFILES["full_lifecycle"])
    assert result.commit_valid_success is True
    assert result.dimensions["outcome_recoverability"] == "pass"


def test_failed_compensation_requires_escalation_and_truthful_pending_recovery() -> None:
    scenario = PACK.get("ER-09")  # reservation succeeds, payment fails, release also fails
    for profile_name in ("direct", "policy_gated", "commit_guarded", "reconciled"):
        result = evaluate(scenario, BASELINE_PROFILES[profile_name])
        assert result.commit_valid_success is False, profile_name

    result = evaluate(scenario, BASELINE_PROFILES["full_lifecycle"])
    assert result.commit_valid_success is True
    assert "OR_ESCALATION_MISSING" not in result.failure_codes


def test_truthful_partial_outcome_reporting_gates_cvsr_for_bulk_partial_cancellation() -> None:
    scenario = PACK.get("ER-08")  # two of three item cancellations succeed
    naive = evaluate(scenario, BASELINE_PROFILES["reconciled"])  # lacks recovery_coordinator
    assert naive.commit_valid_success is False
    assert "OR_FALSE_SUCCESS_REPORT" in naive.failure_codes

    honest = evaluate(scenario, BASELINE_PROFILES["full_lifecycle"])
    assert honest.commit_valid_success is True
    assert "OR_FALSE_SUCCESS_REPORT" not in honest.failure_codes
