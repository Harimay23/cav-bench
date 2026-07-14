# Product Requirements Document — CAV-Bench v1.0

**Product:** CAV-Bench  
**Expansion:** Commit-Time Action Validity Benchmark  
**Version target:** 1.0.0  
**Status:** Implementation-ready  
**Primary audience:** AI-agent engineers, evaluation researchers, AI security teams, enterprise AI platform teams, and tool/MCP ecosystem developers

---

## 1. Product summary

CAV-Bench is an open-source benchmark and deterministic evaluation harness for measuring whether consequential AI-agent actions remain valid when they become external side effects.

The benchmark separates three questions:

1. **Outcome Success Rate (OSR):** Did the task reach the expected outcome?
2. **Policy-Aware Outcome Success Rate (PAOSR):** Did the outcome also satisfy static intent and authority constraints?
3. **Commit-Valid Success Rate (CVSR):** Did the task succeed without any invalid consequential commit and with all required recovery obligations satisfied?

The product also reports:

- **Validity Gap (VG):** `OSR - CVSR`
- **Policy-Adjusted Validity Gap (PAVG):** `PAOSR - CVSR`

CAV-Bench v1.0 turns the current research prototype into a community-grade benchmark that can be installed, run, extended, reproduced, and cited.

---

## 2. Problem statement

A tool-using agent can appear successful while still producing an invalid execution path.

Examples include:

- an order is cancelled after it became ineligible for cancellation;
- a refund is issued twice after a timeout and retry;
- an action exceeds the user's requested scope or delegated authority;
- a multi-step workflow partially commits and the agent reports full success;
- normalized final state hides multiple irreversible side effects.

Outcome-oriented evaluation can miss these failures because the final state may look correct even when the side-effect path was not.

Existing agent evaluation work already covers important areas such as task success, policy compliance, stateful tool use, runtime safety, and prompt injection. CAV-Bench's product focus is narrower: **evaluating the transition from proposed action to committed external effect across the full validity lifecycle.**

---

## 3. Product goals

### G1. Provide a reproducible benchmark for commit-time action validity

A user must be able to run the included 40-scenario benchmark locally and reproduce the published architecture-ablation results.

### G2. Preserve the distinction between outcome success and path validity

The benchmark must independently compute OSR, PAOSR, CVSR, VG, and PAVG.

### G3. Use deterministic, inspectable scoring

The primary metrics must not require an LLM judge.

### G4. Make consequential effects observable

The evaluator must inspect an append-only side-effect ledger in addition to normalized final state.

### G5. Make the benchmark extensible

A contributor must be able to add new scenario packs and execution adapters without modifying the core evaluator.

### G6. Make the benchmark suitable for engineering workflows

The CLI and Python API must support local experimentation, reproducible reports, and CI regression checks.

### G7. Make the research artifact professionally citable

The repository must be release-ready with versioning, citation metadata, license, changelog, reproducibility documentation, and stable schemas.

---

## 4. Non-goals for v1.0

The following are explicitly out of scope:

- A leaderboard claiming performance for GPT, Claude, Gemini, or any other model.
- Hosted SaaS evaluation infrastructure.
- A web UI.
- A production transaction coordinator.
- Real payment, commerce, CRM, or ERP integrations.
- Hidden/private test sets designed to prevent benchmark contamination.
- Security isolation against a malicious local adapter reading benchmark source files.
- An MCP adapter. The architecture must support one, but implementation is a later milestone.
- Automatic publication to PyPI or Zenodo unless explicitly enabled during release execution.

---

## 5. Target users and jobs to be done

### 5.1 Agent framework engineer

**Job:** Determine whether a new execution safeguard reduces invalid side effects.

Needs to:

- run the same scenario set against two execution configurations;
- compare OSR, PAOSR, CVSR, and family-level results;
- inspect failing traces;
- add the benchmark to CI.

### 5.2 AI evaluation researcher

**Job:** Study how agent architectures behave under mutable state and execution faults.

Needs to:

- reproduce baseline results;
- plug in a custom adapter;
- fix seeds and scenario versions;
- export machine-readable traces and summaries.

### 5.3 AI security/red-team practitioner

**Job:** Test legitimate-looking agent actions that become unsafe or invalid without adversarial prompt injection.

Needs to:

- inspect intent/authority violations;
- test cross-tenant and over-broad actions;
- add domain-specific scenarios.

### 5.4 Enterprise AI platform team

