"""Run manifest: the root reproducibility artifact for every run.

Every value here is either fixed benchmark/package metadata or explicit run
configuration -- never derived from adapter behavior.
"""

from __future__ import annotations

import platform
import subprocess
import sys
from datetime import datetime, timezone
from typing import Any

from cavbench.adapters.protocol import ExecutionAdapter
from cavbench.config import RunConfig
from cavbench.scenarios.models import ScenarioPack
from cavbench.version import __version__


def _git_commit() -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


def build_manifest(pack: ScenarioPack, adapter: ExecutionAdapter, config: RunConfig, *, run_id: str) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "cavbench_version": __version__,
        "git_commit": _git_commit(),
        "python_version": sys.version.split()[0],
        "platform": platform.platform(),
        "scenario_pack": {
            "id": pack.pack_id,
            "version": pack.pack_version,
            "digest": pack.digest,
        },
        "adapter": {
            "name": adapter.name,
            "version": adapter.version,
        },
        "seed": config.seed,
        "command": config.command,
        "started_at": datetime.now(timezone.utc).isoformat(),
    }


def make_run_id(pack: ScenarioPack, adapter: ExecutionAdapter, config: RunConfig) -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{timestamp}-{adapter.name}-{pack.pack_id}-seed{config.seed}"
