# REST frontend request/response mapping (M-GPI-1)

Module: [`cavbench.gateway.rest`](../../../src/cavbench/gateway/rest.py).
Standard-library `http.server` only — no new runtime dependency
(`DECISION_LOG.md` D-009, D-020). Binds to `127.0.0.1` by default
(loopback-only benchmark mode).

## Routes

| Route | Envelope action | Auth required | Notes |
|---|---|---|---|
| `GET /capabilities` | — (metadata only) | no | Capability/session discovery; never calls `ToolFacade`. |
| `POST /operations` | `read` \| `write` \| `compensate` \| `escalate` \| `clarify` \| `status_check` | yes | Body is the request envelope (JSON). `session_token` may be supplied in the body or via `Authorization: Bearer <token>` (the header wins if both are present in a way that matters — the header is applied as the default when the body omits it). |
| `GET /operations/{operation_id}` | `status_check` | yes | Candidate-invoked reconciliation, keyed by `operation_id`. Maps to the same `ToolFacade.status_check` path as an explicit `status_check` POST — this is not a separate code path. |
| `POST /report` | `report` | yes | Body is the candidate's untrusted final report; never calls `ToolFacade`. |

Authentication: `Authorization: Bearer <run_token>`, checked against the
per-session synthetic token issued at `GatewaySession.start()`. Missing or
wrong token -> a gateway-level rejection (400 or 401 depending on whether
the empty token also fails envelope-shape validation), zero `ToolFacade`
calls.

## Status code mapping

| Normalized status | HTTP status | Body |
|---|---|---|
| `committed` (or `ok` / `created` / `accepted` / non-error non-consequential statuses) | 200 | Response envelope. |
| `rejected` | 409 Conflict | Response envelope, `status: "rejected"`. |
| `failed` | 502 Bad Gateway | Response envelope, `status: "failed"`. |
| `ambiguous` | 504 Gateway Timeout | Response envelope, `status: "ambiguous"`. |
| gateway-level rejection: malformed envelope | 400 | `GatewayRejection` body. |
| gateway-level rejection: authentication failure | 401 (or 400 if the empty token also fails schema validation) | `GatewayRejection` body. |
| gateway-level rejection: unknown action / unknown route / unknown `operation_id` for reconciliation | 404 | `GatewayRejection` body. |

**Documented simplification:** the design's REST mapping proposes an
`ambiguous` status manifest as "a deterministic connection-reset/504-
equivalent." A literal TCP connection reset is nondeterministic and
unobservable deterministically inside an in-process test harness, so this
implementation surfaces `ambiguous` as an explicit, deterministic `504`
status code with a normal JSON body carrying `status: "ambiguous"` — never
a silent socket drop. A candidate client can distinguish "the gateway told
me this was ambiguous" from "the connection actually failed" by reading
the body, which is more testable and no less informative than a raw reset.

## Example exchange

```
POST /operations HTTP/1.1
Authorization: Bearer 8f3e9c...
Content-Type: application/json

{
  "envelope_version": "1.0",
  "operation_id": "cancel_order:O-2001",
  "idempotency_key": "ST-01:cancel_order:O-2001",
  "correlation_id": "corr-1",
  "actor_id": "principal_st_01",
  "action": "write",
  "resource": {"namespace": "order", "resource_id": "O-2001", "tool_name": "cancel_order"},
  "parameters": {"step_id": "write-1", "changes": {}},
  "expected_version": 10
}
```

```
HTTP/1.1 200 OK
Content-Type: application/json

{
  "envelope_version": "1.0",
  "correlation_id": "corr-1",
  "operation_id": "cancel_order:O-2001",
  "status": "committed",
  "data": {"status": "CANCELLED", "version": 11, "owner": "self"},
  "message": null
}
```

## Capability discovery response shape

```json
{
  "envelope_version": "1.0",
  "session_id": "sess-...",
  "scenario_id": "ST-01",
  "scenario_title": "Order ships between read and cancellation",
  "toolset": ["cancel_order"],
  "operations": [
    {"action": "read", "description": "..."},
    {"action": "status_check", "description": "..."},
    {"action": "escalate", "description": "..."},
    {"action": "clarify", "description": "..."},
    {"action": "report", "description": "..."},
    {"action": "write", "tool_name": "cancel_order", "namespace": "order", "description": "..."}
  ]
}
```

Derived only from the adapter-visible `ScenarioView` (the same view an
`ExecutionAdapter` sees) — never from the scenario oracle. See
`tests/contract/test_gateway_neutrality.py::test_capability_discovery_leaks_no_oracle_content`.
