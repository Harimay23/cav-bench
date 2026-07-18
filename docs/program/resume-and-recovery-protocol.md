# Resume and Recovery Protocol

Status: Proposed

Defines the **execution journal** an executor maintains while working the
[`implementation-manifest.md`](implementation-manifest.md) queue, and the
restart behavior after every recognized interruption class. The journal
exists so that a fresh session — with no memory of the previous one — can
reconstruct exactly where work stood, what is safe to do next, and what
must not be done, using only the journal plus observable git/GitHub
state.

## Journal format

The journal is both machine-readable and human-readable: an append-only
JSON Lines file (one checkpoint per line) plus an optional rendered
Markdown view generated from it. Proposed location:
`docs/program/journal/execution-journal.jsonl` on the **milestone
branch** while work is in flight (so the journal travels with the work
and lands in the PR), with the session-start and session-end checkpoints
also summarized in the PR body. The location is fixed at design approval.

The journal is append-only: corrections are new checkpoints referencing
the corrected one, never edits.

### Checkpoint schema

Each checkpoint records:

| Field | Meaning |
|---|---|
| `timestamp` | ISO-8601, executor's clock. |
| `checkpoint_id` | Monotonic per journal (e.g. `ckpt-0007`). |
| `milestone` | `milestone_id` from the manifest (or `none`). |
| `repository` | Remote URL being worked. |
| `worktree` | Absolute path of the working directory. |
| `branch` | Current branch name. |
| `base_branch` | The branch this milestone's PR targets. |
| `base_commit` | SHA of the base at branch creation / last rebase. |
| `head_commit` | Current local HEAD SHA (and pushed SHA if different). |
| `pr_number` | PR number/URL once one exists, else `null`. |
| `status` | The milestone's gate state as the executor understands it. |
| `completed_tasks` | Finished steps, each with evidence (commit SHA, file list, command). |
| `remaining_tasks` | Ordered remaining steps for this milestone. |
| `tests_run` | Commands executed this session. |
| `test_results` | Per command: pass/fail + failure summary verbatim. |
| `external_dependencies` | Awaited external inputs: what, from whom, evidence class that unblocks (`external-evidence-policy.md`). |
| `open_risks` | Known unresolved risks. |
| `unresolved_decisions` | Decisions deferred to humans, with context. |
| `next_permitted_action` | The single action a resuming session should take first. |
| `prohibited_next_actions` | Actions that must NOT be taken from this state (e.g. "do not re-push; push may have partially completed", "do not create PR; creation may have succeeded"). |

`next_permitted_action` and `prohibited_next_actions` are mandatory in
every checkpoint — they are what make blind resumption safe.

### When to checkpoint

At minimum: session start (after preflight), milestone selection, branch
creation, after each logical commit, before and after any push, before
and after PR creation, on every validation run, on entering/leaving a
blocked state, and at session end. Checkpoints are cheap; missing ones
are expensive.

## Restart behavior

Universal resume sequence, before any recovery case is even identified:

1. Read the latest checkpoint (and scan recent ones for unfinished
   two-phase operations like push/PR-create).
2. Observe reality: `git status`, `git log` local vs. `origin`,
   the PR list for the milestone branch, CI state.
3. **Reconcile** journal vs. reality; classify into one of the cases
   below. Reality wins over the journal for facts; the journal wins for
   intent (`next_permitted_action`).
4. Write a resume checkpoint recording the reconciliation before acting.

### Case: context loss (session ended mid-milestone, state clean)

Journal and reality agree; work is simply unfinished. Resume at
`next_permitted_action`. Do not re-plan from scratch; do not restart
completed tasks (their evidence is in `completed_tasks`).

### Case: tool failure (a command errored mid-operation)

Identify what the failed tool may have half-done (the previous
checkpoint's `prohibited_next_actions` should anticipate this). Verify
each potentially-affected artifact directly (file exists? commit exists?
remote updated?), then either complete or cleanly redo the single
operation. Never assume a failed tool did nothing.

### Case: failed tests

Failing validation is recorded state, not an emergency: resume by reading
`test_results`, fix on the milestone branch, re-run the full required
validation (not just the failed test), checkpoint. If the failure is a
golden deviation, that is a stop condition — checkpoint, escalate, do not
"fix."

### Case: merge conflict

Occurs during rebase/retarget per
[`pr-and-branch-strategy.md`](pr-and-branch-strategy.md). If mid-rebase
state is found on resume: complete or abort the rebase (`git rebase
--abort` restores a known state; prefer abort-then-redo over resuming a
half-understood rebase). Semantic conflicts escalate per the branch
strategy.

### Case: base branch moved

`origin/main` (or the stacked base) advanced since `base_commit`. Not
inherently a problem: finish the milestone against the recorded base
unless (a) the manifest entry's dependencies merged (→ retarget per the
branch strategy), or (b) conflicting changes landed (→ rebase per the
branch strategy, full re-validation). Record the observed new base SHA
either way.

### Case: interrupted push

Local `head_commit` may or may not have reached origin. Compare local and
remote SHAs directly. If remote matches: the push succeeded; continue. If
remote is behind: re-push (a plain push is idempotent-safe here). If
remote has commits the journal doesn't know: **stop** — someone else
touched the branch; escalate rather than force-push.

### Case: partially created PR

PR creation may have succeeded without the executor recording it. Query
PRs for the milestone branch **before** creating one. Exactly one exists
→ adopt it (record `pr_number`, verify body completeness, update).
None → create it. More than one → close nothing; escalate to a human
(closing PRs is not the executor's call).

### Case: unavailable external evidence

The journal says an external input was awaited; on resume it still is not
recorded. Remain `BLOCKED_EXTERNAL_INPUT`: re-verify whether the input
arrived (recorded evidence only — an issue comment claiming approval is
checked against `gate-state.md` authorization rules), then either proceed
or re-checkpoint the continued block. Never proceed on the theory that
enough time passing constitutes approval.

## Journal integrity

- The journal file is committed with the work it describes; its history
  is the audit trail.
- A journal that contradicts itself (e.g. two `ckpt-0007`s) or contradicts
  git history in ways reconciliation cannot resolve is a stop condition:
  the executor reports the contradiction and a human decides the true
  state.
- On milestone completion (PR merged, entry advanced), the final journal
  state is preserved in the merged history; a new milestone starts a new
  journal segment (new `milestone` value, continuing the same file).

## Relationship to the execution contract

The [`fable-execution-contract.md`](fable-execution-contract.md)
preflight *requires* reading this journal, and its context-exhaustion
behavior *requires* writing checkpoints; this protocol supplies the
format and the per-case recovery rules. Where a case here would violate a
contract rule (e.g. force-push), the contract wins and the case escalates.
