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

## D-020 — Framework-adapter scenarios ship as a separate builtin pack (`framework-v1`), never as `core-v1` additions

**Decision:** The four framework-adapter scenarios defined in `docs/framework-adapter-brief.md` (stale state before commit, ambiguous retry, partial execution, authority change before commit) are implemented as a second builtin pack, `framework-v1` (`FA-01`…`FA-04`), loaded through the same `load_builtin_pack` / schema-validation path as `core-v1`. They are framework-neutral scenario definitions (any adapter, including the five baselines, can execute them); the LangGraph reference fixture is merely their first consumer.

**Reason:** `core-v1` is the frozen canonical 40-scenario corpus whose aggregate ablation results are golden regression targets (D-012); adding scenarios to it would silently change every aggregate metric. A separate pack lets framework-adapter work ship executable, schema-validated scenarios without perturbing the canonical table, and keeps the brief's promise that these are new framework-facing scenarios, not aliases of existing `core-v1` IDs. Tests pin that `core-v1` still contains exactly 40 scenarios with no `FA-*` ids and that the canonical ablation is unchanged.

---

## D-021 — Generic protocol integration (M-GPI-1): benchmark-owned gateway topology, REST-first, MCP deferred

**Decision:** M-GPI-1 implements a **benchmark-owned protocol gateway**: the candidate agent or service is the protocol *client*; `cavbench.gateway.core.GatewaySession` (run by the harness) is the protocol *server*. **Every accepted tool-operation request maps to exactly one `ToolFacade` invocation. Final-report submission is an accepted non-tool request and maps to zero `ToolFacade` invocations by design.** The gateway performs no batching, caching, speculative execution, or replay. `BenchmarkEnvironment.commit()` remains the sole effect executor and sole commit authority, unchanged and untouched by any new code path; the gateway holds no commit path of its own and never writes to the `SideEffectLedger` directly. A malformed envelope, a failed session-token check, or a **capability violation** — an `(action, tool_name, namespace, resource_id)` combination the current scenario's `cavbench.gateway.capabilities.derive_operations` did not advertise, including a write tool submitted as a compensation and vice versa, or a real tool used against the wrong `resource_id` — is rejected before any `ToolFacade` call and therefore creates zero benchmark attempts (recorded only in the gateway's own redacted session log, never in the benchmark trace). `capabilities()` (advertisement) and `_check_capability()` (enforcement) read the identical, memoized set of `OperationDescriptor`s from `derive_operations`, so the two cannot diverge; deduplication is by the full `(action, tool_name, namespace, resource_id)` tuple, never by `tool_name` alone, so the same tool name can be independently visible under different actions, namespaces, or resource IDs. Capability discovery (`GET /capabilities` -> `GatewaySession.discover_capabilities()`) records the exact returned advertisement in the session log on every call — GPI-FR-009 — with the same frozen content on repeat calls. The gateway never generates, repairs, or regenerates the candidate's `operation_id`, `idempotency_key`, or `correlation_id` — whether the candidate manages retry identity correctly, blind-retries with fresh identity, or reconciles ambiguity via the explicit `status_check` operation is itself part of what the benchmark measures, exactly as for a native `ExecutionAdapter`. The candidate's final report (the `report` action) is carried into `BenchmarkEnvironment.finalize()` exactly as `AdapterResult` metadata is today: untrusted comparison input, never commit truth (verified by `tests/contract/test_gateway_forged_report.py`, mirroring `tests/contract/test_evaluator_independence.py`). The REST frontend binds loopback-only by construction: `cavbench.gateway.bind.validate_loopback_host` rejects any bind address that resolves to a non-loopback interface (`0.0.0.0`, `::`, LAN/public addresses, or a hostname resolving to any non-loopback address) before a socket is ever opened.

