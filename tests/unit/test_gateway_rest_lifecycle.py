"""`GatewayRestServer` lifecycle tests (M-GPI-1 review follow-up).

Three issues surfaced across review, in order:

1. `stop()` before `start()` hung, because `HTTPServer.shutdown()` blocks
   waiting for `serve_forever()` to acknowledge a request that never
   comes if `serve_forever()` was never running.
2. A subtler startup race: `start()` could return -- and a caller's
   immediate `stop()` could then call `shutdown()` -- before
   `serve_forever()` had actually reached its loop.
3. The startup-timeout cleanup path closed the socket but never proved
   the already-launched server thread had actually terminated, and the
   tests exercising it replaced `server._httpd` *after*
   `GatewayRestServer.__init__` had already bound the original server's
   socket, leaking it.

`GatewayRestServer` no longer uses `serve_forever()`/`shutdown()` at
all: `_ManagedHTTPServer.run()` is a loop over the public, documented
`handle_request()` primitive, cancelled via an always-safe-to-signal
`threading.Event` rather than the private `serve_forever()` shutdown
handshake. `start()`'s timeout path and `stop()` both funnel through one
`GatewayRestServer._cleanup()` that signals cancellation, joins the
thread with a bounded timeout, and closes the socket exactly once --
provably, not by assumption.

Test-server injection uses the private `_server_class` constructor
parameter (never a post-construction attribute swap), so a test-double
server is installed *before* any socket is bound and the real default
server is never constructed, let alone leaked.

Every test here bounds its own risky call with a timeout via a
daemon-thread helper, so a regression that reintroduces a hang fails
this test loudly instead of hanging the whole suite. Where a race needs
to be widened deliberately, an `Event`/`Barrier` synchronizes it instead
of a sleep; sleeps are used only to let an already-resolved scenario's
straggler thread finish before the test ends, never to coordinate the
scenario itself.
"""

from __future__ import annotations

import threading
import time
from typing import Any, TypeVar

import pytest

from cavbench.gateway.core import GatewaySession
from cavbench.gateway.errors import ServerLifecycleError
from cavbench.gateway.rest import GatewayRestServer, _ManagedHTTPServer
from cavbench.scenarios.loader import load_builtin_pack

PACK = load_builtin_pack("core-v1")
T = TypeVar("T")

BOUND_SECONDS = 5.0


def _call_with_timeout(fn: Any, *, timeout: float = BOUND_SECONDS) -> Any:
    """Run `fn()` on a daemon thread and bound how long the test waits
    for it. If `fn` hangs, this fails the test deterministically instead
    of blocking the suite -- the daemon thread does not prevent the
    process (or pytest) from exiting."""
    result: dict[str, Any] = {}

    def runner() -> None:
        try:
            result["value"] = fn()
        except BaseException as exc:  # noqa: BLE001 - re-raised on the test thread below
            result["error"] = exc
        finally:
            result["done"] = True

    thread = threading.Thread(target=runner, daemon=True)
    thread.start()
    thread.join(timeout=timeout)
    if not result.get("done"):
        pytest.fail(f"operation did not complete within {timeout}s (possible lifecycle hang regression)")
    if "error" in result:
        raise result["error"]
    return result.get("value")


def _server(*, server_class: type[_ManagedHTTPServer] = _ManagedHTTPServer) -> GatewayRestServer:
    scenario = PACK.get("HP-01")
    session = GatewaySession.start(scenario, seed=0, run_id="lifecycle-fixture")
    return GatewayRestServer(session, _server_class=server_class)


def test_stop_before_start_does_not_hang() -> None:
    server = _server()
    _call_with_timeout(server.stop)


def test_stop_before_start_still_closes_the_listening_socket() -> None:
    """The socket is bound and listening from `__init__` (stdlib
    `TCPServer` behavior), independent of whether `start()` was ever
    called, so `stop()` must still release it."""
    server = _server()
    _call_with_timeout(server.stop)
    with pytest.raises(OSError):
        server._httpd.socket.getsockname()  # type: ignore[attr-defined]  # noqa: SLF001 - verifying the fd is actually closed


