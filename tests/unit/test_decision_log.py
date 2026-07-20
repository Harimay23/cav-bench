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


def test_decision_log_identifiers_are_distinct_from_pr8_reserved_ids() -> None:
    """PR #8 (feat/langgraph-four-scenario-runtime) is open, frozen, and
    reserves D-020 for the framework-v1 pack decision on its own branch --
    it is not visible in this branch's DECISION_LOG.md, so the generic
    duplicate check above cannot see it. Pin it explicitly so a future
    rename accident is still caught locally before the branches merge."""
    text = Path("DECISION_LOG.md").read_text()
    ids = set(DECISION_HEADING.findall(text))
    assert "D-020" not in ids, (
        "D-020 is reserved by open PR #8 (framework-v1 pack decision) -- "
        "do not reuse it in this branch's DECISION_LOG.md"
    )
