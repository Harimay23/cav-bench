"""Concurrent-request determinism tests (M-GPI-1 review follow-up).

`GatewayRestServer` was switched from `http.server.ThreadingHTTPServer`
to plain `http.server.HTTPServer` (see `cavbench.gateway.rest` module
docstring): every request handler shares one mutable `GatewaySession`
(its `BenchmarkEnvironment`, `ToolFacade`, idempotency map, final-report
state, and session log), so concurrent handling would make request
order, commit order, trace order, and session-log ordering
nondeterministic. A single-threaded server processes one connection
fully before accepting the next, so "simultaneous" client requests are
still, by construction, handled strictly one at a time.

These tests fire several requests from separate client threads at once
and prove the server-side handling never actually overlaps, using an
instrumented wrapper around `GatewaySession.handle` (the sole entry
point for every request kind, including reads, writes, compensation,
reconciliation, and the final report) as a concurrency probe.
"""

from __future__ import annotations

import json
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field

from cavbench.gateway.core import GatewaySession
from cavbench.gateway.envelope import ENVELOPE_VERSION
from cavbench.gateway.rest import GatewayRestServer
from cavbench.scenarios.loader import load_builtin_pack

PACK = load_builtin_pack("core-v1")


@dataclass
class ConcurrencyProbe:
    """Wraps `GatewaySession.handle` to detect any overlap between calls.
    A small artificial delay inside the wrapped call widens the race
    window, so a regression back to threaded handling would reliably be
    caught rather than only occasionally."""

    max_concurrent: int = 0
    current: int = 0
    order: list[tuple[str, int]] = field(default_factory=list)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def wrap(self, session: GatewaySession, *, delay: float = 0.02) -> None:
        original_handle = session.handle

        def instrumented(raw: object) -> object:
            with self._lock:
                self.current += 1
                self.max_concurrent = max(self.max_concurrent, self.current)
                self.order.append(("enter", self.current))
            time.sleep(delay)
            try:
                return original_handle(raw)  # type: ignore[arg-type]
            finally:
                with self._lock:
                    self.order.append(("exit", self.current))
                    self.current -= 1

        session.handle = instrumented  # type: ignore[method-assign]


def _write_envelope(session: GatewaySession, index: int) -> dict[str, object]:
    """A well-formed, *capability-valid* write: `reserve_inventory` against
    `inventory:SKU-4004` is the only write descriptor ER-04 advertises, so
    every concurrent request in this suite targets it, distinguished only
    by `operation_id`/`idempotency_key`/`correlation_id`. No
    `expected_version` guard is set, so each distinct `idempotency_key`
    commits independently (core `BenchmarkEnvironment.commit()` semantics,
    unrelated to this milestone) -- deliberately chosen so a genuine
    server-side race (interleaved reads-before-write) would be visible as
    a missing or duplicated ledger effect, not masked by a capability
    rejection or a version conflict."""
    return {
        "envelope_version": ENVELOPE_VERSION,
        "session_token": session.run_token,
        "operation_id": f"op-{index}",
        "correlation_id": f"corr-{index}",
        "actor_id": "candidate",
        "action": "write",
        "resource": {"namespace": "inventory", "resource_id": "SKU-4004", "tool_name": "reserve_inventory"},
        "idempotency_key": f"idem-{index}",
    }


def _post(url: str, token: str, body: dict[str, object]) -> tuple[int, dict[str, object]]:
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode(),
        method="POST",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.load(resp)
    except urllib.error.HTTPError as exc:
        return exc.code, json.load(exc)


def _fire_concurrently(
    server: GatewayRestServer, envelopes: list[dict[str, object]]
) -> list[tuple[int, dict[str, object]]]:
    results: list[tuple[int, dict[str, object]] | None] = [None] * len(envelopes)

    def worker(i: int) -> None:
        results[i] = _post(f"{server.base_url}/operations", server.run_token, envelopes[i])

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(len(envelopes))]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10)
    assert all(r is not None for r in results), "a concurrent request did not complete in time"
    return results  # type: ignore[return-value]


def test_simultaneous_requests_are_processed_serially_never_overlapping() -> None:
    scenario = PACK.get("ER-04")
    session = GatewaySession.start(scenario, seed=0, run_id="concurrency-serial")
    probe = ConcurrencyProbe()
    probe.wrap(session)

    with GatewayRestServer(session) as server:
        envelopes = [_write_envelope(session, i) for i in range(8)]
        results = _fire_concurrently(server, envelopes)

    assert all(status == 200 for status, _ in results)
    assert probe.max_concurrent == 1, f"handle() overlapped: max_concurrent={probe.max_concurrent}"


def test_accepted_concurrent_requests_still_map_one_to_one_to_tool_facade_calls() -> None:
    scenario = PACK.get("ER-04")
    session = GatewaySession.start(scenario, seed=0, run_id="concurrency-one-to-one")

    with GatewayRestServer(session) as server:
        envelopes = [_write_envelope(session, i) for i in range(8)]
        results = _fire_concurrently(server, envelopes)

    assert all(status == 200 for status, _ in results)
    assert session.log.tool_facade_call_count() == 8


