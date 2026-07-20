"""A minimal REST gateway client, standard-library only.

This is the reference candidate's transport layer: it is the *candidate
side* of the wire boundary, exactly the shape of code any third-party REST
client would write against the gateway's documented mapping
(``docs/program/gateway/rest-mapping.md``). It has no special access to the
gateway's internals -- it only ever sees whatever
:class:`cavbench.gateway.rest.GatewayRestServer` returns over HTTP.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class GatewayResponse:
    http_status: int
    body: dict[str, Any]

    @property
    def status(self) -> str | None:
        return self.body.get("status")


class RestGatewayClient:
    """Talks to a `cavbench.gateway.rest.GatewayRestServer` over HTTP."""

    def __init__(self, base_url: str, run_token: str, *, timeout: float = 5.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._run_token = run_token
        self._timeout = timeout

    def capabilities(self) -> dict[str, Any]:
        with urllib.request.urlopen(f"{self._base_url}/capabilities", timeout=self._timeout) as resp:
            return json.load(resp)  # type: ignore[no-any-return]

    def _request(self, method: str, path: str, body: dict[str, Any] | None) -> GatewayResponse:
        data = json.dumps(body).encode("utf-8") if body is not None else None
        req = urllib.request.Request(
            f"{self._base_url}{path}",
            data=data,
            method=method,
            headers={
                "Authorization": f"Bearer {self._run_token}",
                "Content-Type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                return GatewayResponse(http_status=resp.status, body=json.load(resp))
        except urllib.error.HTTPError as exc:
            payload = json.load(exc) if exc.length else {}
            return GatewayResponse(http_status=exc.code, body=payload)

    def submit(self, envelope: dict[str, Any]) -> GatewayResponse:
        return self._request("POST", "/operations", envelope)

    def reconcile(self, operation_id: str) -> GatewayResponse:
        return self._request("GET", f"/operations/{operation_id}", None)

    def report(self, report: dict[str, Any]) -> GatewayResponse:
        return self._request("POST", "/report", report)
