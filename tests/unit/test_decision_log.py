"""Structural check on `DECISION_LOG.md`: decision identifiers must be
unique.

Added after a review caught PR #12 colliding with an identifier
(`D-020`) already reserved by the in-flight PR #8 branch. This is a
lightweight, repository-local check — it does not know about identifiers
reserved on other branches, only duplicates within this file, but a
duplicate here is always a bug regardless of what else may collide.
"""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

DECISION_HEADING = re.compile(r"^##\s+(D-\d+)\b", re.MULTILINE)


def test_decision_log_has_no_duplicate_identifiers() -> None:
    text = Path("DECISION_LOG.md").read_text()
    ids = DECISION_HEADING.findall(text)
    assert ids, "expected at least one '## D-NNN' heading in DECISION_LOG.md"

    counts = Counter(ids)
    duplicates = sorted(identifier for identifier, count in counts.items() if count > 1)
    assert not duplicates, f"duplicate decision identifiers in DECISION_LOG.md: {duplicates}"


def test_generic_protocol_gateway_decision_is_d021() -> None:
    """The M-GPI-1 gateway decision was originally recorded as D-020,
    which collided with an identifier PR #8
    (feat/langgraph-four-scenario-runtime, framework-v1 pack) legitimately
    owns on its own branch. It was renamed to D-021 on this branch.

    This assertion is scoped to *this decision*, not to D-020's absence
    from the file in general: once PR #8 merges, D-020 will correctly
    exist in DECISION_LOG.md for the framework-v1 pack decision, and that
    is not a regression -- it is the expected valid merged state (D-020
    framework-v1, D-021 M-GPI-1). A prior version of this test asserted
    D-020 could never appear at all, which would have started failing
    the moment PR #8 merged; that assertion has been removed."""
    text = Path("DECISION_LOG.md").read_text()
    match = re.search(r"^## (D-\d+) — Generic protocol integration \(M-GPI-1\)", text, re.MULTILINE)
    assert match is not None, "expected a 'Generic protocol integration (M-GPI-1)' decision heading"
    assert match.group(1) == "D-021"
    assert match.group(1) != "D-020"