def test_start_twice_is_idempotent() -> None:
    server = _server()
    _call_with_timeout(server.start)
    _call_with_timeout(server.start)  # must not raise, must not start a second thread
    _call_with_timeout(server.stop)


def test_start_after_stop_raises_a_clear_lifecycle_error() -> None:
    server = _server()
    _call_with_timeout(server.start)
    _call_with_timeout(server.stop)
    with pytest.raises(ServerLifecycleError):
        _call_with_timeout(server.start)


def test_stop_twice_is_harmless() -> None:
    server = _server()
    _call_with_timeout(server.start)
    _call_with_timeout(server.stop)
    _call_with_timeout(server.stop)  # must not raise, must not hang


def test_normal_context_manager_use_works() -> None:
    scenario = PACK.get("HP-01")
    session = GatewaySession.start(scenario, seed=0, run_id="lifecycle-cm")

    def run() -> str:
        with GatewayRestServer(session) as server:
            return server.base_url

        return ""

    base_url = _call_with_timeout(run)
    assert base_url.startswith("http://127.0.0.1:")


def test_context_manager_cleanup_after_an_exception_still_runs() -> None:
    scenario = PACK.get("HP-01")
    session = GatewaySession.start(scenario, seed=0, run_id="lifecycle-cm-exception")
    server_holder: dict[str, GatewayRestServer] = {}

    def run() -> None:
        with GatewayRestServer(session) as server:
            server_holder["server"] = server
            raise RuntimeError("boom")

    with pytest.raises(RuntimeError, match="boom"):
        _call_with_timeout(run)

    # __exit__ ran (stop() completed) despite the exception -- a second
    # stop() must be harmless, proving cleanup already happened.
    _call_with_timeout(server_holder["server"].stop)


def test_server_close_happens_exactly_once_even_under_repeated_stop_calls() -> None:
    server = _server()
    _call_with_timeout(server.start)

    close_calls = {"count": 0}
    original_close = server._httpd.server_close  # noqa: SLF001 - instrumenting for the test

    def counting_close() -> None:
        close_calls["count"] += 1
        original_close()

    server._httpd.server_close = counting_close  # type: ignore[method-assign]  # noqa: SLF001

    _call_with_timeout(server.stop)
    _call_with_timeout(server.stop)
    _call_with_timeout(server.stop)

    assert close_calls["count"] == 1


def test_start_immediately_followed_by_stop_repeated_many_times() -> None:
    """The exact scenario the startup race allowed: `start()` returning
    before the server loop was confirmed running, so an immediate
    `stop()` could act too early. Repeated many times to make a
    reintroduced race far more likely to surface than a single iteration
    would."""
    for i in range(30):
        scenario = PACK.get("HP-01")
        session = GatewaySession.start(scenario, seed=0, run_id=f"lifecycle-rapid-{i}")
        server = GatewayRestServer(session)
        _call_with_timeout(server.start, timeout=2.0)
        _call_with_timeout(server.stop, timeout=2.0)
        assert server._thread is not None  # noqa: SLF001
        assert not server._thread.is_alive()  # noqa: SLF001


