# Design Approval — M-GPI-1

Status: Recorded

This is a **design-approval record** in the format defined by
[`../gate-state.md`](../gate-state.md#design-approval-record-format). It
approves one specific design document at one specific reviewed commit for
one bounded implementation milestone. It is not a PR approval, not a merge
authorization, and not external validation — see
[Scope of this record](#scope-of-this-record).

| Field | Value |
|---|---|
| `milestone_id` | `M-GPI-1` |
| `design_path` | [`../../design/generic-protocol-integration.md`](../../design/generic-protocol-integration.md) |
| `reviewed_commit` | `38c5e1e8590e17c2798618c0490db7958d7f739d` |
| `merged_main_commit` | `6aee17723c53cc9fc56f2e40a793c5ffc1d8b6ce` |
| `decision` | `approved_with_conditions` |
| `approver` | Nixalkumar Patel (GitHub: `Harimay23`) |
| `timestamp` | 2026-07-19T18:59:44Z |

## Approved scope

- The benchmark-owned protocol gateway topology (candidate as protocol
  client; gateway as benchmark-owned mediator; `ToolFacade` and
  `BenchmarkEnvironment` as the sole effect executor and commit authority).
- The candidate acting strictly as a protocol client — never an effect
  executor.
- `BenchmarkEnvironment` remaining the sole effect executor and commit
  authority; no new commit path.
- The one-request-to-one-`ToolFacade`-invocation mapping.
- A shared gateway core, transport-independent, with REST as the first
  implemented transport frontend.
- A deterministic reference candidate client for local development and CI.
- Loopback-only reproducible benchmark mode.
- Optional-dependency isolation for all protocol extras.
- The rejected imported-evidence topology (external execution with
  results mirrored into the benchmark afterward) — this rejection is
  itself part of the approved design and must not be revisited without a
  new design review.
- Proposed branch: `feat/generic-protocol-integration`.
- Proposed PR: `feat: add generic protocol gateway core with REST frontend`.

## Explicitly unapproved scope

- Production MCP transport implementation. The architecture may preserve
  the MCP extension boundary, but MCP transport code is not authorized by
  this record and requires its own later milestone or scope extension.
- Any topology in which the candidate executes effects outside the
  benchmark environment (the rejected imported-evidence topology, named
  above, remains rejected).
- Any change to evaluator or runtime semantics, schema, or core-v1.

## Conditions

1. The implementing PR must add a binding `DECISION_LOG.md` entry
   recording: the approved gateway topology; the REST-first transport
   order; the rejected imported-evidence topology; and the
   benchmark-owned commit-truth boundary.
2. The implementation must introduce no new evaluator truth source, no
   new commit path, and no behavior that manufactures ledger effects from
   candidate claims.
3. MCP implementation is not approved in this milestone (see
   [Explicitly unapproved scope](#explicitly-unapproved-scope)).
4. The implementation must stop and escalate if it requires: evaluator
   changes; core-v1 changes; schema semantic changes; adapter-supplied
   commit truth; or external execution mirrored into the benchmark.

## Unresolved external prerequisites

Implementation may not treat these as satisfied by this approval:

- External technical review of the envelope and both frontend mappings is
  required before the integration may be represented publicly as
  externally usable or externally validated (per the design's acceptance
  criteria).
- No official REST, MCP, framework, or community support or endorsement
  is implied by this approval or by implementation.

## Evidence references

- [Pull request #9](https://github.com/Harimay23/cav-bench/pull/9)
  (merged), which carried the reviewed design text at commit
  `38c5e1e8590e17c2798618c0490db7958d7f739d`.
- [Pull request #10](https://github.com/Harimay23/cav-bench/pull/10)
  (`docs/approve-initial-workstreams`) introduces and records this human
  approval decision. Additional provenance: PR #10 branch head at commit
  `617f6f0be6600a0bf7d2ceccef141e45959040e9` as of the decision above;
  the PR head advances with subsequent corrections to this documentation
  package, which does not itself reopen the approval.

## Scope of this record

This record approves **this design, at this reviewed commit, for this
milestone** — nothing more. It is not approval of any implementation PR
that will later claim to satisfy `M-GPI-1` (that PR requires its own human
review and approval per `gate-state.md`); it is not a merge authorization
for anything; and it is not external validation of the gateway design or
of CAV-Bench generally. If `generic-protocol-integration.md` changes
materially after `38c5e1e8590e17c2798618c0490db7958d7f739d`, this record
becomes **stale** and a new review and record are required before
implementation may proceed (typo-level fixes are exempt at the approver's
recorded discretion).
