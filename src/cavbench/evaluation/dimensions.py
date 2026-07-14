"""Mechanical, adapter-independent derivations for the two dimensions that
are cheap to compute directly from trace facts rather than declarative
oracle predicates: temporal state validity (stale-witness commits) and the
duplicate-effect portion of execution integrity.

Both operate purely on benchmark-owned facts (trace events, the side-effect
ledger) and never consult adapter-supplied metadata.
"""

from __future__ import annotations

from collections.abc import Mapping

from cavbench.runtime.trace import EpisodeTrace
from cavbench.scenarios.models import JSONValue


def stale_witness_commits(trace: EpisodeTrace) -> tuple[dict[str, JSONValue], ...]:
    """A commit is a stale-witness commit when the version authoritative at
    the moment of commit differs from the version most recently observed via
    a read of the same resource. This is derived purely from trace facts the
    environment always records, regardless of whether the acting profile
    used an atomic precondition.
    """
    last_observed: dict[str, int | None] = {}
    findings: list[dict[str, JSONValue]] = []
    for event in trace.events:
        if event.event_type == "tool_read":
            for ref in event.resource_refs:
                last_observed[ref] = (event.versions_before or {}).get(ref)
        elif event.event_type == "side_effect_commit":
            for ref in event.resource_refs:
                observed = last_observed.get(ref)
                actual = (event.versions_before or {}).get(ref)
                if observed is not None and actual is not None and observed != actual:
                    findings.append(
                        {
                            "seq": event.seq,
                            "tool_name": event.tool_name,
                            "resource_refs": list(event.resource_refs),
                            "reason": "stale_witness_commit",
                            "observed_version": observed,
                            "actual_version_at_commit": actual,
                        }
                    )
    return tuple(findings)


def duplicate_logical_effects(side_effects: tuple[Mapping[str, JSONValue], ...]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for effect in side_effects:
        logical_operation_id = effect.get("logical_operation_id")
        if logical_operation_id:
            counts[logical_operation_id] = counts.get(logical_operation_id, 0) + 1
    return {k: v for k, v in counts.items() if v > 1}