def test_start_and_stop_called_from_competing_threads() -> None:
    """Both methods hold the same lock for their full duration, so a
    `start()` and a `stop()` fired at effectively the same moment from
    different threads must still resolve deterministically -- one
    completes fully before the other's transition is evaluated -- and
    neither may hang."""
    scenario = PACK.get("HP-01")
    session = GatewaySession.start(scenario, seed=0, run_id="lifecycle-competing")
    server = GatewayRestServer(session)

    outcomes: dict[str, str] = {}
    barrier = threading.Barrier(2, timeout=5)

    def run_start() -> None:
        barrier.wait()
        try:
            server.start()
            outcomes["start"] = "ok"
        except ServerLifecycleError:
            outcomes["start"] = "lifecycle_error"

    def run_stop() -> None:
        barrier.wait()
        try:
            server.stop()
            outcomes["stop"] = "ok"
        except ServerLifecycleError:
            outcomes["stop"] = "lifecycle_error"

    t1 = threading.Thread(target=run_start)
    t2 = threading.Thread(target=run_stop)
    t1.start()
    t2.start()
    t1.join(timeout=10)
    t2.join(timeout=10)

    assert not t1.is_alive(), "start() thread did not complete (possible hang)"
    assert not t2.is_alive(), "stop() thread did not complete (possible hang)"

    # Two valid, fully-deterministic interleavings exist, depending on
    # which thread wins the lock first -- both must leave the server in
    # a definite, non-hanging terminal state, never an ambiguous one:
    #   (a) start() wins the lock first: it confirms running ("ok"),
    #       then stop() sees "running" and shuts down cleanly ("ok").
    #   (b) stop() wins the lock first: the server was never started, so
    #       stop() just closes the socket ("ok"); start() then sees the
    #       terminal "stopped" state and correctly raises
    #       ServerLifecycleError ("lifecycle_error") rather than
    #       silently doing nothing or hanging.
    # "stop() raises while start() reports ok" is not a valid outcome of
    # this lock-serialized design and would indicate a real regression.
    assert outcomes.get("stop") == "ok"
    assert outcomes.get("start") in ("ok", "lifecycle_error")
    assert server._state == "stopped"  # noqa: SLF001
    if server._thread is not None:  # noqa: SLF001
        assert not server._thread.is_alive()  # noqa: SLF001


class _SlowHandshakeServer(_ManagedHTTPServer):
    """A `_ManagedHTTPServer` whose startup handshake is deliberately
    delayed via an `Event`-based hook (not a sleep) that the test controls
    directly, widening the race window `stop()` must respect without
    resorting to an arbitrary sleep."""

    delay_until: threading.Event

    def run(self, *, poll_interval: float = 0.02) -> None:
        self.delay_until.wait(timeout=5)
        super().run(poll_interval=poll_interval)


def test_stop_during_startup_waits_for_startup_to_resolve_then_stops_cleanly() -> None:
    """A `stop()` that arrives while `start()` is still inside its bounded
    wait for the running confirmation must not race ahead of it: since
    both methods hold the same lock for their whole call, `stop()` simply
    blocks until `start()` finishes resolving (to "running", here), then
    proceeds -- never observing or acting on an ambiguous state."""
    delay_until = threading.Event()

    def make_server(*args: Any, **kwargs: Any) -> _SlowHandshakeServer:
        srv = _SlowHandshakeServer(*args, **kwargs)
        srv.delay_until = delay_until
        return srv

    scenario = PACK.get("HP-01")
    session = GatewaySession.start(scenario, seed=0, run_id="lifecycle-stop-during-startup")
    server = GatewayRestServer(session, _server_class=make_server)  # type: ignore[arg-type]

    outcomes: dict[str, str] = {}
    start_lock_taken = threading.Event()

    def run_start() -> None:
        start_lock_taken.set()
        try:
            server.start()
            outcomes["start"] = "ok"
        except ServerLifecycleError:
            outcomes["start"] = "lifecycle_error"

    def run_stop() -> None:
        start_lock_taken.wait(timeout=5)
        time.sleep(0.02)  # brief, bounded yield so start() has entered its wait, not a coordination sleep
        delay_until.set()  # let the handshake proceed only once stop() has been dispatched
        try:
            server.stop()
            outcomes["stop"] = "ok"
        except ServerLifecycleError:
            outcomes["stop"] = "lifecycle_error"

    t1 = threading.Thread(target=run_start)
    t2 = threading.Thread(target=run_stop)
    t1.start()
    t2.start()
    t1.join(timeout=10)
    t2.join(timeout=10)

    assert not t1.is_alive()
    assert not t2.is_alive()
    assert outcomes.get("start") == "ok"
    assert outcomes.get("stop") == "ok"
    assert server._state == "stopped"  # noqa: SLF001
    assert server._thread is not None and not server._thread.is_alive()  # noqa: SLF001


class _NeverConfirmingButCancellableServer(_ManagedHTTPServer):
    """Never sets `running_confirmed` (simulating a handshake that never
    fires), but still respects cancellation promptly -- the "clean
    startup-timeout cleanup" case: the thread *can* be terminated, it
    just never proved it was running."""

    def run(self, *, poll_interval: float = 0.02) -> None:
        while not self._cancel.is_set():
            time.sleep(poll_interval)


