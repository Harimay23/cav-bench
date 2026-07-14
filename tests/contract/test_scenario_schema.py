from __future__ import annotations

import json

import jsonschema
import pytest

from cavbench.errors import SchemaValidationError, UnsupportedSchemaVersion
from cavbench.scenarios.loader import (
    _scenario_schema,
    load_builtin_pack,
    validate_scenario_document,
)

PACK = load_builtin_pack("core-v1")


def test_all_40_scenarios_are_present() -> None:
    assert len(PACK) == 40
    assert len(set(PACK.scenario_ids)) == 40


@pytest.mark.parametrize("scenario_id", PACK.scenario_ids)
def test_each_scenario_validates_against_the_schema(scenario_id: str) -> None:
    scenario = PACK.get(scenario_id)
    validate_scenario_document(scenario.to_dict(), source=scenario_id)


def test_pack_digest_is_stable_across_repeated_loads() -> None:
    load_builtin_pack.cache_clear()
    first = load_builtin_pack("core-v1")
    load_builtin_pack.cache_clear()
    second = load_builtin_pack("core-v1")
    assert first.digest == second.digest


def test_unsupported_schema_version_is_rejected() -> None:
    with pytest.raises(UnsupportedSchemaVersion):
        validate_scenario_document({"schema_version": "99.0"}, source="bad-version")


def test_malformed_scenario_missing_required_field_is_rejected() -> None:
    scenario = json.loads(json.dumps(PACK.get("HP-01").to_dict()))
    del scenario["oracle"]
    with pytest.raises(SchemaValidationError):
        validate_scenario_document(scenario, source="malformed")


def test_malformed_scenario_wrong_type_is_rejected() -> None:
    scenario = json.loads(json.dumps(PACK.get("HP-01").to_dict()))
    scenario["family"] = "not_a_real_family"
    with pytest.raises(SchemaValidationError):
        validate_scenario_document(scenario, source="malformed-family")


def test_malformed_scenario_unknown_top_level_field_is_rejected() -> None:
    scenario = json.loads(json.dumps(PACK.get("HP-01").to_dict()))
    scenario["unexpected_field"] = True
    with pytest.raises(SchemaValidationError):
        validate_scenario_document(scenario, source="unexpected-field")


def test_schema_itself_is_valid_json_schema() -> None:
    jsonschema.Draft202012Validator.check_schema(_scenario_schema())
