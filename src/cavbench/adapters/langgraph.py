"""LangGraph execution adapter.

Runs a compiled LangGraph graph against a CAV-Bench ``AdapterSession`` and
maps its terminal state to an (untrusted) ``AdapterResult``. See
``docs/langgraph-adapter-mapping.md`` for the full mapping: normalized event
vocabulary, the four `framework-v1` scenario flows, stable identifier
derivation, and synchronous checkpoint durability.

Adapter-visible trust boundary (unchanged from every other adapter -- see
``cavbench.adapters.protocol`` and ``docs/architecture.md``):
``AdapterSession.tools`` is the adapter's only execution path into the
benchmark environment. Authoritative attempt and commit truth is owned by
``BenchmarkEnvironment`` and recorded in the canonical trace and
side-effect ledger -- the tool facade itself records nothing; it delegates
and relays results. LangGraph runtime state -- checkpoints, node outputs,
retry counts -- remains untrusted ordering, retry, and resume context only:
it may only ever be used by this adapter to decide *how* to call the tool
facade (e.g. deriving a stable idempotency key from checkpointed
thread/node identity), never as evidence that an effect validly committed.
``DeterministicEvaluator`` never sees it: everything this adapter returns
lands in the trace's untrusted ``adapter_report``.

LangGraph is an optional dependency: importing this module, and importing
``cavbench`` generally, never requires LangGraph to be installed. This
module never imports ``langgraph`` at module scope -- only lazily, from
inside ``run()``. Install it with ``pip install "cav-bench[langgraph]"``.
"""

from __future__ import annotations

import importlib
from collections.abc import Callable, Mapping
from typing import Any

from cavbench.adapters.protocol import COMPLETION_STATUSES, AdapterResult
from cavbench.runtime.session import AdapterSession
from cavbench.scenarios.models import ScenarioView

_ISSUE_URL = "https://github.com/Harimay23/cav-bench/issues/5"
_MAPPING_DOC = "docs/langgraph-adapter-mapping.md"

# A graph provider receives the adapter-visible scenario view and a
# checkpointer, and returns a compiled LangGraph graph ready to be invoked.
GraphProvider = Callable[..., Any]


def _ensure_langgraph_installed() -> None:
    """Lazily imports ``langgraph`` to verify it is installed.

    Called only from inside ``run()``, never at module import time -- this
    is what keeps LangGraph an optional dependency of CAV-Bench. Raises a
    clear, specific invocation-time error rather than letting a bare
    ``ModuleNotFoundError`` surface with no context.

    Only a ``ModuleNotFoundError`` for ``langgraph`` itself is treated as
    "not installed" -- a ``ModuleNotFoundError`` raised from *inside*
    langgraph (e.g. one of its own missing dependencies) is a different
    failure mode and must propagate unchanged rather than being misreported
    as "langgraph is not installed".
    """
    try:
        importlib.import_module("langgraph")
    except ModuleNotFoundError as exc:
        if exc.name != "langgraph":
            raise
        raise ImportError(
            "LangGraphAdapter requires the optional 'langgraph' package, which "
            "is not installed and is not a core CAV-Bench dependency. Install "
            "it with: pip install \"cav-bench[langgraph]\". "
            f"See {_MAPPING_DOC}."
        ) from exc


def _langgraph_version() -> str:
    """Diagnostic-only version string for ``AdapterResult.metadata``.

    ``langgraph`` does not set a stable module-level ``__version__``
    attribute (confirmed against the declared floor, 0.6.0), so this reads
    installed package metadata instead. Never trusted for scoring -- like
    everything else in ``metadata``, it only ever lands in the trace's
    untrusted ``adapter_report``.
    """
    import importlib.metadata

    try:
        return importlib.metadata.version("langgraph")
    except importlib.metadata.PackageNotFoundError:
        return "unknown"


class LangGraphAdapter:
    """Implements the ``ExecutionAdapter`` protocol over a LangGraph graph.

    By default it runs the deterministic reference fixture graph for the
    `framework-v1` scenarios (``cavbench.adapters.langgraph_reference`` --
    a test fixture, not a production agent design). The bundled reference
    fixture routes every consequential benchmark effect through
    ``session.tools``, and is adversarially tested for it
    (``tests/langgraph/test_trust_boundary.py``).

    Pass ``graph_provider`` to run a different graph. A custom provider is
    expected to follow the same ``ExecutionAdapter`` contract, but CAV-Bench
    does not sandbox arbitrary Python code and cannot prevent a custom
    graph from producing out-of-band effects. Only effects recorded through
    the benchmark environment can be evaluated as benchmark evidence --
    scoring independence (the evaluator never trusts graph state or
    self-reported completion) holds regardless of which graph runs, but
    that is a property of what the evaluator trusts, not an enforcement
    mechanism against what a custom graph can do.
    """

    name: str = "langgraph"
    version: str = "0.1.0"

    def __init__(
        self,
        *,
        graph_provider: GraphProvider | None = None,
        variant: str = "guarded",
        thread_id: str | None = None,
        checkpointer: Any = None,
        durability: str = "sync",
    ) -> None:
        self._graph_provider = graph_provider
        self._variant = variant
        self._thread_id = thread_id
        self._checkpointer = checkpointer
        self._durability = durability

    def run(self, session: AdapterSession) -> AdapterResult:
        _ensure_langgraph_installed()
        from langgraph.checkpoint.memory import InMemorySaver

        # A fresh in-memory checkpointer per run keeps repeated runs
        # deterministic; pass `checkpointer=` to share one across resumes.
        checkpointer = self._checkpointer if self._checkpointer is not None else InMemorySaver()
        graph = self._build_graph(session.scenario, checkpointer)

        # Thread identity is durable, derived from scenario identity -- it is
        # part of what makes operation/idempotency identifiers stable across
        # retries and checkpoint resumes (docs/langgraph-adapter-mapping.md).
        thread_id = self._thread_id or f"cavbench-{session.scenario.id}"
        config = {"configurable": {"thread_id": thread_id, "cavbench_session": session}}

        # durability="sync": a checkpoint is written synchronously after each
        # super-step before execution proceeds, so any resume observes a
        # complete record of what already executed.
        final_state: Mapping[str, Any] = graph.invoke(
            {"user_request": session.scenario.user_request}, config=config, durability=self._durability
        )

        completion_status = str(final_state.get("completion_status", "partial"))
        if completion_status not in COMPLETION_STATUSES:
            completion_status = "partial"
        return AdapterResult(
            final_message=str(final_state.get("final_message", "")),
            completion_status=completion_status,
            metadata={
                # Diagnostic only. Everything here lands in the untrusted
                # adapter_report; none of it can influence evaluator output.
                "framework": "langgraph",
                "langgraph_version": _langgraph_version(),
                "thread_id": thread_id,
                "graph_variant": self._variant if self._graph_provider is None else "custom",
                "normalized_events": list(final_state.get("normalized_events", [])),
            },
        )

    def _build_graph(self, scenario: ScenarioView, checkpointer: Any) -> Any:
        if self._graph_provider is not None:
            return self._graph_provider(scenario, checkpointer=checkpointer)
        from cavbench.adapters.langgraph_reference import build_reference_graph

        return build_reference_graph(scenario, variant=self._variant, checkpointer=checkpointer)
