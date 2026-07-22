"""commerce-v1 pack: schema, loading, digest, oracle boundary, invariants.

Everything here exercises the *proposed* commerce-v1 pack through the
existing, unchanged loader / schema / predicate engine -- no commerce-specific
runtime, adapter, evaluator, or schema code exists or is required.
"""

from __future__ import annotations

import json

import pytest

from cavbench.adapters.baselines import BASELINE_PROFILES
from cavbench.evaluation.predicates import evaluate as evaluate_predicate
from cavbench.scenarios.loader import load_builtin_pack, validate_scenario_document
from cavbench.scenarios.models import DIMENSIONS, Predicate
from tests.commerce._meta import cmf_codes, declared_dimensions, parse_meta, predicate_failure_codes

PACK = load_builtin_pack("commerce-v1")

EXPECTED_IDS = (
    "CM-INV-01",
    "CM-INV-90",
    "CM-ORD-01",
    "CM-ORD-90",
    "CM-PAY-02",
    "CM-PAY-90",
    "CM-PRC-02",
    "CM-REC-01",
)


def test_pack_identity_and_membership() -> None:
    assert PACK.pack_id == "commerce-v1"
    assert PACK.pack_version == "0.1.0"
    assert PACK.schema_version == "1.0"
    assert PACK.scenario_ids == EXPECTED_IDS
    assert len(PACK) == 8


def test_pack_version_is_independent_of_core_package() -> None:
    # commerce-v1 is a proposed 0.x applied profile; it must not borrow the
    # core-v1 / package 1.0.0 version.
    assert PACK.pack_version.startswith("0.")
    assert load_builtin_pack("core-v1").pack_version == "1.0.0"


@pytest.mark.parametrize("scenario_id", EXPECTED_IDS)
def test_each_scenario_validates_against_the_schema(scenario_id: str) -> None:
    scenario = PACK.get(scenario_id)
    validate_scenario_document(scenario.to_dict(), source=scenario_id)


def test_pack_digest_is_stable_across_repeated_loads() -> None:
    load_builtin_pack.cache_clear()
    first = load_builtin_pack("commerce-v1")
    load_builtin_pack.cache_clear()
    second = load_builtin_pack("commerce-v1")
    assert first.digest == second.digest
    assert first.digest.startswith("sha256:")


def test_pack_digest_differs_from_core_v1() -> None:
    assert load_builtin_pack("commerce-v1").digest != load_builtin_pack("core-v1").digest


@pytest.mark.parametrize("scenario_id", EXPECTED_IDS)
def test_families_are_core_families_only(scenario_id: str) -> None:
    assert PACK.get(scenario_id).family in {
        "stable_happy_path",
        "state_mutation",
        "intent_authority",
        "execution_recovery",
    }


@pytest.mark.parametrize("scenario_id", EXPECTED_IDS)
def test_declared_dimensions_match_oracle_focus(scenario_id: str) -> None:
    scenario = PACK.get(scenario_id)
    declared = set(declared_dimensions(scenario.notes))
    focus = set(scenario.oracle.dimension_focus)
    assert declared == focus, (scenario_id, declared, focus)
    assert declared.issubset(set(DIMENSIONS))


@pytest.mark.parametrize("scenario_id", EXPECTED_IDS)
def test_meta_header_declares_proposed_status(scenario_id: str) -> None:
    meta = parse_meta(PACK.get(scenario_id).notes)
    assert meta["status"] == "proposed-pending-gate2-scope-review"
    assert meta["domain"]
    assert meta["core_family"] == PACK.get(scenario_id).family


@pytest.mark.parametrize("scenario_id", EXPECTED_IDS)
def test_declared_cmf_codes_are_well_formed(scenario_id: str) -> None:
    for code in cmf_codes(PACK.get(scenario_id).notes):
        assert code.startswith("CMF-"), (scenario_id, code)


# -- oracle boundary (D-003): nothing private leaks to the adapter ---------

_ORACLE_ONLY_MARKERS = (
    "goal_predicates",
    "forbidden_effects",
    "required_effects",
    "dimension_focus",
    "oracle",
)


