"""The generic protocol gateway (M-GPI-1): a benchmark-owned protocol
gateway mediating between a candidate protocol client and the existing
`ToolFacade` / `BenchmarkEnvironment` commit path.

This subpackage is **not** imported by `cavbench/__init__.py` or
`cavbench.api` -- importing plain `cavbench` never imports
`cavbench.gateway` (GPI-FR-013, extras isolation). Import
`cavbench.gateway` explicitly to use it.

See ``docs/design/generic-protocol-integration.md``,
``docs/program/gateway/architecture.md``, and
``docs/program/gateway/envelope.md``.
"""

from __future__ import annotations

from cavbench.gateway.core import GatewayOutcome, GatewaySession
from cavbench.gateway.envelope import RequestEnvelope, ResponseEnvelope

__all__ = [
    "GatewayOutcome",
    "GatewaySession",
    "RequestEnvelope",
    "ResponseEnvelope",
]