The **imported-evidence topology** — the candidate executing effects against its own systems, with a measurement adapter later mirroring observed results into the benchmark via `ToolFacade` — was considered in `docs/design/generic-protocol-integration.md` and is explicitly **rejected**: it would manufacture a benchmark commit from an untrusted account of an effect that already happened elsewhere, violating `CLAUDE.md` rules 2–3 (framework/adapter/agent-reported status is never authoritative commit truth; committed-effect truth comes only from the benchmark environment). This rejection is part of the approved design (`docs/program/approvals/M-GPI-1.md`) and is not revisited by this milestone.

**Transport order:** a shared, transport-neutral gateway core (`cavbench.gateway.envelope`, `cavbench.gateway.core`) with **REST as the first implemented frontend** (`cavbench.gateway.rest`, standard-library `http.server` only — zero new runtime dependency, consistent with D-009). An MCP frontend is **deferred to a separately approved future milestone**; the core's transport-neutral shape preserves the extension point, but no MCP transport code, dependency, or behavior exists in this milestone, and none of this milestone's documentation describes MCP as supported.

**Gateway neutrality:** the gateway must stay measurement plumbing — it advertises, translates, correlates, and records, but never adds a safeguard the candidate didn't exhibit (no auto-reconciliation, no identity repair, no retry suppression on the candidate's behalf) and never hides a hazard it did exhibit. Enforced by `tests/contract/test_gateway_neutrality.py`: exact one-request-to-one-`ToolFacade`-invocation correspondence; zero attempts on malformed/unauthenticated requests; no gateway-initiated retry on `CONFLICT`; no gateway-initiated reconciliation on `AMBIGUOUS` (the ledger retains the committed effect regardless); candidate-invoked reconciliation maps to the existing `ToolFacade.status_check` path; a blind retry with a fresh `idempotency_key` produces a duplicate effect exactly as core ledger semantics already model, because the gateway adds no dedup of its own.

