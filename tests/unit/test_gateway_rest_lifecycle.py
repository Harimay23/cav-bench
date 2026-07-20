"""`GatewayRestServer` lifecycle tests (M-GPI-1 review follow-up).

A prior test discovered that calling `stop()` before `start()` hung,
because `HTTPServer.shutdown()` blocks waiting for `serve_forever()` to
acknowledge a shutdown request that will never come if `serve_forever()`
was never running. Every test here bounds its own risky call with a
timeout via a daemon-thread helper, so a regression that reintroduces a
hang fails this test loudly instead of hanging the whole suite.
"""

from __future__ import annotations

import threading
from typing import Any, TypeVar

import pytest

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
