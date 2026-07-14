"""Deterministic, side-effect-free predicate engine.

Used in two places: (1) an execution adapter may consult a scenario's
adapter-visible ``PlannedStep.precondition`` against a freshly read resource
before deciding whether to act, and (2) the evaluator consults benchmark-owned
``ScenarioOracle`` predicates against derived evaluation facts. Both go
through this same module so there is exactly one predicate semantics in the
codebase.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from cavbench.scenarios.models import JSONValue, Predicate

_MISSING = object()


def resolve_path(context: Mapping[str, JSONValue], path: str) -> JSONValue:
    cursor: JSONValue = context
    for part in path.split("."):
        if isinstance(cursor, Mapping) and part in cursor:
            cursor = cursor[part]
        else:
            return _MISSING
    return cursor


def _matches_where(item: Mapping[str, JSONValue], where: Mapping[str, JSONValue]) -> bool:
    for key, expected in where.items():
        if item.get(key) != expected:
            return False
    return True


def _count(context: Mapping[str, JSONValue], collection: str, where: Mapping[str, JSONValue]) -> int:
    items = resolve_path(context, collection) if "." in collection else context.get(collection, ())
    if items is _MISSING or items is None:
        return 0
    if not isinstance(items, Sequence):
        raise ValueError(f"Predicate collection {collection!r} did not resolve to a sequence")
    return sum(1 for item in items if isinstance(item, Mapping) and _matches_where(item, where))


def evaluate(predicate: Predicate, context: Mapping[str, JSONValue]) -> bool:
    op = predicate.op

    if op in ("all", "any", "not"):
        results = [evaluate(p, context) for p in predicate.predicates]
        if op == "all":
            return all(results)
        if op == "any":
            return any(results)
        return not results[0]

    if op in ("count_eq", "count_lte", "count_gte"):
        assert predicate.collection is not None
        count = _count(context, predicate.collection, predicate.where)
        if op == "count_eq":
            return bool(count == predicate.value)
        if op == "count_lte":
            return bool(count <= predicate.value)
        return bool(count >= predicate.value)

    assert predicate.path is not None
    resolved = resolve_path(context, predicate.path)

    if op == "exists":
        return resolved is not _MISSING
    if op == "not_exists":
        return resolved is _MISSING

    if resolved is _MISSING:
        # Any comparison against a missing path is false, not an error --
        # this keeps predicates safe to write defensively.
        return False

    if op == "eq":
        return bool(resolved == predicate.value)
    if op == "ne":
        return bool(resolved != predicate.value)
    if op == "lt":
        return bool(resolved < predicate.value)
    if op == "lte":
        return bool(resolved <= predicate.value)
    if op == "gt":
        return bool(resolved > predicate.value)
    if op == "gte":
        return bool(resolved >= predicate.value)
    if op == "in":
        return resolved in predicate.value
    if op == "not_in":
        return resolved not in predicate.value

    raise ValueError(f"Unsupported predicate op: {op!r}")