**Reason:** This is the same trust-boundary discipline the framework-adapter model already established (D-004 and `docs/architecture.md`), extended over a real wire boundary instead of an in-process `AdapterSession`. The gateway-mediated topology is the only one under consideration in which the benchmark structurally cannot manufacture a commit from an untrusted response, because there is exactly one effect executor (`BenchmarkEnvironment`) in the entire topology. REST-first (over MCP-first) was chosen because the envelope/session-binding/request-to-attempt-mapping semantics are the hard, novel, transport-independent work, and a stdlib-only REST frontend proves that work with zero new dependencies before taking on a moving external specification and a real dependency for MCP. Capability enforcement and loopback-only bind validation were added following an initial technical review, which found that an unconstrained candidate-supplied `tool_name`/`namespace` could reach `ToolFacade` with a shape the scenario never advertised, and that the REST server accepted arbitrary bind hosts including `0.0.0.0`. A follow-up review found the resulting enforcement still stopped short of `resource_id`, that capability discovery was never logged despite GPI-FR-009 requiring it, and that advertisement and enforcement were two independently-maintained tool-name-keyed lookups that could silently diverge (and could not express the same tool name being visible under one action/namespace/resource combination but not another). `cavbench.gateway.capabilities.derive_operations` closes all three: one canonical, resource-level model read by both advertisement and enforcement, and `GatewaySession.discover_capabilities()` logs every capability-discovery call. A third review found two more issues, both now fixed: read *advertisement* (explicit `read`-kind steps only) and read *enforcement* (any resource touched by any resource-scoped step) were still two different rules computed separately, so a request could be accepted with no equivalent line in `/capabilities`; and `capabilities()`/`discover_capabilities()` returned the same cached mutable `dict` on every call while `SessionLogEntry.to_dict()` only shallow-copied its top level, so a caller mutating a returned object could corrupt future discovery responses or a stored log entry. `derive_operations` now synthesizes the implicit-read descriptors itself (one per unique `(namespace, resource_id)` touched by any resource-scoped step) as the *only* source of read visibility, so advertisement and enforcement are definitionally identical; and every accessor (`capabilities()`, `discover_capabilities()`, `SessionLogEntry.to_dict()`) now returns an independent `copy.deepcopy`, never a shared reference. A final review found two more issues: `tests/unit/test_decision_log.py` asserted `D-020` could never appear in `DECISION_LOG.md` at all, which would have started failing the moment PR #8 (which legitimately owns `D-020` for its framework-v1 pack decision) merges — replaced with an assertion scoped to this decision (`the M-GPI-1 heading is D-021, not D-020`) alongside the still-generic duplicate-identifier check; and `GatewaySessionLog` exposed a public mutable `entries` list and `SessionLogEntry.detail` backed by a plain mutable dict a caller could reach directly, so the log was not actually append-only despite its docstring's claim. `_entries` is now private; `record_request`/`record_rejection`/`record_discovery` (routed through one private `_append`) are the only ways to add an entry; and the public `entries` property and `to_list()` both return fresh defensive copies (including a fresh deep copy of `detail`) on every access, so nothing obtained from either can clear, append to, reorder, or mutate what is actually stored. A fifth review found one more determinism issue and one closely related lifecycle bug: `GatewayRestServer` used `http.server.ThreadingHTTPServer` while every request handler shares one mutable `GatewaySession` (its `BenchmarkEnvironment`, `ToolFacade`, idempotency map, final-report state, and session log) — concurrent handling could make request order, commit order, trace order, and session-log ordering nondeterministic; and calling `stop()` before `start()` hung, because `HTTPServer.shutdown()` blocks waiting for a `serve_forever()` loop that was never running (the listening socket already exists from `__init__` regardless). `GatewayRestServer` now uses plain `http.server.HTTPServer` (no `ThreadingMixIn`): requests are handled one at a time, in full, before the next is accepted — the simplest approved deterministic model, with no remote mode, worker pools, async execution, batching, or parallel commit semantics introduced. **The concurrency contract is stated precisely, not overclaimed:** requests never overlap and are processed sequentially; processing order is whatever order `HTTPServer` actually accepted the underlying TCP connections in (no gateway-imposed queueing, sorting, or reordering); a deterministic, reproducible candidate trace requires the candidate itself to send one request at a time and wait for each response (as the reference candidate and every baseline profile already do); arbitrary concurrent client arrival ordering across independent connections is not claimed to be reproducible. A sixth review found that `start()` launched the server thread and returned before proving `serve_forever()` had actually reached its loop, so an immediate `stop()` could still call `shutdown()` too early (the same hang as before, reachable through a race rather than a missing call) — closed by `_HandshakingHTTPServer`, which overrides the documented `service_actions()` extension point to signal a `threading.Event` on its first invocation (always *after* that loop iteration's `select()` returns, so it is authoritative proof the loop is running); `start()` now blocks on that event (bounded by a startup timeout, raising `ServerLifecycleError` and tearing the server down cleanly if it never fires) before returning, and `start()`/`stop()` share one lock for their entire call so competing invocations from different threads serialize deterministically instead of racing — a `stop()` arriving mid-startup simply waits for `start()` to finish resolving first. Lifecycle remains state-aware (`created -> running -> stopped`): `stop()` before `start()` only closes the listening socket and returns immediately (no `shutdown()` call, no hang); `start()` while already running is an idempotent no-op; `start()` after `stop()` raises `cavbench.gateway.errors.ServerLifecycleError`; `stop()` is idempotent and calls `server_close()` exactly once. A seventh review found the round-six fix's own startup-timeout cleanup closed the socket but never proved the already-launched server thread had actually terminated, and that the tests exercising it replaced `GatewayRestServer._httpd` *after* construction had already bound the original server's socket, leaking it. `GatewayRestServer` no longer uses `serve_forever()`/`shutdown()` at all: `_ManagedHTTPServer.run()` is a loop over the public `handle_request()` primitive, cancelled via an always-safe-to-signal `threading.Event` (`request_cancellation()`, safe to call at any time, including before the thread has started) rather than `serve_forever()`'s private shutdown handshake. One internal `GatewayRestServer._cleanup()` -- signal cancellation, join the thread with a bounded timeout, close the socket exactly once -- is called by both `start()`'s timeout path and `stop()`, and returns whether the thread was actually confirmed dead; if a bounded join cannot confirm termination, `start()` raises a distinct `ServerLifecycleError` naming both failures rather than claiming a teardown that did not happen. Test-server injection now uses a private `_server_class` constructor parameter, installing a test double before any socket is bound, so the default server is never separately constructed or leaked. An eighth review found `stop()` itself did not honor `_cleanup()`'s own contract: `_cleanup()` returns `False` when a bounded join cannot confirm the server thread actually terminated, and `start()`'s startup-timeout path already treated that as a real failure, but ordinary `stop()` discarded the return value entirely and always reported success even when the thread was still alive. `stop()` now captures `_cleanup()`'s result and raises `ServerLifecycleError` (stating that cancellation was requested but the thread did not terminate within `_SHUTDOWN_JOIN_TIMEOUT_SECONDS`) under the same condition `start()` already raises for -- the same honest-termination contract now applies uniformly to both lifecycle paths, and to direct `GatewayRestServer.stop()`, the callable `serve()` returns (now `serve()` also accepts the private `_server_class` injection point, since its returned stopper is literally `GatewayRestServer.stop`), and context-manager `__exit__`. The socket is still closed exactly once regardless of whether termination was confirmed (`_closed` is guarded independently of `_state`), state remains the terminal `"stopped"`, and a later `stop()` call is always safe to retry: it re-signals cancellation (harmless if already signaled) and rejoins the same thread reference, succeeding harmlessly once that thread has actually exited, with `server_close()` never called a second time.

