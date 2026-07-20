"""Skips the whole directory when the optional `langgraph` extra is absent.

The dependency-isolation and missing-dependency contracts are covered
independently (without langgraph installed) in
``tests/contract/test_langgraph_adapter_contract.py``.
"""

from __future__ import annotations

import pytest

pytest.importorskip("langgraph", reason="requires the optional extra: pip install 'cav-bench[langgraph]'")
