"""Contract tests for the design-stage LangGraph adapter skeleton.

These do not test LangGraph integration behavior (there isn't any yet --
see docs/langgraph-adapter-mapping.md). They test the three properties the
skeleton is required to have: it satisfies the ExecutionAdapter protocol
shape, it never makes LangGraph a hard dependency of importing cavbench,
and it fails honestly rather than fabricating a result.
"""

from __future__ import annotations

import sys

import pytest

from cavbench.adapters.protocol import ExecutionAdapter
from cavbench.runtime.environment import BenchmarkEnvironment
from cavbench.runtime.session import AdapterSession
from cavbench.runtime.tools import ToolFacade
from cavbench.scenarios.loader import load_builtin_pack

PACK = load_builtin_pack("core-v1")


def test_langgraph_module_is_not_already_imported() -> None:
    """Sanity check on the test environment itself: if this fails, some
    other test already imported langgraph and the isolation tests below
    would not be meaningful."""
    assert "langgraph" not in sys.modules


def test_importing_the_adapter_module_does_not_require_or_import_langgraph() -> None:
    # Re-import is safe/idempotent even if another test already imported it.
    import cavbench.adapters.langgraph  # noqa: F401

    assert "langgraph" not in sys.modules, (
        "importing cavbench.adapters.langgraph must not eagerly import langgraph -- "
        "LangGraph is an optional dependency (docs/langgraph-adapter-mapping.md)"
    )


def test_langgraph_adapter_satisfies_the_execution_adapter_protocol() -> None:
    from cavbench.adapters.langgraph import LangGraphAdapter

    adapter = LangGraphAdapter()
    assert isinstance(adapter, ExecutionAdapter)
    assert isinstance(adapter.name, str) and adapter.name
    assert isinstance(adapter.version, str) and adapter.version


def test_langgraph_adapter_run_fails_clearly_instead_of_fabricating_a_result() -> None:
    from cavbench.adapters.langgraph import LangGraphAdapter

    scenario = PACK.get("HP-01")
    env = BenchmarkEnvironment(scenario, seed=0, run_id="langgraph-skeleton-test")
    session = AdapterSession(scenario.view, ToolFacade(env))

    adapter = LangGraphAdapter()
    with pytest.raises((ImportError, NotImplementedError)) as exc_info:
        adapter.run(session)

    message = str(exc_info.value)
    assert message, "the raised error must carry a clear, non-empty explanation"


def test_langgraph_adapter_run_raises_not_implemented_once_langgraph_is_available(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Isolates the "graph not implemented yet" failure mode from the
    "langgraph isn't installed" failure mode: even with the installation
    check stubbed out (as if langgraph were available), run() must still
    fail honestly with NotImplementedError, and the message must clearly
    say the graph is not implemented yet -- not just raise something."""
    import cavbench.adapters.langgraph as langgraph_adapter_module

    monkeypatch.setattr(langgraph_adapter_module, "_ensure_langgraph_installed", lambda: None)

    scenario = PACK.get("HP-01")
    env = BenchmarkEnvironment(scenario, seed=0, run_id="langgraph-skeleton-test-not-implemented")
    session = AdapterSession(scenario.view, ToolFacade(env))

    adapter = langgraph_adapter_module.LangGraphAdapter()
    with pytest.raises(NotImplementedError) as exc_info:
        adapter.run(session)

    message = str(exc_info.value).lower()
    assert "graph" in message
    assert "no graph implementation yet" in message
