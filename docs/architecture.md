# Architecture

## Objective

Evaluate the validity of **actual consequential commits**, not claims an
adapter makes about those commits. This drives one structural rule that
overrides every other design decision in this codebase:

> **No adapter-controlled field may directly set or override OSR, PAOSR,
> CVSR, dimension status, invalid-commit status, or failure codes.**

## Components and where they live

```
src/cavbench/
├── scenarios/
│   ├── models.py        # ScenarioView (adapter-visible) / ScenarioOracle (private) / Predicate
│   ├── loader.py         # schema validation, digest, ScenarioPack construction
│   ├── schemas/           # scenario-v1 / trace-v1 / evaluation-v1 JSON Schemas
│   └── packs/core-v1/     # the 40 canonical scenarios + pack.json
├── runtime/
│   ├── state.py           # VersionedStateStore: optimistic concurrency
│   ├── faults.py          # FaultScheduler: deterministic, one-shot, hook-based
│   ├── ledger.py           # SideEffectLedger: append-only, idempotency-key dedup
│   ├── environment.py      # BenchmarkEnvironment: the only writer of side_effect_commit
│   ├── tools.py             # ToolFacade: the only adapter-visible entry point
│   ├── session.py            # AdapterSession: scenario view + tools, nothing else
│   └── trace.py               # TraceEvent / EpisodeTrace
├── adapters/
│   ├── protocol.py         # ExecutionAdapter Protocol, AdapterResult (untrusted)
│   └── baselines/            # direct / policy_gated / commit_guarded / reconciled / full_lifecycle
│       └── _engine.py          # the one generic, capability-parameterized engine they all use
├── evaluation/
│   ├── predicates.py        # the one predicate engine (also used by adapter-side preconditions)
│   ├── dimensions.py         # mechanical temporal-validity / duplicate-effect derivations
│   ├── evaluator.py            # DeterministicEvaluator: orchestrates all of the above
│   ├── metrics.py               # OSR/PAOSR/CVSR/VG/PAVG aggregation
│   └── results.py                # EvaluationResult / MetricSummary (evaluator-owned only)
├── runner.py       # BenchmarkRunner: ties a pack + adapter + evaluator into a CompletedRun
├── manifest.py      # reproducibility manifest
├── reports/           # JSON/JSONL/Markdown output
├── cli.py               # doctor/list/validate/run/ablate/replay/report
└── api.py                 # the small stable public Python surface
```

## Trust model

### Trusted (benchmark-owned)

Scenario loader/validator, the private `ScenarioOracle`, `VersionedStateStore`,
`FaultScheduler`, `SideEffectLedger`, `BenchmarkEnvironment`, the trace
recorder, `DeterministicEvaluator`, metrics aggregation.

### Untrusted (the evaluation subject)

Execution adapters, whatever a model or framework does inside `.run()`,
tool-call arguments, an adapter's final message, and `AdapterResult.metadata`
— including `completion_status`. This last field is used exactly once, as a
comparison input to catch an overclaim, never as ground truth (see
`evaluator.py`'s truthful-reporting check and D-017 in `DECISION_LOG.md`).

### What the adapter session can see

`AdapterSession` (`runtime/session.py`) exposes exactly two things:
`scenario: ScenarioView` and `tools: ToolFacade`. `ScenarioView` has no
oracle field, no goal predicates, no forbidden/required effects, no
recovery obligations — `tests/contract/test_adapter_session_boundary.py`
asserts this at the dataclass-field level, not just by convention.

## Runtime sequence

```
Runner
  -> loads + validates ScenarioPack                 (scenarios/loader.py)
  -> constructs BenchmarkEnvironment(scenario, seed)  (runtime/environment.py)
  -> wraps it in a ToolFacade                          (runtime/tools.py)
  -> builds an AdapterSession(view, tools)               (runtime/session.py)
  -> adapter.run(session)                                  # untrusted
       -> session.tools.read/write/status_check/escalate/clarify
            -> BenchmarkEnvironment fires deterministic fault hooks,
               validates/rejects/commits, appends to the ledger,
               records canonical trace events
  -> env.finalize(adapter_report)  -> EpisodeTrace           # adapter_report is untrusted
  -> DeterministicEvaluator.evaluate(scenario, trace)          # derives everything independently
  -> aggregate metrics, write run artifacts
```

## The commit path

`BenchmarkEnvironment.commit()` is the **only** code path that can append to
the side-effect ledger or emit a `side_effect_commit` trace event. Every
consequential write, from every profile, from any future adapter, goes
through it. It:

1. records the attempt,
2. fires `before_commit_step:<step_id>` and `before_commit:<tool>:<namespace>:<resource_id>` fault hooks (may mutate state or mark this exact commit attempt as force-failed),
3. rejects on a forced failure, a stale `expected_version` (if one was supplied — omitting it is what lets an unguarded strategy commit against stale data), or an idempotency-key replay,
4. otherwise mutates state, appends to the ledger, and records the commit,
5. fires `after_commit_step:<step_id>` and `after_commit:<tool>:<namespace>:<resource_id>` (may sabotage a *later* step) and `after_commit_before_response:<tool>:<namespace>:<resource_id>` (may make *this* response ambiguous even though the commit already truly happened).

The environment always records the version that was actually authoritative
at the moment of commit, regardless of whether the caller supplied an
`expected_version` — this is what lets the evaluator derive temporal state
validity mechanically instead of trusting that the caller "used" a guard.

## Adapter architecture

All five baseline profiles implement `ExecutionAdapter` via one shared engine
(`adapters/baselines/_engine.py`) parameterized by four boolean capabilities:
`intent_authority_gate`, `commit_time_state_guard`, `idempotency_reconciliation`,
`recovery_coordinator`. They differ only in which capabilities are set —
none of them, and no part of the evaluator, special-cases a scenario ID or a
profile name. A future real-agent adapter implements the same
`ExecutionAdapter` protocol and is scored by the identical evaluator, with
no changes required on either side (see
`tests/integration/test_extensibility.py`).

## Output layout

```
runs/<run-id>/
├── manifest.json        # cavbench version, git commit, pack digest, adapter, seed, command
├── traces/<scenario-id>.json
├── evaluations.jsonl
├── summary.json
└── summary.md
```

`cavbench ablate` writes one such directory per profile under a shared
ablation directory, plus an ablation-level `summary.json`/`summary.md`.

## Extensibility boundaries

- **`ExecutionAdapter`** — real LLM agents, agent frameworks, and a future
  MCP adapter all plug in here without evaluator changes.
- **`ScenarioPack`** — new domains load via `load_pack_from_directory()`
  without runner changes, as long as they validate against
  `scenario-v1.schema.json`.
- **`ReportExporter`**-shaped functions in `reports/` — Markdown and JSON
  today; CSV/chart export lives behind the optional `reporting` extra.

The evaluator core is intentionally closed to casual extension: adding a
new validity dimension is a schema-version change and a methodology
decision, not a routine PR.
