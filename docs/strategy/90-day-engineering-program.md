# CAV-Bench 90-Day Technical Validation and Adoption Roadmap

**Program duration:** 13 weeks  
**Primary outcome:** Demonstrate that CAV-Bench can be independently reviewed, run, and used to identify consequential-action failures that ordinary outcome testing misses.

## Program principles

- Build for adoption rather than feature volume.
- Run development and external validation in parallel.
- Preserve the benchmark trust boundary.
- Use commerce as the first applied profile, not the project’s sole identity.
- Treat framework and protocol integrations as evaluation surfaces, not endorsements.
- Produce externally reproducible evidence at each milestone.

## Success conditions

By the end of the program, target:

1. One production-quality framework adapter.
2. One generic protocol or REST integration path.
3. One applied domain scenario pack.
4. Three or more substantive external reviewers.
5. At least one benchmark run conducted outside the core project team.
6. At least one weakness found that ordinary outcome testing did not expose.
7. At least one documented architecture, control, or testing-process improvement.
8. One public or permissioned before-and-after case study.
9. One recognized community work product, session, mapping, or external reference.
10. A versioned public release containing reproducible artifacts.

## Workstreams

### W1 — Program foundation

- Claude Code operating rules
- roadmap and diagrams
- issue hierarchy
- branch and PR conventions
- adoption and validation tracking

### W2 — Framework integration

- complete LangGraph runtime adapter
- support stale state, ambiguous retry, partial execution, and authority change
- preserve optional dependency isolation
- externally review event mapping

### W3 — Demonstration and reporting

- show outcome-pass/CAV-fail cases
- provide benchmark-derived evidence traces
- add actionable remediation guidance
- produce JSON, Markdown, and HTML outputs

### W4 — External validation

- framework reviewers
- protocol/tool developers
- researchers
- commerce and service architects
- security and assurance communities

### W5 — Commerce profile

- consequential-action taxonomy
- 15–20 high-value scenarios
- reference workflow
- adopter-readable risk and control mapping

### W6 — Generic integration

- MCP or REST adapter
- low-friction CI usage
- sample external tool server or service

### W7 — Applied validation and improvement

- external run
- finding analysis
- architecture recommendation
- retest after improvement
- case study

### W8 — Community and release

- technical report
- community session or work product
- reproducibility package
- release notes
- roadmap update

## Program gates

### Gate 1 — Day 14: demand validation

**Green**

- functioning four-scenario integration or executable demo;
- three substantive external reviewers;
- one potential user or independent runner;
- one recognized technical or community participant;
- clear evidence that the benchmark addresses a missing assurance gap.

**Yellow**

- problem is validated, but no external run commitment;
- simplify onboarding and narrow the profile.

**Red**

- no meaningful differentiation;
- integration burden is considered excessive;
- metrics are not actionable;
- no credible participant agrees to review or run it.

### Gate 2 — Week 5: usable adoption package

- installation path is documented and tested;
- report is understandable without reading evaluator internals;
- one outside party can reproduce a run;
- commerce profile scope is validated.

### Gate 3 — Week 9: demonstrated improvement

- benchmark identifies a hidden failure;
- corrective control is proposed or implemented;
- retest shows measurable improvement;
- evidence can be documented.

### Gate 4 — Week 13: public release

- artifacts are reproducible;
- external participation is accurately attributed;
- unsupported claims are excluded;
- roadmap reflects validated demand.

## Program constraints

- No broad rewrite of the evaluator.
- No new validity dimension during the initial program without a separate design review.
- No production transaction platform.
- No certification program.
- No foundation transfer.
- No multi-framework expansion before the first adapter and external run are complete.
