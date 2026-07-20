# CAV-Bench v1.0 Decision Log

## D-001 — v1.0 is a hardening project, not a benchmark redesign

**Decision:** Preserve the existing research construct, 40-scenario corpus, five dimensions, and primary metrics unless implementation uncovers a correctness defect.

**Reason:** The concept and prototype have already been validated sufficiently to proceed.

---

## D-002 — Deterministic evaluator remains the source of headline metrics

**Decision:** No LLM judge is used for OSR, PAOSR, CVSR, VG, or PAVG.

**Reason:** Headline metrics should remain inspectable and reproducible.

---

## D-003 — Separate adapter-visible task view from private oracle

**Decision:** `ScenarioView` and `ScenarioOracle` are distinct types.

**Reason:** Prevent accidental leakage of expected outcomes through the public execution interface.

---

## D-004 — Adapter metadata is untrusted

**Decision:** An adapter cannot set validity labels, goal truth, dimension failures, or benchmark scores.

**Reason:** Benchmark subjects must not grade themselves.

---

## D-005 — Side-effect ledger is first-class benchmark truth

**Decision:** Execution integrity is evaluated using actual committed effects, not only normalized final state.

**Reason:** Duplicate and conflicting external effects can be invisible in collapsed object state.

---

## D-006 — Core runtime is local and network-free

**Decision:** CAV-Bench v1.0 requires no external API.

**Reason:** Reproducibility, CI usability, and clean separation between benchmark methodology and later real-agent studies.

---

## D-007 — Architecture baselines share the same adapter protocol as future agents

**Decision:** The five deterministic profiles implement `ExecutionAdapter`.

**Reason:** Future model/framework/MCP adapters should not require evaluator changes.

---

## D-008 — Python 3.11+ and `src/` package layout

**Decision:** Support Python 3.11, 3.12, and 3.13.

**Reason:** Modern typing and packaging with a broad practical compatibility range.

---

## D-009 — Core dependencies remain minimal

**Decision:** Prefer standard library; allow `jsonschema` as a small core dependency. Reporting libraries remain optional extras.

**Reason:** Lower adoption friction and easier reproducibility.

---

## D-010 — Apache-2.0 is the recommended public license

**Decision:** Use Apache-2.0 unless the project owner chooses another license before public release.

**Reason:** Permissive use with an explicit patent grant is generally suitable for an open technical benchmark.

**Note:** License selection should be confirmed before release.

---

## D-011 — Public v1.0 is transparent, not a hidden leaderboard

**Decision:** Scenario and oracle definitions may be public in the repository, while runtime APIs still separate them.

**Reason:** The first release is a methodology and engineering benchmark. Hidden-test anti-contamination infrastructure is out of scope.

---

## D-012 — Canonical ablation results are regression targets

**Decision:** Preserve the published v0.3 aggregate results as golden expected values for v1.0 migration.

**Reason:** They validate semantic equivalence across the hardening refactor.

---

## D-013 — MCP integration is post-v1.0

**Decision:** Design the adapter interface for MCP compatibility but do not make MCP a v1.0 release blocker.

**Reason:** Avoid expanding scope before the benchmark core is stable.

---

## D-014 — Replace v0.3's fixture-selection ablation with a real, plan-driven execution engine

**Decision:** The v0.3 prototype never actually executed a strategy against the environment: `ReferenceTraceFactory` hand-authored one "good" and one "bad" trace per scenario, and `run_ablation_study.py`'s `use_safe_trace()` picked which pre-baked trace to score per profile, keyed off a static `(family, capability)` lookup table. v1.0 replaces this entirely. Each scenario now declares an adapter-visible `policy` envelope (a `requested_intent`/`allowed_scope`/`ambiguous_reference` description of what the literal request licenses) and a `plan` (an ordered list of `PlannedStep`s: the mechanical actions a request-following executor would attempt, including an optional scope-narrowed alternative and an optional compensating step). All five baseline profiles are one shared, capability-parameterized engine (`adapters/baselines/_engine.py`) that walks this plan and calls the real `ToolFacade` against the real `BenchmarkEnvironment`; profiles differ only in which of four generic guard behaviors they apply (`intent_authority_gate`, `commit_time_state_guard`, `idempotency_reconciliation`, `recovery_coordinator`).