**Job:** Use commit-validity metrics as a regression signal before deploying agent changes.

Needs to:

- run non-interactively;
- set failure thresholds;
- receive stable exit codes;
- preserve reports as build artifacts.

### 5.5 Tool or MCP ecosystem developer

**Job:** Evaluate whether tool integrations preserve validity under state changes, retries, and partial failures.

Needs to:

- implement an adapter against the public interface;
- map tool calls to benchmark trace events;
- reuse evaluator and scenario contracts.

---

## 6. Core concepts

### 6.1 Commit-Time Action Validity

A consequential action is commit-valid when every applicable dimension passes:

- **Intent grounding**
- **Authority validity**
- **Temporal state validity**
- **Execution integrity**
- **Outcome recoverability**

Recovery is conditionally applicable.

### 6.2 Consequential commit

A consequential commit is an event that changes externally meaningful state or creates an irreversible/compensatable side effect.

Reads, reasoning steps, and rejected write attempts are not consequential commits.

### 6.3 Side-effect ledger

The side-effect ledger records actual committed effects separately from normalized object state.

This allows the benchmark to detect cases such as two refunds that leave the order in a single `REFUNDED` state.

### 6.4 Scenario oracle

The oracle is benchmark-owned evaluation configuration that defines:

- goal predicates;
- intent and authority constraints;
- commit-time preconditions;
- forbidden and required effects;
- recovery obligations;
- applicable dimensions.

The adapter must never be able to write or override oracle results.

---

## 7. Functional requirements

### FR-1. Scenario loading and validation

The system must:

- load a versioned scenario pack;
- validate all scenarios against a published JSON Schema;
- reject unknown or incompatible schema versions;
- compute a stable digest for the scenario pack;
- expose only the adapter-visible scenario view to an adapter.

### FR-2. Deterministic benchmark environment

The environment must provide:

- versioned authoritative state;
- optimistic concurrency or equivalent atomic preconditions;
- deterministic mutation and fault hooks;
- append-only side-effect recording;
- deterministic logical time;
- reproducible seed handling.

### FR-3. Trace capture

The runner must record a normalized event stream including:

- user input;
- tool reads;
- external mutations;
- write attempts;
- rejected commits;
- committed side effects;
- operation-status reads;
- retries;
- compensation attempts/results;
- escalations;
- final agent message.

### FR-4. Evaluator

The evaluator must derive, not trust:

- `outcome_success`;
- `policy_aware_outcome_success`;
- `commit_valid_success`;
- dimension pass/fail/not-applicable states;
- invalid commit list;
- failure codes;
- diagnostics.

### FR-5. Baseline execution profiles

v1.0 must include five deterministic baselines:

1. Direct Tool Executor
2. Policy-Gated Executor
3. Commit-Guarded Executor
4. Commit-Guarded + Reconciliation
5. Full Lifecycle Executor

These are architecture baselines, not LLM results.

### FR-6. Benchmark runner

The runner must:

- run all or selected scenarios;
- run one or more profiles/adapters;
- accept a seed;
- create a run manifest;
- write traces and evaluations;
- aggregate overall and by-family metrics;
- return non-zero exit status on execution or validation failure.

### FR-7. CLI

Required commands:

```text
cavbench doctor
cavbench list
cavbench validate
cavbench run
cavbench ablate
cavbench replay
cavbench report
```

### FR-8. Reporting

The product must generate:

- `manifest.json`
- trace files
- `evaluations.jsonl` or equivalent
- `summary.json`
- `summary.md`

Optional reporting extras may generate CSV and PNG charts.

### FR-9. Extensibility

The product must expose stable protocols/interfaces for:

- execution adapters;
- scenario packs;
- report exporters.

The core evaluator must not depend on a specific model provider or agent framework.

### FR-10. Package and release metadata

The repository must include:

- `LICENSE`
- `CITATION.cff`
- `CHANGELOG.md`
- `CONTRIBUTING.md`
- `CODE_OF_CONDUCT.md`
- `SECURITY.md`
- versioned package metadata;
- release notes template.

---

## 8. Non-functional requirements

### NFR-1. Determinism

For the same:

- package version;
- scenario-set digest;
- adapter/profile version;
- seed;

baseline runs must produce equivalent evaluation results.

### NFR-2. Reproducibility

Every run manifest must record enough information to reproduce the run.

At minimum:

