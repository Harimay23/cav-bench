# CAV-Bench

**Commit-Time Action Validity Benchmark** — an open-source, deterministic benchmark for evaluating whether consequential AI-agent actions remain valid at the moment they commit, across intent, authority, changing state, side-effect execution, and recovery.

> CAV-Bench proposes a unified benchmark for measuring the gap between successful outcomes and commit-valid execution across consequential-action failure classes.

[![CI](https://github.com/Harimay23/cav-bench/actions/workflows/ci.yml/badge.svg)](https://github.com/Harimay23/cav-bench/actions/workflows/ci.yml)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.21364385.svg)](https://doi.org/10.5281/zenodo.21364385)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)

Created and maintained by Nixalkumar Patel.

## The problem

A tool-using agent can look successful while its execution path was not. An order gets cancelled after it shipped. A refund fires twice after a retry. An action exceeds the caller's delegated authority. A multi-step workflow partially commits and the agent reports full success anyway. In each case, checking the *final state* can miss the failure, because the final value can coincidentally look fine even when an invalid side effect was committed along the way.

CAV-Bench separates two questions that outcome-only evaluation conflates:

1. **Did the task reach the expected end state?** (Outcome Success Rate)
2. **Did every consequential commit along the way stay valid — grounded in intent, authorized, current at commit time, executed without duplication or conflict, and recovered from truthfully when something went wrong?** (Commit-Valid Success Rate)

## What CAV-Bench does **not** evaluate

- It is **not an LLM leaderboard**. The included study runs five deterministic, non-LLM execution strategies (see [Controlled architecture ablation](#controlled-architecture-ablation-not-an-llm-benchmark) below), not language models.
- It does not claim to be the first benchmark to touch policy compliance, stateful tool use, idempotency, or authorization — those are established concerns. Its contribution is a single reproducible protocol that evaluates the *transition* from proposed action to committed external side effect.
- It is not a production transaction coordinator, a security sandbox against a malicious adapter, or a comprehensive benchmark of all agent reliability risks.
- It does not (yet) measure real frontier-model behavior. Building a model/tool adapter and running it through CAV-Bench is future work anyone can do against the stable adapter protocol described below.

## The five validity dimensions

A consequential commit is **commit-valid** when every dimension that applies to it passes:

| Dimension | Question |
|---|---|
| **Intent grounding** | Does the committed action stay within what the user actually asked for — scope, conditions, and parameters? |
| **Authority validity** | Is the principal (or its delegated agent) permitted to take this action, on this resource, in this tenant, right now? |
| **Temporal state validity** | Did the business precondition that justified the action still hold *at the commit boundary*, not just when it was first observed? |
| **Execution integrity** | Does the logical action map to the correct external side-effect cardinality — no harmful duplicates, no conflicting writes, no silent partial execution? |
| **Outcome recoverability** | When completion was partial or ambiguous, did the agent reconcile, compensate, safely stop, or escalate — and report the resulting state truthfully? |

Recovery is conditionally applicable; it is scored `not_applicable` for scenarios with no partial/ambiguous outcome to recover from.

## Metrics

```
OSR   = outcome_success / n                          # did the end state satisfy the goal?
PAOSR = policy_aware_outcome_success / n              # ...and no intent/authority violation?
CVSR  = commit_valid_success / n                      # ...and every dimension passed, non-compensatory?
VG    = OSR - CVSR                                    # Validity Gap
PAVG  = PAOSR - CVSR                                  # Policy-Adjusted Validity Gap
```

`commit_valid_success` is **non-compensatory**: a severe authority violation or a duplicated side effect is not averaged away by success elsewhere. CVSR is derived from the trace's committed side-effect ledger and authoritative state history — never from a label the system under test wrote about itself (see [Trust boundary](#trust-boundary)).

## Trust boundary

**The system under evaluation can never grade itself.** No adapter-, agent-, or trace-supplied field is trusted for pass/fail truth — not `commit_valid`, not `cvsr`, not a `failed_dimensions` list, nothing. `DeterministicEvaluator` derives every metric independently from:

- the scenario's private oracle (goal predicates, forbidden/required effects, recovery obligations — never exposed to the adapter),
- authoritative state and its version history,
- the canonical trace of environment-recorded events,
- the append-only side-effect ledger,
- recovery/escalation events the environment itself recorded.

An adapter's own `completion_status` claim is used exactly once: compared against a benchmark-derived floor to catch a false "success" report. It is never trusted directly. `tests/contract/test_evaluator_independence.py` proves this by forging `commit_valid`, `cvsr`, and `failed_dimensions` in adapter-supplied metadata and asserting the evaluator's result doesn't move.

## Controlled architecture ablation, not an LLM benchmark

The included `core-v1` scenario pack (40 scenarios across four families) ships with five **deterministic, non-LLM execution profiles** — controlled architecture baselines, not model results:

| Profile | Adds |
|---|---|
| `direct` | nothing — calls tools with no intent/authority gate, no commit-time guard, no reconciliation, no recovery |
| `policy_gated` | intent/authority checks before a consequential call |
| `commit_guarded` | + version-aware commit-time preconditions |
| `reconciled` | + stable idempotency keys and operation-status reconciliation |
| `full_lifecycle` | + compensation, bounded escalation, and truthful partial-state reporting |

Each profile is the *same* generic, capability-parameterized engine reacting to real tool calls against a real deterministic environment — not a lookup table of pre-selected pass/fail traces. Running all 40 scenarios through all five profiles reproduces this table exactly:

| Profile | OSR | PAOSR | CVSR | VG |
|---|---:|---:|---:|---:|
| direct | 0.925 | 0.750 | 0.250 | 0.675 |
| policy_gated | 1.000 | 1.000 | 0.500 | 0.500 |
| commit_guarded | 1.000 | 1.000 | 0.750 | 0.250 |
| reconciled | 1.000 | 1.000 | 0.875 | 0.125 |
| full_lifecycle | 1.000 | 1.000 | 1.000 | 0.000 |

This is a controlled ablation demonstrating that the benchmark is sensitive to specific, addable architectural safeguards — it is **not** a claim about how often any real model exhibits these failures. See [`docs/methodology.md`](docs/methodology.md) for the full methodology and limitations.

## Install

```bash
git clone https://github.com/Harimay23/cav-bench
cd cav-bench
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Requires Python 3.11, 3.12, or 3.13. Core execution requires no network access.

## Quickstart

```bash
pytest
cavbench doctor
cavbench list scenarios
cavbench run --profile direct
cavbench ablate
```

`cavbench run` and `cavbench ablate` write a full run directory (manifest, per-scenario traces, evaluation results, JSON/Markdown summaries) under `runs/`. See [`docs/reproducibility.md`](docs/reproducibility.md) for exact expected output and how to reproduce the table above from a clean checkout.

## Extending CAV-Bench

The adapter and scenario-pack boundaries are stable extension points; neither requires touching evaluator internals.

- **Add an adapter** (a real LLM agent, an agent framework, a future MCP client): implement `cavbench.adapters.protocol.ExecutionAdapter` — see [`docs/adapter-authoring.md`](docs/adapter-authoring.md) and [`examples/custom_adapter.py`](examples/custom_adapter.py).
- **Add a scenario pack** (a new domain, more coverage): author scenario JSON documents against `scenario-v1.schema.json` — see [`docs/scenario-authoring.md`](docs/scenario-authoring.md) and [`examples/custom_scenario_pack/`](examples/custom_scenario_pack/).
- **Use CAV-Bench in CI** as a regression gate: `cavbench run --profile <your-adapter> --fail-on-cvsr-below 0.9` exits non-zero when the threshold isn't met — see [`examples/ci_threshold.sh`](examples/ci_threshold.sh).

## Documentation

- [`docs/methodology.md`](docs/methodology.md) — full construct definition, scoring rules, limitations, non-claims
- [`docs/architecture.md`](docs/architecture.md) — component boundaries and the trust model
- [`docs/scenario-authoring.md`](docs/scenario-authoring.md) — scenario schema and how to write one
- [`docs/adapter-authoring.md`](docs/adapter-authoring.md) — the adapter protocol
- [`docs/reproducibility.md`](docs/reproducibility.md) — exact reproduction commands and expected output
- [`docs/citation.md`](docs/citation.md) — which DOI to cite and when, APA/BibTeX, future-release DOI handling
- [`docs/design/future-workstreams-index.md`](docs/design/future-workstreams-index.md) — proposed (not yet approved) designs for future validation, integration, and release workstreams, with program execution-control documents and diagrams
- [`DECISION_LOG.md`](DECISION_LOG.md) — locked design decisions, including everything changed during the v0.3 → v1.0 hardening pass

## Limitations

- Scenarios are synthetic and public; a model that has memorized them is not being tested honestly. CAV-Bench is a transparent methodology benchmark, not a hidden anti-contamination leaderboard.
- The benchmark is not a security sandbox: it does not defend against a malicious adapter's source code, only evaluate the actions a cooperating adapter takes through the tool facade.
- 40 scenarios across four families is a starting corpus, not exhaustive coverage of consequential-action failure modes.

## Citation

CAV-Bench has two distinct DOIs, for two distinct citation needs:

- **Concept DOI** [`10.5281/zenodo.21364385`](https://doi.org/10.5281/zenodo.21364385) identifies the CAV-Bench project across all versions. Use this when referring to CAV-Bench in general — it always resolves to the latest archived release.
- **Version DOI** [`10.5281/zenodo.21364386`](https://doi.org/10.5281/zenodo.21364386) identifies the exact, immutable `v1.0.0` artifact used to produce the canonical ablation results in this README. Use this when reproducibility of a specific result matters, e.g. citing the numbers in the [ablation table](#controlled-architecture-ablation-not-an-llm-benchmark) above.

For general references to the evolving project, cite the concept DOI:

> https://doi.org/10.5281/zenodo.21364385

For the exact v1.0.0 implementation and canonical ablation results, cite:

> Patel, Nixalkumar. (2026). *CAV-Bench: Commit-Time Action Validity Benchmark* (Version v1.0.0) [Computer software]. Zenodo. https://doi.org/10.5281/zenodo.21364386

```bibtex
@software{patel_2026_cav_bench,
  author    = {Patel, Nixalkumar},
  title     = {CAV-Bench: Commit-Time Action Validity Benchmark},
  version   = {v1.0.0},
  year      = {2026},
  publisher = {Zenodo},
  doi       = {10.5281/zenodo.21364386},
  url       = {https://doi.org/10.5281/zenodo.21364386}
}
```

The exact source archive associated with the canonical v1.0.0 experiment is preserved on Zenodo under DOI [10.5281/zenodo.21364386](https://doi.org/10.5281/zenodo.21364386), independent of any later changes to this repository.

See also [`CITATION.cff`](CITATION.cff), which GitHub's "Cite this repository" button reads automatically, and [`docs/citation.md`](docs/citation.md) for the full citation guide, including why reproducibility claims specifically must cite the version DOI rather than the concept DOI.

## License

Apache-2.0 — see [`LICENSE`](LICENSE).
