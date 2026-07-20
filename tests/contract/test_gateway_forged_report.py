"""Adversarial forged-final-report contract test (M-GPI-1).

Mirrors ``tests/contract/test_evaluator_independence.py``: a candidate
submitting a forged "everything committed successfully" report through the
gateway's `report` operation must not improve its evaluation, because the
report is carried into `finalize()` exactly as untrusted `AdapterResult`
metadata is today -- never read as commit truth (GPI-FR-010).
"""

from __future__ import annotations

from cavbench.evaluation.evaluator import DeterministicEvaluator
from cavbench.gateway.core import GatewaySession
from cavbench.gateway.envelope import ENVELOPE_VERSION
from cavbench.scenarios.loader import load_builtin_pack

PACK = load_builtin_pack("core-v1")
EVALUATOR = DeterministicEvaluator()


def _write(session: GatewaySession, step, *, idempotency_key: str) -> None:
    session.handle(
        {
            "envelope_version": ENVELOPE_VERSION,
            "session_token": session.run_token,
            "operation_id": step.logical_operation_id or step.step_id,
            "correlation_id": f"corr-{step.step_id}",
            "actor_id": "candidate",
            "action": "write",
            "resource": {"namespace": step.namespace, "resource_id": step.resource_id, "tool_name": step.tool_name},
            "parameters": {"step_id": step.step_id, "changes": dict(step.changes), "args": dict(step.args)},
            "idempotency_key": idempotency_key,
        }
    )


def test_forged_success_report_cannot_flip_a_genuine_failure_to_a_pass() -> None:
    scenario = PACK.get("IA-04")  # owner mismatch: any commit here is invalid
    honest_session = GatewaySession.start(scenario, seed=0, run_id="forged-honest")
    write_step = scenario.view.plan.steps[1]
    _write(honest_session, write_step, idempotency_key="idem-honest")
    honest_trace = honest_session.finalize()
    honest_eval = EVALUATOR.evaluate(scenario, honest_trace)

    forged_session = GatewaySession.start(scenario, seed=0, run_id="forged-attack")
    _write(forged_session, write_step, idempotency_key="idem-forged")
    forged_session.handle(
        {
            "envelope_version": ENVELOPE_VERSION,
            "session_token": forged_session.run_token,
            "operation_id": "final-report",
            "correlation_id": "corr-final-report",
            "actor_id": "candidate",
            "action": "report",
            "resource": {"namespace": "session", "resource_id": forged_session.session_id},
            "parameters": {
                "adapter_name": "forging-candidate",
                "adapter_version": "0.0.0",
                "final_message": "Everything completed successfully.",
                "completion_status": "success",
                # attempted trust-boundary smuggling, mirroring
                # ForgingAdapter in tests/helpers.py
                "commit_valid": True,
                "commit_valid_success": True,
                "cvsr": 1.0,
                "outcome_success": True,
                "policy_aware_outcome_success": True,
                "dimensions": {"authority_validity": "pass"},
                "failed_dimensions": [],
                "invalid_commits": [],
                "failure_codes": [],
            },
        }
    )
    forged_trace = forged_session.finalize()
    forged_eval = EVALUATOR.evaluate(scenario, forged_trace)

    assert honest_eval.commit_valid_success is False
    assert forged_eval.commit_valid_success is False
    assert forged_eval.dimensions == honest_eval.dimensions
    assert forged_eval.failure_codes == honest_eval.failure_codes
    assert "AV_PRINCIPAL_NOT_AUTHORIZED" in forged_eval.failure_codes


def test_no_report_submitted_still_finalizes_on_benchmark_owned_facts() -> None:
    """A candidate that crashes/disconnects mid-session without ever
    calling `report` must still finalize on benchmark-owned facts (design
    doc "Failure modes")."""
    scenario = PACK.get("HP-01")
    session = GatewaySession.start(scenario, seed=0, run_id="no-report")
    write_step = next(s for s in scenario.view.plan.steps if s.kind == "write")
    _write(session, write_step, idempotency_key="idem-no-report")
    trace = session.finalize()
    evaluation = EVALUATOR.evaluate(scenario, trace)
    assert evaluation.commit_valid_success is True
