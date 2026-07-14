"""Small shared helpers used across the runtime, evaluation, and scenario layers."""

from __future__ import annotations

from types import MappingProxyType
from typing import Any, Mapping


def freeze(value: Any) -> Any:
    """Recursively convert plain JSON containers into immutable equivalents."""
    if isinstance(value, Mapping):
        return MappingProxyType({k: freeze(v) for k, v in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(freeze(v) for v in value)
    return value


def thaw(value: Any) -> Any:
    """Recursively convert frozen containers back into plain dict/list for JSON output."""
    if isinstance(value, Mapping):
        return {k: thaw(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [thaw(v) for v in value]
    return value
