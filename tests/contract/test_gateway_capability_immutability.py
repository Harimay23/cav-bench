"""Capability-advertisement and session-log immutability tests (M-GPI-1
review follow-up).

`GatewaySession.capabilities()`/`discover_capabilities()` previously
returned the *same* cached mutable dict object on every call, and
`SessionLogEntry.to_dict()` shallow-copied only its top level, leaving
nested containers (e.g. `detail["advertisement"]["operations"]`) shared
with the stored entry. A caller mutating what it received could
therefore corrupt every future discovery response and the stored log
record. Both now return fresh, fully independent deep copies -- see
`GatewaySession._canonical_advertisement`/`capabilities`/
`discover_capabilities` and `SessionLogEntry.to_dict`.
"""

from __future__ import annotations

import copy
import json

from cavbench.gateway.core import GatewaySession
from cavbench.scenarios.loader import load_builtin_pack

PACK = load_builtin_pack("core-v1")


def _resource_scoped_index(operations: list[dict[str, object]]) -> int:
    return next(i for i, op in enumerate(operations) if "namespace" in op)


def test_mutating_a_returned_advertisement_does_not_affect_a_later_discovery_call() -> None:
    scenario = PACK.get("ER-04")
    session = GatewaySession.start(scenario, seed=0, run_id="immut-rediscover")

    first = session.discover_capabilities()
    canonical = copy.deepcopy(first)

    idx = _resource_scoped_index(first["operations"])
    first["operations"][idx]["namespace"] = "MUTATED"
    first["operations"][idx]["resource_id"] = "MUTATED"
    first["operations"].append({"action": "write", "tool_name": "evil", "namespace": "x", "resource_id": "y"})
    first["session_id"] = "MUTATED"
    first["toolset"].append("evil_tool")

    second = session.discover_capabilities()
    assert second == canonical


def test_mutating_nested_operations_does_not_affect_the_internal_cached_model() -> None:
    scenario = PACK.get("ER-04")
    session = GatewaySession.start(scenario, seed=0, run_id="immut-internal")

    first = session.capabilities()
    idx = _resource_scoped_index(first["operations"])
    original_namespace = first["operations"][idx]["namespace"]
    first["operations"][idx]["namespace"] = "MUTATED"

    # the internal canonical snapshot -- and therefore every future call --
    # must be unaffected.
    third = session.capabilities()
    assert third["operations"][idx]["namespace"] == original_namespace


def test_mutating_a_returned_advertisement_does_not_affect_a_prior_log_entry() -> None:
    scenario = PACK.get("ER-04")
    session = GatewaySession.start(scenario, seed=0, run_id="immut-prior-log")

    returned = session.discover_capabilities()
    logged_before = copy.deepcopy(session.log.entries[-1].to_dict())

    idx = _resource_scoped_index(returned["operations"])
    returned["operations"][idx]["namespace"] = "MUTATED"
    returned["operations"][idx]["resource_id"] = "MUTATED"

    logged_after = session.log.entries[-1].to_dict()
    assert logged_after == logged_before


def test_a_later_log_entry_is_unaffected_and_equals_the_canonical_snapshot() -> None:
    scenario = PACK.get("ER-04")
    session = GatewaySession.start(scenario, seed=0, run_id="immut-later-log")

    first = session.discover_capabilities()
    idx = _resource_scoped_index(first["operations"])
    first["operations"][idx]["namespace"] = "MUTATED"

    session.discover_capabilities()
    later_logged = session.log.entries[-1].to_dict()
    canonical = session.capabilities()
    assert later_logged["detail"]["advertisement"] == canonical


def test_mutating_the_object_returned_by_log_entry_to_dict_does_not_mutate_the_stored_entry() -> None:
    scenario = PACK.get("ER-04")
    session = GatewaySession.start(scenario, seed=0, run_id="immut-to-dict")
    session.discover_capabilities()

    entry = session.log.entries[-1]
    snapshot_before = entry.to_dict()
    idx = _resource_scoped_index(snapshot_before["detail"]["advertisement"]["operations"])

    mutable_view = entry.to_dict()
    mutable_view["detail"]["advertisement"]["operations"][idx]["namespace"] = "MUTATED"
    mutable_view["detail"]["advertisement"]["session_id"] = "MUTATED"
    mutable_view["seq"] = 999999

    snapshot_after = entry.to_dict()
    assert snapshot_after == snapshot_before
    assert snapshot_after["seq"] == entry.seq


def test_canonical_json_from_discovery_is_byte_identical_before_and_after_attempted_mutation() -> None:
    scenario = PACK.get("ER-04")
    session = GatewaySession.start(scenario, seed=0, run_id="immut-canonical-json")

    first = session.discover_capabilities()
    before_json = json.dumps(session.capabilities(), sort_keys=True)

    idx = _resource_scoped_index(first["operations"])
    first["operations"][idx]["namespace"] = "MUTATED"
    first["operations"].clear()
    first.clear()

    after_json = json.dumps(session.capabilities(), sort_keys=True)
    assert before_json == after_json

    rediscovered_json = json.dumps(session.discover_capabilities(), sort_keys=True)
    assert rediscovered_json == before_json


def test_two_calls_to_capabilities_return_distinct_objects_with_equal_content() -> None:
    scenario = PACK.get("ER-04")
    session = GatewaySession.start(scenario, seed=0, run_id="immut-distinct-objects")
    a = session.capabilities()
    b = session.capabilities()
    assert a == b
    assert a is not b
    assert a["operations"] is not b["operations"]
