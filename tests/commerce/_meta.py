"""Parser for the machine-readable ``[commerce-v1 meta] ...`` header that
each commerce-v1 scenario carries in its (schema-native) ``notes`` field.

The scenario-v1 schema is strict (``additionalProperties: false``) and has no
free metadata object, so per-scenario adopter metadata (domain, core family,
dimensions, CMF-* codes, safeguards) rides the existing ``notes`` string plus
``oracle.dimension_focus`` and predicate ``failure_code`` -- never a schema
change. This helper is the single place that decodes that header so tests and
the control-mapping documentation stay in lockstep.
"""

from __future__ import annotations

import re
from collections.abc import Mapping

_HEADER = re.compile(r"\[commerce-v1 meta\]\s*(.*?)\.\s", re.DOTALL)
_LIST_FIELDS = ("dimensions", "cmf", "safeguards")


def parse_meta(notes: str) -> dict[str, object]:
    match = _HEADER.search(notes)
    if not match:
        raise AssertionError(f"scenario notes missing [commerce-v1 meta] header: {notes[:80]!r}")
    fields: dict[str, object] = {}
    for chunk in match.group(1).split(";"):
        chunk = chunk.strip()
        if not chunk or "=" not in chunk:
            continue
        key, _, value = chunk.partition("=")
        key = key.strip()
        value = value.strip()
        if key in _LIST_FIELDS:
            items = [v.strip() for v in value.split(",") if v.strip() and v.strip() != "none"]
            fields[key] = items
        else:
            fields[key] = value
    return fields


def cmf_codes(notes: str) -> list[str]:
    return list(parse_meta(notes).get("cmf", []))  # type: ignore[arg-type]


def declared_dimensions(notes: str) -> list[str]:
    return list(parse_meta(notes).get("dimensions", []))  # type: ignore[arg-type]


def safeguards(notes: str) -> list[str]:
    return list(parse_meta(notes).get("safeguards", []))  # type: ignore[arg-type]


def predicate_failure_codes(oracle_dict: Mapping[str, object]) -> set[str]:
    codes: set[str] = set()
    for key in ("forbidden_effects", "required_effects", "policy_constraints"):
        for pred in oracle_dict.get(key, []) or []:  # type: ignore[union-attr]
            code = pred.get("failure_code")  # type: ignore[union-attr]
            if code:
                codes.add(str(code))
    recovery = oracle_dict.get("recovery") or {}
    for pred in recovery.get("obligations", []) or []:  # type: ignore[union-attr]
        code = pred.get("failure_code")  # type: ignore[union-attr]
        if code:
            codes.add(str(code))
    return codes
