"""The adoption-facing control-mapping doc must cover the pack (COM-FR-008).

Every scenario id, every declared validity dimension, every declared CMF-*
code, and every declared safeguard must appear in
docs/commerce-v1-profile.md, and safeguard references must resolve to the
canonical benchmark capability set.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from cavbench.scenarios.loader import load_builtin_pack
from tests.commerce._meta import cmf_codes, declared_dimensions, predicate_failure_codes, safeguards

PACK = load_builtin_pack("commerce-v1")
DOC = Path(__file__).resolve().parents[2] / "docs" / "commerce-v1-profile.md"
DOC_TEXT = DOC.read_text()

CANONICAL_SAFEGUARDS = {
    "intent_authority_gate",
    "commit_time_state_guard",
    "idempotency_reconciliation",
    "recovery_coordinator",
}


def test_doc_exists_and_marks_proposed_pending_review() -> None:
    assert DOC.exists()
    lowered = DOC_TEXT.lower()
    assert "proposed" in lowered
    assert "gate-2" in lowered
    assert "first applied" in lowered  # commerce is not the project's identity
    assert "synthetic" in lowered
    assert "no pii" in lowered or "no real payment" in lowered


@pytest.mark.parametrize("scenario_id", PACK.scenario_ids)
def test_every_scenario_id_appears(scenario_id: str) -> None:
    assert scenario_id in DOC_TEXT, scenario_id


@pytest.mark.parametrize("scenario_id", PACK.scenario_ids)
def test_every_declared_dimension_appears(scenario_id: str) -> None:
    for dimension in declared_dimensions(PACK.get(scenario_id).notes):
        assert dimension in DOC_TEXT, (scenario_id, dimension)


@pytest.mark.parametrize("scenario_id", PACK.scenario_ids)
def test_every_declared_cmf_code_appears(scenario_id: str) -> None:
    scenario = PACK.get(scenario_id)
    codes = set(cmf_codes(scenario.notes)) | {
        c for c in predicate_failure_codes(scenario.oracle.to_dict()) if c.startswith("CMF-")
    }
    for code in codes:
        assert code in DOC_TEXT, (scenario_id, code)


@pytest.mark.parametrize("scenario_id", PACK.scenario_ids)
def test_every_declared_safeguard_resolves_and_appears(scenario_id: str) -> None:
    for safeguard in safeguards(PACK.get(scenario_id).notes):
        assert safeguard in CANONICAL_SAFEGUARDS, (scenario_id, safeguard)
        assert safeguard in DOC_TEXT, (scenario_id, safeguard)


def test_doc_declares_non_claims() -> None:
    lowered = DOC_TEXT.lower()
    assert "not" in lowered
    assert "adoption" in lowered
    assert "not a compliance" in lowered or "certification" in lowered