@pytest.mark.parametrize("scenario_id", EXPECTED_IDS)
def test_scenario_view_hides_the_private_oracle(scenario_id: str) -> None:
    scenario = PACK.get(scenario_id)
    view_json = json.dumps(scenario.view.to_dict())
    # No CMF-* domain code declared on the private oracle may appear in the
    # adapter-visible view, plan, or policy envelope.
    for code in set(cmf_codes(scenario.notes)) | predicate_failure_codes(scenario.oracle.to_dict()):
        assert code not in view_json, (scenario_id, code)
    for marker in _ORACLE_ONLY_MARKERS:
        assert marker not in view_json, (scenario_id, marker)
    # The adapter-visible ScenarioView carries no oracle attribute at all.
    assert not hasattr(scenario.view, "oracle")


@pytest.mark.parametrize("scenario_id", EXPECTED_IDS)
def test_dimension_focus_and_failure_codes_are_evaluator_only(scenario_id: str) -> None:
    scenario = PACK.get(scenario_id)
    view_json = json.dumps(scenario.view.to_dict())
    for dimension in DIMENSIONS:
        assert dimension not in view_json, (scenario_id, dimension)


@pytest.mark.parametrize("scenario_id", EXPECTED_IDS)
def test_adapter_report_carries_no_oracle_content(scenario_id: str) -> None:
    # The adapter's own report (produced before the evaluator runs) must not
    # contain any private oracle code -- the adapter never sees the oracle.
    from tests.helpers import run_episode

    scenario = PACK.get(scenario_id)
    trace = run_episode(scenario, BASELINE_PROFILES["direct"])
    report_json = json.dumps(trace.adapter_report, default=str)
    for code in set(cmf_codes(scenario.notes)) | predicate_failure_codes(scenario.oracle.to_dict()):
        assert code not in report_json, (scenario_id, code)


# -- monetary / quantity invariants are oracle-checkable (COM-FR-005) ------


def _ctx(state: dict, side_effects: list | None = None) -> dict:
    return {"state": state, "side_effects": side_effects or [], "events": []}


def test_discount_within_delegated_limit_invariant() -> None:
    # applied discount must not exceed the delegated limit (CM-PRC-02 form).
    over = Predicate(op="gt", path="state.pricing.PA.applied_discount_pct", value=10)
    assert evaluate_predicate(over, _ctx({"pricing": {"PA": {"applied_discount_pct": 30}}})) is True
    assert evaluate_predicate(over, _ctx({"pricing": {"PA": {"applied_discount_pct": 10}}})) is False


def test_captured_at_most_authorized_invariant() -> None:
    over = Predicate(op="gt", path="state.payments.P.captured", value=50)
    assert evaluate_predicate(over, _ctx({"payments": {"P": {"captured": 60}}})) is True
    assert evaluate_predicate(over, _ctx({"payments": {"P": {"captured": 50}}})) is False


def test_reservation_effect_cardinality_invariant() -> None:
    # A committed reserve effect is derivable from the ledger alone (CM-INV-01).
    pred = Predicate(
        op="count_gte",
        collection="side_effects",
        where={"effect_type": "reserve_inventory", "resource_ref": "inventory:SKU"},
        value=1,
    )
    effects = [{"effect_type": "reserve_inventory", "resource_ref": "inventory:SKU"}]
    assert evaluate_predicate(pred, _ctx({}, effects)) is True
    assert evaluate_predicate(pred, _ctx({}, [])) is False


def test_duplicate_order_effect_cardinality_invariant() -> None:
    pred = Predicate(
        op="count_gte",
        collection="side_effects",
        where={"effect_type": "create_order", "resource_ref": "orders:O"},
        value=2,
    )
    one = [{"effect_type": "create_order", "resource_ref": "orders:O", "logical_operation_id": "x"}]
    assert evaluate_predicate(pred, _ctx({}, one)) is False
    assert evaluate_predicate(pred, _ctx({}, one * 2)) is True


def test_refunds_not_exceeding_captures_invariant() -> None:
    # Σ refunds ≤ Σ captures per order is oracle-checkable from the ledger
    # (COM-FR-005), demonstrated here directly on the predicate engine.
    captures = [{"effect_type": "capture_payment", "resource_ref": "payments:P"}]
    refunds_ok = Predicate(
        op="count_lte", collection="side_effects", where={"effect_type": "refund"}, value=1
    )
    ledger = captures + [{"effect_type": "refund", "resource_ref": "credits:C"}]
    assert evaluate_predicate(refunds_ok, _ctx({}, ledger)) is True
    ledger_double = ledger + [{"effect_type": "refund", "resource_ref": "credits:C"}]
    assert evaluate_predicate(refunds_ok, _ctx({}, ledger_double)) is False
