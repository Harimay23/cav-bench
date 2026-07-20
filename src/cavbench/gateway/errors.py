"""Gateway-level error taxonomy.

These are *gateway-level rejections*: raised and handled before any
:class:`~cavbench.runtime.tools.ToolFacade` call is made, so raising one of
these guarantees zero benchmark attempts were created (design doc
GPI-FR-011). They are distinct from benchmark-level outcomes
(``committed`` / ``rejected`` / ``failed`` / ``ambiguous``), which are
always backed by a real :class:`~cavbench.runtime.tools.ToolResult`.
"""

from __future__ import annotations

from cavbench.errors import CavBenchError


class GatewayError(CavBenchError):
    """Base class for gateway-level (pre-ToolFacade) errors."""


class EnvelopeError(GatewayError):
    """The request envelope is malformed or fails schema validation."""


class AuthenticationError(GatewayError):
    """The request's session token is missing or does not match the session."""


class UnknownOperationError(GatewayError):
    """The requested action does not map to any known gateway operation."""


class UnknownSessionError(GatewayError):
    """The request does not correlate to any active gateway session."""


class MissingExtraError(GatewayError, ImportError):
    """An optional gateway dependency required for a feature is not installed.

    Raised at the point of use (invocation-time), never at package import
    time -- see :mod:`cavbench.gateway.optional`.
    """