**Reason:** This is the core "prototype shortcut" the hardening mandate calls out: a benchmark subject that never actually acts cannot demonstrate that safeguards causally change outcomes, and hand-picking a good/bad trace per profile is a disguised form of an adapter (or its author) grading itself. The new design makes the ablation's headline numbers an *emergent property* of real tool-call sequences reacting to a real deterministic environment, not a lookup table.

**Verification:** Running all 40 scenarios through the 5 real profiles reproduces the exact canonical table from `TECHNICAL_DESIGN.md` / `ACCEPTANCE_CHECKLIST.md` (Direct 0.925/0.750/0.250/0.675 … Full lifecycle 1.000/1.000/1.000/0.000), including the by-family breakdown, with no hard-coded results anywhere in the runtime or evaluator.

---

## D-015 — Temporal state validity is derived mechanically from trace facts, not from guard usage

**Decision:** `evaluation/dimensions.py::stale_witness_commits` derives a stale-witness commit purely by comparing, for each `side_effect_commit` event, the version most recently observed via a `tool_read` of the same resource against the version the environment recorded as authoritative at the moment of that commit (`versions_before`, always recorded regardless of whether the caller supplied `expected_version`). It does not ask whether the caller "used" an atomic precondition.

**Reason:** Matches `ARCHITECTURE.md` §10: the store must make it provable *what version was observed* vs *what version existed at commit*, independent of adapter behavior. A profile that happens to avoid staleness without ever sending `expected_version` (impossible in practice here, but hypothetically) would still be judged correctly, and the check cannot be spoofed by an adapter claiming it "checked" a precondition it did not.

---

## D-016 — Faulted write steps use empty `changes` so a naive commit doesn't need to reproduce a business value to be judged invalid

**Decision:** For `state_mutation` scenarios (and other scenarios marked as able to mask failure behind a conventional outcome check), the scenario's write step declares `changes: {}`. The side effect (an illegitimate commit landing in the ledger against stale state) is what's invalid, independent of whether that commit also happens to overwrite the field a shallow oracle checks.

**Reason:** This reproduces the v0.3 prototype's central empirical claim — that outcome-only checking can miss invalid execution paths — mechanically and generically, without hand-authoring a narrative reason why the specific field value would coincidentally survive. It also keeps `goal_predicates` (OSR) and the ledger/version-derived `temporal_state_validity` check (CVSR) genuinely independent measurements of the same episode, as the architecture requires.

---

## D-017 — Truthful-reporting check combines declarative recovery obligations with a mechanical "any forced failure occurred" signal

**Decision:** `DeterministicEvaluator` computes a benchmark-derived "actual floor" for episode completion (`success` / `partial`) from (a) whether all declared `recovery.obligations` predicates hold and (b) whether any environment-owned `commit_rejected` event with `response_status == "FAILED"` exists in the canonical trace — a fact recorded by the environment when a scenario's fault forces a step to fail, entirely independent of adapter behavior. It then compares this floor against the adapter's self-reported (untrusted) `completion_status`; an adapter that reports better than the derived floor is flagged `OR_FALSE_SUCCESS_REPORT`, which fails `outcome_recoverability` regardless of what the adapter claims.

**Reason:** `TECHNICAL_DESIGN.md` §11.6 warns against free-form LLM semantic grading of truthful reporting, but a purely obligation-predicate-based floor is not, by itself, robust against a hypothetical adapter that fails a step and simply never mentions it. The mechanical "was a FAILED rejection ever recorded" signal closes that gap without inventing per-scenario bespoke checks, and is itself derived only from environment-owned trace facts.

---

## D-018 — `MAX_WRITE_ATTEMPTS = 4`

**Decision:** The generic engine's per-step retry budget is 4 attempts, shared between commit-time-guard-driven conflict retries and idempotency-reconciliation-driven ambiguous-response retries.

