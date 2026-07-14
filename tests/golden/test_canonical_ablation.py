"""The canonical five-profile ablation is a golden regression artifact.

Do not update these expected values to make the test pass -- if a real
implementation change causes a deviation, investigate the semantic cause
and document it in DECISION_LOG.md before touching this file
(AGENTS.md / CLAUDE.md "Do not rewrite expected results to make tests green").
"""

from __future__ import annotations

from cavbench.adapters.baselines import BASELINE_PROFILES, CANONICAL_PROFILE_ORDER
from cavbench.evaluation.metrics import aggregate
from cavbench.scenarios.loader import load_builtin_pack
from tests.helpers import evaluate

PACK = load_builtin_pack("core-v1")

EXPECTED = {
    "direct": {"OSR": 0.925, "PAOSR": 0.750, "CVSR": 0.250, "VG": 0.675},
    "policy_gated": {"OSR": 1.000, "PAOSR": 1.000, "CVSR": 0.500, "VG": 0.500},
    "commit_guarded": {"OSR": 1.000, "PAOSR": 1.000, "CVSR": 0.750, "VG": 0.250},
    "reconciled": {"OSR": 1.000, "PAOSR": 1.000, "CVSR": 0.875, "VG": 0.125},
    "full_lifecycle": {"OSR": 1.000, "PAOSR": 1.000, "CVSR": 1.000, "VG": 0.000},
}


def test_canonical_ablation_matches_the_published_table() -> None:
    for profile_name in CANONICAL_PROFILE_ORDER:
        adapter = BASELINE_PROFILES[profile_name]
        rows = [(scenario, evaluate(scenario, adapter)) for scenario in PACK]
        overall = aggregate(rows).overall.to_dict()
        expected = EXPECTED[profile_name]
        assert overall["OSR"] == expected["OSR"], profile_name
        assert overall["PAOSR"] == expected["PAOSR"], profile_name
        assert overall["CVSR"] == expected["CVSR"], profile_name
        assert overall["VG"] == expected["VG"], profile_name


def test_cvsr_is_monotonically_non_decreasing_as_capability_tiers_are_added() -> None:
    cvsr_by_profile = {}
    for profile_name in CANONICAL_PROFILE_ORDER:
        adapter = BASELINE_PROFILES[profile_name]
        rows = [(scenario, evaluate(scenario, adapter)) for scenario in PACK]
        cvsr_by_profile[profile_name] = aggregate(rows).overall.cvsr
    values = [cvsr_by_profile[p] for p in CANONICAL_PROFILE_ORDER]
    assert values == sorted(values)
