# GitHub Issue Hierarchy

These issue bodies are ready to paste into GitHub. Keep public issues focused on technical scope, user value, validation criteria, and project outcomes.

## Master issue — 90-Day Technical Validation and Adoption Roadmap

### Objective

Coordinate the 90-day program to make CAV-Bench independently reviewable, reproducible, adoptable, and capable of demonstrating measurable improvement in consequential-agent execution.

### Outcomes

- [ ] One production-quality framework adapter
- [ ] One generic protocol or REST integration
- [ ] One applied domain scenario pack
- [ ] Three substantive external reviewers
- [ ] One independently conducted benchmark run
- [ ] One hidden consequential-action failure identified
- [ ] One architecture, control, or test-process improvement documented
- [ ] One before-and-after case study
- [ ] One community work product, session, mapping, or external reference
- [ ] One versioned public release

### Program gates

- [ ] Day-14 external-validation gate
- [ ] Week-5 usability gate
- [ ] Week-9 demonstrated-improvement gate
- [ ] Week-13 public-release gate

### Non-goals

- production transaction platform;
- framework ranking;
- certification program;
- broad standards claim;
- multiple framework adapters before the first independent run.

---

## Issue — Add public engineering program and Claude Code guidance

### Objective

Add the public-safe engineering blueprint, visual roadmap, and execution constraints used during the 90-day program.

### Deliverables

- `CLAUDE.md`
- program plan
- validation sprint
- adoption and validation tracking
- Gantt chart
- dependency graph
- milestone map
- architecture roadmap
- Claude Code prompt library

### Acceptance criteria

- [ ] No production-code changes
- [ ] No benchmark semantic changes
- [ ] Public documentation is limited to technical scope, user value, validation criteria, and project outcomes
- [ ] Mermaid diagrams render correctly
- [ ] Documentation links resolve
- [ ] Changelog updated
- [ ] Full quality gate passes

---

## Issue — Complete LangGraph four-scenario runtime adapter

### Objective

Replace the design-stage skeleton with a real LangGraph integration that runs four deterministic consequential-action scenarios through the existing CAV-Bench evaluator.

### Scenarios

- [ ] stale state before commit
- [ ] ambiguous retry
- [ ] partial execution
- [ ] authority change

### Acceptance criteria

- [ ] benchmark environment remains sole commit truth
- [ ] LangGraph remains optional
- [ ] stable identifiers survive retries
- [ ] fine-grained nodes used
- [ ] tests assert evaluator-derived results
- [ ] no evaluator semantic changes
- [ ] full quality gate passes
- [ ] no endorsement claims

---

## Issue — Build outcome-pass versus commit-valid-fail demonstration

### Objective

Create a concise executable demonstration showing why final-outcome testing can miss invalid committed effects.

### Acceptance criteria

- [ ] conventional outcome reports pass
- [ ] CAV-Bench identifies the hidden failure
- [ ] evidence trace is benchmark-derived
- [ ] remediation is demonstrated
- [ ] before-and-after result is reproducible
- [ ] setup takes less than 15 minutes in the reference environment

---

## Issue — Create external reviewer and adopter kit

### Objective

Provide a minimal package that enables a qualified external reviewer to understand, run, and comment on the benchmark without reading the full codebase.

### Deliverables

- [ ] one-page problem statement
- [ ] five-minute walkthrough
- [ ] quick start
- [ ] four scenarios
- [ ] sample output
- [ ] five precise review questions
- [ ] claims and non-claims section

---

## Issue — Conduct Day-14 external-validation gate

### Objective

Evaluate external signals and make a green, yellow, or red program decision.

### Required inputs

- [ ] executable integration or demo
- [ ] three substantive reviewers
- [ ] one recognized technical/community participant
- [ ] one potential independent user
- [ ] documented objections and changes

### Output

A decision report covering demand, differentiation, onboarding friction, metric usefulness, next scope, and decision rationale.

---

## Issue — Design commerce-v1 consequential-action profile

### Objective

Define a testable commerce profile covering high-impact durable actions while preserving the framework-neutral core model.

### Candidate areas

- orders
- inventory
- pricing
- payments
- fulfillment
- cancellation
- refunds
- returns
- recovery

### Acceptance criteria

- [ ] 15–20 candidate scenarios
- [ ] private-oracle strategy for each
- [ ] CAV-dimension mapping
- [ ] safeguard mapping
- [ ] operational consequence
- [ ] initial implementation subset selected
- [ ] externally reviewed before implementation

---

## Issue — Add generic MCP or REST integration

### Objective

Provide a low-friction integration that allows an external tool server or service to be evaluated without embedding framework-specific logic into the core benchmark.

### Acceptance criteria

- [ ] optional dependency isolation
- [ ] stable normalized event mapping
- [ ] authoritative effect evidence
- [ ] reference server or service
- [ ] CI example
- [ ] quick start
- [ ] full quality gate passes

---

## Issue — Run first independent validation and document improvement

### Objective

Support an external team or project in running CAV-Bench, identifying a hidden failure, applying a control change, and retesting.

### Acceptance criteria

- [ ] independent runner identified
- [ ] benchmark version recorded
- [ ] baseline result preserved
- [ ] hidden failure documented
- [ ] remediation agreed or implemented
- [ ] retest result preserved
- [ ] publication permissions recorded
- [ ] case study drafted at allowed disclosure level
