"""Redaction of secrets and run tokens from anything recorded by the gateway.

GPI-FR-012: tokens and any candidate-supplied secrets appearing in payloads
must be redacted from all recorded artifacts (the session log). This module
is the single place that decides what "redacted" means; the session log
never records a raw envelope.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

REDACTED = "[REDACTED]"

# Keys that are always redacted wherever they appear in a payload, matched
# case-insensitively against the trailing path segment.
_SENSITIVE_KEY_MARKERS = ("token", "secret", "password", "credential", "authorization", "api_key")

# Envelope fields that are never recorded verbatim, regardless of key name.
_ALWAYS_REDACT_FIELDS = ("session_token",)


def _is_sensitive_key(key: str) -> bool:
    lowered = key.lower()
    return any(marker in lowered for marker in _SENSITIVE_KEY_MARKERS)


def redact(value: Any, *, _top_level: bool = True) -> Any:
    """Recursively redact sensitive keys/values from a JSON-like structure."""
    if isinstance(value, Mapping):
        result: dict[str, Any] = {}
        for key, inner in value.items():
            if key in _ALWAYS_REDACT_FIELDS or _is_sensitive_key(str(key)):
                result[key] = REDACTED
            else:
                result[key] = redact(inner, _top_level=False)
        return result
    if isinstance(value, (list, tuple)):
        return [redact(item, _top_level=False) for item in value]
    return value


def redact_error_message(message: str, *secrets: str) -> str:
    """Strip any known secret value out of a free-text error message."""
    redacted = message
    for secret in secrets:
        if secret:
            redacted = redacted.replace(secret, REDACTED)
    return redacted
