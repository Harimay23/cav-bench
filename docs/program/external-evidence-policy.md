# External Evidence Policy

Status: Proposed

This policy separates **what automation may prepare** from **what must be
real** — the boundary that keeps every external-facing claim in this
project substantiated. It binds the
[`fable-execution-contract.md`](fable-execution-contract.md), the
[`implementation-manifest.md`](implementation-manifest.md) completion
evidence, the release gate
([`../design/follow-up-release.md`](../design/follow-up-release.md)), and
all public documentation, and it operationalizes the claim discipline of
[`../strategy/adoption-and-validation-tracking.md`](../strategy/adoption-and-validation-tracking.md)
and `CLAUDE.md` non-negotiable rule 7 (no endorsement/adoption/validation
claims without explicit external evidence).

## The principle

Automation can build every tool, template, and check this program needs.
Automation can never *be* the external world. Anything whose value comes
from an outside party's independent act — a run, a review, a permission,
an adoption, a discovery in a real system — exists only when that party's
act is recorded with provenance. Preparing the stage is automatable;
the performance is not.

## What automation may prepare

Automation (including a Fable executor operating under the execution
contract) may build, without any external evidence existing yet:

- **tooling** — runners, packagers, verifiers, connectors, analysis
  pipelines;
- **templates** — manifests, attestations, checklists, report and
  case-study skeletons;
- **manifests** — implementation queue entries, evidence-manifest
  scaffolds, checksum manifests and bundle roots over project-generated
  artifacts;
- **evidence collectors** — code that captures, checksums, and archives
  artifacts produced by whoever runs it;
- **validators** — schema checks, link checks, claim-scan tooling,
  reproducibility verifiers;
- **report generators** — rendering recorded evidence into readable
  outputs;
- **case-study scaffolding** — structure and placeholders, clearly
  labeled as containing no real case;
- **reproducibility checks** — dry runs, rehearsals, and synthetic
  demonstrations, always labeled as project-generated.

Prepared artifacts must be **self-describing about their emptiness**: a
template that could be mistaken for a filled record must carry an
explicit "no real evidence recorded" marker until real evidence fills it.

## What automation may not claim

Automation may never state, imply, mark complete, or generate text
asserting any of the following, in any repository file, PR, report, or
release artifact:

- **independent external execution** — that anyone outside the project
  ran the benchmark;
- **reviewer endorsement** — that any reviewer approved, endorsed, or
  validated anything;
- **external adoption** — that any person, team, or project uses
  CAV-Bench;
- **hidden failure discovery without preserved evidence** — a finding
  claim requires a `validated`, `reproduced` finding record with its
  archived evidence chain;
- **remediation adoption** — that any subject team implemented or
  accepted a change;
- **measured before-and-after improvement** — that a retest showed
  improvement;
- **publication permission** — that anyone consented to being named,
  quoted, or described;
- **community recognition** — sessions, references, mappings, or work
  products attributed to a community;
- **official framework support** — that LangChain, LangGraph, MCP's
  stewards, or any framework/protocol organization supports, endorses,
  or is affiliated with this project;
- **certification** — of anything, by anyone, in either direction;
- **standards status** — that CAV-Bench is, or is becoming, a standard.

When real evidence of one of these *does* exist, the claim must be scoped
to exactly what the evidence supports, use the allowed claim shapes from
the tracking guidance ("Reviewed by…", "Reproduced independently by…"),
and carry an evidence reference.

## Evidence classes

Every piece of evidence cited by a manifest entry, gate transition,
finding, case study, or release claim belongs to exactly one class:

| Class | Definition | Example |
|---|---|---|
| **Repository-generated** | Produced by project code/tools run by the project, deterministic from the repository. | Golden ablation outputs; pack digests; rehearsal bundles. |
| **CI-generated** | Produced by the project's CI on identified commits. | CI run results; double-run determinism hashes. |
| **Project-team** | Produced by a maintainer's recorded manual act. | Dry-run bundle (`project_self_run`); review sign-offs by maintainers; decision-log entries. |
| **Assisted external** | Produced by an outside party with project assistance beyond the support boundary. | An `assisted_external` validation-run bundle. |
| **Independent external** | Produced by an outside party's independent act, attested by them. | An `independent_external` run bundle; an external technical review; an owner's remediation record. |
| **Permission / attribution** | A recorded grant by an external party covering identity, quotation, or detail level. | Disclosure records; publication permissions. |

Class is determined by **who performed the generative act**, not who
stored the file. Evidence may be reclassified only downward (e.g.
independent → assisted when undisclosed assistance surfaces), never
upward.

## Minimum provenance and integrity fields

Every recorded evidence item carries at least:

**All classes:** stable evidence ID; class; what it evidences; creation
timestamp; storage location; integrity binding — either the item's own
SHA-256 checksum, or membership in an evidence bundle via that bundle's
`checksums.sha256` and recorded bundle-root checksum (the non-recursive
integrity model defined in
[`../design/independent-validation-run.md`](../design/independent-validation-run.md));
creator identity.

**Repository-generated, additionally:** repository commit SHA and command
that produced it; seed/configuration where applicable.

**CI-generated, additionally:** CI provider, workflow, run ID/URL;
triggering commit SHA.

**Project-team, additionally:** the maintainer's name and role; the
manual act performed; date.

**Assisted external, additionally:** the external party (or anonymized
handle plus a restricted identity record); the attestation; a complete
assistance disclosure; the disclosure level governing use.

**Independent external, additionally:** the external party's own
attestation in their words; independence-rubric result
([`../design/independent-validation-run.md`](../design/independent-validation-run.md));
confirmation that assistance stayed within the support boundary;
disclosure level.

**Permission / attribution, additionally:** grantor identity; exact scope
granted (identity, organization, quotation, artifact detail); grant date
and channel; any expiry or embargo; where the grant record is stored
(restricted records by default).

An item missing its class's minimum fields is not evidence — it is a
note, and nothing may cite it as evidence.

## Enforcement points

- **Gate transitions:** `gate-state.md` names which transitions demand
  which classes; automation cannot substitute a lower class.
- **Manifest completion:** completion-evidence lists in the
  implementation manifest name classes explicitly (e.g. `M-HFA-1`'s
  discovery outcome requires independent/assisted external evidence,
  never repository-generated).
- **Release gate:** the evidence manifest maps every claim → class →
  reference; unmapped claims are removed before tagging
  (REL-FR-011).
- **Documentation reviews:** the prohibited-claims scan (release claims
  review, and this PR's validation practice) checks changed files against
  the "may not claim" list.
- **Execution journal:** every checkpoint's "external dependencies" field
  names awaited evidence by class, so a resumed executor cannot mistake a
  prepared template for arrived evidence.

## Failure handling

Discovering a violated rule (a claim without evidence, a misclassified
item, a fabricated record) is a stop-condition event: freeze the affected
claim's surface, correct or retract it publicly if already published, and
record the incident. An executor that cannot determine an item's class
must treat it as the lowest plausible class and flag it for human review.
