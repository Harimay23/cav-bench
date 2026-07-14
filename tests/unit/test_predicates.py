from __future__ import annotations

from cavbench.evaluation.predicates import evaluate
from cavbench.scenarios.models import Predicate


def test_eq_ne() -> None:
    ctx = {"state": {"a": 1}}
    assert evaluate(Predicate(op="eq", path="state.a", value=1), ctx) is True
    assert evaluate(Predicate(op="ne", path="state.a", value=2), ctx) is True
    assert evaluate(Predicate(op="eq", path="state.a", value=2), ctx) is False


def test_ordering_ops() -> None:
    ctx = {"n": 5}
    assert evaluate(Predicate(op="lt", path="n", value=10), ctx) is True
    assert evaluate(Predicate(op="lte", path="n", value=5), ctx) is True
    assert evaluate(Predicate(op="gt", path="n", value=1), ctx) is True
    assert evaluate(Predicate(op="gte", path="n", value=5), ctx) is True


def test_in_not_in() -> None:
    ctx = {"status": "OPEN"}
    assert evaluate(Predicate(op="in", path="status", value=["OPEN", "CLOSED"]), ctx) is True
    assert evaluate(Predicate(op="not_in", path="status", value=["CLOSED"]), ctx) is True


def test_exists_not_exists() -> None:
    ctx = {"a": {"b": 1}}
    assert evaluate(Predicate(op="exists", path="a.b"), ctx) is True
    assert evaluate(Predicate(op="not_exists", path="a.c"), ctx) is True
    assert evaluate(Predicate(op="exists", path="a.c"), ctx) is False


def test_missing_path_comparison_is_false_not_an_error() -> None:
    ctx = {"a": {}}
    assert evaluate(Predicate(op="eq", path="a.missing", value=1), ctx) is False


def test_count_ops() -> None:
    ctx = {
        "side_effects": [
            {"effect_type": "refund"},
            {"effect_type": "refund"},
            {"effect_type": "escalate_case"},
        ]
    }
    refund_where = {"effect_type": "refund"}
    escalate_where = {"effect_type": "escalate_case"}
    missing_where = {"effect_type": "nonexistent"}
    assert evaluate(Predicate(op="count_eq", collection="side_effects", where=refund_where, value=2), ctx) is True
    assert evaluate(Predicate(op="count_gte", collection="side_effects", where=refund_where, value=1), ctx) is True
    assert evaluate(Predicate(op="count_lte", collection="side_effects", where=escalate_where, value=1), ctx) is True
    assert evaluate(Predicate(op="count_eq", collection="side_effects", where=missing_where, value=0), ctx) is True


def test_all_any_not() -> None:
    ctx = {"a": 1, "b": 2}
    eq_a1 = Predicate(op="eq", path="a", value=1)
    eq_a99 = Predicate(op="eq", path="a", value=99)
    eq_b2 = Predicate(op="eq", path="b", value=2)
    p_all = Predicate(op="all", predicates=(eq_a1, eq_b2))
    p_any = Predicate(op="any", predicates=(eq_a99, eq_b2))
    p_not = Predicate(op="not", predicates=(eq_a99,))
    assert evaluate(p_all, ctx) is True
    assert evaluate(p_any, ctx) is True
    assert evaluate(p_not, ctx) is True
