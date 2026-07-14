# Adapter authoring

An execution adapter is anything that implements
`cavbench.adapters.protocol.ExecutionAdapter`:

```python
from typing import Protocol
from cavbench.runtime.session import AdapterSession
from cavbench.adapters.protocol import AdapterResult

class ExecutionAdapter(Protocol):
    @property
    def name(self) -> str: ...
    @property
    def version(self) -> str: ...
    def run(self, session: AdapterSession) -> AdapterResult: ...
```

This is a `typing.Protocol` — you don't need to inherit from anything, just
match the shape. The five baseline profiles in `adapters/baselines/` all
implement it; so can a real LLM agent, an agent-framework wrapper, or a
future MCP client.

## What `session` gives you

`AdapterSession` exposes exactly two things:

- `session.scenario: ScenarioView` — `id`, `family`, `title`,
  `user_request`, `principal`, `toolset`, `policy`, `plan`. **No oracle, no
  goal predicates, no forbidden/required effects, no expected answer.**
  What you see here is genuinely everything the benchmark considers "given"
  to the agent.
- `session.tools: ToolFacade` — the only path into the environment:

```python
result = session.tools.read("order", "O-1001")
# result.status == "OK", result.data == {...current fields...}

result = session.tools.write(
    step_id="cancel-1",
    tool_name="cancel_order",
    namespace="order",
    resource_id="O-1001",
    changes={"status": "CANCELLED"},
    args={},
    logical_operation_id="cancel_order:O-1001",
    idempotency_key="stable-key-if-you-want-reconciliation",
    expected_version=3,  # omit to skip the optimistic-concurrency guard
)
# result.status in {"COMMITTED", "CONFLICT", "AMBIGUOUS", "IDEMPOTENT_REPLAY", "FAILED"}

session.tools.status_check(idempotency_key="stable-key-if-you-want-reconciliation")
session.escalate("reason")
session.clarify("question")
```

`step_id` only needs to be a stable string you choose per logical step in
your own strategy — it doesn't have to match anything in the scenario's
`plan` (that plan is a description of what a naive strategy would attempt,
not an instruction your adapter must follow).

## Returning a result

```python
return AdapterResult(
    final_message="Order cancelled.",
    completion_status="success",  # "success" | "partial" | "pending_recovery" | "failed"
    metadata={},  # anything you want in the trace's adapter_report; never trusted for scoring
)
```

**`completion_status` and `metadata` are never trusted for scoring.** The
evaluator only ever *compares* `completion_status` against a fact it
derived independently (did any step actually get rejected as `FAILED`? did
every recovery obligation hold?) to catch a false "success" report — see
`docs/methodology.md`. There is no field anywhere in `AdapterResult` that
can set your own OSR/PAOSR/CVSR, dimension status, or failure codes. Setting
`metadata={"commit_valid": True, "cvsr": 1.0}` does nothing;
`tests/contract/test_evaluator_independence.py` verifies this directly.

## A minimal custom adapter

```python
class AlwaysEscalateAdapter:
    name = "always_escalate"
    version = "0.1.0"

    def run(self, session):
        session.escalate("always escalates for manual review")
        return AdapterResult(final_message="Escalated.", completion_status="pending_recovery")
```

See `examples/custom_adapter.py` for a runnable version, and
`tests/integration/test_extensibility.py` for one wired through the
evaluator end to end.

## Running your adapter

The CLI only knows about the five built-in baseline names. To run a custom
adapter, use the Python API directly:

```python
from cavbench.scenarios.loader import load_builtin_pack
from cavbench.runtime.environment import BenchmarkEnvironment
from cavbench.runtime.tools import ToolFacade
from cavbench.runtime.session import AdapterSession
from cavbench.evaluation.evaluator import DeterministicEvaluator

pack = load_builtin_pack("core-v1")
adapter = MyAdapter()
evaluator = DeterministicEvaluator()

for scenario in pack:
    env = BenchmarkEnvironment(scenario, seed=0, run_id=f"{scenario.id}-{adapter.name}")
    session = AdapterSession(scenario.view, ToolFacade(env))
    result = adapter.run(session)
    trace = env.finalize({
        "adapter_name": adapter.name,
        "adapter_version": adapter.version,
        "final_message": result.final_message,
        "completion_status": result.completion_status,
    })
    print(scenario.id, evaluator.evaluate(scenario, trace).commit_valid_success)
```

`BenchmarkRunner.run()` does exactly this for a `RunConfig` plus a named
built-in profile; pass `adapter=` explicitly to use it with a custom
adapter instead of a profile name.
