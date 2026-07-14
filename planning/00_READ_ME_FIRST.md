# CAV-Bench v1.0 Implementation Handoff

## Status

**Ready for implementation.** No additional conceptual research is required before a coding agent begins the public-quality v1.0 hardening work.

The current research prototype already provides:

- 40 deterministic scenarios across four families.
- A versioned in-memory state store.
- A deterministic fault injector.
- An append-only side-effect ledger.
- A deterministic evaluator.
- 80 golden validation traces.
- A controlled five-profile architecture ablation.
- Reproducible OSR, PAOSR, CVSR, Validity Gap, and PAVG metrics.

The public v1.0 work is therefore a **hardening and productization project**, not a greenfield benchmark-design project.

## Source baseline

The implementation agent should start from the latest prototype package:

- `cav_benchmark_v0_3_ablation.zip`

The existing package contains the current executable prototype, scenario corpus, reference traces, ablation code, and evidence outputs.

## Required documents

Read in this order:

1. `PRD.md` — what v1.0 must achieve and what is out of scope.
2. `ARCHITECTURE.md` — component boundaries, trust model, data flows, and repository structure.
3. `TECHNICAL_DESIGN.md` — schemas, APIs, CLI contracts, evaluator rules, packaging, testing, and release mechanics.
4. `IMPLEMENTATION_PLAN.md` — ordered execution plan and acceptance gates.
5. `DECISION_LOG.md` — locked design decisions and defaults.
6. `AGENTS.md` or `CLAUDE.md` — coding-agent operating instructions.
7. `ACCEPTANCE_CHECKLIST.md` — release gate for `v1.0.0`.

## Implementation principle

CAV-Bench evaluates whether **consequential side effects remained valid at commit time**. The benchmark must therefore keep the following concerns separate:

- what the agent or execution profile proposes;
- what the benchmark environment actually knows;
- what side effects actually commit;
- what recovery actually occurs;
- what the evaluator derives after the run.

An adapter, execution profile, or agent must never be able to pass by writing its own validity labels into the trace.

## Non-negotiable hardening requirement

The v0.3 prototype contains fixture-oriented shortcuts such as harness-computed validity checks stored in trace metadata. These are acceptable for prototype self-validation, but **must not be part of the public evaluation trust path**.

For v1.0:

- validity must be derived from scenario rules, authoritative state, commit events, side-effect identity, recovery events, and final state;
- adapter-controlled data must be treated as untrusted input;
- `outcome_success`, dimension results, invalid commits, and failure codes must be evaluator outputs only;
- reference/golden fixtures may use internal helpers, but those helpers must live under test-only or clearly internal modules and must not be callable by normal benchmark adapters.

## Recommended default technology choices

These defaults are locked for implementation unless a concrete blocker is found:

- Python `>=3.11`.
- Package/import name: `cavbench`.
- Distribution/project name: `cav-bench`.
- CLI command: `cavbench`.
- Core benchmark remains local and deterministic; no network required.
- Standard library for core runtime where practical.
- `jsonschema` as the only required schema-validation dependency if necessary.
- `pytest`, `ruff`, and `mypy` as development tooling.
- `matplotlib`/`pandas` only as optional reporting extras, not core runtime requirements.
- Apache-2.0 is the recommended public license; confirm before the public release is created.
- GitHub Actions for test, lint, type-check, build, and package smoke-test CI.

## Definition of done

CAV-Bench v1.0 is ready to publish when a new user can:

```bash
python -m venv .venv
source .venv/bin/activate
pip install cav-bench
cavbench doctor
cavbench list
cavbench run --profile direct
cavbench ablate
```

and obtain deterministic, schema-valid outputs with documented metrics and no access to private implementation shortcuts.
