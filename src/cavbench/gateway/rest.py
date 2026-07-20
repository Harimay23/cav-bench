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


# How often the request loop below re-checks the cancellation flag when
# idle. Small enough that the startup handshake resolves near-instantly
# and cleanup notices cancellation quickly; irrelevant to request-handling
# latency, since a ready connection is always handled as soon as it is
# reported, regardless of this value.
_POLL_INTERVAL_SECONDS = 0.05
_STARTUP_TIMEOUT_SECONDS = 5.0
_SHUTDOWN_JOIN_TIMEOUT_SECONDS = 5.0


class _ManagedHTTPServer(HTTPServer):
    """An `HTTPServer` driven by an explicit, always-safe-to-signal
    cancellation event instead of `serve_forever()`'s private shutdown
    handshake.

    `run()` replaces `serve_forever()` with a loop built from the public,
    documented `handle_request()` primitive (one request, or a
    `self.timeout`-bounded no-op if none arrives) -- the same idiom the
    stdlib docs suggest for a cancellable server loop. `_cancel` can be
    `set()` at *any* time, including before `run()` has even started on
    its thread: the very first loop check will then exit immediately.
    This is what makes cleanup after a startup failure sound -- unlike
    `HTTPServer.shutdown()`, which blocks forever if called before
    `serve_forever()` has genuinely begun, signaling `_cancel` is never
    itself a blocking or racy operation.

    `running_confirmed` is set as the first statement inside `run()`,
    which -- because it necessarily executes on the server thread -- is
    authoritative proof the loop has actually started (not just that the
    thread was scheduled).
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.running_confirmed = threading.Event()
        self._cancel = threading.Event()

    def run(self, *, poll_interval: float = _POLL_INTERVAL_SECONDS) -> None:
        self.timeout = poll_interval
        self.running_confirmed.set()
        while not self._cancel.is_set():
            self.handle_request()

    def request_cancellation(self) -> None:
        """Always safe to call, from any thread, at any time -- including
        before `run()` has started, while it is running, or after it has
        already exited."""
        self._cancel.set()


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

    Built on `http.server.HTTPServer` (never `ThreadingHTTPServer`), via
    `_ManagedHTTPServer.run()` rather than `serve_forever()`: requests are
    handled one at a time, in full, before the next is accepted -- see
    module docstring for the exact concurrency contract. `socketserver.
    TCPServer.__init__` already binds and listens on the socket, so it
    exists (and must eventually be closed) even if `start()` is never
    called.

    Lifecycle states: `created -> running -> stopped`, protected by a
    single lock so `start()`/`stop()` calls from competing threads
    serialize deterministically rather than racing:

    - `start()` launches the server thread and **blocks until `run()` has
      confirmed it is actually running** (`_ManagedHTTPServer.
      running_confirmed`) or a bounded startup timeout elapses. On
      timeout, `start()` runs the same cleanup `stop()` would (signal
      cancellation, join the thread with a bounded timeout, close the
      socket exactly once) *before* raising `ServerLifecycleError` --
      it never leaves a launched thread unaccounted for. If the thread
      still has not terminated after that bounded join (only reachable
      under extreme scheduling starvation, since the loop's cancellation
      check is on the order of `poll_interval`), `start()` raises a
      distinct `ServerLifecycleError` stating startup failed *and* the
      server thread could not be terminated, rather than silently
      claiming clean teardown.
    - `stop()` before `start()` is idempotent and harmless: cancellation
      is signaled (a no-op if nothing is running), there is nothing to
      join, and the socket is closed exactly once.
    - `start()` while already running is an idempotent no-op; `start()`
      after `stop()` (including after a startup failure, which also
      transitions to the terminal `stopped` state) raises
      `ServerLifecycleError`.
    - `stop()` uses the same honest-termination contract as `start()`'s
      timeout path: if the bounded join cannot confirm the server thread
      has actually terminated, `stop()` raises `ServerLifecycleError`
      rather than silently reporting success while the thread is still
      alive. The socket is still closed exactly once regardless (guarded
      by an internal flag independent of `_state`, so repeated calls --
      including a retry after a termination-failure `stop()`, or after a
      startup-failure cleanup already ran -- never double-close). A
      `stop()` that raised this way can simply be called again: it
      re-signals cancellation (harmless if already signaled) and retries
      the join against the same thread; once that thread has actually
      exited, the retry succeeds harmlessly.
    - Because `start()` and `stop()` hold the same lock for their full
      duration (including any bounded wait), a `stop()` racing a
      `start()` simply waits for `start()` to finish resolving to a
      definite state first -- there is no window where `stop()` can
      observe or act on an ambiguous "maybe running" state.
    - One internal `_cleanup()` implements the signal-join-close sequence
      exactly once; `start()`'s timeout path, `stop()`, and (via `stop()`)
      context-manager exit all call it, so there is exactly one place
      that can leak a thread or a socket, and it is exercised by every
      lifecycle path's tests.
    """

    def __init__(
        self,
        session: GatewaySession,
        *,
        host: str = "127.0.0.1",
        port: int = 0,
        _server_class: type[_ManagedHTTPServer] = _ManagedHTTPServer,
    ) -> None:
        """`_server_class` is a private, test-only extension point (note
        the leading underscore -- never a supported production
        parameter): it lets tests install a `_ManagedHTTPServer` subclass
        *before* any socket is bound, so a test can observe or delay the
        startup handshake without ever constructing (and thus leaking) a
        separate, unused default server instance."""
        validate_loopback_host(host)
        self._session = session
        handler = make_handler(session)
        self._httpd = _server_class((host, port), handler)
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._state = "created"  # "created" | "running" | "stopped"
        self._closed = False

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
                target=self._httpd.run,
                kwargs={"poll_interval": _POLL_INTERVAL_SECONDS},
                daemon=True,
            )
            self._thread.start()

            confirmed = self._httpd.running_confirmed.wait(timeout=_STARTUP_TIMEOUT_SECONDS)
            if not confirmed:
                # The thread was launched but never proved it reached
                # run()'s loop. Tear it down completely before raising --
                # request_cancellation() is always safe to call regardless
                # of whether the thread has started, so this never risks
                # the hang a premature shutdown() call would.
                self._state = "stopped"
                terminated = self._cleanup(join_timeout=_STARTUP_TIMEOUT_SECONDS)
                if not terminated:
                    raise ServerLifecycleError(
                        f"GatewayRestServer startup failed (no confirmation within "
                        f"{_STARTUP_TIMEOUT_SECONDS}s) and the server thread could not be "
                        f"terminated within {_STARTUP_TIMEOUT_SECONDS}s"
                    )
                raise ServerLifecycleError(
                    f"GatewayRestServer did not confirm startup within {_STARTUP_TIMEOUT_SECONDS}s"
                )

            self._state = "running"

    def stop(self) -> None:
        """Request cancellation, join the server thread (bounded), and
        close the socket -- honestly. `_cleanup()`'s contract is that a
        `False` return means the thread's termination could not be
        confirmed within the bound, and callers must treat that as a real
        failure, not a successful shutdown. `stop()` now honors that
        contract instead of discarding the result: it raises
        `ServerLifecycleError` when termination cannot be confirmed,
        exactly as `start()`'s startup-timeout path already does.

        Always safe to call again after such a failure: `_state` is
        already `"stopped"` (a terminal state, so this call does not
        re-enter "running"), and re-invoking `_cleanup()` re-signals
        cancellation (harmless if already signaled) and retries the join
        against the *same* thread reference -- if it has since exited,
        this call succeeds harmlessly; the socket, already closed on the
        first attempt (`_cleanup()` closes it regardless of thread
        status), is never closed a second time (`_closed` guards that
        independently of how many times `stop()` itself is called)."""
        with self._lock:
            self._state = "stopped"
            terminated = self._cleanup(join_timeout=_SHUTDOWN_JOIN_TIMEOUT_SECONDS)
            if not terminated:
                raise ServerLifecycleError(
                    f"GatewayRestServer requested cancellation but the server thread did not "
                    f"terminate within {_SHUTDOWN_JOIN_TIMEOUT_SECONDS}s"
                )

    def _cleanup(self, *, join_timeout: float) -> bool:
        """Signal cancellation (always safe), join the server thread
        (bounded), and close the listening socket exactly once. Returns
        `True` if the thread is confirmed no longer alive (or was never
        started) -- `False` only if it is still alive after the bounded
        join, which callers must treat as a real failure to terminate,
        never silently ignore. Never relies on daemon-thread process exit
        for correctness: this method itself proves the thread is gone
        (or reports that it could not confirm that) before returning."""
        self._httpd.request_cancellation()
        thread_alive = False
        if self._thread is not None:
            self._thread.join(timeout=join_timeout)
            thread_alive = self._thread.is_alive()
        if not self._closed:
            self._closed = True
            self._httpd.server_close()
        return not thread_alive

    def __enter__(self) -> GatewayRestServer:
        self.start()
        return self

    def __exit__(self, *exc_info: object) -> None:
        # Always runs, including when the `with` body raised -- Python's
        # context-manager protocol guarantees __exit__ fires on exception,
        # so cleanup (thread join + socket close) happens either way.
        self.stop()


def serve(
    session: GatewaySession,
    *,
    host: str = "127.0.0.1",
    port: int = 0,
    _server_class: type[_ManagedHTTPServer] = _ManagedHTTPServer,
) -> Callable[[], None]:
    """Convenience helper: start a server, return a callable that stops
    it. The returned stopper *is* `GatewayRestServer.stop` -- it carries
    the same honest-termination contract (raises `ServerLifecycleError`
    if the server thread's termination cannot be confirmed within the
    bound) rather than a separate, potentially-inconsistent wrapper.
    `_server_class` is the same private, test-only injection point as
    `GatewayRestServer.__init__`'s."""
    server = GatewayRestServer(session, host=host, port=port, _server_class=_server_class)
    server.start()
    return server.stop
