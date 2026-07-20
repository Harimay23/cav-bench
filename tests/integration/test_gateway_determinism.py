"""Double-run determinism check (M-GPI-1 acceptance criterion 2 /
GPI-FR-015): two consecutive gateway + reference-candidate runs over the
same scenario and capability configuration must produce byte-identical
canonical trace artifacts."""

from __future__ import annotations

import json

import pytest

from cavbench.gateway.core import GatewaySession
from cavbench.gateway.rest import GatewayRestServer
from cavbench.scenarios.loader import load_builtin_pack
from examples.reference_candidate.client import RestGatewayClient
from examples.reference_candidate.driver import GUARDED, ReferenceCandidate

PACK = load_builtin_pack("core-v1")


def _run(scenario_id: str) -> dict[str, object]:
    scenario = PACK.get(scenario_id)
    session = GatewaySession.start(scenario, seed=0, run_id=f"determinism::{scenario_id}")
    with GatewayRestServer(session) as server:
        client = RestGatewayClient(server.base_url, server.run_token)
        ReferenceCandidate(client, scenario.view, GUARDED).run()
    trace = session.finalize()
    payload = trace.to_dict()
    # session-scoped, intentionally-random identifiers (run token, session
    # id) never enter the trace; strip only the fields that are inherently
    # per-process (the report's completion_status text is deterministic).
    return payload


@pytest.mark.parametrize("scenario_id", ["ST-01", "ER-03", "ER-04", "IA-04"])
def test_double_run_produces_byte_identical_trace(scenario_id: str) -> None:
    first = _run(scenario_id)
    second = _run(scenario_id)
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)
