# 14-Day External Validation Sprint

## Objective

Determine whether qualified outsiders will review, run, extend, or apply CAV-Bench before expanding the 90-day engineering backlog.

## Day-by-day timeline

| Day | Engineering | Validation and adoption | Output |
|---|---|---|---|
| 1 | Commit program docs and Claude guidance | Finalize target categories | Program baseline |
| 2 | Confirm LangGraph implementation scope | Identify 10 framework/protocol reviewers | Reviewer list v1 |
| 3 | Implement fixture graph foundation | Identify 10 commerce/service reviewers | Target list v2 |
| 4 | Implement stale-state scenario | Begin first outreach wave | Executable scenario 1 |
| 5 | Implement ambiguous-retry scenario | Begin research/security outreach | Executable scenario 2 |
| 6 | Implement partial-execution scenario | Follow up with high-priority reviewers | Executable scenario 3 |
| 7 | Implement authority-change scenario | Collect early objections and questions | Executable scenario 4 |
| 8 | Integrate CAV scoring across all four | Hold first technical review | Four-scenario run |
| 9 | Build outcome-pass/CAV-fail demo | Send reviewer kit | Demo v1 |
| 10 | Add evidence trace and remediation output | Hold commerce design review | Report v1 |
| 11 | Improve setup and documentation | Seek one independent reproduction | Quick start v1 |
| 12 | Address substantive review feedback | Confirm one pilot or external run | Revision PR |
| 13 | Run full quality and reproducibility gate | Score all external signals | Gate evidence |
| 14 | Prepare decision report | Conduct green/yellow/red review | Sprint decision |

## Engineering scope

### Required

- LangGraph reference fixture
- four scenario flows
- stable operation and idempotency identifiers
- benchmark-owned commit truth
- deterministic tests
- outcome-pass/CAV-fail demonstration
- concise adopter-readable report

### Explicit non-goals

- production agent architecture
- framework ranking
- model intelligence evaluation
- broad commerce scenario pack
- certification
- official support claims

## External validation targets

| Group | Contacts | Desired commitments |
|---|---:|---:|
| Framework and protocol experts | 10 | 3 responses, 1 review |
| Commerce and service architects | 10 | 3 responses, 1 design partner |
| Security and assurance communities | 6 | 2 responses, 1 work-product discussion |
| Researchers | 5 | 1 methodology review or reproduction |

## What counts as substantive validation

- detailed technical feedback;
- reproduction attempt;
- adapter correction;
- submitted scenario;
- pilot commitment;
- public discussion or presentation invitation;
- willingness to document a resulting change.

Generic praise or passive social engagement does not count.

## Decision report template

1. What was built?
2. Who reviewed or ran it?
3. What objections were raised?
4. What changed because of feedback?
5. Did an external user commit to a run?
6. Is the metric actionable?
7. Is onboarding acceptable?
8. Which profile has the strongest demand?
9. Green, yellow, or red decision?
10. What changes in the next 30 days?
