# LangGraph Adapter Mapping

Status: **Implemented (executable milestone)** — design specified in
[PR #6](https://github.com/Harimay23/cav-bench/pull/6), implemented by the
follow-up executable-runtime PR.
Related framework-neutral RFC: [Issue #3](https://github.com/Harimay23/cav-bench/issues/3), [`docs/framework-adapter-brief.md`](framework-adapter-brief.md)
Related implementation issue: [Issue #5 — Implement initial CAV-Bench LangGraph adapter](https://github.com/Harimay23/cav-bench/issues/5)

This document specifies how a LangGraph-based agent maps onto CAV-Bench's
normalized event model and `ExecutionAdapter` protocol, and documents the
executable implementation of that mapping. It is framework-specific detail
that `docs/framework-adapter-brief.md` deliberately left out of the
framework-neutral specification.

**Provenance.** PR #6 is, and remains, the stable design-stage artifact:
the integration boundary, trust boundary, event mapping, scenario flows,
identifier rules, and durability decision below were all specified there
(and in Issue #5) before any runtime code existed. The executable-runtime
PR implements the next milestone from Issue #5 on top of that design; where
a section below describes running code, it is labeled as implemented
behavior. This is **not** official LangChain or LangGraph support,
endorsement, adoption, certification, or validation. Community feedback
through the LangChain Forum informed the architecture; the implementation
remains independently maintained.

## Design decisions inherited from PR #6

Unchanged from the design stage, and binding on the implementation:

- **External adapter as the integration surface.** `LangGraphAdapter`
  implements `cavbench.adapters.protocol.ExecutionAdapter` (`name`,
  `version`, `run(session) -> AdapterResult`) — the same protocol every
  other adapter implements. No evaluator or runtime changes.
- **Trust boundary.** The CAV-Bench tool facade is the sole adapter-visible
  execution path; `BenchmarkEnvironment`, the canonical trace, and the
  side-effect ledger are the authoritative sources of attempted and
  committed-effect truth (see below).
- **LangGraph is an optional dependency** (see below).
- **Reference graph is a deterministic test fixture**, not a production
  agent design (see [Fixture limitations](#fixture-limitations)).
- **Normalized event vocabulary**, the **four scenario flows**, **stable
  operation/idempotency identifiers**, **`durability="sync"`**, and
  **fine-grained node boundaries**, each detailed below.

## Implemented runtime behavior (this milestone)

What now exists as running, tested code:

- `src/cavbench/adapters/langgraph.py` — a real `LangGraphAdapter`. It
  compiles a graph (by default the reference fixture), injects the
  CAV-Bench session and a durable `thread_id` into the run's configurable
  context, invokes the graph with `durability="sync"` under an in-memory
  checkpointer, and maps the graph's terminal state to an untrusted
  `AdapterResult`.
- `src/cavbench/adapters/langgraph_reference.py` — the deterministic
  reference graphs for the four `framework-v1` scenarios, in two variants:
  `guarded` (commit-time revalidation, stable-key reconciliation,
  compensation routing, commit-time authority recheck) and `naive` (the
  deliberately flawed control used to demonstrate outcome-pass vs.
  commit-valid-fail).
- `src/cavbench/scenarios/packs/framework-v1/` — the four
  framework-adapter scenarios from `docs/framework-adapter-brief.md`
  (`FA-01` stale state, `FA-02` ambiguous retry, `FA-03` partial
  execution, `FA-04` authority change), as ordinary schema-validated
  scenarios usable by any adapter.
- `tests/langgraph/` — runtime, trust-boundary/adversarial,
  identifier-stability (retry + checkpoint resume), and determinism tests;
  `tests/contract/test_langgraph_adapter_contract.py` — dependency
  isolation and protocol conformance, run *without* langgraph installed.
- `examples/langgraph_adapter.py` — the runnable outcome-pass vs.
  commit-valid-fail demonstration.

## Trust boundary

Unchanged from every other adapter (`docs/architecture.md`,
`docs/adapter-authoring.md`), with a precise split between the
adapter-visible path and where truth actually lives:

- **The CAV-Bench tool facade is the sole adapter-visible execution path**
  for reads, writes, reconciliation, clarification, and escalation. Every
  consequential effect the adapter causes is issued exclusively through
  `session.tools.write(...)` → `ToolFacade` → `BenchmarkEnvironment`.
- **`BenchmarkEnvironment`, the canonical trace, and the side-effect ledger
  are the authoritative sources of attempted and committed-effect truth.**
  `BenchmarkEnvironment` is the only component that can append to the
  side-effect ledger or emit `tool_call_attempt` / `side_effect_commit`
  trace events (`src/cavbench/runtime/environment.py`). `ToolFacade.write()`
  itself records nothing — it delegates to `BenchmarkEnvironment.commit()`
  and relays back the result (`src/cavbench/runtime/tools.py`).

**LangGraph's own runtime state — checkpoints, node outputs, retry counts,
`get_state()`/`get_state_history()` — provides ordering, attempt, retry,
checkpoint, and recovery *context* only.** It is read by the adapter to
decide *how* to call the tool facade (e.g. "has this logical operation
already been attempted on a prior run of this thread?"), never as evidence
of whether an effect actually validly committed. `DeterministicEvaluator`
never sees LangGraph state directly and never trusts anything the adapter
or the graph self-reports (`AdapterResult.completion_status` is compared
against a benchmark-derived floor, never trusted — same as every adapter).

Implemented enforcement: the fixture's `naive` variants *do* claim clean
success — in graph state, in `completion_status`, and in their
normalized-event diagnostics — while the benchmark's own evidence shows a
stale, duplicated, incomplete, or unauthorized commit.
`tests/langgraph/test_trust_boundary.py` asserts the evaluator follows the
benchmark evidence in every such case, that forged trust-boundary metadata
changes nothing, and that the integration code never references the
harness-owned components (`BenchmarkEnvironment`, state store, ledger,
oracle) directly.

## Optional dependency model

LangGraph is **not** a core CAV-Bench dependency. `import cavbench` and the
core benchmark run (`cavbench doctor`, `cavbench ablate`, ...) never
require LangGraph to be installed. Neither
`src/cavbench/adapters/langgraph.py` nor
`src/cavbench/adapters/langgraph_reference.py` imports `langgraph` at
module level — only lazily, inside the code paths that actually execute a
graph. A missing dependency surfaces as a clear invocation-time
`ImportError` from `LangGraphAdapter.run(...)` naming the extra to install.

Implemented as the `langgraph` optional extra in `pyproject.toml`
(analogous to the existing `reporting` extra), with the smallest justified
range for the APIs actually used (`StateGraph`, `add_conditional_edges`,
`compile(checkpointer=..., interrupt_after=...)`,
`invoke(..., durability=...)`, `langgraph.config.get_config`,
`InMemorySaver`): `langgraph>=0.6,<2` — `0.6` introduced the `durability`
invoke argument used by the adapter, and `<2` is a one-major-version buffer
under the project's ordinary semver trust assumption (no breaking changes
within a documented major version), not a claim that every version in that
range has been individually tested.

**What is actually continuously tested, and where** (see
[Local vs. CI validation](#local-vs-ci-validation) for the full
distinction): the `langgraph` CI job (`.github/workflows/ci.yml`) runs the
full `tests/langgraph/` suite, `examples/langgraph_adapter.py`, and
`cavbench validate --pack framework-v1` against exactly two resolved
versions on every push/PR — the declared floor, `langgraph==0.6.0`, and
whatever `pip install ".[langgraph]"` resolves to as "latest" at CI run
time (currently `1.2.9`). Versions strictly between the floor and latest
are **not** individually exercised by CI; if the range needs narrowing or
splitting because an intermediate release turns out to be incompatible,
that would surface as a `langgraph` job failure on a version bump, not
silently.

## Normalized-event-to-LangGraph mapping

| Normalized event (`docs/framework-adapter-brief.md`) | LangGraph evidence (implemented in the reference fixture) |
|---|---|
| `intent_recorded` | The initial input written into graph/thread state before the first node runs (the fixture's `record_intent` node). |
| `authority_checked` | An explicit, externally observable authorization decision. The reference fixture implements this as a fresh authoritative read through the tool facade, recorded by the benchmark as a `tool_read` (see [Authority evidence](#authority-evidence)); the general contract also permits an `interrupt()` / `Command(resume=...)` step for a future real-agent adapter. Either way this makes the decision *observable*; it is **not itself authorization truth**. See [Authority: observability versus truth](#authority-observability-versus-truth). |
| `state_read` | A node's read via a CAV-Bench tool call (`session.tools.read(...)`), captured in that node's output. |
| `state_revalidated` | A node that re-reads state immediately before a commit-issuing node and re-evaluates the action against it (see [State read vs. commit-time revalidation](#state-read-versus-commit-time-revalidation) and [Stale-state TOCTOU protection](#stale-state-toctou-protection) — revalidation alone does not close the race). |
| `effect_attempted` | Backed by the benchmark-owned `tool_call_attempt` trace event, recorded synchronously near the beginning of `BenchmarkEnvironment.commit()` — after `ToolFacade.write()` delegates the operation and before the environment applies fault hooks, validation checks, idempotency checks, or external effects. Entering a graph node alone is **not** sufficient evidence: a node may run and exit without ever invoking a consequential tool. See [Evidence spine](#evidence-spine-attempted-versus-committed). |
| `effect_committed` | Authoritative only when backed by the benchmark-owned `side_effect_commit` trace event / side-effect ledger — never from a LangGraph-reported fact. `ToolResult.status="COMMITTED"` gives the adapter immediate confirmation; `status="AMBIGUOUS"` gives it neither confirmation nor disconfirmation and requires reconciliation. See [Trust boundary](#trust-boundary), [Evidence spine](#evidence-spine-attempted-versus-committed), and [Attempted versus committed](#attempted-versus-committed) for the implemented `FA-02`/`FA-03` behavior. |
| `effect_reconciled` | A call to `session.tools.status_check(...)` with the same stable `idempotency_key`, performed **unconditionally** before any write and again before any retry (implemented: `FA-02`'s `commit_refund` node reconciles immediately before every possible write, on every invocation; its dedicated `reconcile` node reconciles again after an `AMBIGUOUS` or `IDEMPOTENT_REPLAY` write response). See [Reconciliation behavior](#reconciliation-behavior) and [Stable operation identity and reconciliation](#stable-operation-identity-and-reconciliation). |
| `compensation_started` / `compensation_completed` | A dedicated compensation node, reached via a conditional edge when a downstream node's write returns `FAILED` (implemented: `FA-03`'s `compensate` node). |
| `escalation_created` | A node calling `session.escalate(...)` (implemented in the `FA-02`/`FA-03`/`FA-04` block/escalate nodes), optionally surfaced to a human via LangGraph's `interrupt()` / human-in-the-loop mechanism for a future real-agent adapter. |
| `outcome_reported` | The graph's terminal node output, mapped to `AdapterResult.completion_status` — untrusted, exactly as for every other adapter. |

The reference fixture also records this vocabulary into graph state as a
diagnostic stream surfaced via `AdapterResult.metadata["normalized_events"]`
— explicitly **untrusted**; tests assert both that the vocabulary is used
consistently and that the evaluator's output is unchanged when the stream
is stripped or forged.

## Evidence spine: attempted versus committed

The **single authoritative evidence spine** for `effect_attempted`,
`effect_committed`, and ambiguous-commit reconciliation is
`BenchmarkEnvironment`'s own records — the canonical trace and side-effect
ledger — produced when the adapter calls through the tool facade, never
anything LangGraph observes about itself. The tool facade is the adapter's
only path to *trigger* these records; it is not itself where the evidence
lives.

### Attempt evidence

`effect_attempted` is backed by the benchmark-owned `tool_call_attempt`
trace event, recorded synchronously near the beginning of
`BenchmarkEnvironment.commit()` — after `ToolFacade.write()` delegates the
operation and before the environment applies fault hooks, validation
checks, idempotency checks, or external effects
(`src/cavbench/runtime/environment.py`). `on_tool_start` (from
`astream_events`) and task-stream events (`stream_mode="tasks"`) are
**corroborating ordering evidence only** — useful for reconstructing *when*
things happened relative to each other, never a substitute for that fact.
This is load-bearing, not cautious phrasing, for two reasons:

- **A plain graph node that calls `session.tools.write(...)` directly (not
  through a LangChain-wrapped `Tool`) may emit no `on_tool_start` event at
  all.** LangChain's callback instrumentation fires for `Runnable`/`Tool`
  invocations; an ordinary Python function call inside a node body is
  invisible to it. An adapter that waited for `on_tool_start` before
  considering an effect attempted could simply never see one.
- **Task streams and tool streams are different granularities that do not
  generally coincide.** `stream_mode="tasks"` emits one event per graph
  task/node; `astream_events` emits events per instrumented `Runnable`,
  which can be finer-grained than node boundaries (a single node could wrap
  zero, one, or several instrumented tools). These two granularities line
  up 1:1 **only because the reference fixture deliberately enforces exactly
  one consequential action per node** (see
  [Fine-grained node boundaries](#fine-grained-node-boundaries)) — that is
  a property of the fixture's design, not a general LangGraph guarantee.

### Immediate confirmed commit

A `ToolResult` with `status="COMMITTED"` gives the adapter an **immediate,
adapter-visible confirmation** that the effect committed. Even so, the
benchmark-owned `side_effect_commit` trace event and side-effect ledger
remain the actual authoritative scoring evidence — `DeterministicEvaluator`
derives `effect_committed` from those benchmark-owned records directly,
never from the adapter having observed `status="COMMITTED"` and reported it
onward.

### Ambiguous response: what `ToolResult` cannot tell the adapter

`BenchmarkEnvironment.commit()` records the `side_effect_commit` trace
event and appends to the side-effect ledger **before** it decides whether
to return `status="COMMITTED"` or simulate a lost response and return
`status="AMBIGUOUS"` (`src/cavbench/runtime/environment.py`'s
`after_commit_before_response` fault hook). This means an `AMBIGUOUS`
response can mean the effect **already committed** — the caller genuinely
cannot distinguish "committed, response lost" from "not committed" using
`ToolResult` alone, and `ToolFacade.write()` exposes no trusted
`committed=True` field that would resolve this for the adapter.

Consequently:

- A `ToolResult` with `status="AMBIGUOUS"` **establishes neither outcome**
  — not committed, not uncommitted.
- The adapter **must not** emit or infer confirmed `effect_committed`
  evidence from an `AMBIGUOUS` response alone.
- The adapter must reconcile via `session.tools.status_check(...)`, using
  the *same* stable idempotency key, before ever attempting a retry — see
  [Unconditional reconciliation before retry](#unconditional-reconciliation-before-retry).
- The benchmark-owned trace and ledger — not the adapter's own guess about
  what `AMBIGUOUS` meant — determine whether the effect actually committed.
  `DeterministicEvaluator` reads those records directly and never consults
  what the adapter inferred.

### Reconciliation is corroborating evidence, not new authority

`status_check(...)` returning `COMMITTED` is `effect_reconciled` evidence:
it tells the adapter that a prior attempt with this operation identity did
commit, so it can avoid a duplicate write. It does **not** retroactively
make LangGraph's own state, or anything the adapter self-reports, an
authoritative source of commit truth — the benchmark-owned trace and ledger
already recorded the actual outcome at commit time, independent of when or
whether the adapter ever calls `status_check`. Normalized event correlation
between `effect_attempted`, `effect_committed`, and `effect_reconciled`
must use the same **stable operation identity** throughout (see
[Stable operation identity and reconciliation](#stable-operation-identity-and-reconciliation))
— never a freshly generated identifier per call.

**The executable reference fixture emits normalized diagnostic events
through checkpointed graph state**, not through LangGraph's own
callback/stream hooks (`on_tool_start`/`astream_events`,
`stream_mode="tasks"`) — each node explicitly appends to the
`normalized_events` list it returns, correlated directly with the
tool-facade call that node makes. This sidesteps the granularity mismatch
discussed above entirely, rather than resolving it: **it does not
implement a general callback- or stream-correlation layer for arbitrary
LangGraph applications.** A generalized emission mechanism — one that
could observe an arbitrary graph's own tool/task streams and correlate
them with tool-facade calls without the graph's own nodes cooperating —
remains future work; see
[Next implementation milestones](#next-implementation-milestones).

## Authority: observability versus truth

`interrupt()` and `Command(resume=...)` make an authorization decision
**externally observable** — a human or a scripted process can see the
decision point and provide a response. They do **not** make that response
authorization truth.

### A. LangGraph observability

- `interrupt()` / `Command(resume=...)` expose an approval or decision
  point to a human or scripted process.
- The resume payload is **adapter/harness input**, exactly like any other
  value a node receives — it carries no more trust than an argument the
  graph was called with, and is **not itself authorization truth**.
- **CI fixtures use deterministic scripted resume values, not a human**, to
  keep the four scenarios reproducible (`docs/methodology.md`'s
  determinism requirements apply here exactly as everywhere else in
  CAV-Bench).

### B. Current adapter behavior

- The adapter must perform a **fresh, authoritative read and semantic
  authority evaluation immediately before attempting the consequential
  action** — the same commit-time revalidation discipline as
  [Stale-state TOCTOU protection](#stale-state-toctou-protection), applied
  to authority rather than resource state.
- A stale planning-time approval — including an earlier `interrupt()`
  resume value — must **never** be treated as sufficient on its own to
  justify the write.

### C. Current runtime limitation and future prerequisite

The community-expert review that produced this section correctly
identified the desired trust property: a revoked actor should receive a
hard refusal that a stale "approve" resume value cannot override. This
section documents that **the present CAV-Bench runtime does not yet
implement that property as an atomic guarantee** — the review identified
the right target; this is a statement about today's implementation, not a
disagreement with the review.

- `ToolFacade.write()` currently receives no actor identity or complete
  authorization context (`src/cavbench/runtime/tools.py`), and
  `BenchmarkEnvironment.commit()` currently has no general
  authorization-adjudication interface (`src/cavbench/runtime/environment.py`)
  — its commit-time checks cover forced-failure hooks, the
  `expected_version` compare-and-set guard, and idempotency-key replay, but
  nothing authority-specific.
- Therefore the fresh adapter-side revalidation in (B) **narrows, but does
  not atomically close,** the authority time-of-check/time-of-use window —
  structurally the same limitation as
  [Stale-state TOCTOU protection](#stale-state-toctou-protection): between
  the adapter's fresh authority check and the actual
  `session.tools.write(...)` call, authority could still change.
- The evaluator can already independently identify an invalid
  authority-related outcome from benchmark-owned evidence and oracle
  constraints (`authority_validity` in
  `src/cavbench/evaluation/evaluator.py`) regardless of this limitation —
  that scoring path is unaffected and requires no change here.
- **Commit-boundary authority enforcement — an atomic, environment-level
  hard refusal comparable to the `expected_version` compare-and-set guard —
  requires a separately reviewed runtime design change** to carry
  authorization context into `ToolFacade.write()` /
  `BenchmarkEnvironment.commit()`. **This PR does not implement or claim
  atomic commit-boundary authority enforcement.** That capability requires
  a separately reviewed runtime change (see
  [Next implementation milestones](#next-implementation-milestones)) and
  must not be claimed as already implemented until it actually is.

## Four scenario execution flows

The four scenarios from `docs/framework-adapter-brief.md`, implemented as
the `framework-v1` pack and executed by the reference graphs:

1. **Stale state before commit (`FA-01`).** A `state_read` node observes
   the order at a known version; the scenario injects an external state
   change (the order ships) after that read. Commit-time revalidation is
   **not** simply reading the newest version and proceeding: the
   `revalidate` node (a) performs a distinct commit-time reread, (b)
   re-evaluates the action's precondition, intent, scope, and authority
   against the current state, (c) blocks/clarifies/escalates without
   committing if the change invalidates the action, and only otherwise (d)
   commits with the revalidated version as `expected_version`. In `FA-01`
   the precondition no longer holds, so the guarded graph refuses; the
   naive graph commits against the stale observation and the evaluator
   derives `TS_STALE_WITNESS` from environment-recorded versions.
2. **Ambiguous retry after a committed operation (`FA-02`).** The
   `commit_refund` node reconciles via `session.tools.status_check(...)`
   with the *same* stable `idempotency_key`, derived from durable
   identity, **immediately before every possible write** — including its
   first invocation. Finding `NOT_FOUND`, it writes once; the scenario's
   `ambiguous_response` fault swallows the acknowledgement, and the
   dedicated `reconcile` node performs a second status check that finds
   the commit confirmed, ending the run with exactly one ledger effect. If
   this node is instead re-invoked after a crash that lost its own result
   before LangGraph checkpointed it — the external effect having already
   committed — its own pre-write status check finds `COMMITTED` and skips
   the write entirely, rather than blindly reissuing it (see
   [Reconciliation behavior](#reconciliation-behavior) for why a separate
   preceding node cannot catch this case). A replay under the same key
   that does reach `session.tools.write(...)` is answered
   `IDEMPOTENT_REPLAY` and does not grow the ledger, but is routed through
   the same explicit post-write reconciliation as `AMBIGUOUS` — never
   treated as direct confirmation. The naive graph retries under a fresh
   per-attempt key and produces `EI_DUPLICATE_LOGICAL_EFFECT`.
3. **Partial workflow execution (`FA-03`).** The `reserve` node's effect
   commits; the scenario force-fails the downstream `capture` write. A
   conditional edge routes to the `compensate` node (releasing the
   committed reservation, with `compensation_for` linking it to the
   original step; escalation if compensation itself fails), and the
   terminal report is `"partial"` — never terminal success while required
   work is incomplete. The naive graph ignores the failure and reports
   success; the evaluator flags the missing compensation and the false
   success report from benchmark-derived facts.
4. **Authority change before commit (`FA-04`).** A planning-time authority
   check is recorded as an externally observable authoritative read; the
   scenario then reassigns ownership of the order. The guarded graph's
   `recheck_authority` node performs a second, equally independent
   authority check immediately before the consequential effect — a fresh
   read, never the checkpointed planning-time flag or an earlier graph
   branch — and does not call `session.tools.write(...)` because current
   authority no longer permits it (it escalates instead). The naive graph
   trusts its checkpointed `authorized_at_plan` flag, commits, and the
   evaluator derives `AV_PRINCIPAL_NOT_AUTHORIZED` from the ledger.

## Authority evidence

CAV-Bench's environment models authority as authoritative resource state
(`owner`, `tenant`) whose reads the benchmark itself records as
`tool_read` events — so an authority check is externally observable
evidence exactly when it is a fresh facade read, and the evaluator's
authority dimension is derived from what actually committed, not from any
adapter-side conclusion. The reference fixture's authority checks
(planning-time and commit-time in `FA-04`, and as part of every guarded
revalidation) are implemented this way. A LangGraph human-in-the-loop
interrupt resolved through `Command(resume=...)` remains a valid
alternative source of an explicit authorization decision for a future
real-agent adapter; the fixture does not need one because the benchmark
environment itself provides the observable authority record.

## Stale-state TOCTOU protection

**Node ordering alone does not remove the time-of-check/time-of-use
(TOCTOU) window.** Even after the semantic revalidation described in
scenario 1 passes, state can change *again* in the gap between the
revalidation read and the actual write call. Revalidation reduces the
window; it does not close it.

**`session.tools.write(..., expected_version=...)` must perform the atomic
final compare-and-set guard** that actually closes it — this is
`BenchmarkEnvironment`'s own commit-time version check
(`docs/architecture.md`'s commit path), not anything the revalidation
node's own logic can substitute for.

The implementation must cover **two deterministic stale-state fixture
variants**, not one mutation injected mid-run:

1. **State changes before semantic revalidation** — testing whether the
   semantic re-check blocks an invalid action.
2. **State changes after semantic revalidation but before
   `session.tools.write(...)`** — testing whether the atomic
   `expected_version` compare-and-set guard rejects the stale commit.

For the second variant, the expected outcome must be:

- `session.tools.write(...)` returns `CONFLICT`;
- no invalid effect is committed;
- the test demonstrates that the atomic write-boundary guard, not
  graph-node ordering, is the load-bearing protection.

## Stable operation identity and reconciliation

**`thread_id` + node/task name alone is not sufficient** to derive a stable
operation identity. Multiple invocations of the same node across
`RetryPolicy` retries, loop iterations, `Send` fan-out, or a mapped batch
would otherwise collide on the same identity. Operation identity must be
composed from:

- `thread_id`;
- node/task identity;
- a **durable per-operation discriminator stored in checkpointed state** —
  e.g. an operation counter, loop iteration index, `Send` index, or map
  index — never derived freshly from anything computed only at call time.

This composite identity must remain **identical** across:

- `RetryPolicy` retry attempts within the same run;
- a crash or interrupt resume from the last checkpoint.

### Unconditional reconciliation before retry

A node must reconcile *before* attempting a write with a given
`idempotency_key` more than once — unconditionally, not only after
observing an ambiguous response, since the node cannot always tell from its
own local state whether a prior attempt with this key already ran to
completion on an earlier invocation:

```python
result = session.tools.status_check(idempotency_key=idempotency_key)

if result.status != "COMMITTED":
    result = session.tools.write(
        ...,
        idempotency_key=idempotency_key,
        expected_version=version,
    )
```

### `IDEMPOTENT_REPLAY` is not sufficient evidence for Recovery

A `session.tools.write(...)` response of `IDEMPOTENT_REPLAY` may be enough
to preserve **Execution integrity** (no duplicate effect was created), but
**does not, by itself, satisfy Recovery** — Recovery requires the explicit
`status_check` / `effect_reconciled` evidence above to actually have
occurred before that replay, not merely for the ledger to happen to show no
duplicate. A node that got lucky and never needed to reconcile is not the
same as a node that correctly reconciled.

The ambiguity fixture (scenario 2, above) must inject the lost response
**before the write super-step's checkpoint is persisted** — the fault must
fire such that, on resume, the graph genuinely cannot tell from its own
checkpointed state whether the write committed, which is what forces real
reconciliation rather than a reconciliation step that never has anything to
do.

## State read versus commit-time revalidation

`state_read` (observe once, act later) and `state_revalidated` (a distinct
reread immediately before commit, plus re-evaluation of precondition,
intent, scope, and authority against the fresh observation) are separate
events and separate nodes in the fixture. A node that re-reads the version
but skips the re-evaluation has not revalidated anything — and a node that
"revalidates" by simply adopting the newest version and proceeding is the
exact anti-pattern `FA-01` exists to catch. The benchmark does not trust
either label: temporal validity is derived mechanically by comparing the
last version observed via `tool_read` against the version authoritative at
the moment of commit (DECISION_LOG D-015).

## Attempted versus committed

LangGraph's own state reflects that a node *ran* and what it *returned* —
it does not, by itself, distinguish "the external system confirmed this
effect committed" from "the node believes it committed" or "the node timed
out without knowing." `session.tools.write(...)`'s returned
`ToolResult.status` (`COMMITTED` / `CONFLICT` / `AMBIGUOUS` /
`IDEMPOTENT_REPLAY` / `FAILED`, per `docs/adapter-authoring.md`) is the
adapter-visible signal reflecting `BenchmarkEnvironment`'s own record, and
is what the adapter must act on, never the node's own control flow having
"succeeded" — but that signal only fully closes the gap when it is
`COMMITTED`. An `AMBIGUOUS` response leaves the adapter with neither
confirmation nor disconfirmation; it must reconcile via `status_check(...)`
rather than guess, and the benchmark-owned trace and ledger — not
`ToolResult` itself — remain the actual authority regardless of what the
adapter guesses (see [Evidence spine](#evidence-spine-attempted-versus-committed)).
This is the same distinction [Trust boundary](#trust-boundary) describes
generally and [Evidence spine](#evidence-spine-attempted-versus-committed)
describes mechanically; it is called out separately here because it is the
most common way a framework integration would accidentally re-introduce a
self-grading path.

On the benchmark side the two are distinct event types (`tool_call_attempt`
vs. `side_effect_commit`), and attempted, acknowledged-ambiguous,
committed, reconciled, compensated, and reported effects remain distinct
facts throughout: `FA-03`'s failed capture leaves an attempt plus a
`commit_rejected`, never a commit; `FA-02`'s ambiguous write leaves a
commit whose acknowledgement was lost, resolved only by reconciliation
(never by the adapter inferring an outcome from the `AMBIGUOUS` response
itself).

## Reconciliation behavior

The guarded FA-02 write node (`fa02_commit_refund`) reconciles via a
stable-key `status_check(idempotency_key=<same stable key>)` **immediately
before every possible write, inside the write node itself, on every
invocation** — not only after observing an `AMBIGUOUS` acknowledgement,
and not in a separate node that runs once before it.

**Why a separate preceding reconciliation node is not sufficient:** a
checkpoint could be persisted after that separate node runs; the external
effect could then commit inside the write node; and the process could
crash before the write node's own return value is checkpointed. Resuming
from that checkpoint re-invokes the write node directly — the separate
reconciliation node never runs again — so a design that only reconciled
*before entering* the write node would blindly reissue the write against
an operation that had already committed. Performing the status check
*inside* the write node, first, on every invocation (including the very
first), is what closes this gap:

- **Pre-write status check.** `NOT_FOUND` means nothing has committed yet
  under this key; the node proceeds to write once. `COMMITTED` means a
  prior invocation of this same node already committed the effect but its
  result was never checkpointed (the crash-before-checkpoint case above);
  the node does not write again, and does not fabricate
  `effect_attempted`/`effect_committed` diagnostics for the write it never
  issued.
- **After the write:** `COMMITTED` may route directly to confirmation.
  `AMBIGUOUS` and `IDEMPOTENT_REPLAY` both route to the same explicit
  post-write reconciliation node — `IDEMPOTENT_REPLAY` indicates the
  environment deduplicated against an already-committed effect, not a new
  commit by this invocation, and by itself is **not sufficient evidence
  for Recovery**; it must not be treated as direct confirmation. Only a
  `NOT_FOUND` post-write reconciliation result can route back to a
  (bounded) retry of the write, under the same key, so even a
  wrongly-repeated write is deduplicated by the environment.

Tests assert the full ordering (pre-write `NOT_FOUND` reconciliation
precedes the one write attempt; a post-write reconciliation follows the
commit), the single ledger entry, the safe-replay property, and —
separately — the precise crash-before-checkpoint interleaving described
above (`tests/langgraph/test_identifiers_retry_resume.py`).

## Stable identifier derivation

Both `operation_id` and `idempotency_key` are derived from **durable,
checkpointed identity only** — never freshly generated (e.g. via
`uuid4()`) on a node invocation:

- `logical_operation_id` comes from the scenario plan's step (durable
  across everything).
- `idempotency_key = f"lg:{scenario_id}:{thread_id}:{step_id}"`
  (`derive_idempotency_key(...)` in the fixture) — scenario identity,
  LangGraph thread identity, and the plan step the node maps 1:1 to.

A LangGraph resume after a crash or interrupt re-executes from the last
checkpoint; because the key is a pure function of durable identity, the
resumed run re-derives the *same* key, so CAV-Bench's duplicate-effect
detection distinguishes a legitimate resume/replay (`IDEMPOTENT_REPLAY`,
ledger unchanged) from a genuinely new logical operation. If the key were
regenerated per invocation, a safe resume would be indistinguishable from
a duplicate — the naive `FA-02` variant demonstrates precisely this
failure. `tests/langgraph/test_identifiers_retry_resume.py` exercises
stability across a checkpoint interrupt/resume (a genuine LangGraph
crash-and-resume, `test_checkpoint_resume_reuses_the_same_identifiers_and_reconciles_before_writing`)
and a manual replay.

**Why `thread_id` + `step_id` alone is a sufficient discriminator for this
fixture, but not in general.** Each `framework-v1` scenario's plan has each
`step_id` appear **at most once** per run — there are no loops, no `Send`
fan-out, and no node that maps to more than one logical operation. Under
that constraint, `step_id` alone already uniquely identifies the operation
within a thread, so no additional per-operation discriminator (an
operation counter, loop iteration index, `Send` index, or map index, per
[Stable operation identity and reconciliation](#stable-operation-identity-and-reconciliation))
is needed. **A general LangGraph adapter — one whose graphs may loop, fan
out, or otherwise invoke the same node more than once per logical
operation — must add such a discriminator to the key composition**, or
distinct operations within the same node would collide on the same
`idempotency_key`. This fixture does not need one only because its graphs
are scenario-shaped and non-repeating (see
[Fixture limitations](#fixture-limitations)).

**`RetryPolicy` is not currently wired into any node.** The fixture handles
retries at the graph level instead — an explicit conditional edge routes
back to a write node (e.g. `fa02_route_after_reconcile` routing to
`commit_refund` again) as an ordinary graph step, not as LangGraph's
automatic node-level retry mechanism. `derive_idempotency_key(...)` is a
pure function of scenario/thread/step identity with no invocation counter,
so it would remain stable if a future scenario did attach a `RetryPolicy`
to a node — but that specific mechanism is not exercised by any current
test, and no milestone claim below should say otherwise.

## `durability="sync"`

Graph execution uses LangGraph's `durability="sync"` mode (available since
langgraph 0.6) so completed super-step checkpoints are persisted
synchronously before execution advances. This reduces checkpoint lag and
ensures that completed super-steps are durably represented before later
graph work proceeds — a resume never observes a checkpoint that predates a
*completed* step. The adapter passes it on every `invoke`. Weaker
durability modes remain out of scope until there is a specific, documented
reason to relax this.

**It does not eliminate the external-effect/checkpoint gap inside a
running node.** An external effect may commit and the process may fail
before that node's own returned state is checkpointed. In that
interleaving, the last durable graph checkpoint can still predate the
committed effect — synchronous durability only guarantees that a
*completed* node's result is checkpointed before the graph proceeds; it
says nothing about a node whose own execution is interrupted mid-flight.
Stable operation identity, environment-owned idempotency, and the guarded
`FA-02` node's pre-write status reconciliation (see
[Reconciliation behavior](#reconciliation-behavior)) remain necessary for
safe recovery from that interleaving — this is precisely the case the
hidden-prior-commit regression test exercises.

Two distinct resume tests cover the two distinct cases:
`test_checkpoint_resume_reuses_the_same_identifiers_and_reconciles_before_writing`
interrupts *after* `commit_refund` has already returned (`interrupt_after=
["commit_refund"]`), so the checkpoint it resumes from already reflects a
*completed* node execution — this is the case synchronous durability
directly covers.
`test_resume_from_pre_write_checkpoint_reconciles_hidden_prior_commit_before_reissuing`
interrupts *before* `commit_refund` ever runs (`interrupt_after=
["read_state"]`) and then commits the effect directly through the tool
facade to simulate `commit_refund`'s own execution having happened but
never been checkpointed — this is the external-effect/checkpoint gap
synchronous durability does *not* close, and what the write node's
pre-write reconciliation exists to handle.

## Fine-grained node boundaries

One LangGraph node per logical CAV-Bench step — never a coarse node that
bundles multiple consequential actions. This is what makes per-step
checkpointing, per-step `operation_id`/`idempotency_key` derivation, and
per-step evidence collection meaningful. In the fixture, every
consequential write lives in its own node (`commit`, `commit_refund`,
`reserve`, `capture`, `compensate`), and each node's identifiers derive
from the plan step it implements.

## Fixture limitations

The reference graphs are deterministic test fixtures with deliberate
limitations; they are **not** a recommended production architecture:

- No model calls, no prompts, no nondeterminism — control flow is fixed
  per scenario and variant.
- Graph structure is scenario-shaped: each `framework-v1` scenario has its
  own small graph, wired from the scenario's adapter-visible plan. Real
  agents do not know the scenario ahead of time.
- The `naive` variants are intentionally defective controls for the
  outcome-pass vs. commit-valid-fail demonstration. Do not copy them.
- Checkpointing uses the in-memory saver; production persistence,
  multi-actor authorization flows, human-in-the-loop interrupts, streaming
  event capture (`astream_events`), and MCP/REST tool transport are all
  out of scope for this milestone.
- The fixture covers the four `framework-v1` scenarios only; it is not a
  general LangGraph-agent harness.

## Local vs. CI validation

Two distinct things can be called "the tests pass," and this document
keeps them separate:

- **Local validation** is whatever a contributor (or an agent) runs by
  hand in a development environment — e.g. `pytest`,
  `pytest tests/langgraph`, `ruff check .`, `mypy src/cavbench`,
  `python -m build`, ad hoc venvs pinned to a specific `langgraph`
  version. It is useful for iterating and for spot-checking versions
  outside the CI matrix, but it is **not** a substitute for CI: a local
  run reflects one machine, one Python build, and whatever was installed
  by hand at that moment, and it does not run on every push or PR.
- **CI validation** is exactly what `.github/workflows/ci.yml` runs on
  every push to `main` and every pull request, and is the only validation
  that gates merges. As of this milestone it includes, specifically for
  the LangGraph integration:
  - `test` (unchanged): `pytest -q` across Python 3.11/3.12/3.13, **without**
    the `langgraph` extra installed — this is what continuously verifies
    core dependency isolation (`tests/langgraph/` skips cleanly) and the
    missing-dependency error path (`tests/contract/test_langgraph_adapter_contract.py`).
  - `langgraph` (new): a two-leg matrix (`langgraph==0.6.0` and the
    range's "latest" resolved version) that installs
    `.[dev,langgraph]`, then runs `pytest -q tests/langgraph`,
    `python examples/langgraph_adapter.py`, and
    `cavbench validate --pack framework-v1` — this is what continuously
    exercises the real LangGraph runtime, not just source that happens to
    reference it.
  - `wheel-smoke-test-langgraph` (new): installs the *built wheel* with
    its `[langgraph]` extra (not an editable source install) and runs
    `cavbench validate --pack framework-v1` plus the example, so the
    packaged optional extra is verified too, not only the source tree.

Any claim in this document about what is "tested" or "exercised" refers to
this CI matrix, not to a one-off local run.

## Installation and minimal execution

```bash
pip install "cav-bench[langgraph]"   # core install never requires langgraph
```

Minimal run (the adapter is driven through the public Python API, like any
custom adapter — see `docs/adapter-authoring.md`):

```python
from cavbench.adapters.langgraph import LangGraphAdapter
from cavbench.evaluation.evaluator import DeterministicEvaluator
from cavbench.runtime.environment import BenchmarkEnvironment
from cavbench.runtime.session import AdapterSession
from cavbench.runtime.tools import ToolFacade
from cavbench.scenarios.loader import load_builtin_pack

pack = load_builtin_pack("framework-v1")
scenario = pack.get("FA-02")
env = BenchmarkEnvironment(scenario, seed=0, run_id="demo")
session = AdapterSession(scenario.view, ToolFacade(env))
result = LangGraphAdapter().run(session)
trace = env.finalize({
    "adapter_name": "langgraph",
    "adapter_version": "0.1.0",
    "final_message": result.final_message,
    "completion_status": result.completion_status,
})
print(DeterministicEvaluator().evaluate(scenario, trace).commit_valid_success)
```

`python examples/langgraph_adapter.py` runs the full outcome-pass vs.
commit-valid-fail demonstration. Without the extra installed,
`LangGraphAdapter().run(...)` raises a clear `ImportError` naming
`cav-bench[langgraph]`; importing `cavbench` (including the adapter
modules) works regardless.

## External review status

**PR #6 has received substantive community-expert review through the
LangChain Forum.** The reviewer confirmed the trust boundary and the
honest-failure skeleton design, and identified corrections involving: the
evidence spine (`effect_attempted`/`effect_committed` authoritative versus
corroborating evidence), authorization truth (observability via
`interrupt()` versus actual adjudication by the facade/environment),
time-of-check/time-of-use protection for the stale-state scenario, stable
operation identity and reconciliation requirements, and skeleton test
coverage. **These corrections have been incorporated** into this document
and the skeleton's test suite.

A follow-up self-review against the current runtime implementation
(`src/cavbench/runtime/tools.py`, `src/cavbench/runtime/environment.py`)
found that two statements in the incorporated corrections described the
*desired* trust properties more strongly than the *current* runtime
implements them: (1) `effect_committed` evidence in the ambiguous-response
case, and (2) commit-boundary authority enforcement. Both are now corrected
— see [Evidence spine](#evidence-spine-attempted-versus-committed) and
[Authority: observability versus truth](#authority-observability-versus-truth)
respectively — without disputing the reviewer's identification of the
target properties themselves.

A second follow-up self-review found the document was still inconsistent
about *where* commit truth lives: several passages described the tool
facade itself as the "authoritative source of commit truth" and said
`effect_attempted` was recorded "at `ToolFacade.write()` entry." Per
`src/cavbench/runtime/tools.py` and `src/cavbench/runtime/environment.py`,
`ToolFacade.write()` records nothing itself — it delegates to
`BenchmarkEnvironment.commit()`, which records `tool_call_attempt` near the
beginning of its own execution and owns `side_effect_commit` and the
side-effect ledger. Corrected throughout to the precise split: the tool
facade is the sole *adapter-visible execution path*; `BenchmarkEnvironment`,
the canonical trace, and the side-effect ledger are the *authoritative
sources of attempted and committed-effect truth*. The missing-LangGraph-
dependency skeleton test was also made deterministic (previously it
depended on LangGraph actually being absent from the test environment; it
now simulates that path via monkeypatching regardless of what is
installed).

**Neither PR #6's mapping document nor this executable-milestone
implementation has been reviewed by a LangGraph maintainer.** Community
feedback through the LangChain Forum informed the architecture; the
implementation remains independently maintained.

This is **not**: official LangChain endorsement, official LangGraph
endorsement, LangGraph maintainer approval, adoption, certification, or
production validation. See [Non-goals](#non-goals) and Issue #3's open
maintainer questions, which remain open.

## Non-goals

Same as `docs/framework-adapter-brief.md`, plus adapter-specific
clarifications:

- Not a comparison of LangGraph against other frameworks or against model
  intelligence.
- Not a claim of official LangGraph support, endorsement, adoption,
  certification, or validation.
- Not a production agent design — the reference graph is a test fixture.
- Does not change CAV-Bench's evaluator, scoring definitions, validity
  dimensions, or canonical golden results.
- Does not make LangGraph a core CAV-Bench dependency.
- No MCP or REST integrations, commerce-specific scenario packs, or
  broader case-study material in this milestone.

## Implementation milestones

1. ~~Design-stage skeleton (PR #6): `LangGraphAdapter` satisfying the
   `ExecutionAdapter` protocol shape, raising a clear development-stage
   error on `run()`; no real graph.~~ **Done (PR #6 — remains the
   design-stage artifact).**
2. ~~Reference fixture graph implementing the four scenarios above with
   `durability="sync"` and fine-grained nodes, including the two
   stale-state timing variants from
   [Stale-state TOCTOU protection](#stale-state-toctou-protection) and the
   checkpoint-timed lost-response fixture from
   [Stable operation identity and reconciliation](#stable-operation-identity-and-reconciliation).~~
   **Done (this milestone).** The canonical `FA-01` fixture exercises the
   first timing variant (state changes before revalidation, caught by the
   revalidation node itself). The second timing variant (state changes
   after revalidation but before the write, caught only by the atomic
   `expected_version` compare-and-set guard) is exercised by
   `tests/langgraph/test_runtime_scenarios.py::test_stale_state_scenario_second_timing_variant_relies_on_the_atomic_guard`,
   which constructs the same scenario with the fault moved from
   `after_read` to `before_commit` rather than adding a second scenario
   file for what is the same write step. The checkpoint-timed
   lost-response fixture is `FA-02`, exercised by
   `tests/langgraph/test_identifiers_retry_resume.py`.
3. ~~Operation identity derivation from checkpointed `thread_id` + node/task
   identity + a durable per-operation discriminator (not `thread_id` +
   node name alone).~~ **Partially done (this milestone) — see
   [Stable identifier derivation](#stable-identifier-derivation): exercised
   by the ambiguous-retry scenario across a genuine checkpoint interrupt
   and resume, and stability is proven for this fixture's non-repeating,
   scenario-shaped graphs (`thread_id` + `step_id` alone is a sufficient
   discriminator here). `RetryPolicy`-triggered node-level retry is
   **not** wired into any node or exercised by any test. A durable
   per-operation discriminator beyond `step_id` (an operation counter,
   loop iteration index, `Send` index, or map index) remains required for
   a general adapter whose graphs loop, fan out, or invoke the same node
   more than once per logical operation — this fixture does not need one.**
4. ~~The runtime normalized-event emission mechanism deferred in
   [Evidence spine](#evidence-spine-attempted-versus-committed).~~ **Done
   (this milestone), resolved without subscribing to LangGraph's own
   callback/stream hooks at all: the fixture's own nodes explicitly record
   the normalized-event vocabulary into graph state as a diagnostic stream
   (`AdapterResult.metadata["normalized_events"]`) correlated directly with
   the tool-facade calls each node makes — sidestepping the
   `on_tool_start`/task-stream granularity mismatch documented in
   [Evidence spine](#evidence-spine-attempted-versus-committed) entirely,
   rather than resolving it. This diagnostic stream remains untrusted;
   `tests/langgraph/test_trust_boundary.py` asserts evaluator output is
   unchanged when it is stripped or forged.**
5. ~~Automated tests running all four scenarios through the real graph and
   asserting on CAV-Bench's independently-derived `EvaluationResult`, not
   on anything the graph or adapter self-reports.~~ **Done (this
   milestone) — `tests/langgraph/`.**
6. ~~Optional `langgraph` extra added to `pyproject.toml`.~~ **Done (this
   milestone).**
7. **Not implemented in this milestone, by design (see
   [Authority: observability versus truth](#authority-observability-versus-truth),
   part C).** Commit-boundary authority enforcement: a separately reviewed
   runtime design change to carry authorization context into
   `ToolFacade.write()` / `BenchmarkEnvironment.commit()`, providing an
   atomic, environment-level hard refusal for revoked authority. This is a
   runtime prerequisite, not adapter work, and remains out of scope for the
   LangGraph adapter itself — `FA-04`'s guarded fixture only narrows the
   window via fresh adapter-side revalidation (see
   [Authority evidence](#authority-evidence)).
8. External review request directed at a LangGraph maintainer specifically
   (as opposed to the community-expert review already received), per
   Issue #3's open maintainer questions — still open.
