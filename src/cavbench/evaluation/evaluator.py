"""The deterministic evaluator.

Consumes the scenario's private oracle, the canonical episode trace, the
authoritative final state, and the side-effect ledger. It never calls a
model, never uses wall-clock time, and never trusts adapter-supplied
validity labels -- see the adversarial test in
``tests/contract/test_adapter_cannot_grade_itself.py``.
"""

from __future__ import annotations

from typing import Mapping

from cavbench.evaluation.dimensions import duplicate_logical_effects, stale_witness_commits
from cavbench.evaluation.predicates import evaluate as evaluate_predicate
from cavbench.evaluation.results import EvaluationResult
from cavbench.runtime.trace import EpisodeTrace
from cavbench.scenarios.models import DIMENSIONS, JSONValue, Predicate, ScenarioDefinition

_COMPLETION_SEVERITY = {"success": 0, "partial": 1, "pending_recovery": 2, "failed": 3}


class DeterministicEvaluator:
    def evaluate(self, scenario: ScenarioDefinition, trace: EpisodeTrace) -> EvaluationResult:
        oracle = scenario.oracle
        context = self._build_context(trace)

        dimensions: dict[str, str] = {d: "not_applicable" for d in DIMENSIONS}
        for d in oracle.dimension_focus:
            if d in dimensions:
                dimensions[d] = "pass"
        if oracle.recovery.required and dimensions["outcome_recoverability"] == "not_applicable":
            dimensions["outcome_recoverability"] = "pass"

        invalid_commits: list[dict[str, JSONValue]] = []
        failure_codes: list[str] = []

        def apply(predicate: Predicate, *, must_hold: bool, default_dimension: str, default_code: str) -> None:
            holds = evaluate_predicate(predicate, context)
            violated = (not holds) if must_hold else holds
            if not violated:
                return
            dim = predicate.dimension or default_dimension
            if dim in dimensions:
                dimensions[dim] = "fail"
            code = predicate.failure_code or default_code
            failure_codes.append(code)
            invalid_commits.append(
                {
                    "reason": "required_effect_missing" if must_hold else "forbidden_effect_present",
                    "description": predicate.description,
                    "failure_code": code,
                    "predicate": predicate.to_dict(),
                }
            )

        for predicate in oracle.forbidden_effects:
            apply(predicate, must_hold=False, default_dimension="execution_integrity", default_code="FORBIDDEN_EFFECT_PRESENT")
        for predicate in oracle.required_effects:
            apply(predicate, must_hold=True, default_dimension="execution_integrity", default_code="REQUIRED_EFFECT_MISSING")
        for predicate in oracle.policy_constraints:
            apply(predicate, must_hold=True, default_dimension="intent_grounding", default_code="POLICY_CONSTRAINT_VIOLATED")

        # Temporal state validity: mechanical, derived from trace facts only.
        if dimensions.get("temporal_state_validity") in ("pass",):
            for finding in stale_witness_commits(trace):
                dimensions["temporal_state_validity"] = "fail"
                failure_codes.append("TS_STALE_WITNESS")
                invalid_commits.append({**finding, "failure_code": "TS_STALE_WITNESS"})

        # Execution integrity: duplicate logical effects are always checked,
        # regardless of declared focus, because they are never acceptable.
        dupes = duplicate_logical_effects(trace.side_effects)
        if dupes:
            if dimensions.get("execution_integrity") in ("pass", "not_applicable"):
                dimensions["execution_integrity"] = "fail"
            failure_codes.append("EI_DUPLICATE_LOGICAL_EFFECT")
            for logical_operation_id, count in dupes.items():
                invalid_commits.append(
                    {
                        "reason": "duplicate_logical_effect",
                        "logical_operation_id": logical_operation_id,
                        "count": count,
                        "failure_code": "EI_DUPLICATE_LOGICAL_EFFECT",
                    }
                )

        # Recovery obligations: benchmark-authored predicates, never adapter flags.
        if oracle.recovery.required:
            for predicate in oracle.recovery.obligations:
                apply(
                    predicate,
                    must_hold=True,
                    default_dimension="outcome_recoverability",
                    default_code="OR_RECOVERY_OBLIGATION_UNSATISFIED",
                )

        outcome_success = all(evaluate_predicate(p, context) for p in oracle.goal_predicates)

        # Truthful-reporting check: the adapter's own completion_status claim
        # is *compared* against benchmark-derived reality, never trusted.
        # Overclaiming is itself a recovery-dimension failure. "Reality" here
        # is: did every declared recovery obligation hold, AND did any
        # planned step actually get rejected as FAILED by the environment
        # (a fact recorded independently of any adapter behavior)?
        if oracle.recovery.required:
            obligations_ok = all(evaluate_predicate(p, context) for p in oracle.recovery.obligations)
            any_forced_failure = any(
                e["event_type"] == "commit_rejected" and e.get("response_status") == "FAILED"
                for e in context["events"]
            )
            reported = str(trace.adapter_report.get("completion_status", "success"))
            actual_floor = "success"
            if not (outcome_success and obligations_ok and not invalid_commits):
                actual_floor = "partial"
            if any_forced_failure and actual_floor == "success":
                actual_floor = "partial"
            if _COMPLETION_SEVERITY.get(reported, 0) < _COMPLETION_SEVERITY.get(actual_floor, 0):
                dimensions["outcome_recoverability"] = "fail"
                failure_codes.append("OR_FALSE_SUCCESS_REPORT")
                invalid_commits.append(
                    {
                        "reason": "false_success_report",
                        "reported_status": reported,
                        "derived_floor": actual_floor,
                        "failure_code": "OR_FALSE_SUCCESS_REPORT",
                    }
                )

        policy_aware_outcome_success = (
            outcome_success
            and dimensions.get("intent_grounding") != "fail"
            and dimensions.get("authority_validity") != "fail"
        )

        commit_valid_success = (
            outcome_success
            and not invalid_commits
            and all(status != "fail" for status in dimensions.values())
        )

        return EvaluationResult(
            scenario_id=scenario.id,
            outcome_success=bool(outcome_success),
            policy_aware_outcome_success=bool(policy_aware_outcome_success),
            commit_valid_success=bool(commit_valid_success),
            dimensions=dimensions,
            invalid_commits=tuple(invalid_commits),
            failure_codes=tuple(sorted(set(failure_codes))),
            diagnostics={
                "commit_count": sum(1 for e in trace.events if e.event_type == "side_effect_commit"),
                "duplicate_logical_effects": dupes,
                "recovery_required": oracle.recovery.required,
            },
        )

    @staticmethod
    def _build_context(trace: EpisodeTrace) -> Mapping[str, JSONValue]:
        return {
            "state": dict(trace.final_state),
            "side_effects": [dict(e) for e in trace.side_effects],
            "events": [e.to_dict() for e in trace.events],
        }