**Verification:** `pytest tests/unit/test_gateway_envelope.py tests/unit/test_gateway_rest.py tests/unit/test_gateway_extras_isolation.py tests/unit/test_gateway_bind.py tests/unit/test_decision_log.py tests/unit/test_gateway_capabilities_model.py tests/unit/test_gateway_session_log.py tests/unit/test_gateway_rest_lifecycle.py tests/contract/test_gateway_rest_concurrency.py tests/contract/test_gateway_neutrality.py tests/contract/test_gateway_capability_enforcement.py tests/contract/test_gateway_capability_discovery.py tests/contract/test_gateway_capability_consistency.py tests/contract/test_gateway_capability_immutability.py tests/contract/test_gateway_forged_report.py tests/integration/test_gateway_hazards.py tests/integration/test_gateway_determinism.py` — envelope validation and identity pass-through; REST status-code mapping; core-import extras isolation; loopback-only bind validation (allowed: `127.0.0.1`/`::1`/`localhost`; rejected: `0.0.0.0`, `::`, LAN/public addresses, non-loopback-resolving hostnames, mixed-resolution hostnames); DECISION_LOG.md duplicate-identifier check; the canonical capability model (same tool name distinct under different action/namespace/resource_id, dedup by full tuple not `tool_name` alone); request-to-attempt correspondence, zero-attempt, no-auto-retry/reconciliation, compensation/escalation mapping, and oracle-leakage tests; capability-enforcement adversarial tests at the resource_id level (unadvertised tool, wrong namespace, wrong action, wrong resource_id for a valid write/compensate/read, compensation-as-write, write-as-compensation, a resource visible for one operation but not another, unavailable operation — each a zero-`ToolFacade`-call rejection); generic advertisement/enforcement consistency tests across five scenarios (every advertised resource-scoped descriptor is accepted with its exact action/tool/namespace/resource, every accepted request's descriptor is a literal member of the advertised set, an unadvertised operation is rejected with zero attempts, write-only and compensate-only resources advertise the implicit read); capability-discovery logging tests (logged, equals returned advertisement, no run token, no oracle content, deterministic across repeated calls with one log entry per call); immutability tests (mutating a returned advertisement does not affect a later call, the internal cached model, a prior log entry, or a later log entry; mutating a log entry's `to_dict()` output does not mutate the stored entry; canonical JSON is byte-identical before and after attempted mutation); genuinely-append-only session-log tests (`entries` cannot be cleared/appended/reordered, mutating nested `detail` from an exposed entry or `to_list()` output does not affect internal state, prior entries remain unchanged after later writes, sequence numbers are monotonic, `tool_facade_call_count()` stays correct against mutation attempts including a `frozen=True` bypass via `object.__setattr__`, and capability-discovery entries are byte-identical after attempted external mutation); a scoped decision-identifier regression test (the M-GPI-1 heading is `D-021`, not `D-020`, without asserting `D-020`'s permanent absence — that would break once PR #8 legitimately merges its own `D-020`); concurrent-request serialization tests (simultaneous requests never overlap in `GatewaySession.handle`, accepted concurrent requests still map one-to-one to `ToolFacade` calls, log sequence numbers stay unique/contiguous in actual processing order without claiming a predicted order, ledger commits never race, report submission cannot race a consequential operation, two independent runs of the same concurrent workload converge on the same final state without claiming a reproducible ordered trace, and finalization cannot observe an in-flight operation because `stop()` joins the server thread first); server-lifecycle tests bounded by a daemon-thread timeout helper (`stop()` before `start()` does not hang and still closes the socket, `start()` is idempotent while running and raises `ServerLifecycleError` after `stop()`, `stop()` is idempotent, normal and exception-path context-manager use both clean up correctly, `server_close()` is called exactly once under repeated `stop()` calls, rapid repeated start/stop cycles never hang, competing threads calling `start()`/`stop()` simultaneously resolve deterministically to one of two valid outcomes, `stop()` arriving mid-startup waits for `start()` to resolve first rather than racing it, a simulated startup timeout raises `ServerLifecycleError` and leaves the server cleanly stopped, and no server thread or listening socket survives `stop()`; startup-timeout cleanup leaves no live server thread; a thread reference exists but `is_alive()` is confirmed false after cleanup; `stop()` after a startup failure is harmless and repeatable without a second `server_close()` call; startup-failure cleanup completes within a bounded timeout; cleanup honestly reports when a pathological thread cannot be confirmed terminated in time; ten repeated startup-failure runs compared against the process's live-thread set before and after accumulate no leaked threads; and injecting a test server via the private `_server_class` constructor parameter never leaks a separately-constructed default server); ordinary-shutdown termination-failure tests using an `Event`-gated test double that ignores cancellation until explicitly released (first `stop()` raises `ServerLifecycleError` with termination-specific wording while the thread is genuinely still alive and the socket is already closed and state is already `"stopped"`; a second `stop()` after the thread actually exits succeeds harmlessly and a third remains idempotent; `server_close()` is called exactly once across a failed attempt and its retries; the same failure surfaces through context-manager `__exit__` and through the stopper `serve()` returns); the adversarial forged-report test; the four canonical hazard patterns (stale state before commit, ambiguous acknowledgement and retry, partial execution and recovery, authority change before commit) in guarded and flawed reference-candidate configurations, cross-checked against the existing `direct`/`full_lifecycle` baseline profiles' `commit_valid_success` outcome for the same scenarios; and double-run byte-identical trace determinism (unchanged trace digest from the prior round, confirming no behavioral regression). All 40 `core-v1` scenarios' canonical ablation goldens (`tests/golden/test_canonical_ablation.py`) remain byte-identical before and after this milestone — no evaluator, runtime, or scenario-schema code changed.

