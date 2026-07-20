"""The REST transport frontend (M-GPI-1 first transport, GPI-FR delivery
phase 2).

Standard-library only (``http.server``): no new runtime dependency, per
`DECISION_LOG.md` D-009 and the design's open question 4 default. Binds to
loopback only by default (``127.0.0.1``), matching the design's
loopback-only reproducible benchmark mode.

Routes:

- ``GET  /capabilities``            -- capability/session discovery
- ``POST /operations``              -- one consequential/read/escalate/
                                        clarify request (envelope body)
- ``GET  /operations/{operation_id}`` -- explicit, candidate-invoked status
                                        reconciliation
- ``POST /report``                  -- untrusted final report submission

All routes require ``Authorization: Bearer <run_token>`` except discovery,
which is unauthenticated read-only metadata (no ToolFacade call, no oracle
content).
"""

from __future__ import annotations

import json
import threading
from collections.abc import Callable
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from cavbench.gateway.core import GatewaySession
from cavbench.gateway.envelope import ENVELOPE_VERSION

_HTTP_HINT_TO_STATUS = {
    "ok": HTTPStatus.OK,
    "conflict": HTTPStatus.CONFLICT,
    "failed": HTTPStatus.BAD_GATEWAY,
    # A literal TCP reset is nondeterministic and untestable in-process;
    # this gateway surfaces "ambiguous" as a distinguished, deterministic
    # status code + body instead (documented simplification -- see
    # docs/program/gateway/rest-mapping.md).
    "ambiguous": HTTPStatus.GATEWAY_TIMEOUT,
    "bad_request": HTTPStatus.BAD_REQUEST,
    "unauthorized": HTTPStatus.UNAUTHORIZED,
    "not_found": HTTPStatus.NOT_FOUND,
}


def _write_json(handler: BaseHTTPRequestHandler, status: HTTPStatus, payload: dict[str, Any]) -> None:
    body = json.dumps(payload, sort_keys=True).encode("utf-8")
    handler.send_response(int(status))
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def _bearer_token(handler: BaseHTTPRequestHandler) -> str | None:
    header = handler.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        return None
    return header[len("Bearer ") :]


def make_handler(session: GatewaySession) -> type[BaseHTTPRequestHandler]:
    class GatewayRequestHandler(BaseHTTPRequestHandler):
        server_version = "cavbench-gateway/0.1 (M-GPI-1 reference implementation)"

        def log_message(self, fmt: str, *args: Any) -> None:  # noqa: A003 - stdlib hook name
            return  # silence default stderr access log; callers use the session log instead

        def do_GET(self) -> None:  # noqa: N802 - stdlib hook name
            if self.path == "/capabilities":
                _write_json(self, HTTPStatus.OK, session.capabilities())
                return
            if self.path.startswith("/operations/"):
                operation_id = self.path[len("/operations/") :]
                token = _bearer_token(self)
                envelope = {
                    "envelope_version": ENVELOPE_VERSION,
                    "session_token": token or "",
                    "operation_id": operation_id,
                    "correlation_id": f"reconcile:{operation_id}",
                    "actor_id": "candidate",
                    "action": "status_check",
                    "resource": {"namespace": "operation", "resource_id": operation_id},
                }
                self._handle_envelope(envelope)
                return
            _write_json(self, HTTPStatus.NOT_FOUND, {"detail": f"no such route {self.path!r}"})

        def do_POST(self) -> None:  # noqa: N802 - stdlib hook name
            length = int(self.headers.get("Content-Length", "0"))
            raw_body = self.rfile.read(length) if length else b"{}"
            try:
                payload = json.loads(raw_body.decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError) as exc:
                _write_json(self, HTTPStatus.BAD_REQUEST, {"detail": f"invalid JSON body: {exc}"})
                return

            if self.path == "/operations":
                token = _bearer_token(self)
                payload.setdefault("session_token", token if token is not None else "")
                self._handle_envelope(payload)
                return
            if self.path == "/report":
                token = _bearer_token(self)
                envelope = {
                    "envelope_version": ENVELOPE_VERSION,
                    "session_token": token or "",
                    "operation_id": payload.get("operation_id", "final-report"),
                    "correlation_id": payload.get("correlation_id", "final-report"),
                    "actor_id": payload.get("actor_id", "candidate"),
                    "action": "report",
                    "resource": {"namespace": "session", "resource_id": session.session_id},
                    "parameters": payload,
                }
                self._handle_envelope(envelope)
                return
            _write_json(self, HTTPStatus.NOT_FOUND, {"detail": f"no such route {self.path!r}"})

        def _handle_envelope(self, envelope: dict[str, Any]) -> None:
            outcome = session.handle(envelope)
            status = _HTTP_HINT_TO_STATUS[outcome.http_hint]
            if outcome.accepted:
                assert outcome.response is not None
                _write_json(self, status, outcome.response.to_dict())
            else:
                assert outcome.rejection is not None
                _write_json(self, status, outcome.rejection.to_dict())

    return GatewayRequestHandler


class GatewayRestServer:
    """A loopback-only REST server fronting exactly one `GatewaySession`."""

    def __init__(self, session: GatewaySession, *, host: str = "127.0.0.1", port: int = 0) -> None:
        self._session = session
        handler = make_handler(session)
        self._httpd = ThreadingHTTPServer((host, port), handler)
        self._thread: threading.Thread | None = None

    @property
    def base_url(self) -> str:
        host, port = self._httpd.server_address[0], self._httpd.server_address[1]
        host_str = host.decode("ascii") if isinstance(host, bytes) else str(host)
        return f"http://{host_str}:{port}"

    @property
    def run_token(self) -> str:
        return self._session.run_token

    def start(self) -> None:
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._httpd.shutdown()
        self._httpd.server_close()
        if self._thread is not None:
            self._thread.join(timeout=5)

    def __enter__(self) -> GatewayRestServer:
        self.start()
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.stop()


def serve(
    session: GatewaySession, *, host: str = "127.0.0.1", port: int = 0
) -> Callable[[], None]:
    """Convenience helper: start a server, return a callable that stops it."""
    server = GatewayRestServer(session, host=host, port=port)
    server.start()
    return server.stop
