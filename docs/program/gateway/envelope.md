# Common protocol envelope reference (M-GPI-1)

Schema: [`src/cavbench/gateway/schemas/envelope.schema.json`](../../../src/cavbench/gateway/schemas/envelope.schema.json)
(JSON Schema draft-07). Python types:
[`cavbench.gateway.envelope.RequestEnvelope`](../../../src/cavbench/gateway/envelope.py) /
`ResponseEnvelope` / `GatewayRejection`.

Every transport frontend (today: REST) translates its wire format into
this envelope before calling `cavbench.gateway.core.GatewaySession.handle`,
and translates the response back out. The envelope itself has no
transport-specific fields.

## Request envelope

| Field | Type | Required | Meaning |
|---|---|---|---|
| `envelope_version` | string | yes | Must equal `"1.0"` (the only version this gateway serves). |
| `session_token` | string | yes | The harness-issued synthetic run token for this session. Never a real credential. |
| `operation_id` | string | yes | Candidate-supplied, stable across retries of the *same logical operation*. A retry reuses it; a new logical operation gets a fresh one. Passed through to `ToolFacade` unmodified — the gateway never generates, repairs, or regenerates it. |
| `idempotency_key` | string \| null | no | Candidate-supplied dedup key, scoped to (operation, resource). Passed through unmodified. |
| `correlation_id` | string | yes | Unique per wire request (many-to-one with `operation_id` under retry). Echoed back unchanged on the response. |
| `actor_id` | string | yes | The principal on whose behalf the action runs. |
| `action` | string | yes | One of `read`, `write`, `compensate`, `status_check`, `escalate`, `clarify`, `report`. |
| `resource` | object | yes | `{"namespace": str, "resource_id": str, "tool_name": str (write/compensate only)}`. |
| `parameters` | object | no | Action-specific payload — see below. |
| `expected_version` | integer \| null | no | Optional state guard the candidate conditions a write on. |

`additionalProperties: false` at both the top level and inside `resource`
(except the documented `tool_name` field): an unrecognized field is a
schema-validation failure, i.e. a gateway-level rejection with zero
`ToolFacade` calls.

### `parameters` by action

| Action | `parameters` fields |
|---|---|
| `write` | `step_id` (optional, defaults to `operation_id`), `changes` (object), `args` (object) |
| `compensate` | as `write`, plus `compensation_for` (the `operation_id`/effect the compensation targets) |
| `escalate` | `reason` (string) |
| `clarify` | `question` (string) |
| `report` | the candidate's untrusted final report: `adapter_name`, `adapter_version`, `final_message`, `completion_status`, and any additional metadata — carried into `finalize()` exactly as `AdapterResult` metadata is today |
| `read`, `status_check` | none |

## Response envelope

| Field | Meaning |
|---|---|
| `envelope_version` | Always `"1.0"`. |
| `correlation_id` | Echoed back unchanged from the request. |
| `operation_id` | Echoed back unchanged from the request. |
| `status` | See [`architecture.md`](architecture.md#normalized-outcome-statuses). |
| `data` | The (possibly `null`) result payload from the authoritative `ToolResult`. |
| `message` | Optional human-readable detail. |

## Gateway-level rejections

A malformed envelope, an unknown `action`, or a failed `session_token`
check produces a `GatewayRejection`, never a `ResponseEnvelope`:

```json
{"envelope_version": "1.0", "correlation_id": "...", "reason": "malformed_envelope", "detail": "..."}
```

`reason` is one of `malformed_envelope`, `authentication_failed`,
`unknown_operation`, `unknown_operation_id` (reconciliation for an
`operation_id` the gateway never saw a write for). None of these ever
correspond to a `ToolFacade` call.

## Compatibility policy

`envelope_version` is the only compatibility signal today: additive fields
are a minor version; a semantic change is a major version and needs a
documented migration note here. This milestone serves exactly one version
(`"1.0"`); a request declaring any other version is rejected.