**Reason:** A `commit_time_state_guard`-only profile (no `idempotency_reconciliation`) needs enough budget to: (1) attempt the write, hit an ambiguous response after it actually committed, (2) naively retry with a stale `expected_version` and hit a spurious CONFLICT caused by its own earlier attempt, (3) re-read and retry with the now-current version, and (4) actually create the duplicate side effect it lacks the capability to avoid. A budget of 2 caused this profile to exhaust its attempts on step (2) and accidentally never create the duplicate — passing CVSR on execution-recovery scenarios it should fail per the canonical table. This was caught by comparing the computed ablation against the golden table (Commit-guarded showed CVSR 0.875 instead of the expected 0.750) before being accepted, per the "investigate deviations before changing anything" rule.

---

## D-019 — Cross-step fault targeting uses step-scoped hooks, not only tool/resource-scoped hooks

**Decision:** In addition to the `after_read:<namespace>:<resource_id>` and `before_commit:<tool>:<namespace>:<resource_id>` hooks (used for state mutation faults), the environment fires `before_commit_step:<step_id>` and `after_commit_step:<step_id>` on every commit attempt. `downstream_failure` and `compensation_failure` injections target a step_id directly (via this hook, or via an explicit `affects_step` payload fired from an earlier step's `after_commit_step` hook), rather than a tool/resource pair.

**Reason:** Several execution-recovery scenarios (e.g. `ER-08`) have multiple steps that share the same tool and resource (three `cancel_order_item` calls against the same order) but need only one of them to fail. Tool/resource-scoped hooks cannot express that; step-scoped hooks can, without adding scenario-ID-specific branches to the environment or engine.

---

## D-021 — Generic protocol integration (M-GPI-1): benchmark-owned gateway topology, REST-first, MCP deferred

**Decision:** M-GPI-1 implements a **benchmark-owned protocol gateway**: the candidate agent or service is the protocol *client*; `cavbench.gateway.core.GatewaySession` (run by the harness) is the protocol *server*. **Every accepted tool-operation request maps to exactly one `ToolFacade` invocation. Final-report submission is an accepted non-tool request and maps to zero `ToolFacade` invocations by design.** The gateway performs no batching, caching, speculative execution, or replay. `BenchmarkEnvironment.commit()` remains the sole effect executor and sole commit authority, unchanged and untouched by any new code path; the gateway holds no commit path of its own and never writes to the `SideEffectLedger` directly. A malformed envelope, a failed session-token check, or a **capability violation** — a `tool_name`/`namespace`/action combination the current scenario's `capabilities()` did not advertise, including a write tool submitted as a compensation and vice versa — is rejected before any `ToolFacade` call and therefore creates zero benchmark attempts (recorded only in the gateway's own redacted session log, never in the benchmark trace). The gateway never generates, repairs, or regenerates the candidate's `operation_id`, `idempotency_key`, or `correlation_id` — whether the candidate manages retry identity correctly, blind-retries with fresh identity, or reconciles ambiguity via the explicit `status_check` operation is itself part of what the benchmark measures, exactly as for a native `ExecutionAdapter`. The candidate's final report (the `report` action) is carried into `BenchmarkEnvironment.finalize()` exactly as `AdapterResult` metadata is today: untrusted comparison input, never commit truth (verified by `tests/contract/test_gateway_forged_report.py`, mirroring `tests/contract/test_evaluator_independence.py`). The REST frontend binds loopback-only by construction: `cavbench.gateway.bind.validate_loopback_host` rejects any bind address that resolves to a non-loopback interface (`0.0.0.0`, `::`, LAN/public addresses, or a hostname resolving to any non-loopback address) before a socket is ever opened.

The **imported-evidence topology** — the candidate executing effects against its own systems, with a measurement adapter later mirroring observed results into the benchmark via `ToolFacade` — was considered in `docs/design/generic-protocol-integration.md` and is explicitly **rejected**: it would manufacture a benchmark commit from an untrusted account of an effect that already happened elsewhere, violating `CLAUDE.md` rules 2–3 (framework/adapter/agent-reported status is never authoritative commit truth; committed-effect truth comes only from the benchmark environment). This rejection is part of the approved design (`docs/program/approvals/M-GPI-1.md`) and is not revisited by this milestone.