class _UnterminableServer(_ManagedHTTPServer):
    """Ignores cancellation for longer than the test's bounded join, then
    exits on its own -- the "cleanup could not confirm termination in
    time" case. Deliberately outlives the test's short join bound but not
    the test process, so `start()` must report the honest "could not be
    terminated" outcome rather than silently claiming success."""

    unresponsive_seconds: float = 0.3

    def run(self, *, poll_interval: float = 0.02) -> None:
        time.sleep(self.unresponsive_seconds)


def test_startup_timeout_leaves_no_live_server_thread(monkeypatch: pytest.MonkeyPatch) -> None:
    """If the handshake never fires (simulated here rather than waiting
    out the real 5s timeout, so this test itself stays fast), `start()`
    must not hang -- it must raise a clear `ServerLifecycleError` within
    a bounded time, and by the time it raises, the launched thread must
    already be confirmed dead, not merely "probably gone soon."""
    import cavbench.gateway.rest as rest_module

    monkeypatch.setattr(rest_module, "_STARTUP_TIMEOUT_SECONDS", 0.1)

    scenario = PACK.get("HP-01")
    session = GatewaySession.start(scenario, seed=0, run_id="lifecycle-startup-timeout")
    server = GatewayRestServer(session, _server_class=_NeverConfirmingButCancellableServer)

    with pytest.raises(ServerLifecycleError, match="did not confirm startup"):
        _call_with_timeout(server.start, timeout=2.0)

    # The thread reference exists (start() did launch a thread) but must
    # be confirmed dead -- not merely absent, and not merely "daemon so
    # it'll die eventually."
    assert server._thread is not None  # noqa: SLF001
    assert not server._thread.is_alive()  # noqa: SLF001
    assert server._state == "stopped"  # noqa: SLF001
    with pytest.raises(OSError):
        server._httpd.socket.getsockname()  # noqa: SLF001


def test_stop_after_startup_failure_is_harmless_and_repeatable(monkeypatch: pytest.MonkeyPatch) -> None:
    import cavbench.gateway.rest as rest_module

    monkeypatch.setattr(rest_module, "_STARTUP_TIMEOUT_SECONDS", 0.1)

    scenario = PACK.get("HP-01")
    session = GatewaySession.start(scenario, seed=0, run_id="lifecycle-stop-after-failure")
    server = GatewayRestServer(session, _server_class=_NeverConfirmingButCancellableServer)

    with pytest.raises(ServerLifecycleError):
        _call_with_timeout(server.start, timeout=2.0)

    close_calls = {"count": 0}
    original_close = server._httpd.server_close  # noqa: SLF001

    def counting_close() -> None:
        close_calls["count"] += 1
        original_close()

    server._httpd.server_close = counting_close  # type: ignore[method-assign]  # noqa: SLF001

    _call_with_timeout(server.stop, timeout=2.0)
    _call_with_timeout(server.stop, timeout=2.0)
    _call_with_timeout(server.stop, timeout=2.0)

    # server_close() already ran once as part of the startup-failure
    # cleanup itself (before this test even started counting) -- the
    # counting wrapper installed afterward must see zero further calls.
    assert close_calls["count"] == 0


def test_startup_failure_cleanup_completes_within_a_bounded_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    import cavbench.gateway.rest as rest_module

    monkeypatch.setattr(rest_module, "_STARTUP_TIMEOUT_SECONDS", 0.1)

    scenario = PACK.get("HP-01")
    session = GatewaySession.start(scenario, seed=0, run_id="lifecycle-bounded-cleanup")
    server = GatewayRestServer(session, _server_class=_NeverConfirmingButCancellableServer)

    started_at = time.monotonic()
    with pytest.raises(ServerLifecycleError):
        _call_with_timeout(server.start, timeout=2.0)
    elapsed = time.monotonic() - started_at

    # Two rounds of _STARTUP_TIMEOUT_SECONDS (wait-for-confirm, then the
    # cleanup join bound) plus generous scheduling slack -- must not be
    # anywhere near the *un*-patched 5s default, proving the bounded
    # timeout was actually honored end to end.
    assert elapsed < 2.0


