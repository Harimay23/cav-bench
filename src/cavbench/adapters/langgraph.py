"""Design-stage skeleton for a LangGraph execution adapter.

**Status: draft, not implemented.** See `docs/langgraph-adapter-mapping.md`
for the full design (event mapping, scenario flows, durability/idempotency
requirements) and Issue #5 for implementation tracking.

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
thread/node identity), never as evidence that an effect validly committed,
and ``DeterministicEvaluator`` never sees it.

LangGraph is an optional dependency: importing this module, and importing
``cavbench`` generally, must never require LangGraph to be installed. This
module therefore never imports ``langgraph`` at module scope -- only
lazily, from inside the methods that would actually need it once
implemented.
"""

from __future__ import annotations

import importlib

from cavbench.adapters.protocol import AdapterResult
from cavbench.runtime.session import AdapterSession

_ISSUE_URL = "https://github.com/Harimay23/cav-bench/issues/5"
_MAPPING_DOC = "docs/langgraph-adapter-mapping.md"


def _ensure_langgraph_installed() -> None:
    """Lazily imports ``langgraph`` to verify it is installed.

    Called only from inside adapter methods, never at module import time --
    this is what keeps LangGraph an optional dependency of CAV-Bench. Raises
    a clear, specific error rather than letting a bare ``ModuleNotFoundError``
    surface with no context.

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
            "LangGraphAdapter requires the optional 'langgraph' package, "
            "which is not installed and is not a core CAV-Bench dependency. "
            f"See {_MAPPING_DOC}."
        ) from exc


class LangGraphAdapter:
    """Design-stage skeleton implementing the ``ExecutionAdapter`` protocol shape.

    This class satisfies ``cavbench.adapters.protocol.ExecutionAdapter``
    structurally (``name``, ``version``, ``run``), so it can already be
    passed anywhere an ``ExecutionAdapter`` is expected -- but ``run()``
    always raises. There is no graph implementation yet, and this class
    must not pretend otherwise: see ``docs/langgraph-adapter-mapping.md``
    for the real design and Issue #5 for progress.
    """

    name: str = "langgraph"
    version: str = "0.0.0-skeleton"

    def run(self, session: AdapterSession) -> AdapterResult:
        """Always raises: no LangGraph graph has been implemented yet.

        Deliberately does not fabricate an ``AdapterResult`` -- an adapter
        that appeared to run but silently did nothing would itself be a
        self-grading trust-boundary violation of exactly the kind
        CAV-Bench's evaluator independence exists to catch.
        """
        _ensure_langgraph_installed()
        raise NotImplementedError(
            "LangGraphAdapter has no graph implementation yet. This is a "
            f"design-stage skeleton; see {_MAPPING_DOC} for the design and "
            f"{_ISSUE_URL} for implementation status."
        )
