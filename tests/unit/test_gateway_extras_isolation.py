"""Optional-dependency isolation tests (M-GPI-1, GPI-FR-013).

The REST frontend is standard-library-only, so there is no dependency that
can genuinely be "missing" today (see `cavbench.gateway.optional`
docstring). What's tested here: (1) importing plain `cavbench` never pulls
in `cavbench.gateway`, matching the existing `reporting` extra's isolation
pattern; (2) the reusable invocation-time missing-extra guard raises a
clear, actionable error and does so only when called, not at import time.
"""

from __future__ import annotations

import subprocess
import sys

import pytest

from cavbench.gateway.errors import MissingExtraError
from cavbench.gateway.optional import require_extra


def test_importing_cavbench_does_not_import_gateway_modules() -> None:
    script = (
        "import sys\n"
        "import cavbench\n"
        "leaked = sorted(m for m in sys.modules if m.startswith('cavbench.gateway'))\n"
        "assert 'cavbench.gateway' not in sys.modules, leaked\n"
        "print('OK')\n"
    )
    result = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "OK"


def test_importing_cavbench_api_does_not_import_gateway_modules() -> None:
    script = (
        "import sys\n"
        "import cavbench.api\n"
        "leaked = sorted(m for m in sys.modules if m.startswith('cavbench.gateway'))\n"
        "assert 'cavbench.gateway' not in sys.modules, leaked\n"
        "print('OK')\n"
    )
    result = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "OK"


def test_require_extra_succeeds_for_a_real_installed_module() -> None:
    module = require_extra("json", extra_name="rest", feature="JSON encoding")
    assert module is not None


def test_require_extra_raises_clear_actionable_error_for_a_missing_module() -> None:
    with pytest.raises(MissingExtraError) as excinfo:
        require_extra("cavbench_nonexistent_dependency_demo", extra_name="mcp", feature="the MCP frontend")
    message = str(excinfo.value)
    assert "cav-bench[mcp]" in message
    assert "the MCP frontend" in message


def test_missing_extra_error_is_raised_at_call_time_not_import_time() -> None:
    # importing the module itself must never raise, even though it defines
    # a function capable of raising MissingExtraError.
    import importlib

    module = importlib.import_module("cavbench.gateway.optional")
    assert hasattr(module, "require_extra")
