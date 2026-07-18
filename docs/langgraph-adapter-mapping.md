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
- **Trust boundary.** The CAV-Bench session/tool facade is the sole
  authoritative source of commit truth (see below).
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
`docs/adapter-authoring.md`): the **CAV-Bench session/tool facade is the
sole authoritative source of commit truth.** Every consequential effect the
adapter causes is committed exclusively through
`session.tools.write(...)` → `ToolFacade` → `BenchmarkEnvironment`, which is
the only code path that can append to the side-effect ledger or emit a
`side_effect_commit` trace event.

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
invoke argument; both ends of the range are exercised by the test suite.

## Normalized-event-to-LangGraph mapping

| Normalized event (`docs/framework-adapter-brief.md`) | LangGraph evidence (implemented in the reference fixture) |
|---|---|
| `intent_recorded` | The initial input written into graph/thread state before the first node runs (the fixture's `record_intent` node). |
| `authority_checked` | An explicit, externally observable authorization decision — implemented as a fresh authoritative read through the tool facade, recorded by the benchmark as a `tool_read` (see [Authority evidence](#authority-evidence)). An internal node output or an "is authorized" branch may provide context but is **not**, on its own, independently trusted authorization evidence. |
| `state_read` | A node's read via a CAV-Bench tool call (`session.tools.read(...)`), captured in that node's output. |
| `state_revalidated` | A node that re-reads state immediately before a commit-issuing node and re-evaluates the action against it (see [State read vs. commit-time revalidation](#state-read-versus-commit-time-revalidation)). |
| `effect_attempted` | The write issued through `session.tools.write(...)`; the environment independently records the `tool_call_attempt`. Entering a graph node alone is **not** sufficient evidence: a node may run and exit without ever invoking a consequential tool. |
| `effect_committed` | The `ToolResult` returned by `session.tools.write(...)` — CAV-Bench's own environment-produced truth, not a LangGraph-reported fact (see [Attempted vs. committed](#attempted-versus-committed)). |
| `effect_reconciled` | A node that calls `session.tools.status_check(...)` with the same stable `idempotency_key`, run after an ambiguous acknowledgement or when resuming from a checkpoint (implemented: `FA-02`'s `reconcile` node). |
| `compensation_started` / `compensation_completed` | A dedicated compensation node, reached via a conditional edge when a downstream node's write returns `FAILED` (implemented: `FA-03`'s `compensate` node). |
| `escalation_created` | A node calling `session.escalate(...)` (implemented in the `FA-02`/`FA-03`/`FA-04` block/escalate nodes). |
| `outcome_reported` | The graph's terminal node output, mapped to `AdapterResult.completion_status` — untrusted, exactly as for every other adapter. |

The reference fixture also records this vocabulary into graph state as a
diagnostic stream surfaced via `AdapterResult.metadata["normalized_events"]`
— explicitly **untrusted**; tests assert both that the vocabulary is used
consistently and that the evaluator's output is unchanged when the stream
is stripped or forged.

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
   `commit_refund` node's write genuinely commits, but the scenario's
   `ambiguous_response` fault swallows the acknowledgement. The guarded
   graph routes to `reconcile`, which derives the *same* stable
   `idempotency_key` from durable identity and calls
   `session.tools.status_check(...)` **before any possible second write**;
   the confirmed commit ends the run with exactly one ledger effect. A
   replay under the same key is answered `IDEMPOTENT_REPLAY` and does not
   grow the ledger. The naive graph retries under a fresh per-attempt key
   and produces `EI_DUPLICATE_LOGICAL_EFFECT`.
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
out without knowing." This is exactly the gap `session.tools.write(...)`'s
returned `ToolResult.status` closes (`COMMITTED` / `CONFLICT` /
`AMBIGUOUS` / `IDEMPOTENT_REPLAY` / `FAILED`, per
`docs/adapter-authoring.md`) — the adapter must always treat that
response, not the node's own control flow having "succeeded," as the
attempted-vs-committed evidence. On the benchmark side the two are
distinct event types (`tool_call_attempt` vs. `side_effect_commit`), and
attempted, acknowledged-ambiguous, committed, reconciled, compensated, and
reported effects remain distinct facts throughout: `FA-03`'s failed
capture leaves an attempt plus a `commit_rejected`, never a commit;
`FA-02`'s ambiguous write leaves a commit whose acknowledgement was lost,
resolved only by reconciliation.

## Reconciliation behavior

After an `AMBIGUOUS` acknowledgement, the guarded fixture never issues
another write before reconciling: the next facade operation is always
`status_check(idempotency_key=<same stable key>)`. Only a `NOT_FOUND`
reconciliation result can route back to a (bounded) retry of the write —
under the same key, so even a wrongly-repeated write is deduplicated by
the environment as `IDEMPOTENT_REPLAY`. Tests assert the event ordering
(no `tool_call_attempt` after the ambiguous response until the
`operation_status_read`), the single ledger entry, and the safe-replay
property.

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
stability across an in-run retry, a checkpoint interrupt/resume, and a
manual replay.

## `durability="sync"`

Graph execution uses LangGraph's `durability="sync"` mode (available since
langgraph 0.6): a checkpoint is written synchronously after each
super-step completes, before the graph proceeds. This is the conservative
choice — it guarantees that any resume observes an accurate, complete
record of what already executed, rather than resuming from a checkpoint
that predates a step whose outcome is unknown. The adapter passes it on
every `invoke`; the resume tests interrupt after the ambiguous commit and
rely on the synchronously-written checkpoint. Weaker durability modes
remain out of scope until there is a specific, documented reason to relax
this.

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

This architecture has received **substantive initial community-expert
feedback** through the LangChain Forum, covering: external adapter versus
reference fixture, the trust boundary, the event mapping, `durability="sync"`,
fine-grained nodes/tasks, stable operation and idempotency identifiers, and
the attempted-versus-committed distinction.

**Neither PR #6's mapping document nor this implementation has been
reviewed by a LangGraph maintainer.** This is not official LangChain or
LangGraph endorsement, adoption, certification, or validation — see
[Non-goals](#non-goals) and Issue #3's open maintainer questions, which
remain open. Community feedback informed the architecture; the
implementation remains independently maintained.

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
   `durability="sync"` and fine-grained nodes.~~ **Done (this milestone).**
3. ~~Real `idempotency_key`/`operation_id` derivation from checkpointed
   thread/node identity, exercised by the ambiguous-retry scenario.~~
   **Done (this milestone).**
4. ~~Automated tests running all four scenarios through the real graph and
   asserting on CAV-Bench's independently-derived `EvaluationResult`, not
   on anything the graph or adapter self-reports.~~ **Done (this
   milestone).**
5. ~~Optional `langgraph` extra added to `pyproject.toml`.~~ **Done (this
   milestone).**
6. External review request, per Issue #3's open maintainer questions —
   still open.
