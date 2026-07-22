# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project uses schema-versioned scenario/trace/evaluation contracts
(currently `1.0`) documented in `docs/scenario-authoring.md`.

## [Unreleased]

### Added

- `commerce-v1` builtin scenario pack — **proposed initial subset, pending Gate-2 external scope review** (M-COM-V1, Issue #13; design `docs/design/commerce-v1-profile.md`, approval `docs/program/approvals/M-COM-V1.md`, decision `DECISION_LOG.md` D-022). The first applied domain profile: five synthetic consequential-commerce hazard scenarios spanning all five validity dimensions and three core hazard families — `CM-ORD-01` duplicate order, `CM-INV-01` stale stock, `CM-PRC-02` discount beyond delegated limit, `CM-PAY-02` capture after authorization void, `CM-REC-01` divergent partial cancellation — plus three `stable_happy_path` controls (`CM-ORD-90`, `CM-INV-90`, `CM-PAY-90`). Loads through the existing pack loader with no schema, evaluator, runtime, adapter, or `core-v1` change; reuses the existing fault hooks, duplicate-effect/stale-witness derivations, and truthful-report floor. Adopter-facing control-mapping documentation (`docs/commerce-v1-profile.md`) and a commerce-v1-only golden ablation (`tests/golden/test_commerce_v1_ablation.py`, CVSR 0.375 → 1.000 across the five baselines) accompany the pack; `tests/commerce/` adds schema, load/digest, oracle-boundary, monetary/quantity-invariant, and control-mapping coverage. Commerce is the first applied profile, not CAV-Bench's identity or exclusive scope. Fixtures are synthetic: no real merchant incidents, no real payment integration, no PII; implementation is not external adoption or domain validation, and the subset is not confirmed, final, or externally reviewed.
- Executable LangGraph integration (the next milestone from Issue #5, implementing the merged PR #6 design-stage skeleton):
  - `LangGraphAdapter` now actually runs a compiled LangGraph graph against an `AdapterSession` (checkpointer, durable `thread_id`, `durability="sync"`), mapping terminal graph state to an untrusted `AdapterResult`. LangGraph stays an optional, lazily-imported dependency; a missing install raises a clear invocation-time error naming `cav-bench[langgraph]`.
  - Optional `langgraph` extra in `pyproject.toml` (`langgraph>=0.6,<2`; CI continuously tests the declared floor, `langgraph==0.6.0`, and the range's latest resolved release — see `docs/langgraph-adapter-mapping.md#local-vs-ci-validation`).
  - `framework-v1` builtin scenario pack: the four framework-adapter scenarios from `docs/framework-adapter-brief.md` (FA-01 stale state before commit, FA-02 ambiguous retry, FA-03 partial execution, FA-04 authority change before commit), kept separate from the frozen `core-v1` corpus (see DECISION_LOG D-020).
  - Deterministic reference LangGraph graphs (`cavbench.adapters.langgraph_reference`) — test fixtures, not a production design — in `guarded` and deliberately-flawed `naive` variants, with stable `operation_id`/`idempotency_key` derivation from durable scenario/thread/step identity.
  - `tests/langgraph/`: runtime tests for all four scenarios, adversarial trust-boundary tests (graph/adapter success claims cannot alter evaluator output), identifier stability across retry and checkpoint resume, safe idempotent replay, and bit-for-bit determinism; `tests/contract/test_langgraph_adapter_contract.py` covers dependency isolation without langgraph installed.
  - `examples/langgraph_adapter.py`: runnable outcome-pass vs. commit-valid-fail demonstration (naive run passes a conventional outcome check but fails commit validity on `TS_STALE_WITNESS`; the guarded control adds one revalidation node and becomes commit-valid).
  - CI (`.github/workflows/ci.yml`): a new `langgraph` job (matrix: `langgraph==0.6.0` and the latest resolved release) actually runs `tests/langgraph/`, the runnable example, and `cavbench validate --pack framework-v1` against the real dependency on every push/PR — previously the executable LangGraph suite silently skipped in CI (`pytest.importorskip`) because only the base `.[dev]` extra was installed. A new `wheel-smoke-test-langgraph` job additionally installs the *built wheel* with its `[langgraph]` extra and re-runs the same validation, so the packaged optional extra is verified, not only the source tree. The existing Python 3.11/3.12/3.13 `test` matrix is unchanged and continues to run without the extra, which is what continuously verifies dependency isolation and the missing-dependency error path.
- `cavbench list packs` now lists all builtin packs (`commerce-v1`, `core-v1`, `framework-v1`).
- Synchronized the executable LangGraph work with the final merged PR #6
  trust-boundary and dependency-isolation contract: corrected residual
  "tool facade is the authoritative source of commit truth" language in the
  mapping doc and the adapter's module docstring to the precise split (tool
  facade as the sole adapter-visible execution path;
  `BenchmarkEnvironment`/trace/ledger as authoritative truth); made
  `tests/contract/test_langgraph_adapter_contract.py`'s missing-dependency
  test deterministic (monkeypatched, no longer environment-dependent) and
  added a nested-import-failure test; fixed `AdapterResult.metadata`'s
  `langgraph_version` diagnostic, which always reported `"unknown"` because
  `langgraph` does not set a module-level `__version__` attribute, to read
  installed package metadata instead; added the missing second stale-state
  TOCTOU timing variant test for `FA-01` (state changes after revalidation
  but before the write, caught only by the atomic `expected_version`
  guard); and corrected a milestone claim that overstated `RetryPolicy`
  coverage (no node currently uses one -- retries are handled at the graph
  level via explicit conditional edges).

### Fixed

- **Guarded `FA-02` recovery correctness.** The guarded write node now
  reconciles with a stable-key `status_check(...)` immediately before
  every possible write, inside the write node itself, on every
  invocation -- not only after an `AMBIGUOUS` acknowledgement, and not in
  a separate node that ran only once before it. A separate preceding
  reconciliation node cannot catch a crash between the external effect
  committing and that node's own return value being checkpointed: resuming
  re-invokes the write node directly without ever re-running the separate
  node, so it would blindly reissue the write. Reconciling inside the
  write node, first, on every invocation closes this gap. New regression
  test: `tests/langgraph/test_identifiers_retry_resume.py::test_resume_from_pre_write_checkpoint_reconciles_hidden_prior_commit_before_reissuing`.
- **`IDEMPOTENT_REPLAY` is no longer represented as a newly committed
  effect.** It previously routed directly to confirmation alongside
  `COMMITTED` and was reported as an `effect_committed` diagnostic; it now
  routes through the same explicit post-write reconciliation as
  `AMBIGUOUS` (deduplication is not, by itself, evidence of a new commit
  by the replaying invocation) and is never diagnosed as
  `effect_committed`. New test:
  `tests/langgraph/test_identifiers_retry_resume.py::test_idempotent_replay_requires_explicit_reconciliation_not_direct_confirmation`.
- **Custom `graph_provider` contract wording.** The `LangGraphAdapter`
  docstring previously implied CAV-Bench enforces that *any* custom graph
  routes every consequential effect through `session.tools`. Corrected:
  CAV-Bench does not sandbox arbitrary Python code and cannot prevent a
  custom graph from producing out-of-band effects; only effects recorded
  through the benchmark environment are ever evaluated as benchmark
  evidence. The bundled reference fixture does route every consequential
  effect through `session.tools` and is adversarially tested for it --
  that claim is preserved, scoped to the bundled fixture specifically.
- **M-GPI-1: generic protocol gateway core with a REST frontend**
  (`cavbench.gateway`), implementing
  `docs/design/generic-protocol-integration.md` under
  `docs/program/approvals/M-GPI-1.md`. A benchmark-owned protocol gateway
  lets a REST-speaking candidate agent or service be evaluated without
  writing a Python `ExecutionAdapter`: the candidate is the protocol
  client; the gateway is the protocol server; `ToolFacade` and
  `BenchmarkEnvironment` remain the sole effect executor and sole commit
  authority, unchanged. Every accepted tool-operation request maps to
  exactly one `ToolFacade` invocation; final-report submission is an
  accepted non-tool request and maps to zero `ToolFacade` invocations by
  design; a malformed envelope, an authentication failure, or a
  **capability violation** creates zero benchmark attempts. Every
  candidate request is checked, before any `ToolFacade` call, against one
  canonical scenario-visible capability model
  (`cavbench.gateway.capabilities.derive_operations`, shared by
  advertisement and enforcement so the two cannot diverge) at the full
  `(action, tool_name, namespace, resource_id)` level — write and
  compensate tools are never interchangeable, and a resource visible for
  one operation is not automatically visible for another. Read
  visibility is derived, not separately enforced: `derive_operations`
  synthesizes exactly one `read` descriptor per unique
  `(namespace, resource_id)` touched by any resource-scoped step (read,
  write, or compensate), so read advertisement and read enforcement are
  definitionally identical — proved generically across several scenarios
  by `tests/contract/test_gateway_capability_consistency.py`. Capability
  discovery (`GET /capabilities`) returns an independent deep-copy
  snapshot of a frozen advertisement and records an independent
  deep-copy of it in the session log on every call (GPI-FR-009);
  `capabilities()`, `discover_capabilities()`, and
  `SessionLogEntry.to_dict()` all return fresh, fully independent
  copies, so mutating a returned object can never affect a later call, a
  prior log entry, or the internal canonical model. The session log is
  genuinely append-only: internal storage is private, the only append
  paths are `record_request`/`record_rejection`/`record_discovery`, and
  the public `entries` property and `to_list()` return fresh defensive
  copies, so a caller can never clear, append to, reorder, or mutate
  what is actually stored. The REST server is deliberately
  single-threaded (`http.server.HTTPServer`, never `ThreadingHTTPServer`):
  every handler shares one mutable `GatewaySession`, so concurrent
  handling would make commit order, trace order, and log order
  nondeterministic; requests are now handled one at a time, in full,
  before the next is accepted -- processing order follows whatever order
  the underlying TCP connections were accepted in (no gateway-imposed
  queueing, sorting, or reordering); a reproducible ordered candidate
  trace requires the candidate itself to send one request at a time and
  wait for each response. Proven by
  `tests/contract/test_gateway_rest_concurrency.py` (no overlap, 1:1
  request-to-`ToolFacade` mapping under concurrent load, monotonic log
  sequencing in actual processing order, no racing ledger commits,
  report submission cannot race a consequential operation, deterministic
  final benchmark state across repeated concurrent runs without claiming
  a reproducible ordered trace). Server lifecycle
  (`created -> running -> stopped`) is now deterministic and idempotent.
  `GatewayRestServer` no longer uses `serve_forever()`/`shutdown()`:
  `_ManagedHTTPServer.run()` loops over the public `handle_request()`
  primitive, cancelled via an always-safe-to-signal `threading.Event`
  rather than `serve_forever()`'s private shutdown handshake. `start()`
  blocks (bounded) until the loop confirms it is genuinely active before
  returning, and `start()`/`stop()` share one lock so competing calls
  from different threads resolve deterministically instead of racing.
  One internal cleanup routine -- signal cancellation, join the thread
  with a bounded timeout, close the socket exactly once -- backs both a
  startup-timeout failure and a normal `stop()`, and proves the thread
  actually terminated rather than assuming it did; if it cannot confirm
  termination within the bound, `start()` raises a distinct error naming
  both failures. `stop()` before `start()` no longer hangs, `start()`
  while running is a no-op, `start()` after `stop()` (including after a
  startup failure) raises `ServerLifecycleError`, and
  `stop()`/`server_close()` are safe to call repeatedly
  (`tests/unit/test_gateway_rest_lifecycle.py`, including repeated
  startup-failure runs checked against the process's live-thread set for
  leaks). `stop()` now honors the same honest-termination contract as the
  startup-timeout path: it raises `ServerLifecycleError` if the bounded
  join cannot confirm the server thread actually terminated, rather than
  discarding that result and reporting success while the thread is still
  alive; the socket is still closed exactly once, state remains
  `"stopped"`, and a later `stop()` call safely retries the join,
  succeeding harmlessly once the thread exits. The same behavior applies
  to direct `stop()`, the callable `serve()` returns, and context-manager
  `__exit__` (`tests/unit/test_gateway_rest_lifecycle.py`, using an
  `Event`-gated test double, never a wall-clock sleep, to simulate an
  uncooperative thread). Adds: the
  common protocol envelope (`cavbench.gateway.envelope`, schema at
  `src/cavbench/gateway/schemas/envelope.schema.json`); the transport-
  neutral gateway core (`cavbench.gateway.core`); the capability model
  (`cavbench.gateway.capabilities`); loopback-only REST bind validation
  (`cavbench.gateway.bind`, rejects `0.0.0.0`/`::`/LAN addresses/non-
  loopback hostnames before a socket opens); redaction and a
  redacted session log (`cavbench.gateway.redaction`,
  `cavbench.gateway.session_log`); a standard-library-only REST frontend
  (`cavbench.gateway.rest`, no new runtime dependency); a deterministic
  reference candidate client and REST client
  (`examples/reference_candidate/`, a scripted test fixture, not a
  production client library) exercising the four canonical hazard
  patterns (stale state before commit, ambiguous acknowledgement and
  retry, partial execution and recovery, authority change before commit)
  in guarded and flawed configurations; a runnable local example
  (`examples/gateway_rest_demo.py`); gateway documentation under
  `docs/program/gateway/` (architecture, envelope reference, REST
  mapping, candidate integration guide with limitations/non-claims); new
  CI jobs `gateway-core-installs-without-extras` and `gateway-example`
  (loopback-only, double-run determinism check), plus a REST-extra
  gateway smoke test folded into `wheel-smoke-test`; a `rest` optional
  extra (currently empty — the REST frontend needs no dependency beyond
  core). `cavbench.gateway` is never imported by importing plain
  `cavbench` (extras isolation, matching the existing `reporting`
  pattern). No evaluator, runtime, scenario-schema, or `core-v1` change;
  all canonical ablation goldens are byte-identical before and after.
  MCP transport is explicitly out of scope for this milestone (deferred,
  see `DECISION_LOG.md` D-021). External technical review of the
  envelope and REST mapping has not occurred; the gateway is not claimed
  as externally validated, adopted, or production-ready. Tracked by
  [issue #11](https://github.com/Harimay23/cav-bench/issues/11).

### Documentation

- Reconciled program-status documentation
  (`docs/program/implementation-manifest.md`,
  `docs/program/implementation-issue-specifications.md`,
  `docs/program/approvals/README.md`,
  `docs/design/future-workstreams-index.md`, `README.md`) with the actual
  merged repository state: PR #6, #8, #9, #10, and #12 are merged; issue
  #11 (`M-GPI-1`) is closed as implementation-completed, with its
  recorded external technical review still outstanding, so the milestone
  moves from a stale `PR_OPEN` manifest entry to the correct
  `VALIDATING` gate-state; `M-COM-V1` (issue #13) is recorded as the next
  eligible milestone; `M-IVT-1` (issue #14) remains queued after it;
  `M-HFA-1`/`M-IET-1`/`M-REL-NEXT` (issues #15/#16/#17) remain unapproved
  and not executable. Replaced stale `ISSUE-TBD-*` placeholders with the
  real issue links. Appended execution-journal checkpoints recording the
  reconciliation; no prior journal entry was edited, reordered, or
  removed. Documentation and governance only: no evaluator, runtime,
  scenario, schema, dependency, or CI behavior changed, and no
  implementation work began under this change.
- Rewrote `docs/langgraph-adapter-mapping.md` to distinguish design decisions inherited from the merged PR #6 baseline from implemented runtime behavior, and to document authority evidence, state-read vs. commit-time revalidation, attempted-vs-committed evidence, reconciliation behavior, identifier derivation, synchronous durability, fixture limitations, local-vs-CI validation, and installation/minimal-execution instructions. No official LangChain/LangGraph support, endorsement, adoption, certification, or validation is claimed.
- Added a draft LangGraph adapter mapping, a non-executable
  `ExecutionAdapter`-shaped skeleton, and contract tests covering
  optional-dependency isolation and honest failure behavior. The mapping
  documents the benchmark-owned commit-truth boundary, ambiguous-response
  reconciliation requirements, and the current limitation around atomic
  commit-time authorization enforcement. The integration remains
  unimplemented and is not official LangChain or LangGraph support,
  endorsement, adoption, maintainer approval, or production validation.
- Recorded human design approvals for three future-workstream milestones:
  `M-GPI-1` (generic protocol integration), `M-COM-V1` (commerce-v1
  profile), and `M-IVT-1` (independent-validation tooling, tooling scope
  only) — each `approved_with_conditions` by the repository owner, at
  reviewed commit `38c5e1e8590e17c2798618c0490db7958d7f739d` (PR #9's
  design head), with approval records at `docs/program/approvals/`
  (`M-GPI-1.md`, `M-COM-V1.md`, `M-IVT-1.md`, and an index `README.md`).
  Updated the three corresponding design documents' status to `Approved
  for implementation with conditions` and the implementation manifest's
  entries to `APPROVED_FOR_IMPLEMENTATION`. `M-HFA-1`, `M-IET-1`, and
  `M-REL-NEXT` remain unapproved and `Status: Proposed`; no implementation
  has begun for any milestone. Added
  `docs/program/implementation-issue-specifications.md`, ready-to-create
  GitHub issue specifications for all six milestones (three approved,
  three proposed/not executable), to be used after this PR merges. This
  is a documentation and governance change only: no evaluator, runtime,
  scenario, schema, dependency, or CI behavior changed, and nothing is
  merged or implemented by it.
- Added the future-workstream design package (`docs/design/`): proposed
  designs for an independent external validation run, hidden-failure
  discovery, a before-and-after improvement case, the commerce-v1
  consequential-action profile, generic MCP/REST protocol integration, and
  a versioned follow-up release, with an index. All designs are
  `Status: Proposed`; nothing is approved for implementation and no
  production behavior, evaluator semantics, scenario packs, dependencies,
  or version metadata changed.
- Added program execution-control documents (`docs/program/`): an
  implementation manifest (future execution queue), gate-state lifecycle,
  external-evidence policy, Fable execution contract, PR and branch
  strategy, and a resume-and-recovery protocol.
- Added shared program diagrams (`docs/diagrams/`): future system
  architecture, validation and evidence lifecycle, workstream dependency
  map, and release and adoption gates.
- Added Claude Code project guidance, a 90-day technical validation and
  adoption roadmap, a 14-day validation sprint, program and architecture
  diagrams, adoption and validation tracking guidance, and repository-ready
  GitHub issue templates. No benchmark behavior, scoring semantics, or
  evaluator logic changed.
- Added project-level and version-specific DOI guidance.
- Added complete APA and BibTeX citation examples.
- Clarified reproducibility citation for v1.0.0.
- Hardened repository citation and Zenodo metadata.
- Fixed repository URL inconsistencies (`nixalkumar/cav-bench` → `Harimay23/cav-bench`) across `README.md`, `CITATION.cff`, `CONTRIBUTING.md`, `pyproject.toml`, and `docs/`.

## [1.0.0] — 2026-07-14

Initial public hardening of the v0.3 research prototype into an installable,
deterministic, framework-neutral benchmark.

Archived on Zenodo: concept DOI [10.5281/zenodo.21364385](https://doi.org/10.5281/zenodo.21364385), version DOI [10.5281/zenodo.21364386](https://doi.org/10.5281/zenodo.21364386).

### Added

- `src/`-layout installable package `cavbench` (distribution name `cav-bench`), CLI entry point `cavbench`.
- Versioned JSON Schemas (`schema_version: "1.0"`) for scenarios, traces, and evaluation results.
- Immutable domain models with a hard split between `ScenarioView` (adapter-visible) and `ScenarioOracle` (benchmark-private, never exposed through any runtime API).
- All 40 `core-v1` scenarios migrated from the v0.3 prototype, each now declaring a real adapter-visible task plan and policy envelope alongside the private oracle.
- Deterministic runtime: versioned state store, hook-based fault scheduler, append-only side-effect ledger, harness-owned commit path, canonical trace recorder.
- `DeterministicEvaluator`: derives OSR, PAOSR, CVSR, VG, PAVG, and per-dimension status entirely from benchmark-owned facts (oracle, state, ledger, trace) — never from adapter-supplied labels.
- Five canonical baseline architecture profiles (`direct`, `policy_gated`, `commit_guarded`, `reconciled`, `full_lifecycle`), implemented as one shared, capability-parameterized `ExecutionAdapter` engine executing real tool calls against the environment.
- `BenchmarkRunner`, run manifest, and report writers producing the `runs/<run-id>/{manifest.json,traces/,evaluations.jsonl,summary.json,summary.md}` layout.
- CLI: `doctor`, `list`, `validate`, `run`, `ablate`, `replay`, `report`.
- Unit, contract, integration, golden, and CLI test suites, including an adversarial test proving the evaluator ignores forged trust-boundary metadata.
- Public documentation: methodology, architecture, scenario-authoring, adapter-authoring, reproducibility guides.
- Open-source release metadata: `LICENSE` (Apache-2.0), `CITATION.cff`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `SECURITY.md`.

### Changed from v0.3

- The v0.3 prototype selected between two hand-authored "good"/"bad" fixture traces per scenario per profile (`use_safe_trace`); v1.0 replaces this with real execution of the five profiles against a real environment. See `DECISION_LOG.md` D-014.
- `harness_checks` embedded in trace metadata, `explicit_invalid_dimension`, and adapter-reachable `goal_predicates_satisfied`/`recovery_obligation_satisfied` flags are removed from the runtime trust path entirely.

### Verified

- Running all 40 scenarios through all five baseline profiles reproduces the canonical ablation table from the v0.3 research specification exactly (see `tests/golden/test_canonical_ablation.py`).
