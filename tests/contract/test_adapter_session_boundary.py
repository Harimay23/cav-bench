"""The adapter-facing session must not expose the scenario oracle or any
other benchmark-private evaluation detail.
"""

from __future__ import annotations

import dataclasses

from cavbench.runtime.session import AdapterSession
from cavbench.scenarios.loader import load_builtin_pack
from cavbench.scenarios.models import ScenarioOracle, ScenarioView

PACK = load_builtin_pack("core-v1")


def test_adapter_session_only_exposes_scenario_view_and_tools() -> None:
    field_names = {f.name for f in dataclasses.fields(AdapterSession)}
    assert field_names == {"_scenario", "_tools"}


def test_scenario_view_type_has_no_oracle_field() -> None:
    field_names = {f.name for f in dataclasses.fields(ScenarioView)}
    assert "oracle" not in field_names
    assert not any("oracle" in name.lower() for name in field_names)


def test_scenario_oracle_is_a_distinct_type_from_scenario_view() -> None:
    assert ScenarioOracle is not ScenarioView
    view_fields = {f.name for f in dataclasses.fields(ScenarioView)}
    oracle_fields = {f.name for f in dataclasses.fields(ScenarioOracle)}
    assert view_fields.isdisjoint(oracle_fields)


def test_session_scenario_property_returns_the_view_not_the_definition() -> None:
    scenario = PACK.get("HP-01")
    session = AdapterSession(scenario.view, None)  # type: ignore[arg-type]
    assert session.scenario is scenario.view
    assert isinstance(session.scenario, ScenarioView)
    assert not hasattr(session.scenario, "oracle")
