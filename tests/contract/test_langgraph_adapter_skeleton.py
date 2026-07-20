"""Contract tests for the design-stage LangGraph adapter skeleton.

These do not test LangGraph integration behavior (there isn't any yet --
see docs/langgraph-adapter-mapping.md). They test the properties the
skeleton is required to have: it satisfies the ExecutionAdapter protocol
shape, it never makes LangGraph a hard dependency of importing cavbench
(verified in a clean subprocess, not just the parent pytest process), it
fails honestly rather than fabricating a result, and it does not
misattribute a nested import failure inside langgraph to "langgraph is not
installed".
"""

from __future__ import annotations

import subprocess
import sys

import pytest

from cavbench.adapters.protocol import ExecutionAdapter
from cavbench.runtime.environment import BenchmarkEnvironment
from cavbench.runtime.session import AdapterSession
from cavbench.runtime.tools import ToolFacade
from cavbench.scenarios.loader import load_builtin_pack

PACK = load_builtin_pack("core-v1")


def test_importing_the_adapter_module_in_a_clean_subprocess_never_imports_langgraph() -> None:
    """Runs in a fresh interpreter -- not the parent pytest process -- so
    the isolation guarantee cannot be invalidated by test execution order
    or by something else in this process having already imported
    langgraph."""
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import cavbench.adapters.langgraph\n"
            "import sys\n"
            "assert 'langgraph' not in sys.modules, "
            "'importing cavbench.adapters.langgraph must not import langgraph'\n",
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, f"stdout={result.stdout!r} stderr={result.stderr!r}"


def test_langgraph_adapter_satisfies_the_execution_adapter_protocol() -> None:
    from cavbench.adapters.langgraph import LangGraphAdapter

    adapter = LangGraphAdapter()
    assert isinstance(adapter, ExecutionAdapter)
    assert isinstance(adapter.name, str) and adapter.name
    assert isinstance(adapter.version, str) and adapter.version


def test_langgraph_adapter_run_raises_clear_missing_dependency_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The missing-package path is simulated deterministically, via
    monkeypatching, rather than depending on whether the real developer or
    CI environment happens to have langgraph installed -- this test must
    pass either way."""
    import cavbench.adapters.langgraph as langgraph_adapter_module

    class _MissingLangGraphImportlib:
        @staticmethod
        def import_module(name: str) -> object:
            assert name == "langgraph"
            raise ModuleNotFoundError(
                "No module named 'langgraph'",
                name="langgraph",
            )

    monkeypatch.setattr(
        langgraph_adapter_module,
        "importlib",
        _MissingLangGraphImportlib(),
    )

    scenario = PACK.get("HP-01")
    env = BenchmarkEnvironment(
        scenario,
        seed=0,
        run_id="langgraph-skeleton-test-missing-dependency",
    )
    session = AdapterSession(scenario.view, ToolFacade(env))

    with pytest.raises(ImportError) as exc_info:
        langgraph_adapter_module.LangGraphAdapter().run(session)

    message = str(exc_info.value).lower()
    assert "langgraph" in message
    assert "optional" in message
    assert "docs/langgraph-adapter-mapping.md" in message


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


def test_ensure_langgraph_installed_reraises_nested_import_failure_unchanged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A ModuleNotFoundError raised from *inside* langgraph (e.g. one of
    its own missing dependencies) is a different failure mode than
    "langgraph itself is not installed", and must propagate unchanged --
    not be reworded into the optional-dependency message."""
    import cavbench.adapters.langgraph as langgraph_adapter_module

    class _FakeImportlib:
        @staticmethod
        def import_module(name: str) -> object:
            raise ModuleNotFoundError(
                "No module named 'some_nested_dependency'", name="some_nested_dependency"
            )

    monkeypatch.setattr(langgraph_adapter_module, "importlib", _FakeImportlib())

    with pytest.raises(ModuleNotFoundError) as exc_info:
        langgraph_adapter_module._ensure_langgraph_installed()

    assert exc_info.value.name == "some_nested_dependency"
    assert "some_nested_dependency" in str(exc_info.value)
