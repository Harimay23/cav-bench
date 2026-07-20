"""`GatewayRestServer` lifecycle tests (M-GPI-1 review follow-up).

A prior test discovered that calling `stop()` before `start()` hung,
because `HTTPServer.shutdown()` blocks waiting for `serve_forever()` to
acknowledge a shutdown request that will never come if `serve_forever()`
was never running. A follow-up review found a second, subtler race:
`start()` could return -- and a caller's immediate `stop()` could then
call `shutdown()` -- before `serve_forever()` had actually reached its
loop, since nothing previously proved the thread had gotten there.
`start()` now blocks (bounded) until `_HandshakingHTTPServer` confirms
`serve_forever()` is genuinely running, and `start()`/`stop()` share one
lock for their full duration so competing calls serialize instead of
racing. Every test here bounds its own risky call with a timeout via a
daemon-thread helper, so a regression that reintroduces a hang fails
this test loudly instead of hanging the whole suite.
"""

from __future__ import annotations

import threading
import time
from typing import Any, TypeVar

import pytest

import cavbench.gateway.rest as rest_module
from cavbench.gateway.core import GatewaySession
from cavbench.gateway.errors import ServerLifecycleError
from cavbench.gateway.rest import GatewayRestServer
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


def _server() -> GatewayRestServer:
    scenario = PACK.get("HP-01")
    session = GatewaySession.start(scenario, seed=0, run_id="lifecycle-fixture")
    return GatewayRestServer(session)


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
    before `serve_forever()` was confirmed running, so an immediate
    `stop()` could call `shutdown()` too early. Repeated many times to
    make a reintroduced race far more likely to surface than a single
    iteration would."""
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


def test_stop_during_startup_waits_for_startup_to_resolve_then_stops_cleanly() -> None:
    """A `stop()` that arrives while `start()` is still inside its bounded
    wait for `running_confirmed` must not race ahead of it: since both
    methods hold the same lock for their whole call, `stop()` simply
    blocks until `start()` finishes resolving (to "running", here), then
    proceeds -- never observing or acting on an ambiguous state."""

    class _SlowHandshakeServer(rest_module._HandshakingHTTPServer):  # noqa: SLF001
        def service_actions(self) -> None:
            time.sleep(0.2)  # widen the race window `stop()` must respect
            super().service_actions()

    scenario = PACK.get("HP-01")
    session = GatewaySession.start(scenario, seed=0, run_id="lifecycle-stop-during-startup")
    server = GatewayRestServer(session)
    server._httpd = _SlowHandshakeServer((server._httpd.server_address[0], 0), rest_module.make_handler(session))  # noqa: SLF001

    outcomes: dict[str, str] = {}

    def run_start() -> None:
        try:
            server.start()
            outcomes["start"] = "ok"
        except ServerLifecycleError:
            outcomes["start"] = "lifecycle_error"

    def run_stop() -> None:
        time.sleep(0.02)  # ensure start() has already taken the lock and begun waiting
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


def test_startup_timeout_raises_a_clear_error_and_leaves_the_server_stopped(monkeypatch: pytest.MonkeyPatch) -> None:
    """If `running_confirmed` is never set (simulated here rather than
    waiting out the real 5s timeout, so this test itself stays fast),
    `start()` must not hang -- it must raise a clear
    `ServerLifecycleError` within a bounded time and leave the server in
    the terminal "stopped" state with its socket closed, never in an
    ambiguous in-between state."""
    monkeypatch.setattr(rest_module, "_STARTUP_TIMEOUT_SECONDS", 0.1)

    class _NeverConfirmingServer(rest_module._HandshakingHTTPServer):  # noqa: SLF001
        def service_actions(self) -> None:
            pass  # deliberately never sets running_confirmed

    scenario = PACK.get("HP-01")
    session = GatewaySession.start(scenario, seed=0, run_id="lifecycle-startup-timeout")
    server = GatewayRestServer(session)
    server._httpd = _NeverConfirmingServer((server._httpd.server_address[0], 0), rest_module.make_handler(session))  # noqa: SLF001

    with pytest.raises(ServerLifecycleError, match="did not confirm startup"):
        _call_with_timeout(server.start, timeout=2.0)

    assert server._state == "stopped"  # noqa: SLF001
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
