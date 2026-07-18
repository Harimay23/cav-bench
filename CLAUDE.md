# CLAUDE.md

`AGENTS.md` remains the full agent operating-instruction source — read that
first. This file supplements it with current program-level mission and
planning context; it does not replace or override `AGENTS.md`.

## Project mission

CAV-Bench independently evaluates whether consequential AI-agent actions remain valid across intent, authority, current state, execution integrity, and recovery.

## Current program mission

During the current 90-day program, prioritize independently reproducible use, external technical validation, actionable assurance reporting, and documented system improvement.

## Non-negotiable architecture rules

1. The system under evaluation must never grade itself. See
   `docs/architecture.md` for the trust model and
   `tests/contract/test_evaluator_independence.py` for the adversarial test
   that enforces it.
2. Framework state, adapter output, model output, and agent-reported status are never authoritative commit truth.
3. Committed-effect truth must come from the benchmark environment, private oracle, authoritative state history, and side-effect ledger.
4. Never conflate attempted, acknowledged, committed, reconciled, compensated, and reported effects.
5. Do not change CVSR semantics, validity dimensions, or consequential-commit definitions without an approved issue and `DECISION_LOG.md` entry.
6. Never edit canonical golden results merely to make tests pass — see
   `DECISION_LOG.md` D-018 and `AGENTS.md`.
7. Do not claim endorsement, adoption, validation, or official support without explicit external evidence.
8. Keep optional framework dependencies isolated from the core package.

## Development priorities

1. External adoptability
2. Reproducibility
3. Actionable reports
4. One complete framework integration
5. Domain scenario packs
6. Generic protocol integration
7. Broader feature expansion

## Required workflow

For every material change:

1. Read `AGENTS.md` first, then the relevant issue and linked design
   documents.
2. Create a narrowly scoped branch.
3. State assumptions and non-goals before coding.
4. Add or update tests with behavior changes.
5. Update `CHANGELOG.md` under `[Unreleased]`.
6. Update `DECISION_LOG.md` for material design decisions.
7. Run the complete quality gate.
8. Open a focused pull request.

## Quality gate

```bash
pytest
ruff check .
mypy src/cavbench
python -m build
git diff --check
```

## Pull request requirements

Every PR must include:

- problem being solved;
- user or adopter who benefits;
- technical approach;
- trust-boundary impact;
- tests and validation performed;
- adoption barrier removed;
- externally verifiable output enabled;
- claims that remain unsupported;
- explicit non-goals.

## Branch conventions

```text
docs/<artifact>
feat/<capability>
fix/<problem>
test/<coverage>
chore/<maintenance>
```

Do not maintain a long-running program branch. Use short-lived branches and atomic PRs.

## Program execution order

1. Program documentation and visual roadmap
2. LangGraph four-scenario runtime
3. Outcome-versus-commit-valid demonstration
4. External reviewer kit
5. External validation gate
6. Commerce critical-actions profile
7. Generic MCP or REST integration
8. External benchmark runs
9. Before-and-after improvement case study
10. Community work products and release

## Stop conditions

Pause and escalate when:

- evaluator truth would depend on adapter-supplied assertions;
- canonical results unexpectedly change;
- a requested feature expands scope without improving adoption or reproducibility;
- external feedback materially contradicts the current model;
- a public claim cannot be supported by evidence.
