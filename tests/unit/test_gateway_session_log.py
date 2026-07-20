"""Append-only, externally-immutable session log tests (M-GPI-1 review
follow-up).

`GatewaySessionLog` previously exposed a public mutable `entries` list
and `SessionLogEntry.detail` backed by a plain mutable dict a caller
could reach directly. A caller could clear, append to, or reorder
`session.log.entries` outright, or mutate a stored entry's nested
`detail` in place, despite the module's docstring claiming the log was
append-only. `_entries` is now private; `entries` is a read-only
property returning a fresh tuple of defensive copies on every access;
`record_request`/`record_rejection`/`record_discovery` are the only
append paths (routed through a single private `_append`).
"""

from __future__ import annotations

from cavbench.gateway.core import GatewaySession
from cavbench.gateway.session_log import GatewaySessionLog
from cavbench.scenarios.loader import load_builtin_pack

PACK = load_builtin_pack("core-v1")


def _log_with_two_entries() -> GatewaySessionLog:
    scenario = PACK.get("ER-04")
    session = GatewaySession.start(scenario, seed=0, run_id="log-fixture")
    session.discover_capabilities()
    session.discover_capabilities()
    return session.log


def test_entries_is_a_tuple_not_a_mutable_list() -> None:
    log = _log_with_two_entries()
    entries = log.entries
    assert isinstance(entries, tuple)
    assert not hasattr(entries, "append")
    assert not hasattr(entries, "clear")


def test_entries_cannot_be_cleared_appended_or_reordered_via_the_property() -> None:
    log = _log_with_two_entries()
    before = log.entries
    assert len(before) == 2

    # None of these can mutate the underlying store: a tuple has no
    # in-place mutating methods, and reassigning the local variable
    # `mutable` only rebinds a name, it does not touch `log`.
    mutable = list(log.entries)
    mutable.clear()
    mutable.append("not a real entry")
    mutable.reverse()

    after = log.entries
    assert len(after) == 2
    assert [e.seq for e in after] == [0, 1]


def test_mutating_nested_detail_from_an_exposed_entry_does_not_affect_internal_state() -> None:
    log = _log_with_two_entries()
    entry = log.entries[0]
    entry.detail["advertisement"]["session_id"] = "MUTATED"
    entry.detail["advertisement"]["operations"] = []

    re_fetched = log.entries[0]
    assert re_fetched.detail["advertisement"]["session_id"] != "MUTATED"
    assert re_fetched.detail["advertisement"]["operations"] != []


def test_mutating_to_list_output_does_not_affect_internal_state() -> None:
    log = _log_with_two_entries()
    listed = log.to_list()
    listed.clear()
    listed_again_but_wrong: list[object] = []
    listed_again_but_wrong.append("garbage")

    assert len(log.to_list()) == 2

    entries_dict = log.to_list()[0]
    entries_dict["detail"]["advertisement"]["session_id"] = "MUTATED"
    entries_dict["seq"] = 999999

    fresh = log.to_list()[0]
    assert fresh["detail"]["advertisement"]["session_id"] != "MUTATED"
    assert fresh["seq"] == 0


def test_prior_entries_remain_unchanged_after_later_log_writes() -> None:
    scenario = PACK.get("ER-04")
    session = GatewaySession.start(scenario, seed=0, run_id="log-prior-unchanged")
    session.discover_capabilities()
    first_snapshot = session.log.entries[0].to_dict()

    session.discover_capabilities()
    session.discover_capabilities()

    assert session.log.entries[0].to_dict() == first_snapshot


def test_sequence_numbers_are_monotonic_across_all_record_paths() -> None:
    scenario = PACK.get("ER-04")
    session = GatewaySession.start(scenario, seed=0, run_id="log-monotonic")
    session.discover_capabilities()
    session.handle({"garbage": True})  # malformed -> rejection
    session.discover_capabilities()

    seqs = [entry.seq for entry in session.log.entries]
    assert seqs == sorted(seqs)
    assert seqs == list(range(len(seqs)))


def test_tool_facade_call_count_remains_correct_after_external_mutation_attempts() -> None:
    scenario = PACK.get("ER-04")
    session = GatewaySession.start(scenario, seed=0, run_id="log-count-correct")
    session.discover_capabilities()  # not a ToolFacade call

    entries = list(session.log.entries)
    entries.clear()

    # `entries` yields fresh copies each access, so even a determined
    # bypass of `frozen=True` (object.__setattr__ skips the dataclass's
    # own __setattr__ guard) only mutates a copy, never the internal
    # SessionLogEntry the log actually stores.
    exposed_entry = session.log.entries[0]
    object.__setattr__(exposed_entry, "tool_facade_call", True)

    assert session.log.tool_facade_call_count() == 0


def test_capability_discovery_entries_are_byte_identical_after_attempted_external_mutation() -> None:
    import json

    scenario = PACK.get("ER-04")
    session = GatewaySession.start(scenario, seed=0, run_id="log-discovery-byte-identical")
    session.discover_capabilities()

    canonical = json.dumps(session.log.entries[0].to_dict(), sort_keys=True)

    exposed = session.log.entries[0]
    exposed.detail["advertisement"]["operations"].clear()
    exposed.detail["advertisement"]["session_id"] = "MUTATED"

    listed = session.log.to_list()[0]
    listed["detail"]["advertisement"]["operations"] = ["garbage"]

    after = json.dumps(session.log.entries[0].to_dict(), sort_keys=True)
    assert after == canonical