**Transport order:** a shared, transport-neutral gateway core (`cavbench.gateway.envelope`, `cavbench.gateway.core`) with **REST as the first implemented frontend** (`cavbench.gateway.rest`, standard-library `http.server` only — zero new runtime dependency, consistent with D-009). An MCP frontend is **deferred to a separately approved future milestone**; the core's transport-neutral shape preserves the extension point, but no MCP transport code, dependency, or behavior exists in this milestone, and none of this milestone's documentation describes MCP as supported.

**Gateway neutrality:** the gateway must stay measurement plumbing — it advertises, translates, correlates, and records, but never adds a safeguard the candidate didn't exhibit (no auto-reconciliation, no identity repair, no retry suppression on the candidate's behalf) and never hides a hazard it did exhibit. Enforced by `tests/contract/test_gateway_neutrality.py`: exact one-request-to-one-`ToolFacade`-invocation correspondence; zero attempts on malformed/unauthenticated requests; no gateway-initiated retry on `CONFLICT`; no gateway-initiated reconciliation on `AMBIGUOUS` (the ledger retains the committed effect regardless); candidate-invoked reconciliation maps to the existing `ToolFacade.status_check` path; a blind retry with a fresh `idempotency_key` produces a duplicate effect exactly as core ledger semantics already model, because the gateway adds no dedup of its own.

**Reason:** This is the same trust-boundary discipline the framework-adapter model already established (D-004 and `docs/architecture.md`), extended over a real wire boundary instead of an in-process `AdapterSession`. The gateway-mediated topology is the only one under consideration in which the benchmark structurally cannot manufacture a commit from an untrusted response, because there is exactly one effect executor (`BenchmarkEnvironment`) in the entire topology. REST-first (over MCP-first) was chosen because the envelope/session-binding/request-to-attempt-mapping semantics are the hard, novel, transport-independent work, and a stdlib-only REST frontend proves that work with zero new dependencies before taking on a moving external specification and a real dependency for MCP. Capability enforcement and loopback-only bind validation were added following technical review of the initial implementation, which found that an unconstrained candidate-supplied `tool_name`/`namespace` could reach `ToolFacade` with a shape the scenario never advertised, and that the REST server accepted arbitrary bind hosts including `0.0.0.0` — both closed before this decision was considered complete, since either would have violated the approved topology's trust and loopback-only boundaries.

**Verification:** `pytest tests/unit/test_gateway_envelope.py tests/unit/test_gateway_rest.py tests/unit/test_gateway_extras_isolation.py tests/unit/test_gateway_bind.py tests/unit/test_decision_log.py tests/contract/test_gateway_neutrality.py tests/contract/test_gateway_capability_enforcement.py tests/contract/test_gateway_forged_report.py tests/integration/test_gateway_hazards.py tests/integration/test_gateway_determinism.py` — envelope validation and identity pass-through; REST status-code mapping; core-import extras isolation; loopback-only bind validation (allowed: `127.0.0.1`/`::1`/`localhost`; rejected: `0.0.0.0`, `::`, LAN/public addresses, non-loopback-resolving hostnames, mixed-resolution hostnames); DECISION_LOG.md duplicate-identifier check; request-to-attempt correspondence, zero-attempt, no-auto-retry/reconciliation, compensation/escalation mapping, and oracle-leakage tests; capability-enforcement adversarial tests (unadvertised tool, wrong namespace, wrong action, compensation-as-write, write-as-compensation, arbitrary read namespace, unavailable operation — each a zero-`ToolFacade`-call rejection); the adversarial forged-report test; the four canonical hazard patterns (stale state before commit, ambiguous acknowledgement and retry, partial execution and recovery, authority change before commit) in guarded and flawed reference-candidate configurations, cross-checked against the existing `direct`/`full_lifecycle` baseline profiles' `commit_valid_success` outcome for the same scenarios; and double-run byte-identical trace determinism. All 40 `core-v1` scenarios' canonical ablation goldens (`tests/golden/test_canonical_ablation.py`) remain byte-identical before and after this milestone — no evaluator, runtime, or scenario-schema code changed.
