"""The REST transport frontend (M-GPI-1 first transport, GPI-FR delivery
phase 2).

Standard-library only (``http.server``): no new runtime dependency, per
`DECISION_LOG.md` D-009 and the design's open question 4 default. Binds to
loopback only by default (``127.0.0.1``), matching the design's
loopback-only reproducible benchmark mode.

**Deliberately single-threaded.** Every request handler shares one
mutable ``GatewaySession`` (its ``BenchmarkEnvironment``, ``ToolFacade``,
idempotency map, final-report state, and session log). Concurrent
handling would let two requests mutate that shared state at once, making
commit order, trace order, and session-log ordering nondeterministic --
a determinism violation this benchmark exists to prevent, not commit.
``GatewayRestServer`` therefore uses the plain ``http.server.HTTPServer``
(no ``ThreadingMixIn``), which accepts and fully handles one connection
at a time before accepting the next.

**The concurrency contract, precisely:**

- Requests are processed sequentially and never overlap -- two
  "simultaneous" client requests are, by construction, always handled
  one after the other, never concurrently (this is what makes the
  shared-session mutation safe).
- Processing order is whatever order the OS/kernel and
  ``http.server.HTTPServer`` actually accept the underlying TCP
  connections in. This gateway does not read ahead, queue, sort, batch,
  or reorder requests to impose any particular order -- there is no
  ordering guarantee stronger than "whatever `HTTPServer` accepted
  first, this gateway processed first."
- A **deterministic, reproducible** candidate trace requires the
  candidate itself to send one request at a time and wait for each
  response before sending the next (exactly how the reference candidate,
  and every baseline profile, already behave). A candidate that fires
  genuinely concurrent requests is not claiming -- and this gateway does
  not provide -- a reproducible cross-run ordering for those requests;
  only the absence of overlap and corruption is guaranteed in that case.
- No queue ordering, batching, sorting, or parallel execution is
  introduced anywhere in this frontend. Remote mode and worker pools
  remain explicitly out of scope for this milestone.

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
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any

from cavbench.gateway.bind import validate_loopback_host
from cavbench.gateway.core import GatewaySession
from cavbench.gateway.envelope import ENVELOPE_VERSION
from cavbench.gateway.errors import ServerLifecycleError

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
                _write_json(self, HTTPStatus.OK, session.discover_capabilities())
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


# How often serve_forever()'s internal select() loop re-checks the
# shutdown flag when idle. Small enough that the startup handshake below
# resolves near-instantly; irrelevant to request-handling latency, since
# a ready connection is always handled as soon as select() reports it,
# regardless of this value.
_POLL_INTERVAL_SECONDS = 0.05
_STARTUP_TIMEOUT_SECONDS = 5.0
_SHUTDOWN_JOIN_TIMEOUT_SECONDS = 5.0


class _HandshakingHTTPServer(HTTPServer):
    """An `HTTPServer` that signals when `serve_forever()` has genuinely
    entered its request loop.

    `service_actions()` is a documented `socketserver.BaseServer`
    extension point, called once per `serve_forever()` loop iteration --
    always *after* that iteration's `select()` call returns, so its first
    invocation is authoritative proof the loop is actually running (not
    just that the thread was scheduled). This is what closes the
    startup race: without it, `start()` could return -- and a
    same-caller `stop()` could then call `shutdown()` -- before
    `serve_forever()` had reached the point where `shutdown()` is safe to
    call at all (see `GatewayRestServer` docstring).
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.running_confirmed = threading.Event()

    def service_actions(self) -> None:
        self.running_confirmed.set()


