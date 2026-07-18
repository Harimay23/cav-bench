# Claude Code Implementation Prompts

Use each prompt in a fresh Claude Code session on the named branch. Do not combine prompts into one PR.

## Prompt 1 — Program documentation

```text
Work in repository Harimay23/cav-bench.
Create branch docs/90-day-engineering-program from main.

Add the supplied public engineering program artifacts:
- CLAUDE.md
- docs/strategy/90-day-engineering-program.md
- docs/strategy/14-day-validation-sprint.md
- docs/strategy/adoption-and-validation-tracking.md
- docs/diagrams/program-gantt.md
- docs/diagrams/dependency-graph.md
- docs/diagrams/milestone-map.md
- docs/diagrams/architecture-roadmap.md
- docs/prompts/claude-code-prompts.md

Constraints:
- Do not change production code, evaluator behavior, schemas, scenario packs, or dependencies.
- Keep public files focused on technical scope, user value, validation criteria, and project outcomes.
- Update CHANGELOG.md under [Unreleased].
- Verify markdown links and Mermaid syntax manually.
- Run pytest, ruff check ., mypy src/cavbench, python -m build, and git diff --check.
- Open a focused draft PR with exact files, non-goals, validation, and remaining claims.
```

## Prompt 2 — Complete LangGraph runtime

```text
Work from current main after the planning PR is merged.
Create branch feat/langgraph-four-scenario-runtime.
Read Issue #5, PR #6, docs/framework-adapter-brief.md, docs/langgraph-adapter-mapping.md, docs/architecture.md, docs/adapter-authoring.md, CONTRIBUTING.md, CLAUDE.md, and DECISION_LOG.md.

Implement a real LangGraph adapter and deterministic reference fixture for exactly four scenarios:
1. stale state before commit;
2. ambiguous retry after committed operation;
3. partial execution with compensation or escalation;
4. authority change before execution.

Preserve these constraints:
- CAV-Bench environment and ledger are sole commit truth.
- LangGraph state provides context only.
- stable operation_id and idempotency_key survive retries;
- LangGraph remains optional;
- use fine-grained nodes;
- use synchronous durability where supported;
- no evaluator semantic changes;
- no official support or endorsement claims.

Add contract, integration, and scenario tests. Update docs, CHANGELOG.md, and DECISION_LOG.md only where materially required. Run the full quality gate. Open a focused draft PR.
```

## Prompt 3 — Outcome-pass/CAV-fail demo

```text
Create branch feat/outcome-vs-commit-valid-demo.
Build an executable demonstration showing at least one workflow where conventional final-outcome testing passes while CAV-Bench fails because of an invalid committed effect.

Required cases:
- ambiguous retry producing a duplicate effect or requiring reconciliation;
- stale-state commitment that appears successful.

Provide:
- command-line entry point or example script;
- deterministic fixtures;
- expected output;
- evidence trace;
- remediation example;
- before-and-after CVSR comparison;
- concise README for external reviewers.

Do not change evaluator semantics. Add tests and run the full quality gate.
```

## Prompt 4 — Assurance report

```text
Create branch feat/assurance-report.
Add a report format that translates EvaluationResult into:
- apparent outcome;
- commit-valid result;
- validity dimension failures;
- authoritative evidence trace;
- potential operational consequence;
- recommended safeguard category;
- retest comparison.

Produce JSON and Markdown first. Add HTML only if it can be implemented without introducing unnecessary complexity.
Never let adapter-supplied text determine pass/fail or severity.
Add golden/report tests, docs, changelog entry, and full quality-gate validation.
```

## Prompt 5 — Commerce profile design

```text
Create branch docs/commerce-profile-design.
Do not implement scenarios yet.
Create a design RFC for a commerce-v1 scenario pack with 15–20 candidate consequential actions covering orders, inventory, pricing, payment, fulfillment, cancellation, refunds, returns, and recovery.

For each candidate include:
- action and durable effect;
- invalidity condition;
- authoritative state or oracle evidence;
- applicable CAV dimensions;
- expected safeguard;
- business consequence;
- testability without proprietary systems.

Include selection criteria for the initial implementation subset. Open an issue or link the existing issue before implementation.
```
