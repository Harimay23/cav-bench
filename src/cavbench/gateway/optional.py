"""Invocation-time optional-dependency guard for gateway extras.

The M-GPI-1 REST frontend is deliberately standard-library-only
(``http.server`` / ``json`` / ``urllib``) -- see
``docs/design/generic-protocol-integration.md`` open question 4 and
`DECISION_LOG.md` D-009 (minimal core dependencies). It therefore needs no
runtime package beyond what `cav-bench` already requires, and there is
nothing genuinely optional to guard *today*.

This module exists anyway, as the same reusable pattern used by
``cavbench doctor --check-reporting`` for the ``reporting`` extra
(``pandas``/``matplotlib``), so that a future transport frontend with a
real dependency (e.g. an MCP frontend needing an MCP client library) has a
single, tested place to raise a clear, invocation-time error instead of
each frontend inventing its own. Nothing in :mod:`cavbench.gateway` calls
this for the REST frontend, because REST has no such dependency.
"""

from __future__ import annotations

import importlib

from cavbench.gateway.errors import MissingExtraError


def require_extra(module_name: str, *, extra_name: str, feature: str) -> object:
    """Import ``module_name`` or raise a clear, actionable error.

    Called at the point a feature is actually used, never at package
    import time, so importing :mod:`cavbench.gateway` (or `cavbench`
    itself) never fails because an extra is missing.
    """
    try:
        return importlib.import_module(module_name)
    except ImportError as exc:
        raise MissingExtraError(
            f"{feature} requires the optional {module_name!r} dependency. "
            f"Install it with: pip install 'cav-bench[{extra_name}]'"
        ) from exc
