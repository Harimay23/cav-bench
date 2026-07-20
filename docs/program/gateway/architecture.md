# Generic protocol gateway — architecture (M-GPI-1)

Status: Implemented (milestone `M-GPI-1`; see
[`../approvals/M-GPI-1.md`](../approvals/M-GPI-1.md) and
[`../../design/generic-protocol-integration.md`](../../design/generic-protocol-integration.md)
for the approved design this implements).

> External technical review of this document and the REST mapping has
> **not** occurred. Do not cite the gateway as externally validated,
> adopted, or production-ready — see
> [Limitations and non-claims](candidate-integration.md#limitations-and-non-claims).

## What this is

A benchmark-owned protocol gateway that lets a REST-speaking candidate
agent or service be evaluated by CAV-Bench without writing a Python
`ExecutionAdapter`. The candidate is the protocol *client*; the gateway is
the protocol *server*, run by the harness for the duration of one benchmark
session.

```text
Candidate agent/service (protocol client, untrusted)
  -> benchmark-owned protocol gateway (REST frontend + shared core)
    -> ToolFacade (existing, unchanged)
      -> BenchmarkEnvironment + SideEffectLedger (sole effect executor,
         sole commit authority)
    -> authoritative ToolResult (already fault-shaped by the environment's
       deterministic hooks)
  -> gateway response to the candidate
```

## Commit-truth boundary

`BenchmarkEnvironment.commit()` remains the **only** place a side effect is
created, exactly as for every other integration (the LangGraph adapter, the
five baseline profiles). The gateway holds no commit path of its own:

- `cavbench.gateway.core.GatewaySession` wraps one `BenchmarkEnvironment`
  and one `ToolFacade` per benchmark session.
- Every gateway operation that reaches `ToolFacade` does so synchronously,
  inside `GatewaySession.handle()`, while serving exactly one candidate
  request.
- Nothing in `cavbench.gateway` ever imports or touches
  `BenchmarkEnvironment` internals, the raw state store, or the ledger
  directly — only through `ToolFacade`, same as an `ExecutionAdapter`.
- The candidate's final report (`report` action) is carried into
  `BenchmarkEnvironment.finalize()` exactly as `AdapterResult` metadata is
  today: untrusted comparison input, never commit truth. See
  `tests/contract/test_gateway_forged_report.py`.

## The one-request-to-one-attempt invariant

A well-formed, authenticated candidate request maps to **exactly one**
`ToolFacade` invocation (or, for the `report` action, zero — submitting a
report never touches `ToolFacade`; it only sets the input to a later
`finalize()` call). The gateway:

- performs no batching, caching, speculative execution, or replay;
- never retries a `ToolFacade` call on the candidate's behalf;
- never calls `status_check` except when the candidate explicitly requests
  reconciliation (`action: "status_check"`, mapped to the existing
  `ToolFacade.status_check` path);
- never repairs, regenerates, or invents `operation_id`, `idempotency_key`,
  or `correlation_id` — every identity field the candidate supplies passes
  through to `ToolFacade` unmodified.

A malformed or unauthenticated request is rejected inside
`GatewaySession.handle()` **before** any `ToolFacade` call, so it creates
zero benchmark attempts; it is recorded only in the gateway session log,
never in the benchmark trace. See
`tests/contract/test_gateway_neutrality.py` for the tests enforcing this
(1:1 mapping, malformed/auth-failure zero-attempt guarantees, no
unrequested reconciliation, no gateway-side retry).

## Components

| Component | Module | Responsibility |
|---|---|---|
| Envelope | `cavbench.gateway.envelope` | The common request/response envelope; schema validation. |
| Gateway core | `cavbench.gateway.core` | Session binding, the 1:1 mapping, response normalization, capability advertisement, finalize intake. |
| Redaction | `cavbench.gateway.redaction` | Strips run tokens/secrets from anything recorded. |
| Session log | `cavbench.gateway.session_log` | Redacted, append-only record of every wire exchange (including gateway-level rejections). |
| REST frontend | `cavbench.gateway.rest` | Standard-library `http.server` HTTP mapping of the envelope, loopback-only. |
| Reference candidate | `examples.reference_candidate` | Deterministic scripted test-subject client — a fixture, never part of the gateway. |

None of the above is imported by `cavbench/__init__.py` or `cavbench.api`
— importing plain `cavbench` never imports `cavbench.gateway`
(`GPI-FR-013`; see `tests/unit/test_gateway_extras_isolation.py`).

## Normalized outcome statuses

`GPI-FR-004`: every consequential (`write`/`compensate`) `ToolResult` is
normalized to one of four statuses, and only these four:

| `ToolResult.status` | Normalized | Meaning |
|---|---|---|
| `COMMITTED` | `committed` | The effect landed in the ledger. |
| `AMBIGUOUS` | `ambiguous` | Committed, but the environment's own fault hooks made the *response* indeterminate. The gateway never invents or resolves this — it only relays what `BenchmarkEnvironment.commit()` returned. |
| `FAILED` | `failed` | The environment forced this step to fail (a scenario fault). |
| `CONFLICT` / `IDEMPOTENT_REPLAY` | `rejected` | No new effect; either a stale `expected_version` or a duplicate `idempotency_key`. |

Non-consequential actions (`read`, `status_check`, `escalate`, `clarify`,
`report`) use a small separate status vocabulary (`ok` / `not_found` /
`created` / `clarification_requested` / `accepted`) documented in
[`rest-mapping.md`](rest-mapping.md), since they are not commit outcomes
and the four-way ambiguity vocabulary does not apply to them.

## Trust boundaries

- Everything received over the wire (envelope fields, payload values, the
  final report) is untrusted subject output — instruction-like content in
  a payload is data, never an instruction to the gateway.
- Reconciliation, compensation, and escalation are only ever *exposed* by
  the gateway; whether and when the candidate calls them is candidate
  behavior, recorded as evaluator evidence via the normal trace, exactly
  as for a native adapter.
- Session tokens are synthetic, per-session, and never real credentials
  (`GPI-FR-012`). They and any candidate-supplied secret-shaped value are
  redacted from the session log — see
  `tests/unit/test_gateway_envelope.py`'s redaction tests.
- The gateway binds to loopback (`127.0.0.1`) by default. A remote
  candidate connecting over a network is an explicitly non-benchmark-mode
  configuration outside what this milestone claims as reproducible.

## What is out of scope for M-GPI-1

- **No MCP transport.** The extension boundary (`cavbench.gateway.core`
  is transport-neutral) is preserved, but no MCP frontend code exists in
  this milestone — see `DECISION_LOG.md` D-020.
- **No evaluator, runtime, or `core-v1` changes.** Nothing in
  `src/cavbench/evaluation/` or `src/cavbench/runtime/` changed; the
  scenario schema is unchanged; every canonical golden result is
  byte-identical before and after this milestone.
- **No production gateway.** This is measurement plumbing for benchmark
  sessions, not an API gateway, proxy, or monitoring system.
