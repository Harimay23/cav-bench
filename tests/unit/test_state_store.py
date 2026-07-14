from __future__ import annotations

import pytest

from cavbench.errors import ResourceNotFound, VersionConflict
from cavbench.runtime.state import VersionedStateStore


def make_store() -> VersionedStateStore:
    return VersionedStateStore({"order": {"O-1": {"status": "PROCESSING", "version": 1}}})


def test_get_returns_a_copy_not_a_live_reference() -> None:
    store = make_store()
    snapshot = store.get("order", "O-1")
    snapshot["status"] = "MUTATED_LOCALLY"
    assert store.get("order", "O-1")["status"] == "PROCESSING"


def test_mutate_bumps_version_exactly_once() -> None:
    store = make_store()
    result = store.mutate("order", "O-1", {"status": "CANCELLED"})
    assert result.before["version"] == 1
    assert result.after["version"] == 2
    assert store.get("order", "O-1")["version"] == 2


def test_stale_expected_version_is_rejected_deterministically() -> None:
    store = make_store()
    with pytest.raises(VersionConflict):
        store.mutate("order", "O-1", {"status": "CANCELLED"}, expected_version=99)
    # No mutation occurred.
    assert store.get("order", "O-1")["status"] == "PROCESSING"
    assert store.get("order", "O-1")["version"] == 1


def test_matching_expected_version_succeeds() -> None:
    store = make_store()
    store.mutate("order", "O-1", {"status": "CANCELLED"}, expected_version=1)
    assert store.get("order", "O-1")["status"] == "CANCELLED"


def test_missing_resource_raises() -> None:
    store = make_store()
    with pytest.raises(ResourceNotFound):
        store.get("order", "does-not-exist")


def test_nested_path_mutation() -> None:
    store = VersionedStateStore({"order": {"O-1": {"version": 1, "items": {"I-1": "ACTIVE"}}}})
    store.mutate("order", "O-1", {"items.I-1": "CANCELLED"})
    assert store.get("order", "O-1")["items"]["I-1"] == "CANCELLED"
