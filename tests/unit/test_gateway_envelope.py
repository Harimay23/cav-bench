"""Envelope validation, normalization, identity pass-through, and redaction
unit tests (M-GPI-1)."""

from __future__ import annotations

import pytest

from cavbench.gateway.envelope import ENVELOPE_VERSION, RequestEnvelope
from cavbench.gateway.errors import EnvelopeError
from cavbench.gateway.redaction import redact

VALID_ENVELOPE = {
    "envelope_version": ENVELOPE_VERSION,
    "session_token": "tok-abc123",
    "operation_id": "op-1",
    "correlation_id": "corr-1",
    "actor_id": "candidate-1",
    "action": "read",
    "resource": {"namespace": "order", "resource_id": "O-1"},
}


def test_valid_envelope_parses() -> None:
    envelope = RequestEnvelope.from_dict(VALID_ENVELOPE)
    assert envelope.operation_id == "op-1"
    assert envelope.correlation_id == "corr-1"
    assert envelope.idempotency_key is None


@pytest.mark.parametrize(
    "missing_field",
    ["envelope_version", "session_token", "operation_id", "correlation_id", "actor_id", "action", "resource"],
)
def test_missing_required_field_raises_envelope_error(missing_field: str) -> None:
    data = dict(VALID_ENVELOPE)
    del data[missing_field]
    with pytest.raises(EnvelopeError):
        RequestEnvelope.from_dict(data)


def test_unknown_top_level_field_rejected() -> None:
    data = dict(VALID_ENVELOPE, unexpected_field="nope")
    with pytest.raises(EnvelopeError):
        RequestEnvelope.from_dict(data)


def test_wrong_envelope_version_rejected() -> None:
    data = dict(VALID_ENVELOPE, envelope_version="99.0")
    with pytest.raises(EnvelopeError):
        RequestEnvelope.from_dict(data)


def test_non_mapping_body_rejected() -> None:
    with pytest.raises(EnvelopeError):
        RequestEnvelope.from_dict([1, 2, 3])  # type: ignore[arg-type]


def test_identity_fields_pass_through_unchanged() -> None:
    data = dict(
        VALID_ENVELOPE,
        operation_id="op-retry-7",
        idempotency_key="idem-retry-7",
        correlation_id="corr-attempt-3",
    )
    envelope = RequestEnvelope.from_dict(data)
    assert envelope.operation_id == "op-retry-7"
    assert envelope.idempotency_key == "idem-retry-7"
    assert envelope.correlation_id == "corr-attempt-3"
    # round-trips unmodified
    assert envelope.to_dict()["operation_id"] == "op-retry-7"
    assert envelope.to_dict()["idempotency_key"] == "idem-retry-7"
    assert envelope.to_dict()["correlation_id"] == "corr-attempt-3"


# -- redaction -------------------------------------------------------------


def test_redact_strips_session_token() -> None:
    payload = {"session_token": "super-secret-token", "operation_id": "op-1"}
    redacted = redact(payload)
    assert redacted["session_token"] == "[REDACTED]"
    assert redacted["operation_id"] == "op-1"


@pytest.mark.parametrize("key", ["secret", "api_key", "password", "auth_token", "credential_id", "Authorization"])
def test_redact_strips_keys_matching_sensitive_markers(key: str) -> None:
    payload = {key: "value-that-must-not-survive"}
    redacted = redact(payload)
    assert redacted[key] == "[REDACTED]"


def test_redact_is_recursive_through_nested_structures() -> None:
    payload = {"request": {"parameters": {"nested": {"password": "hunter2"}}}}
    redacted = redact(payload)
    assert redacted["request"]["parameters"]["nested"]["password"] == "[REDACTED]"


def test_redact_leaves_non_sensitive_values_untouched() -> None:
    payload = {"operation_id": "op-1", "amount": 42, "nested": {"resource_id": "O-1"}}
    assert redact(payload) == payload
