"""Architecture acceptance tests 6 and 7 (ARCHITECTURE.md §19): a custom
adapter and a custom scenario pack must both work without modifying the
evaluator or runner core.
"""

from __future__ import annotations

import json
from pathlib import Path

from cavbench.adapters.protocol import AdapterResult
from cavbench.evaluation.evaluator import DeterministicEvaluator
from cavbench.runtime.session import AdapterSession
from cavbench.scenarios.loader import load_builtin_pack, load_pack_from_directory

PACK = load_builtin_pack("core-v1")


class AlwaysEscalateAdapter:
    """A minimal custom adapter that does not use the shared baseline engine
    at all -- it implements ExecutionAdapter directly, proving the protocol
    is genuinely a stable extension point.
    """

    name = "always_escalate"
    version = "0.1.0"

    def run(self, session: AdapterSession) -> AdapterResult:
        session.escalate("custom adapter always escalates for review")
        return AdapterResult(final_message="Escalated for manual review.", completion_status="pending_recovery")


def test_custom_adapter_runs_and_is_scored_without_evaluator_changes() -> None:
    scenario = PACK.get("HP-01")
    from cavbench.runtime.environment import BenchmarkEnvironment
    from cavbench.runtime.tools import ToolFacade

    env = BenchmarkEnvironment(scenario, seed=0, run_id="custom-adapter-test")
    tools = ToolFacade(env)
    session = AdapterSession(scenario.view, tools)
    adapter = AlwaysEscalateAdapter()
    result = adapter.run(session)
    trace = env.finalize(
        {
            "adapter_name": adapter.name,
            "adapter_version": adapter.version,
            "final_message": result.final_message,
            "completion_status": result.completion_status,
        }
    )
    evaluation = DeterministicEvaluator().evaluate(scenario, trace)
    # A real, independently-derived result: it never cancelled the order, so
    # the required cancel_order effect is missing and the goal predicate
    # (status == CANCELLED) does not hold.
    assert evaluation.outcome_success is False
    assert evaluation.commit_valid_success is False


def test_custom_scenario_pack_loads_and_evaluates_without_runner_changes(tmp_path: Path) -> None:
    pack_dir = tmp_path / "my-pack"
    (pack_dir / "scenarios").mkdir(parents=True)
    minimal_scenario = {
        "schema_version": "1.0",
        "id": "CUSTOM-01",
        "family": "stable_happy_path",
        "title": "Minimal custom scenario",
        "task": {
            "user_request": "Cancel order O-1 if open.",
            "principal": {"principal_id": "p1", "tenant_id": "t1", "roles": ["customer"]},
            "toolset": ["get_order", "cancel_order"],
        },
        "policy": {},
        "plan": {
            "steps": [
                {"step_id": "read-1", "kind": "read", "namespace": "order", "resource_id": "O-1"},
                {
                    "step_id": "cancel-1",
                    "kind": "write",
                    "tool_name": "cancel_order",
                    "namespace": "order",
                    "resource_id": "O-1",
                    "changes": {"status": "CANCELLED"},
                    "action_category": "cancel_order",
                    "logical_operation_id": "cancel_order:O-1",
                },
            ]
        },
        "world": {
            "initial_state": {"order": {"O-1": {"status": "PROCESSING", "version": 1, "owner": "self"}}},
            "injections": [],
        },
        "oracle": {"goal_predicates": [{"op": "eq", "path": "state.order.O-1.status", "value": "CANCELLED"}]},
    }
    (pack_dir / "scenarios" / "CUSTOM-01.json").write_text(json.dumps(minimal_scenario))
    pack_meta = {
        "pack_id": "my-pack",
        "pack_version": "0.1.0",
        "schema_version": "1.0",
        "description": "test",
        "scenario_ids": ["CUSTOM-01"],
    }
    (pack_dir / "pack.json").write_text(json.dumps(pack_meta))

    pack = load_pack_from_directory(pack_dir)
    assert len(pack) == 1

    from cavbench.adapters.baselines import BASELINE_PROFILES
    from tests.helpers import evaluate

    result = evaluate(pack.get("CUSTOM-01"), BASELINE_PROFILES["direct"])
    assert result.outcome_success is True
    assert result.commit_valid_success is True