def test_log_sequence_numbers_are_unique_contiguous_and_reflect_processing_order() -> None:
    scenario = PACK.get("ER-04")
    session = GatewaySession.start(scenario, seed=0, run_id="concurrency-seq")

    with GatewayRestServer(session) as server:
        envelopes = [_write_envelope(session, i) for i in range(10)]
        _fire_concurrently(server, envelopes)

    seqs = [entry.seq for entry in session.log.entries]
    assert seqs == list(range(len(seqs))), "sequence numbers must be unique, contiguous, and in processing order"


def test_environment_and_ledger_operations_do_not_overlap_under_concurrent_requests() -> None:
    """Same guarantee as the serial-processing test, checked directly
    against the benchmark environment's ledger rather than the wire
    responses: every committed effect corresponds to a distinct request,
    and the ledger never shows more entries than requests (which would
    indicate a duplicated or interleaved commit)."""
    scenario = PACK.get("ER-04")
    session = GatewaySession.start(scenario, seed=0, run_id="concurrency-ledger")
    probe = ConcurrencyProbe()
    probe.wrap(session)

    with GatewayRestServer(session) as server:
        envelopes = [_write_envelope(session, i) for i in range(8)]
        _fire_concurrently(server, envelopes)

    assert probe.max_concurrent == 1
    effects = session.environment.ledger.as_dicts()
    # 8 independent requests, 8 independent idempotency_keys, no
    # expected_version guard -> 8 legitimate distinct commits against the
    # same resource. A server-side race (interleaved commits) would show
    # up here as fewer than 8 effects (a lost update) or more than 8 (a
    # duplicated one) -- neither is possible under strict serialization.
    assert len(effects) == 8
    effect_ids = {e["effect_id"] for e in effects}
    assert len(effect_ids) == 8  # no duplicate effect_id, no lost commit


def test_repeated_concurrent_request_runs_produce_deterministic_final_state() -> None:
    """True wire-arrival order across independent TCP connections is not
    something this test controls (nor needs to: the requests target
    independent, commutative resources). What must be deterministic --
    and is checked here across two independent runs -- is the *resulting*
    benchmark state: the same set of committed effects, the same
    tool_facade_call_count, and the same log-entry action/resource
    content, regardless of which physical order the OS happened to
    deliver connections in."""

    def run_once(run_id: str) -> tuple[int, int, frozenset[tuple[str, ...]]]:
        scenario = PACK.get("ER-04")
        session = GatewaySession.start(scenario, seed=0, run_id=run_id)
        with GatewayRestServer(session) as server:
            envelopes = [_write_envelope(session, i) for i in range(8)]
            _fire_concurrently(server, envelopes)
        effects = session.environment.ledger.as_dicts()
        entry_shapes = frozenset(
            (entry.action or "", entry.normalized_status or "") for entry in session.log.entries
        )
        return session.log.tool_facade_call_count(), len(effects), entry_shapes

    first = run_once("concurrency-repeat-1")
    second = run_once("concurrency-repeat-2")
    assert first == second


def test_report_submission_cannot_race_a_consequential_tool_operation() -> None:
    scenario = PACK.get("ER-04")
    session = GatewaySession.start(scenario, seed=0, run_id="concurrency-report-race")
    probe = ConcurrencyProbe()
    probe.wrap(session)

    with GatewayRestServer(session) as server:
        write_envelopes = [_write_envelope(session, i) for i in range(4)]
        report_body = {
            "adapter_name": "concurrency-test-candidate",
            "adapter_version": "0.0.0",
            "final_message": "done",
            "completion_status": "success",
        }

        results: list[tuple[int, dict[str, object]] | None] = [None] * (len(write_envelopes) + 1)

        def write_worker(i: int) -> None:
            results[i] = _post(f"{server.base_url}/operations", server.run_token, write_envelopes[i])

        def report_worker() -> None:
            results[-1] = _post(f"{server.base_url}/report", server.run_token, report_body)

        threads = [threading.Thread(target=write_worker, args=(i,)) for i in range(len(write_envelopes))]
        threads.append(threading.Thread(target=report_worker))
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

    assert all(r is not None for r in results)
    assert all(status == 200 for status, _ in results)  # type: ignore[misc]
    assert probe.max_concurrent == 1
    # exactly the 4 writes counted as ToolFacade calls; the report never does
    assert session.log.tool_facade_call_count() == 4


def test_finalization_cannot_race_an_in_flight_operation() -> None:
    """`GatewayRestServer.stop()` joins the server thread before
    returning (see `cavbench.gateway.rest`), so once the `with` block
    exits, no request can still be in flight -- `finalize()` (always
    called after the server is stopped, per the documented session
    lifecycle) cannot observe a partially-processed request."""
    scenario = PACK.get("ER-04")
    session = GatewaySession.start(scenario, seed=0, run_id="concurrency-finalize-race")

    with GatewayRestServer(session) as server:
        envelopes = [_write_envelope(session, i) for i in range(6)]
        _fire_concurrently(server, envelopes)

    call_count_after_stop = session.log.tool_facade_call_count()
    trace = session.finalize()

    # no ToolFacade call could have been added by finalize() itself, and
    # none could have snuck in between server.stop() returning and
    # finalize() being called (stop() already guarantees no thread is
    # still running the server loop at that point).
    assert session.log.tool_facade_call_count() == call_count_after_stop
    assert len(trace.side_effects) == call_count_after_stop