---

## D-022 — Commerce-v1 (M-COM-V1) ships as a separate applied-profile pack; adopter metadata rides existing schema fields

**Decision:** The commerce-v1 profile (Issue #13) is implemented as a third builtin pack, `commerce-v1` (`packs/commerce-v1/`), loaded through the same `load_builtin_pack` / schema-validation path as `core-v1` and `framework-v1` (D-020). It contributes a *proposed* working subset of five hazard scenarios — `CM-ORD-01` duplicate order, `CM-INV-01` stale stock, `CM-PRC-02` discount beyond delegated limit, `CM-PAY-02` capture after authorization void, `CM-REC-01` divergent partial cancellation — plus four `stable_happy_path` controls (one per hazard mechanic: `CM-ORD-90`, `CM-INV-90`, `CM-PAY-90`, `CM-PRC-90`), spanning all five validity dimensions and three core hazard families. `CM-PRC-02` independently evidences both declared dimensions (intent_grounding and authority_validity) with two forbidden-effect predicates over the committed discount versus the delegated limit, following a pre-Gate-2 review correction. It reuses the existing fault hooks (`ambiguous_response`, `external_mutation`, step-scoped `downstream_failure`), the mechanical duplicate-effect and stale-witness derivations, the truthful-report floor (D-017), and the empty-`changes` convention (D-016). No `core-v1`, schema, evaluator, runtime, adapter, dependency, or existing golden changed. Per-scenario adopter metadata (domain, core family, applicable dimensions, `CMF-*` domain codes, safeguards) is carried in existing schema-native fields — `oracle.dimension_focus`, predicate `failure_code`, and a machine-readable `[commerce-v1 meta]` header in the schema's free `notes` string — never a new schema field. The pack's own golden ablation (`tests/golden/test_commerce_v1_ablation.py`) is commerce-v1-only and is never co-edited with the frozen `core-v1` canonical table.

**Reason:** `core-v1` is the frozen canonical corpus whose aggregate ablation is a golden regression target (D-012, D-020); commerce scenarios must not perturb it. The scenario-v1 schema is strict (`additionalProperties: false`) with no free metadata object, and adding one would be a schema change — prohibited by the milestone. Carrying the `CMF-*` codes on predicate `failure_code` (an existing evaluator-surfaced label, so domain codes *annotate* rather than replace evaluator failure semantics) and the remaining metadata in the `notes` string keeps the profile fully within existing schema/runtime/evaluator mechanics while remaining machine-readable and testable (`tests/commerce/`). Commerce is the first applied profile, not CAV-Bench's identity or exclusive scope. The exact scenario subset remains subject to external scope review (Gate-2 scope validation), which has not occurred; nothing in the pack, its documentation, or its PR describes the subset as confirmed, final, validated, or externally reviewed, and the milestone may not reach APPROVED/MERGED/COMPLETE until that review is recorded.

**Verification:** `pytest tests/commerce tests/golden/test_commerce_v1_ablation.py` — schema validation of every commerce-v1 scenario; pack loading, id/version, and loader-derived digest determinism; per-scenario `commit_valid_success` across all five baseline profiles (the derived, inspected golden matrix); overall ablation table (CVSR 0.444 → 0.556 → 0.778 → 0.889 → 1.000, monotonic non-decreasing); guarded-vs-flawed separation (`full_lifecycle` is commit-valid on every hazard `direct` fails; controls pass on both ends); domain-code surfacing on the flawed run; oracle-boundary contract tests (no `CMF-*` code, dimension, or oracle marker in the adapter-visible `ScenarioView`, plan, policy envelope, or pre-evaluation adapter report); monetary/quantity invariant predicate forms (discount ≤ delegated limit, captured ≤ authorized, reservation and duplicate-order ledger cardinality, refunds ≤ captures); and the control-mapping documentation test (every scenario id, declared dimension, declared `CMF-*` code, and declared safeguard appears in `docs/commerce-v1-profile.md`, and safeguards resolve to the canonical capability set). All 40 `core-v1` canonical ablation goldens (`tests/golden/test_canonical_ablation.py`) remain byte-identical before and after — no evaluator, runtime, or scenario-schema code changed.
