"""Run configuration for the benchmark runner and CLI."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from cavbench.errors import RunConfigError


@dataclass(frozen=True)
class RunConfig:
    pack_id: str = "core-v1"
    profile: str = "direct"
    scenario_ids: tuple[str, ...] = ()
    families: tuple[str, ...] = ()
    seed: int = 0
    output_dir: Path = field(default_factory=lambda: Path("runs"))
    fail_on_cvsr_below: float | None = None
    command: str = ""

    def __post_init__(self) -> None:
        if self.fail_on_cvsr_below is not None and not (0.0 <= self.fail_on_cvsr_below <= 1.0):
            raise RunConfigError(f"--fail-on-cvsr-below must be between 0 and 1, got {self.fail_on_cvsr_below}")
