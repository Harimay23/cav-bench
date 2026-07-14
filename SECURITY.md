# Security Policy

## Scope

CAV-Bench is a local, deterministic, synthetic-data benchmark. It:

- uses no real customer, employer, or production data,
- requires no network access or credentials to run the core benchmark,
- is not a sandbox against a malicious execution adapter — an adapter runs
  as ordinary Python in your process, with the same trust level as any other
  code you choose to import and execute.

The main security-relevant property this project makes an explicit,
tested claim about is the **evaluator trust boundary**: no
adapter/agent/trace-supplied field can influence OSR, PAOSR, CVSR, dimension
status, or failure codes. See `docs/architecture.md` and
`tests/contract/test_evaluator_independence.py`.

## Reporting a vulnerability

If you find a way for an adapter to force a passing score without the
underlying trace/state/ledger facts actually supporting it, or any other
security-relevant issue (e.g. a scenario-pack loader path traversal, unsafe
deserialization), please report it privately rather than opening a public
issue:

- Open a [GitHub Security Advisory](../../security/advisories/new) on this
  repository, or
- Email the maintainer listed in `CITATION.cff`.

Please include:

- A description of the issue and its impact.
- Steps to reproduce (a minimal scenario/adapter pair is ideal, since the
  whole benchmark is deterministic and local).
- Whether you'd like credit in the fix's release notes.

We aim to acknowledge reports within a few business days.

## Supported versions

Only the latest released minor version receives security fixes.
