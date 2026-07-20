# Candidate integration guide (M-GPI-1)

How to write a REST client that gets evaluated by the CAV-Bench generic
protocol gateway, and how to run the bundled reference candidate locally.

## Installation

The REST frontend is standard-library-only, so no extra install is needed
beyond the core package:

```bash
pip install cav-bench
```

The `cav-bench[rest]` extra spelling is reserved and documented (see
[`architecture.md`](architecture.md)) for forward compatibility with a
future transport that does need a real dependency; installing it today
installs nothing beyond core.

## Running the local example

```bash
python examples/gateway_rest_demo.py --scenario ST-01 --mode guarded
python examples/gateway_rest_demo.py --scenario ST-01 --mode flawed
```

This starts a loopback-only gateway session for one `core-v1` scenario,
runs the deterministic reference candidate against it over real HTTP, and
prints the resulting commit-valid evaluation. It is the same code path
exercised by `tests/integration/test_gateway_hazards.py`.

## Writing your own candidate client

1. `GET /capabilities` to discover the scenario's operations (never
   contains oracle content — do not expect to learn what a "pass" looks
   like from it).
2. For each action you take, build a request envelope
   (see [`envelope.md`](envelope.md)) and `POST /operations`.
   - Generate a stable `operation_id` per logical operation and reuse it
     across your own retries of that operation. Generate a *fresh*
     `correlation_id` for every wire request, including retries.
   - The gateway never repairs your identity fields. If you retry with a
     fresh `idempotency_key`, you are choosing to risk a duplicate effect
     — that is exactly the class of hazard the benchmark measures.
3. Read `status` on the response:
   - `committed` / `rejected` / `failed` — act on it.
   - `ambiguous` — the effect may or may not have committed. Reconcile
     explicitly via `GET /operations/{operation_id}` before deciding
     whether to retry. The gateway will not do this for you.
4. When your task workflow is done, `POST /report` with your own
   completion assessment. This is recorded but never trusted — it cannot
   improve (or worsen) your evaluated outcome; see
   `tests/contract/test_gateway_forged_report.py`.

See [`rest-mapping.md`](rest-mapping.md) for the exact route/status-code
table, and `examples/reference_candidate/driver.py` for a complete,
if intentionally scripted, worked implementation.

## Troubleshooting

**"No module named `cavbench.gateway`"** — you're on a `cav-bench` build
predating M-GPI-1, or you're using `import cavbench` alone (the gateway is
never imported implicitly — `import cavbench.gateway` explicitly).

**A future transport's `MissingExtraError`** — some future gateway
frontend (e.g. MCP, out of scope for this milestone) may require an
optional dependency. The error message names the exact `pip install
'cav-bench[<extra>]'` command to run; see
`cavbench.gateway.optional.require_extra`. No such error is reachable via
the REST frontend today, since it has no optional dependency.

**Connection refused** — the gateway binds loopback (`127.0.0.1`) by
default; a candidate running outside the harness process's network
namespace (a container, a remote host) cannot reach it. This is
intentional (`docs/design/generic-protocol-integration.md`,
"Non-functional requirements") — loopback-only is what keeps a benchmark
run reproducible. A configured remote-candidate mode is out of scope for
this milestone.

## Limitations and non-claims

- **No MCP transport.** Only REST exists in this milestone.
- **No external technical review has occurred.** The envelope and REST
  mapping have not been reviewed by anyone outside this repository. Do not
  cite this integration as externally validated, adopted, certified, or
  production-ready — see `docs/program/approvals/M-GPI-1.md` ("Unresolved
  external prerequisites").
- **The reference candidate is a test fixture, not a client library.** It
  is deterministic and project-authored specifically to exercise the
  gateway in tests and CI; it is not offered as a starting point for a
  real integration's safeguards, and its guarded/flawed behavior is not a
  recommendation for how a real candidate should be built.
- **Remote-candidate mode is not implemented.** Loopback-only in this
  milestone; a real network deployment would be an explicitly labeled,
  non-reproducible configuration per the design, and does not exist yet.
- **This is not a production API gateway, proxy, or monitoring system.**
  It is measurement plumbing for benchmark sessions.
- **No protocol steward endorses or supports this integration.** Speaking
  a REST shape is not affiliation with any REST framework or standard.