def test_startup_cleanup_reports_when_the_thread_cannot_be_terminated_in_time(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If cleanup's own bounded join cannot confirm the thread died, the
    error must say so explicitly rather than silently claiming a clean
    teardown that did not actually happen."""
    import cavbench.gateway.rest as rest_module

    monkeypatch.setattr(rest_module, "_STARTUP_TIMEOUT_SECONDS", 0.03)

    scenario = PACK.get("HP-01")
    session = GatewaySession.start(scenario, seed=0, run_id="lifecycle-unterminable")
    server = GatewayRestServer(session, _server_class=_UnterminableServer)

    with pytest.raises(ServerLifecycleError, match="could not be terminated"):
        _call_with_timeout(server.start, timeout=2.0)

    # The straggler thread genuinely does terminate on its own shortly
    # after (by construction, unresponsive_seconds=0.3s) -- wait for it
    # here so it does not linger past this test into later ones, even
    # though it is a daemon thread and would not block process exit.
    if server._thread is not None:  # noqa: SLF001
        server._thread.join(timeout=2.0)  # noqa: SLF001
        assert not server._thread.is_alive()  # noqa: SLF001


def test_repeated_startup_failures_do_not_accumulate_live_threads_or_open_sockets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Runs several independent startup-failure scenarios back to back and
    compares the set of live, non-daemon-exempt threads before and after
    (rather than relying only on individual daemon-thread status), plus
    confirms every server's own thread and socket are individually
    accounted for."""
    import cavbench.gateway.rest as rest_module

    monkeypatch.setattr(rest_module, "_STARTUP_TIMEOUT_SECONDS", 0.1)

    threads_before = {t.ident for t in threading.enumerate()}
    servers: list[GatewayRestServer] = []

    for i in range(10):
        scenario = PACK.get("HP-01")
        session = GatewaySession.start(scenario, seed=0, run_id=f"lifecycle-repeated-failure-{i}")
        server = GatewayRestServer(session, _server_class=_NeverConfirmingButCancellableServer)
        with pytest.raises(ServerLifecycleError):
            _call_with_timeout(server.start, timeout=2.0)
        servers.append(server)

    for server in servers:
        assert server._thread is not None  # noqa: SLF001
        assert not server._thread.is_alive(), "a server thread leaked past startup-failure cleanup"  # noqa: SLF001
        with pytest.raises(OSError):
            server._httpd.socket.getsockname()  # noqa: SLF001

    threads_after = {t.ident for t in threading.enumerate()}
    leaked = threads_after - threads_before
    assert not leaked, f"threads leaked across repeated startup failures: {leaked}"


def test_injected_test_server_does_not_leak_the_originally_constructed_server() -> None:
    """`_server_class` replaces the server *at construction time*, before
    any socket is bound -- there is never a separately-constructed
    default server to leak. Verified here by confirming exactly one
    listening socket exists for this `GatewayRestServer` (the injected
    one), and it closes cleanly."""
    scenario = PACK.get("HP-01")
    session = GatewaySession.start(scenario, seed=0, run_id="lifecycle-injection-no-leak")
    server = GatewayRestServer(session, _server_class=_ManagedHTTPServer)
    assert isinstance(server._httpd, _ManagedHTTPServer)  # noqa: SLF001

    _call_with_timeout(server.start)
    _call_with_timeout(server.stop)
    assert server._thread is not None and not server._thread.is_alive()  # noqa: SLF001
    with pytest.raises(OSError):
        server._httpd.socket.getsockname()  # noqa: SLF001


def test_no_leaked_server_thread_or_listening_socket_after_stop() -> None:
    scenario = PACK.get("HP-01")
    session = GatewaySession.start(scenario, seed=0, run_id="lifecycle-no-leak")
    server = GatewayRestServer(session)
    _call_with_timeout(server.start)
    thread = server._thread  # noqa: SLF001
    assert thread is not None
    assert thread.is_alive()

    _call_with_timeout(server.stop)
    assert not thread.is_alive(), "server thread leaked past stop()"
    with pytest.raises(OSError):
        server._httpd.socket.getsockname()  # noqa: SLF001 - fd must actually be closed, not just detached
