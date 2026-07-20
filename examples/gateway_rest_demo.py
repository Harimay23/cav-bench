"""Runnable local example: gateway + REST frontend + reference candidate
over one `core-v1` scenario (M-GPI-1).

Run:
    python examples/gateway_rest_demo.py --scenario ST-01 --mode guarded
    python examples/gateway_rest_demo.py --scenario ST-01 --mode flawed

This is also what the CI example job runs twice in a row to check
determinism (see `.github/workflows/ci.yml`, job `gateway-example`).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

if __name__ == "__main__" and __package__ in (None, ""):
    # Allow `python examples/gateway_rest_demo.py` to find the sibling
    # `examples.reference_candidate` package without requiring the caller
    # to set PYTHONPATH themselves.
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cavbench.evaluation.evaluator import DeterministicEvaluator  # noqa: E402
from cavbench.gateway.core import GatewaySession  # noqa: E402
from cavbench.gateway.rest import GatewayRestServer  # noqa: E402
from cavbench.scenarios.loader import load_builtin_pack  # noqa: E402
from examples.reference_candidate.client import RestGatewayClient  # noqa: E402
from examples.reference_candidate.driver import FLAWED, GUARDED, ReferenceCandidate  # noqa: E402

MODES = {"guarded": GUARDED, "flawed": FLAWED}


def run(scenario_id: str, mode: str, *, seed: int = 0) -> dict[str, object]:
    pack = load_builtin_pack("core-v1")
    scenario = pack.get(scenario_id)
    session = GatewaySession.start(scenario, seed=seed, run_id=f"demo::{scenario_id}::{mode}")
    with GatewayRestServer(session) as server:
        client = RestGatewayClient(server.base_url, server.run_token)
        candidate = ReferenceCandidate(client, scenario.view, MODES[mode])
        result = candidate.run()
    trace = session.finalize()
    evaluation = DeterministicEvaluator().evaluate(scenario, trace)
    return {
        "scenario_id": scenario_id,
        "mode": mode,
        "candidate_final_status": result.final_status,
        "tool_facade_calls": session.log.tool_facade_call_count(),
        "commit_valid_success": evaluation.commit_valid_success,
        "trace_digest": hashlib.sha256(json.dumps(trace.to_dict(), sort_keys=True).encode()).hexdigest(),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", default="ST-01")
    parser.add_argument("--mode", choices=sorted(MODES), default="guarded")
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args(argv)

    summary = run(args.scenario, args.mode, seed=args.seed)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