- CAV-Bench version;
- git commit when available;
- scenario-set name/version/digest;
- adapter/profile name/version;
- seed;
- Python version;
- platform;
- start time;
- command invocation.

### NFR-3. Trust separation

Adapter-controlled fields must never determine benchmark scores directly.

### NFR-4. Local-first operation

Core benchmark execution must require no network access.

### NFR-5. Performance

The 40-scenario deterministic baseline suite should complete quickly enough for local iteration and CI use. No specific wall-clock SLA is required for v1.0.

### NFR-6. Portability

Support Python 3.11, 3.12, and 3.13.

### NFR-7. Testability

Core evaluator, state store, ledger, scenario loader, and runner must have unit and integration coverage.

### NFR-8. Backward compatibility

Scenario and trace schemas must be explicitly versioned. Breaking changes after v1.0 require a schema-version change and documented migration.

---

## 9. Required v1.0 scenario set

The canonical `core-v1` pack contains 40 scenarios:

- 10 stable happy-path scenarios;
- 10 state-mutation scenarios;
- 10 intent/authority scenarios;
- 10 execution/recovery scenarios.

The existing scenario IDs and semantic intent must be preserved unless a correctness bug is found and documented.

---

## 10. Required public metrics

### Episode metrics

- outcome success
- policy-aware outcome success
- commit-valid success
- dimension statuses
- invalid commits
- failure codes

### Aggregate metrics

- OSR
- PAOSR
- CVSR
- VG
- PAVG

### Required breakdowns

- overall
- by scenario family

Optional later breakdowns:

- by failure code;
- by dimension;
- by tool/action type;
- repeated-run consistency.

---

## 11. User experience requirements

### First-run experience

A new contributor should be able to:

1. install the package;
2. run `cavbench doctor`;
3. list scenarios and profiles;
4. reproduce the included ablation;
5. locate outputs in a predictable directory;
6. understand why any scenario failed.

### Error messages

Errors must identify:

- the failing scenario or file;
- the schema or contract violation;
- the relevant field or event;
- the corrective action where possible.

---

## 12. Acceptance criteria for v1.0

The release passes when all of the following are true:

1. Clean environment install succeeds from built wheel and sdist.
2. `cavbench doctor` passes.
3. All 40 scenarios validate.
4. All reference fixtures validate.
5. Baseline ablation reproduces the expected metric table.
6. No public evaluator path trusts adapter-supplied validity labels.
7. Output schemas validate.
8. Unit, integration, and CLI smoke tests pass on supported Python versions.
9. Ruff and mypy checks pass at the agreed strictness level.
10. README contains a quickstart that works from a clean clone.
11. Reproduction instructions work without network access after installation.
12. Repository contains release, contribution, security, citation, and license metadata.
13. No confidential, employer-specific, or production data exists in the repository.
14. `v1.0.0` release artifacts are reproducible from the tagged commit.

---

## 13. Success indicators after release

These are adoption signals, not v1.0 release blockers:

- external issue containing substantive benchmark feedback;
- independent reproduction;
- external scenario contribution;
- framework or MCP adapter contribution;
- research citation;
- independent benchmark comparison;
- use in CI or regression testing;
- derivative domain pack.

---

## 14. Product risks

### Risk: The benchmark is interpreted as an LLM leaderboard

**Mitigation:** Every report and README result must label the included study as a deterministic architecture ablation.

### Risk: The evaluator trusts benchmark-profile hints

**Mitigation:** Derive results from benchmark-owned state, oracle, ledger, and trace facts only.

### Risk: Community users cannot adapt the benchmark

**Mitigation:** Stable adapter protocol, scenario-pack contract, examples, and extension documentation.

### Risk: The benchmark becomes too commerce-specific

**Mitigation:** Keep the core semantics generic even when scenarios use transaction examples. Separate future domain packs from the evaluator core.

### Risk: Public scenarios become memorized by models

**Mitigation:** CAV-Bench v1.0 is a transparent methodology benchmark, not a hidden leaderboard. Future model studies must disclose contamination limitations and may add versioned scenario packs.

---

## 15. Release positioning

CAV-Bench v1.0 should be described as:

> An open-source, deterministic benchmark for evaluating whether consequential AI-agent actions remain valid at the moment they commit, across intent, authority, changing state, side-effect execution, and recovery.

Do not describe v1.0 as:

- the first agent safety benchmark;
- proof that frontier models fail at the published ablation rates;
- a production transaction system;
- a comprehensive benchmark of all agent reliability risks.