class GatewayRestServer:
    """A loopback-only, single-threaded REST server fronting exactly one
    `GatewaySession`.

    The `host` is validated by `cavbench.gateway.bind.validate_loopback_host`
    before any socket is opened: only addresses that resolve entirely to
    loopback interfaces are accepted (e.g. `127.0.0.1`, `::1`,
    `localhost`). `0.0.0.0`, `::`, LAN/public addresses, and hostnames that
    resolve to any non-loopback address are rejected with
    `NonLoopbackBindError`. Remote-candidate (non-loopback) mode is out of
    scope for this milestone.

    Uses `http.server.HTTPServer` (never `ThreadingHTTPServer`): requests
    are handled one at a time, in full, before the next is accepted -- see
    module docstring for the exact concurrency contract. `socketserver.
    TCPServer.__init__` already binds and listens on the socket, so it
    exists (and must eventually be closed) even if `start()` is never
    called.

    Lifecycle states: `created -> running -> stopped`, protected by a
    single lock so `start()`/`stop()` calls from competing threads
    serialize deterministically rather than racing:

    - `start()` launches the server thread and **blocks until
      `serve_forever()` has confirmed it is actually running** (via
      `_HandshakingHTTPServer`'s `service_actions()` handshake) or a
      bounded startup timeout elapses, in which case it tears the server
      down and raises `ServerLifecycleError`. `start()` never returns
      while the server's running-state is still ambiguous -- this is
      what closes the startup race: `HTTPServer.shutdown()` blocks
      forever if called before `serve_forever()` has genuinely begun
      (the original hang bug), so `stop()` must never be allowed to see
      "running" until that is actually true.
    - `stop()` before `start()` (or during a state where `start()` never
      confirmed running) only closes the listening socket -- no
      `shutdown()` call, no hang.
    - `start()` while already running is an idempotent no-op; `start()`
      after `stop()` raises `ServerLifecycleError` (restarting a stopped
      `HTTPServer` is not supported).
    - `stop()` is idempotent and calls `server_close()` exactly once.
    - Because both methods hold the same lock for their full duration
      (including any bounded wait), a `stop()` racing a `start()` simply
      waits for `start()` to finish resolving to a definite state first
      -- there is no window where `stop()` can observe or act on an
      ambiguous "maybe running" state.
    """

    def __init__(self, session: GatewaySession, *, host: str = "127.0.0.1", port: int = 0) -> None:
        validate_loopback_host(host)
        self._session = session
        handler = make_handler(session)
        self._httpd = _HandshakingHTTPServer((host, port), handler)
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._state = "created"  # "created" | "running" | "stopped"

    @property
    def base_url(self) -> str:
        host, port = self._httpd.server_address[0], self._httpd.server_address[1]
        host_str = host.decode("ascii") if isinstance(host, bytes) else str(host)
        return f"http://{host_str}:{port}"

    @property
    def run_token(self) -> str:
        return self._session.run_token

    def start(self) -> None:
        with self._lock:
            if self._state == "stopped":
                raise ServerLifecycleError("cannot start a GatewayRestServer that has already been stopped")
            if self._state == "running":
                return  # idempotent: already running

            self._thread = threading.Thread(
                target=self._httpd.serve_forever,
                kwargs={"poll_interval": _POLL_INTERVAL_SECONDS},
                daemon=True,
            )
            self._thread.start()

            confirmed = self._httpd.running_confirmed.wait(timeout=_STARTUP_TIMEOUT_SECONDS)
            if not confirmed:
                # The thread was launched but never proved it reached
                # serve_forever()'s loop -- do not leave the server in an
                # ambiguous state. There is nothing safe to join here
                # (shutdown() is exactly the call that could hang), so
                # the only deterministic recovery is closing the socket
                # and surfacing a clear error.
                self._state = "stopped"
                self._httpd.server_close()
                raise ServerLifecycleError(
                    f"GatewayRestServer did not confirm startup within {_STARTUP_TIMEOUT_SECONDS}s"
                )

            self._state = "running"

    def stop(self) -> None:
        with self._lock:
            if self._state == "stopped":
                return  # idempotent
            was_running = self._state == "running"
            self._state = "stopped"
            if was_running:
                # Safe precisely because `start()` never returns (and
                # therefore never lets `_state` become "running") until
                # `running_confirmed` is set.
                self._httpd.shutdown()
                if self._thread is not None:
                    self._thread.join(timeout=_SHUTDOWN_JOIN_TIMEOUT_SECONDS)
            self._httpd.server_close()

    def __enter__(self) -> GatewayRestServer:
        self.start()
        return self

    def __exit__(self, *exc_info: object) -> None:
        # Always runs, including when the `with` body raised -- Python's
        # context-manager protocol guarantees __exit__ fires on exception,
        # so cleanup (thread join + socket close) happens either way.
        self.stop()


def serve(
    session: GatewaySession, *, host: str = "127.0.0.1", port: int = 0
) -> Callable[[], None]:
    """Convenience helper: start a server, return a callable that stops it."""
    server = GatewayRestServer(session, host=host, port=port)
    server.start()
    return server.stop
