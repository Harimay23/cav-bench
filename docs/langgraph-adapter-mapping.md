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
| `authority_checked` | An explicit, externally observable authorization decision — preferably a human-in-the-loop interrupt resolved through `Command(resume=...)`, or a benchmark/facade-recorded authorization check. An internal node output or an "is authorized" branch may provide context but is **not**, on its own, independently trusted authorization evidence. |
| `state_read` | A node's read via a CAV-Bench tool call (`session.tools.read(...)`), captured in that node's output. |
| `state_revalidated` | A node that re-reads state immediately before a commit-issuing node, comparing against the last checkpointed observation. |
| `effect_attempted` | `on_tool_start` from `astream_events`, or equivalent task-stream evidence (e.g. `stream_mode="tasks"`), emitted immediately before the consequential facade/tool call. Entering a graph node alone is **not** sufficient evidence: a node may run and exit without ever invoking a consequential tool. |
| `effect_committed` | The `ToolResult` returned by `session.tools.write(...)` — CAV-Bench's own environment-produced truth, not a LangGraph-reported fact (see [Trust boundary](#trust-boundary) and [Attempted vs. committed](#attempted-versus-committed-limitation)). |
| `effect_reconciled` | A node that calls `session.tools.status_check(...)` with the same stable `idempotency_key`, run when resuming from a checkpoint after an interrupted or ambiguous prior attempt. |
| `compensation_started` / `compensation_completed` | A dedicated compensation node, reached via a conditional edge when a downstream node reports failure. |
| `escalation_created` | A node calling `session.escalate(...)`, optionally surfaced to a human via LangGraph's `interrupt()` / human-in-the-loop mechanism. |
| `outcome_reported` | The graph's terminal node output, mapped to `AdapterResult.completion_status` — untrusted, exactly as for every other adapter. |

## Four scenario execution flows

The same four scenarios from `docs/framework-adapter-brief.md`, described
in terms of the graph:

1. **Stale state before commit.** A `state_read` node observes a resource's
   version, checkpointed via `durability="sync"`. Between that checkpoint
   and the commit node's execution, the fixture injects an external state
   change. Commit-time revalidation is **not** simply reading the newest
   version and proceeding: immediately before commit, the revalidation node
   must (a) read current state, (b) re-evaluate the action's preconditions,
   intent, scope, and authority against that current state — not just its
   version number, (c) block, clarify, or escalate without committing if
   the change invalidates the action, and only if the action remains valid
   (d) call `session.tools.write(...)` with the revalidated current version
   as `expected_version`. A node that re-reads the version but skips step
   (b) has not actually revalidated anything.
2. **Ambiguous retry after a committed operation.** A tool-calling node's
   `session.tools.write(...)` call actually commits, but the fixture
   simulates a lost response (mirrors CAV-Bench's own `ambiguous_response`
   fault mode). On resume, the node must derive the *same* `idempotency_key`
   it used originally from checkpointed state and call
   `session.tools.status_check(...)` before ever attempting a second write.
3. **Partial workflow execution.** A first node's effect commits; a
   downstream node's tool call is force-failed. A conditional edge routes
   to a compensation node (or an escalation node, if no compensation is
   possible), and the terminal node's `completion_status` must not claim
   `"success"`.
4. **Authority change before execution.** An explicit, externally observable
   authorization decision (per the `authority_checked` mapping above) is
   recorded at planning time; the fixture revokes authority before the
   commit node runs. The commit node must obtain a second, equally
   independent authorization decision immediately before committing — not
   merely proceed because an earlier node's internal branch was "in
   authorized" — and must not call `session.tools.write(...)` if authority
   no longer holds.

## Stable `operation_id` and `idempotency_key` requirements

Both values must be **derived from durable, checkpointed identifiers** —
e.g. a stable composite of `thread_id` and node/task name — never freshly
generated (e.g. via `uuid4()`) on each node invocation. A LangGraph resume
after a crash or interrupt re-executes from the last checkpoint; if the key
were regenerated per invocation, a legitimate resume would look
indistinguishable from a genuinely new logical operation, and CAV-Bench's
duplicate-effect detection (`docs/methodology.md`) would either miss a real
duplicate or flag a safe resume as one, for the wrong reason.

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
actions. This is what makes per-step checkpointing, per-step
`operation_id`/`idempotency_key` derivation, and per-step evidence
collection (the normalized event mapping above) meaningful. A node that
silently performs two consequential writes internally would make it
impossible for the adapter to report `effect_attempted` /
`effect_committed` evidence at the correct granularity.

## Attempted-versus-committed limitation

LangGraph's own state reflects that a node *ran* and what it *returned* —
it does not, by itself, distinguish "the external system confirmed this
effect committed" from "the node believes it committed" or "the node timed
out without knowing." This is exactly the gap `session.tools.write(...)`'s
returned `ToolResult.status` closes (`COMMITTED` / `CONFLICT` / `AMBIGUOUS`
/ `IDEMPOTENT_REPLAY` / `FAILED`, per `docs/adapter-authoring.md`) — the
adapter must always treat that response, not the node's own control flow
having "succeeded," as the attempted-vs-committed evidence. This is the
same distinction the [Trust boundary](#trust-boundary) section describes
generally, called out separately here because it is the most common way a
framework integration would accidentally re-introduce a self-grading path.

## External review status

This architecture has received **substantive initial community-expert
feedback** through the LangChain Forum, covering: external adapter versus
reference fixture, the trust boundary, the event mapping, `durability="sync"`,
fine-grained nodes/tasks, stable operation and idempotency identifiers, and
the attempted-versus-committed distinction.

**PR #6's specific mapping document and skeleton have not yet been reviewed
by a LangGraph maintainer.** This is not official LangChain or LangGraph
endorsement, adoption, or validation — see [Non-goals](#non-goals) and
Issue #3's open maintainer questions, which remain open.

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
   `durability="sync"` and fine-grained nodes.
3. Real `idempotency_key`/`operation_id` derivation from checkpointed
   thread/node identity, exercised by the ambiguous-retry scenario.
4. Automated tests running all four scenarios through the real graph and
   asserting on CAV-Bench's independently-derived `EvaluationResult`, not
   on anything the graph or adapter self-reports.
5. Optional `langgraph` extra added to `pyproject.toml`.
6. External review request, per Issue #3's open maintainer questions.
