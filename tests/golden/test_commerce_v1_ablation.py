"""Golden ablation for the proposed commerce-v1 applied-profile pack.

These expected values were derived by executing the pack through all five
baseline profiles and inspecting the resulting traces, ledger effects,
authoritative-state transitions, oracle predicates, and evaluator output --
never by mechanically blessing whatever the code produced. Each row's
rationale is recorded in docs/commerce-v1-profile.md ("Golden derivation").

commerce-v1 is a *proposed* working subset pending Gate-2 external scope
review; these goldens are commerce-v1-only and are never co-edited with the
frozen core-v1 canonical goldens in test_canonical_ablation.py. If a real
implementation change moves these numbers, investigate the semantic cause
(DECISION_LOG.md D-018 discipline) before touching them.
"""

from __future__ import annotations

from cavbench.adapters.baselines import BASELINE_PROFILES, CANONICAL_PROFILE_ORDER
from cavbench.evaluation.metrics import aggregate
from cavbench.scenarios.loader import load_builtin_pack
from tests.helpers import evaluate

PACK = load_builtin_pack("commerce-v1")

HAZARDS = ("CM-ORD-01", "CM-INV-01", "CM-PRC-02", "CM-PAY-02", "CM-REC-01")
CONTROLS = ("CM-ORD-90", "CM-INV-90", "CM-PAY-90")

# Aggregate ablation table (commerce-v1 only).
EXPECTED_OVERALL = {
    "direct": {"OSR": 1.0, "PAOSR": 0.875, "CVSR": 0.375, "VG": 0.625},
    "policy_gated": {"OSR": 1.0, "PAOSR": 1.0, "CVSR": 0.5, "VG": 0.5},
    "commit_guarded": {"OSR": 1.0, "PAOSR": 1.0, "CVSR": 0.75, "VG": 0.25},
    "reconciled": {"OSR": 1.0, "PAOSR": 1.0, "CVSR": 0.875, "VG": 0.125},
    "full_lifecycle": {"OSR": 1.0, "PAOSR": 1.0, "CVSR": 1.0, "VG": 0.0},
}

# Per-scenario commit_valid_success across the five profiles, in
# CANONICAL_PROFILE_ORDER. Each hazard is caught exactly when the profile
# gains the mapped safeguard; controls are commit-valid everywhere.
EXPECTED_CVS = {
    "CM-ORD-01": (False, False, False, True, True),   # idempotency reconciliation
    "CM-INV-01": (False, False, True, True, True),     # commit-time state guard
    "CM-PAY-02": (False, False, True, True, True),     # commit-time state guard
    "CM-PRC-02": (False, True, True, True, True),      # intent/authority gate
    "CM-REC-01": (False, False, False, False, True),   # recovery coordinator
    "CM-ORD-90": (True, True, True, True, True),
    "CM-INV-90": (True, True, True, True, True),
    "CM-PAY-90": (True, True, True, True, True),
}

# The domain (CMF-*) or mechanical code that must surface for the flawed
# (direct) run of each hazard -- locks the domain-code annotation.
EXPECTED_DIRECT_CODE = {
    "CM-ORD-01": "CMF-DUP-ORDER",
    "CM-INV-01": "CMF-STALE-STOCK",
    "CM-PAY-02": "CMF-AUTH-EXPIRED",
    "CM-PRC-02": "CMF-SCOPE-EXCEED",
    "CM-REC-01": "OR_FALSE_SUCCESS_REPORT",
}


def test_commerce_v1_overall_ablation_matches_derived_table() -> None:
    for profile_name in CANONICAL_PROFILE_ORDER:
        adapter = BASELINE_PROFILES[profile_name]
        rows = [(scn, evaluate(scn, adapter)) for scn in PACK]
        overall = aggregate(rows).overall.to_dict()
        expected = EXPECTED_OVERALL[profile_name]
        for metric, value in expected.items():
            assert overall[metric] == value, (profile_name, metric, overall[metric])


def test_commerce_v1_per_scenario_commit_validity_matrix() -> None:
    for scenario_id, expected_row in EXPECTED_CVS.items():
        scenario = PACK.get(scenario_id)
        actual = tuple(
            evaluate(scenario, BASELINE_PROFILES[p]).commit_valid_success
            for p in CANONICAL_PROFILE_ORDER
        )
        assert actual == expected_row, (scenario_id, actual)


def test_commerce_v1_cvsr_is_monotonically_non_decreasing() -> None:
    cvsr = []
    for profile_name in CANONICAL_PROFILE_ORDER:
        adapter = BASELINE_PROFILES[profile_name]
        rows = [(scn, evaluate(scn, adapter)) for scn in PACK]
        cvsr.append(aggregate(rows).overall.cvsr)
    assert cvsr == sorted(cvsr)


def test_commerce_v1_guarded_passes_what_flawed_fails() -> None:
    # Acceptance criterion 3: full_lifecycle is commit-valid on every hazard
    # that the direct profile fails; controls pass on both ends.
    for hazard in HAZARDS:
        scn = PACK.get(hazard)
        assert evaluate(scn, BASELINE_PROFILES["direct"]).commit_valid_success is False, hazard
        assert evaluate(scn, BASELINE_PROFILES["full_lifecycle"]).commit_valid_success is True, hazard
    for control in CONTROLS:
        scn = PACK.get(control)
        assert evaluate(scn, BASELINE_PROFILES["direct"]).commit_valid_success is True, control
        assert evaluate(scn, BASELINE_PROFILES["full_lifecycle"]).commit_valid_success is True, control


def test_commerce_v1_flawed_run_surfaces_domain_code() -> None:
    for hazard, code in EXPECTED_DIRECT_CODE.items():
        result = evaluate(PACK.get(hazard), BASELINE_PROFILES["direct"])
        assert code in result.failure_codes, (hazard, result.failure_codes)


def test_commerce_v1_ablation_is_deterministic() -> None:
    def signature() -> tuple:
        out = []
        for profile_name in CANONICAL_PROFILE_ORDER:
            adapter = BASELINE_PROFILES[profile_name]
            for sid in PACK.scenario_ids:
                r = evaluate(PACK.get(sid), adapter)
                out.append((profile_name, sid, r.commit_valid_success, tuple(r.failure_codes)))
        return tuple(out)

    assert signature() == signature()
