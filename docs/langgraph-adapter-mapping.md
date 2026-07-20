# LangGraph Adapter Mapping

Status: **Draft**
Related framework-neutral RFC: [Issue #3](https://github.com/Harimay23/cav-bench/issues/3), [`docs/framework-adapter-brief.md`](framework-adapter-brief.md)
Related implementation issue: [Issue #5 — Implement initial CAV-Bench LangGraph adapter](https://github.com/Harimay23/cav-bench/issues/5)

This document specifies how a LangGraph-based agent maps onto CAV-Bench's
normalized event model and `ExecutionAdapter` protocol. It is
framework-specific detail that `docs/framework-adapter-brief.md`
deliberately left out of the framework-neutral specification.

## Integration boundary

The integration surface is an **external `LangGraphAdapter`** implementing
`cavbench.adapters.protocol.ExecutionAdapter`
(`name`, `version`, `run(session: AdapterSession) -> AdapterResult`) — the
same protocol every other adapter, including CAV-Bench's own five baseline
profiles, implements. `LangGraphAdapter` is not a fork of CAV-Bench and
requires no evaluator or runtime changes to plug in (`docs/architecture.md`).

A **reference LangGraph graph** used to exercise the adapter's four
scenarios is a deterministic test fixture only. It demonstrates the mapping
below works end to end; it is not a production agent design and is not
presented as one (see [Non-goals](#non-goals)).

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

## Optional dependency model

LangGraph is **not** a core CAV-Bench dependency. `import cavbench` and the
core benchmark run (`cavbench doctor`, `cavbench ablate`, ...) must never
require LangGraph to be installed. `src/cavbench/adapters/langgraph.py`
never imports `langgraph` at module level — only lazily, inside the methods
that actually need it, so that importing the module itself succeeds
regardless of whether LangGraph is installed. A future PR may add a
`langgraph` optional-dependency extra (analogous to the existing
`reporting` extra in `pyproject.toml`) once the real graph is implemented;
this is out of scope for the design-stage skeleton.

## Normalized-event-to-LangGraph mapping

| Normalized event (`docs/framework-adapter-brief.md`) | LangGraph evidence |
|---|---|
| `intent_recorded` | The initial input written into graph/thread state before the first node runs. |
| `authority_checked` | An explicit, externally observable authorization decision point — typically an `interrupt()` / `Command(resume=...)` step. This makes the decision *observable*; it is **not itself authorization truth**. See [Authority: observability versus truth](#authority-observability-versus-truth). |
| `state_read` | A node's read via a CAV-Bench tool call (`session.tools.read(...)`), captured in that node's output. |
| `state_revalidated` | A node that re-reads state and semantically re-evaluates the action immediately before a commit-issuing node. See [Stale-state TOCTOU protection](#stale-state-toctou-protection) — this alone does not close the race. |
| `effect_attempted` | Authoritative only when recorded synchronously at `session.tools.write(...)` (`ToolFacade.write()`) entry, before `BenchmarkEnvironment` applies the effect. `on_tool_start`/`astream_events` and task-stream (`stream_mode="tasks"`) evidence are *corroborating ordering evidence only* — see [Evidence spine](#evidence-spine-attempted-versus-committed). |
| `effect_committed` | Authoritative only when derived from the `ToolResult` / `BenchmarkEnvironment` result returned by that same `session.tools.write(...)` call — never from a LangGraph-reported fact. See [Trust boundary](#trust-boundary) and [Evidence spine](#evidence-spine-attempted-versus-committed). |
| `effect_reconciled` | A node that calls `session.tools.status_check(...)` with the same stable operation identity, performed **unconditionally** before any retry — see [Stable operation identity and reconciliation](#stable-operation-identity-and-reconciliation). |
| `compensation_started` / `compensation_completed` | A dedicated compensation node, reached via a conditional edge when a downstream node reports failure. |
| `escalation_created` | A node calling `session.escalate(...)`, optionally surfaced to a human via LangGraph's `interrupt()` / human-in-the-loop mechanism. |
| `outcome_reported` | The graph's terminal node output, mapped to `AdapterResult.completion_status` — untrusted, exactly as for every other adapter. |

## Evidence spine: attempted versus committed

The **single authoritative evidence spine** for both `effect_attempted` and
`effect_committed` is the adapter's own call into the tool facade — never
anything LangGraph observes about itself:

- `effect_attempted` is authoritative **only** when recorded synchronously
  at `ToolFacade.write()` entry, before `BenchmarkEnvironment` applies the
  effect.
- `effect_committed` is authoritative **only** when derived from the
  `ToolResult` / `BenchmarkEnvironment` result returned by that same call.

`on_tool_start` (from `astream_events`) and task-stream events
(`stream_mode="tasks"`) are **corroborating ordering evidence only** —
useful for reconstructing *when* things happened relative to each other,
never a substitute for the two facts above. This is load-bearing, not
cautious phrasing, for two reasons:

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

This document does **not** specify a complete runtime normalized-event
emission mechanism — deciding exactly which LangGraph callback/stream hooks
the adapter subscribes to, and how it correlates them with tool-facade
calls into the normalized event stream, is out of scope for this
design-stage PR. It is recorded as a required item under
[Next implementation milestones](#next-implementation-milestones).

## Authority: observability versus truth

`interrupt()` and `Command(resume=...)` make an authorization decision
**externally observable** — a human or a scripted process can see the
decision point and provide a response. They do **not** make that response
authorization truth:

- The resume payload is **adapter/harness input**, exactly like any other
  value a node receives — it carries no more trust than an argument the
  graph was called with.
- **Current authorization must still be adjudicated by the facade or
  `BenchmarkEnvironment`** at commit time, independent of what the resume
  payload said.
- A revoked actor must receive an **environment-level hard refusal**
  regardless of an "approve" resume value — a stale approval cannot
  override a real revocation.
- **CI fixtures use deterministic scripted resume values, not a human**, to
  keep the four scenarios reproducible (`docs/methodology.md`'s
  determinism requirements apply here exactly as everywhere else in
  CAV-Bench).
- The **facade/environment check is primary truth; the interrupt is an
  optional observability wrapper** around it, not a replacement for it.

## Four scenario execution flows

The same four scenarios from `docs/framework-adapter-brief.md`, described
in terms of the graph:

1. **Stale state before commit.** A `state_read` node observes a resource's
   version, checkpointed via `durability="sync"`. Commit-time revalidation
   is **not** simply reading the newest version and proceeding: immediately
   before commit, the revalidation node must (a) read current state, (b)
   re-evaluate the action's preconditions, intent, scope, and authority
   against that current state — not just its version number, and (c)
   block, clarify, or escalate without committing if the change invalidates
   the action. See [Stale-state TOCTOU protection](#stale-state-toctou-protection)
   for why this is still not sufficient on its own.
2. **Ambiguous retry after a committed operation.** A tool-calling node's
   `session.tools.write(...)` call actually commits, but the fixture
   simulates a lost response — injected **before the write super-step's
   checkpoint is persisted** (see
   [Stable operation identity and reconciliation](#stable-operation-identity-and-reconciliation)),
   mirroring CAV-Bench's own `ambiguous_response` fault mode. On resume,
   the node must derive the *same* operation identity it used originally
   from checkpointed state and perform **unconditional** reconciliation
   (`session.tools.status_check(...)`) before ever attempting a second
   write.
3. **Partial workflow execution.** A first node's effect commits; a
   downstream node's tool call is force-failed. A conditional edge routes
   to a compensation node (or an escalation node, if no compensation is
   possible), and the terminal node's `completion_status` must not claim
   `"success"`.
4. **Authority change before execution.** An `interrupt()`/
   `Command(resume=...)` step makes an authorization decision observable at
   planning time — in CI, resolved with a deterministic scripted resume
   value, never a human. The fixture then revokes authority before the
   commit node runs. Per
   [Authority: observability versus truth](#authority-observability-versus-truth),
   the earlier resume payload is not authorization truth: the commit node's
   write must still be adjudicated by `BenchmarkEnvironment` at commit
   time, and `session.tools.write(...)` must be refused if authority no
   longer holds, regardless of what the resume payload said earlier.

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

The fixture implementing this scenario must therefore inject **two**
mutations, not one: the original mutation the current single-mutation
fixture already covers, and a second mutation timed to land **after
semantic revalidation but before commit**. Expected behavior for that
second, later mutation: `session.tools.write(...)` returns `CONFLICT`, and
no invalid effect is committed — proving the atomic guard, not the
revalidation node's own reasoning, is what ultimately protects the commit.

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

## `durability="sync"`

Graph execution must use LangGraph's `durability="sync"` mode: a checkpoint
is written synchronously after each super-step completes, before the graph
proceeds to the next step. This is the conservative choice — it guarantees
that any resume observes an accurate, complete record of what already
executed, rather than resuming from a checkpoint that predates a step whose
outcome is unknown. Weaker durability modes are out of scope until there is
a specific, documented reason to relax this.

## Fine-grained node boundaries

One LangGraph node (or `@task`, under the functional API) per logical
CAV-Bench step — never a coarse node that bundles multiple consequential
actions. This is what makes per-step checkpointing, per-step operation
identity, and per-step evidence collection (the normalized event mapping
above) meaningful, and it is specifically what makes the task-stream and
tool-stream granularities discussed in
[Evidence spine](#evidence-spine-attempted-versus-committed) coincide in
the reference fixture. A node that silently performs two consequential
writes internally would make it impossible for the adapter to report
`effect_attempted` / `effect_committed` evidence at the correct
granularity.

## Attempted-versus-committed limitation

LangGraph's own state reflects that a node *ran* and what it *returned* —
it does not, by itself, distinguish "the external system confirmed this
effect committed" from "the node believes it committed" or "the node timed
out without knowing." This is exactly the gap `session.tools.write(...)`'s
returned `ToolResult.status` closes (`COMMITTED` / `CONFLICT` / `AMBIGUOUS`
/ `IDEMPOTENT_REPLAY` / `FAILED`, per `docs/adapter-authoring.md`) — the
adapter must always treat that response, not the node's own control flow
having "succeeded," as the attempted-vs-committed evidence. This is the
same distinction [Trust boundary](#trust-boundary) describes generally and
[Evidence spine](#evidence-spine-attempted-versus-committed) describes
mechanically; it is called out separately here because it is the most
common way a framework integration would accidentally re-introduce a
self-grading path.

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

This is **not**: official LangChain endorsement, official LangGraph
endorsement, LangGraph maintainer approval, adoption, or production
validation. See [Non-goals](#non-goals) and Issue #3's open maintainer
questions, which remain open.

## Non-goals

Same as `docs/framework-adapter-brief.md`, plus adapter-specific
clarifications:

- Not a comparison of LangGraph against other frameworks or against model
  intelligence.
- Not a claim of official LangGraph support, endorsement, or adoption.
- Not a production agent design — the reference graph is a test fixture.
- Does not change CAV-Bench's evaluator, scoring definitions, or validity
  dimensions.
- Does not make LangGraph a core CAV-Bench dependency.

## Next implementation milestones

1. Design-stage skeleton (this PR): `LangGraphAdapter` satisfying the
   `ExecutionAdapter` protocol shape, raising a clear development-stage
   error on `run()`; no real graph.
2. Reference fixture graph implementing the four scenarios above with
   `durability="sync"` and fine-grained nodes, including the two-mutation
   stale-state fixture from
   [Stale-state TOCTOU protection](#stale-state-toctou-protection) and the
   checkpoint-timed lost-response fixture from
   [Stable operation identity and reconciliation](#stable-operation-identity-and-reconciliation).
3. Operation identity derivation from checkpointed `thread_id` + node/task
   identity + a durable per-operation discriminator (not `thread_id` +
   node name alone), exercised by the ambiguous-retry scenario across both
   `RetryPolicy` retries and crash/interrupt resume.
4. The runtime normalized-event emission mechanism deferred in
   [Evidence spine](#evidence-spine-attempted-versus-committed): deciding
   which LangGraph callback/stream hooks the adapter subscribes to and how
   they correlate with tool-facade calls.
5. Automated tests running all four scenarios through the real graph and
   asserting on CAV-Bench's independently-derived `EvaluationResult`, not
   on anything the graph or adapter self-reports.
6. Optional `langgraph` extra added to `pyproject.toml`.
7. External review request directed at a LangGraph maintainer specifically
   (as opposed to the community-expert review already received), per
   Issue #3's open maintainer questions.
