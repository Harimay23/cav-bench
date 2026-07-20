# PR and Branch Strategy — Future Milestones

Status: Proposed

Branch and pull-request rules for executing the milestones in
[`implementation-manifest.md`](implementation-manifest.md). This extends
the repository's existing conventions (`CLAUDE.md`: short-lived branches,
atomic PRs, no long-running program branch; branch prefixes `docs/`,
`feat/`, `fix/`, `test/`, `chore/`) with the rules an automated executor
needs spelled out. Branch names below are **proposed until design
approval**, at which point the manifest fixes them.

## Core rules

1. **One branch per implementation milestone.** A milestone's entire
   implementation lives on exactly one branch, named in its manifest
   entry. No side branches, no shared branches across milestones.
2. **One focused PR per milestone.** Each branch produces exactly one PR
   covering exactly that milestone's deliverables, opened as **draft**,
   meeting the PR-body requirements of `CLAUDE.md` (problem, beneficiary,
   approach, trust-boundary impact, tests, adoption barrier removed,
   verifiable output, unsupported claims, non-goals).
3. **No giant implementation PR.** If a milestone's diff grows beyond
   focused reviewability, that is a design problem: stop, propose a
   milestone split in the manifest (a human decision), do not open the
   monolith.
4. **No mixing speculative documentation with implementation.** Design
   documents travel in `docs/` PRs like this one; implementation PRs
   change design docs only mechanically (status line updates authorized
   by the gate process). New speculation mid-implementation goes to a new
   docs branch.
5. **No changes to frozen branches.** Branches under review or explicitly
   frozen — currently the LangGraph chain
   (`feat/langgraph-adapter-skeleton` / PR #6, and
   `feat/langgraph-four-scenario-runtime` / PR #8) — are never pushed to,
   rebased, or merged by a milestone executor. Their evolution belongs to
   their own review process.
6. **Merging is human.** No executor merges any PR (see
   [`fable-execution-contract.md`](fable-execution-contract.md)).

## Proposed milestone branches

| Milestone | Branch (proposed) |
|---|---|
| `M-COM-V1` | `feat/commerce-v1-profile` |
| `M-GPI-1` | `feat/generic-protocol-integration` |
| `M-IVT-1` | `feat/independent-validation-tooling` |
| `M-HFA-1` | `feat/hidden-failure-analysis` |
| `M-IET-1` | `feat/improvement-evidence-tooling` |
| `M-REL-NEXT` | `release/follow-up-version` |

`release/` is a new prefix introduced (as proposed) for release-candidate
work; all other prefixes are the existing conventions.

## Base-branch selection rules

- **Default:** every milestone branch is created from the current
  `origin/main` at creation time, and its PR targets `main`.
- **Exception — true code dependency:** if milestone B cannot compile or
  test without milestone A's unmerged code, B may branch from A's branch
  and open a **stacked PR** targeting A's branch (the PR #8-on-PR #6
  pattern). This is the only justification for a non-`main` base;
  "thematically related" is not a dependency.
- The chosen base and its SHA are recorded in the execution journal at
  branch creation.

## Stacked PR rules

- A stacked PR's body must name its base PR and state that it must not
  merge before it.
- Stacks are at most two deep without explicit human approval.
- The stacked branch never modifies files owned by the base PR's diff
  except through the base merging first.
- Current standing stack: PR #8 → PR #6 → main (pre-existing; not
  managed under this strategy, but its retargeting follows the same rules
  below when #6 merges).

## Retargeting rules after dependency PRs merge

When a base PR merges to `main`:

1. Fetch; verify the merge commit exists on `origin/main`.
2. Retarget the stacked PR's base to `main` in the same change window as
   step 3, so reviewers never see a misleading diff for long.
3. Rebase the stacked branch onto `origin/main` (preferred over merge
   commits for short-lived branches); resolve conflicts per the conflict
   rules; force-push **with lease** and record the old and new head SHAs
   in the journal and a PR comment.
4. Re-run the full required validation after retargeting — a green state
   before rebase proves nothing after it.

## Conflict handling

- Conflicts are resolved on the milestone branch, never by pushing to the
  other side of the conflict.
- Semantic conflicts (both sides touch benchmark semantics, goldens, or
  schema contracts) are a stop condition: escalate to a human rather than
  choosing a resolution that silently changes semantics.
- After any conflict resolution: full validation re-run; the resolution
  is described in the PR body or a comment.

## Release branch rules

- `release/follow-up-version` is created only when the release design's
  entry criteria hold (scope freeze); it receives **only**
  release-blocking fixes after creation, each as a normal reviewed PR
  targeting the release branch.
- Tagging happens on the release branch (or on `main` after the release
  PR merges — the release checklist fixes this at rehearsal); tags are
  human-created.
- Hotfixes branch from the release tag (`fix/…` from `vX.Y.Z`), ship as
  patch releases, and are merged back to `main` by a human.

## Branch cleanup

- A milestone branch is deleted after its PR merges (GitHub's
  delete-on-merge or a human act) — never before, and never for
  unmerged branches without human confirmation.
- Abandoned-milestone branches are left in place until the abandonment is
  recorded per `gate-state.md`, then deleted by a human.
- The executor never deletes any branch it did not create in the current
  milestone, and never deletes remote branches at all — deletion is
  human-confirmed cleanup.

## Rollback

- **Pre-merge:** rollback = close the PR and delete the branch (human
  confirmation for the deletion); the manifest entry returns to its prior
  state with a recorded reason.
- **Post-merge:** rollback is a **revert PR** (a new `fix/` branch
  reverting the merge commit), reviewed and merged like any change —
  history is never rewritten on `main`.
- **Post-release:** forward-only, per the release design's rollback/yank
  rules (`../design/follow-up-release.md`).

## Relationship to the in-flight LangGraph chain

PR #6 and PR #8 predate this strategy and remain governed by their own
review process. This strategy's only obligations toward them are
negative: no pushes, no rebases, no merges, no retargeting by any
executor operating under this document. The documentation branch carrying
this package (`docs/future-workstream-designs`) bases on `main` and is
independent of that chain.
