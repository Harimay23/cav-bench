"""Contract tests for the LangGraph adapter's dependency and protocol boundary.

These do not exercise LangGraph execution behavior (that lives in
``tests/langgraph/``, and is skipped when the optional extra is not
installed). They pin the properties that must hold *regardless* of whether
LangGraph is installed: the adapter satisfies the ExecutionAdapter protocol
shape, importing cavbench (including the adapter and reference-fixture
modules) never requires or imports langgraph, a missing dependency produces
a clear invocation-time error, and the optional extra is actually declared.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

from cavbench.adapters.protocol import ExecutionAdapter
from cavbench.runtime.environment import BenchmarkEnvironment
from cavbench.runtime.session import AdapterSession
from cavbench.runtime.tools import ToolFacade
from cavbench.scenarios.loader import load_builtin_pack

LANGGRAPH_INSTALLED = importlib.util.find_spec("langgraph") is not None
REPO_ROOT = Path(__file__).resolve().parents[2]


def test_importing_adapter_modules_does_not_import_langgraph() -> None:
    """Run in a subprocess so the check is meaningful even when other tests
    in this session already imported langgraph (e.g. tests/langgraph/)."""
    code = (
        "import sys; "
        "import cavbench; "
        "import cavbench.adapters.langgraph; "
        "import cavbench.adapters.langgraph_reference; "
        "assert 'langgraph' not in sys.modules, 'lazy-import contract violated'; "
        "assert 'langchain_core' not in sys.modules, 'lazy-import contract violated'"
    )
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert result.returncode == 0, (
        "importing cavbench adapter modules must never import langgraph "
        f"(docs/langgraph-adapter-mapping.md); stderr:\n{result.stderr}"
    )


def test_langgraph_adapter_satisfies_the_execution_adapter_protocol() -> None:
    from cavbench.adapters.langgraph import LangGraphAdapter

    adapter = LangGraphAdapter()
    assert isinstance(adapter, ExecutionAdapter)
    assert isinstance(adapter.name, str) and adapter.name
    assert isinstance(adapter.version, str) and adapter.version


@pytest.mark.skipif(LANGGRAPH_INSTALLED, reason="only meaningful when the optional extra is absent")
def test_missing_langgraph_raises_a_clear_invocation_time_error() -> None:
    """Constructing the adapter must work without langgraph; invoking it must
    fail with an error that names the missing optional dependency and how to
    install it -- not a bare ModuleNotFoundError from deep inside a graph."""
    from cavbench.adapters.langgraph import LangGraphAdapter

    scenario = load_builtin_pack("framework-v1").get("FA-01")
    env = BenchmarkEnvironment(scenario, seed=0, run_id="langgraph-missing-dep-test")
    session = AdapterSession(scenario.view, ToolFacade(env))

    with pytest.raises(ImportError) as exc_info:
        LangGraphAdapter().run(session)

    message = str(exc_info.value)
    assert "langgraph" in message
    assert "cav-bench[langgraph]" in message


def test_reference_graph_builder_rejects_unknown_scenarios_before_importing_langgraph() -> None:
    from cavbench.adapters.langgraph_reference import build_reference_graph

    scenario = load_builtin_pack("core-v1").get("HP-01")
    with pytest.raises(ValueError, match="no reference graph"):
        build_reference_graph(scenario.view)


def test_pyproject_declares_langgraph_as_an_optional_extra_only() -> None:
    pyproject = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text())
    core_deps = " ".join(pyproject["project"]["dependencies"])
    assert "langgraph" not in core_deps, "langgraph must never be a core dependency"
    extra = pyproject["project"]["optional-dependencies"]["langgraph"]
    assert any(dep.startswith("langgraph>=") for dep in extra)
