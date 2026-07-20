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

## The request-to-attempt invariant

**Every accepted tool-operation request maps to exactly one `ToolFacade`
invocation. Final-report submission is an accepted non-tool request and
maps to zero `ToolFacade` invocations by design** — submitting a report
never touches `ToolFacade`; it only sets the input to a later
`finalize()` call. The gateway:

- performs no batching, caching, speculative execution, or replay;
- never retries a `ToolFacade` call on the candidate's behalf;
- never calls `status_check` except when the candidate explicitly requests
  reconciliation (`action: "status_check"`, mapped to the existing
  `ToolFacade.status_check` path);
- never repairs, regenerates, or invents `operation_id`, `idempotency_key`,
  or `correlation_id` — every identity field the candidate supplies passes
  through to `ToolFacade` unmodified.

A request that is not accepted creates zero `ToolFacade` invocations,
rejected inside `GatewaySession.handle()` **before** any `ToolFacade`
call and recorded only in the gateway session log, never in the benchmark
trace. Rejection reasons: a malformed envelope, an authentication
failure, an unknown action, or (see
[Capability enforcement](#capability-enforcement) below) a **capability
violation** — a `tool_name`, `namespace`, or action the current scenario
never advertised via `capabilities()`. See
`tests/contract/test_gateway_neutrality.py` and
`tests/contract/test_gateway_capability_enforcement.py` for the tests
enforcing this (request-to-attempt correspondence, malformed/auth/
capability-violation zero-attempt guarantees, no unrequested
reconciliation, no gateway-side retry).

## One canonical capability model

`cavbench.gateway.capabilities` is the single source of truth for what a
scenario makes visible — both `GatewaySession.capabilities()`
(advertisement) and `GatewaySession._check_capability()` (enforcement)
read from the same `derive_operations(view)` call, so the two can never
silently diverge (a real risk with the initial implementation, which kept
two separately-written, tool-name-keyed lookups).

`derive_operations` walks the adapter-visible `ScenarioView.plan` once
and produces a tuple of `OperationDescriptor`s, each a full
`(action, tool_name, namespace, resource_id)` tuple (`tool_name` is
`None` for `read`). **Deduplication is by the full tuple, never by
`tool_name` alone**: the same tool name can validly appear more than
once with distinct descriptors — under a different action, a different
namespace, or a different `resource_id` — and each combination is
advertised and enforced independently (see
`tests/unit/test_gateway_capabilities_model.py`). Write and compensate
descriptors are not claimed to be disjoint "by construction" — nothing
in the model prevents a future scenario pack from reusing a tool name
across both actions; what actually makes them non-interchangeable is
that enforcement matches on the full descriptor, not on `tool_name`
alone.

**Implicit read rule.** A prior review found that read *advertisement*
and read *enforcement* could diverge: `capabilities()` listed a `read`
descriptor only for explicit `read`-kind plan steps, while enforcement
separately allowed reading any resource touched by *any* resource-scoped
step. A request could be accepted with no equivalent line in
`/capabilities`. Fixed by making the implicit-read rule part of
derivation itself, not a second enforcement-only allowlist:
`derive_operations` synthesizes exactly one `read` descriptor for every
unique `(namespace, resource_id)` referenced by *any* resource-scoped
step (`read`, `write`, or `compensate`) — deduplicated by
`(action="read", namespace, resource_id)` — because a well-behaved
candidate reads a resource before writing or compensating it, exactly as
the reference candidate and every baseline profile do. These synthesized
descriptors are the *only* source of read visibility: `capabilities()`
advertises them and `_check_capability()` enforces against them,
identically, because both read from the same `derive_operations` result
(see `tests/contract/test_gateway_capability_consistency.py`, which
proves the two directions generically across several scenarios rather
than a single hand-picked case).

## Capability enforcement

Before any `ToolFacade` call, `GatewaySession._check_capability()`
verifies the requested operation exactly matches an `OperationDescriptor`
this scenario advertises:

- a `write` request's `(tool_name, namespace, resource_id)` must match an
  advertised `write` descriptor;
- a `compensate` request's `(tool_name, namespace, resource_id)` must
  match an advertised `compensate` descriptor — **write and compensate
  tools are never interchangeable**: a tool advertised only under
  `compensate` is rejected if sent as `write`, and vice versa, even when
  `namespace`/`resource_id` are otherwise correct;
- a `read` request's `(namespace, resource_id)` must match one of the
  synthesized `read` descriptors from `derive_operations` (see "Implicit
  read rule" above) — the identical set `capabilities()` advertised;
- a resource can be visible for one operation and not another: e.g. a
  resource targeted only by a `write` step is read-and-write-visible but
  not compensate-visible, and a request for the missing operation is
  rejected even though the resource is otherwise real (see
  `tests/contract/test_gateway_capability_enforcement.py::test_resource_visible_for_one_operation_but_not_another_is_enforced_per_operation`);
  an unadvertised or mismatched combination — including a real tool
  against the wrong `resource_id` — is a gateway-level
  `capability_violation` rejection — zero `ToolFacade` calls, exactly
  like a malformed envelope.

This is scenario-visible-capability enforcement, not an oracle check: it
never consults `ScenarioOracle` and never judges whether an operation
*should* succeed, only whether it is a shape the scenario advertises at
all.

## Capability discovery is logged (GPI-FR-009)

`GatewaySession.discover_capabilities()` — what `GET /capabilities`
actually calls — returns the same advertisement `capabilities()` always
returns for this session (computed once and cached, since the underlying
`ScenarioView` is immutable for the session's lifetime) and records that
exact advertisement in the session log on every call. Repeated discovery
is therefore deterministic by construction: every logged
`advertisement` is byte-identical, while each call still produces its
own log entry, so an auditor can see exactly how many times — and when —
a candidate asked. The logged entry carries the session ID, scenario ID,
envelope version, and the full operations list (actions, tool names,
namespaces, and resource IDs where applicable); it never carries the
session's run token (capability advertisements never include it) and
never carries oracle content (the advertisement is derived only from
`ScenarioView`) — see
`tests/contract/test_gateway_capability_discovery.py`.

### Immutability of the advertisement and the log

A prior review also found that `capabilities()`/`discover_capabilities()`
returned the *same* cached mutable `dict` on every call, and that
`SessionLogEntry.to_dict()` only shallow-copied its top level — a caller
mutating a nested container (e.g.
`entry.to_dict()["detail"]["advertisement"]["operations"][0]`) could
corrupt the stored entry, and mutating what one `discover_capabilities()`
call returned could corrupt every later call's response.

Fixed with a defensive deep-copy snapshot model:
`GatewaySession._canonical_advertisement()` builds and caches the
advertisement exactly once, privately — no caller ever receives that
object. `capabilities()` and `discover_capabilities()` each return
`copy.deepcopy(canonical)`, and `discover_capabilities()` separately
deep-copies again before handing a third independent copy to
`GatewaySessionLog.record_discovery()`. `SessionLogEntry.to_dict()` now
deep-copies `detail` on every call, so the object it returns shares no
mutable container with the entry it was built from. Net effect: mutating
anything returned by `capabilities()`, `discover_capabilities()`, or
`SessionLogEntry.to_dict()` can never reach the internal canonical model,
any other call's return value, or any already-recorded log entry — see
`tests/contract/test_gateway_capability_immutability.py`.

## Request serialization

Every REST request handler shares one mutable `GatewaySession` — its
`BenchmarkEnvironment`, `ToolFacade`, idempotency map, final-report state,
and session log. A prior review found `GatewayRestServer` used
`http.server.ThreadingHTTPServer`, which would let two requests mutate
that shared state concurrently: request order, commit order, trace
order, and session-log ordering would all become nondeterministic —
exactly the property this benchmark exists to measure, not to introduce
into its own measurement plumbing.

`GatewayRestServer` now uses plain `http.server.HTTPServer` (no
`ThreadingMixIn`): it accepts and fully handles one connection before
accepting the next, so two "simultaneous" client requests are, by
construction, processed strictly one at a time, never concurrently. This
is the simplest approved deterministic model — no remote mode, worker
pools, asynchronous execution, batching, or parallel commit semantics.
See `tests/contract/test_gateway_rest_concurrency.py`, which fires
several requests from separate client threads at once and proves, via an
instrumented wrapper around `GatewaySession.handle` (the single entry
point for every request kind, including reads, writes, compensation,
reconciliation, and the final report), that handling never overlaps;
that accepted concurrent requests still map one-to-one to `ToolFacade`
calls; that session-log sequence numbers stay unique and contiguous;
that ledger commits never race; that report submission cannot race a
consequential operation; and that two independent runs of the same
concurrent workload converge on the same final benchmark state (the
same `tool_facade_call_count`, ledger effect count, and log-entry
shapes), even though true TCP connection-arrival order across
independent client threads is not itself something the test suite
controls.

## Server lifecycle

`GatewayRestServer` lifecycle states: `created -> running -> stopped`.
A prior review found `stop()` before `start()` hung, because
`socketserver.TCPServer.__init__` (transitively, `HTTPServer.__init__`)
already binds and listens on the socket — so it exists even if
`serve_forever()` was never started — while `HTTPServer.shutdown()`
blocks waiting for a `serve_forever()` loop iteration that will never
happen if the loop was never running. `start()`/`stop()` are now
lifecycle-aware: `stop()` before `start()` only closes the listening
socket, never calls `shutdown()`, and returns immediately; `start()`
while already running is an idempotent no-op; `start()` after `stop()`
raises `cavbench.gateway.errors.ServerLifecycleError` (restarting a
stopped `HTTPServer` is not supported); `stop()` is idempotent and calls
`server_close()` exactly once regardless of how many times it is
called. Normal `with GatewayRestServer(session) as server:` use is
unaffected, including cleanup after an exception inside the block
(Python's context-manager protocol always runs `__exit__`). See
`tests/unit/test_gateway_rest_lifecycle.py`, which bounds every risky
call with a daemon-thread timeout helper so a regression that
reintroduces a hang fails the test loudly instead of hanging the suite.

## Components

| Component | Module | Responsibility |
|---|---|---|
| Envelope | `cavbench.gateway.envelope` | The common request/response envelope; schema validation. |
| Capability model | `cavbench.gateway.capabilities` | The canonical scenario-visible operation model (`derive_operations`), shared by advertisement and enforcement. |
| Gateway core | `cavbench.gateway.core` | Session binding, capability enforcement, the request-to-attempt mapping, response normalization, capability advertisement + logged discovery, finalize intake. |
| Bind validation | `cavbench.gateway.bind` | Rejects any non-loopback REST bind address before a socket opens. |
| Redaction | `cavbench.gateway.redaction` | Strips run tokens/secrets from anything recorded. |
| Session log | `cavbench.gateway.session_log` | Redacted, genuinely append-only record of every wire exchange (including gateway-level rejections). Internal storage is private; `record_request`/`record_rejection`/`record_discovery` are the only append paths; the public `entries` property and `to_list()` both return fresh defensive copies, so a caller can never clear, append to, reorder, or mutate the stored log (see `tests/unit/test_gateway_session_log.py`). |
| REST frontend | `cavbench.gateway.rest` | Standard-library `http.server` HTTP mapping of the envelope, loopback-only, deliberately single-threaded (see "Request serialization" below). |
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
  this milestone — see `DECISION_LOG.md` D-021.
- **No evaluator, runtime, or `core-v1` changes.** Nothing in
  `src/cavbench/evaluation/` or `src/cavbench/runtime/` changed; the
  scenario schema is unchanged; every canonical golden result is
  byte-identical before and after this milestone.
- **No production gateway.** This is measurement plumbing for benchmark
  sessions, not an API gateway, proxy, or monitoring system.
