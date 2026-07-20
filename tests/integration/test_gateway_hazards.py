"""Reference-candidate integration tests over the four canonical hazard
patterns, in guarded and flawed configurations, driven entirely over REST
(M-GPI-1).

Each scenario is cross-checked against the same evaluation the repository's
own `direct` (flawed-equivalent) and `full_lifecycle` (guarded-equivalent)
baseline profiles produce for the same scenario, run directly against
`ToolFacade` -- proving the gateway's wire path reaches the same
commit-valid outcome as the native adapter path for identical guard
behavior, with no gateway-side assistance or interference.
"""

from __future__ import annotations

import pytest

from cavbench.adapters.baselines import BASELINE_PROFILES
from cavbench.evaluation.evaluator import DeterministicEvaluator
from cavbench.gateway.core import GatewaySession
from cavbench.gateway.rest import GatewayRestServer
from cavbench.runtime.environment import BenchmarkEnvironment
from cavbench.runtime.session import AdapterSession
from cavbench.runtime.tools import ToolFacade
from cavbench.scenarios.loader import load_builtin_pack
from examples.reference_candidate.client import RestGatewayClient
from examples.reference_candidate.driver import FLAWED, GUARDED, ReferenceCandidate

PACK = load_builtin_pack("core-v1")
EVALUATOR = DeterministicEvaluator()

# scenario_id -> hazard pattern label, per design's four canonical hazards
HAZARD_SCENARIOS = {
    "ST-01": "stale_state_before_commit",
    "ER-03": "ambiguous_acknowledgement_and_retry",
    "ER-04": "partial_execution_and_recovery",
    "IA-04": "authority_change_before_commit",
}


def _run_via_gateway(scenario_id: str, caps: object) -> bool:
    scenario = PACK.get(scenario_id)
    session = GatewaySession.start(scenario, seed=0, run_id=f"hazard-{scenario_id}-{id(caps)}")
    with GatewayRestServer(session) as server:
        client = RestGatewayClient(server.base_url, server.run_token)
        ReferenceCandidate(client, scenario.view, caps).run()  # type: ignore[arg-type]
    trace = session.finalize()
    return bool(EVALUATOR.evaluate(scenario, trace).commit_valid_success)


def _run_via_baseline(scenario_id: str, profile_name: str) -> bool:
    scenario = PACK.get(scenario_id)
    env = BenchmarkEnvironment(scenario, seed=0, run_id=f"baseline-{scenario_id}-{profile_name}")
    tools = ToolFacade(env)
    adapter = BASELINE_PROFILES[profile_name]
    result = adapter.run(AdapterSession(scenario.view, tools))
    trace = env.finalize(
        {
            "adapter_name": adapter.name,
            "adapter_version": adapter.version,
            "final_message": result.final_message,
            "completion_status": result.completion_status,
        }
    )
    return bool(EVALUATOR.evaluate(scenario, trace).commit_valid_success)


@pytest.mark.parametrize("scenario_id,hazard", list(HAZARD_SCENARIOS.items()), ids=list(HAZARD_SCENARIOS.values()))
def test_guarded_reference_candidate_matches_full_lifecycle_outcome(scenario_id: str, hazard: str) -> None:
    assert _run_via_gateway(scenario_id, GUARDED) == _run_via_baseline(scenario_id, "full_lifecycle") is True


@pytest.mark.parametrize("scenario_id,hazard", list(HAZARD_SCENARIOS.items()), ids=list(HAZARD_SCENARIOS.values()))
def test_flawed_reference_candidate_matches_direct_outcome(scenario_id: str, hazard: str) -> None:
    assert _run_via_gateway(scenario_id, FLAWED) == _run_via_baseline(scenario_id, "direct") is False


@pytest.mark.parametrize("scenario_id", list(HAZARD_SCENARIOS))
def test_guarded_and_flawed_configurations_diverge(scenario_id: str) -> None:
    """The whole point of the reference candidate: guarded vs. flawed must
    produce different commit-valid outcomes for every hazard scenario."""
    assert _run_via_gateway(scenario_id, GUARDED) != _run_via_gateway(scenario_id, FLAWED)
