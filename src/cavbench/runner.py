"""The benchmark runner: ties scenario pack, adapter, environment, and
evaluator together for a single profile run or the canonical five-profile
ablation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from cavbench.adapters.baselines import BASELINE_PROFILES, CANONICAL_PROFILE_ORDER
from cavbench.adapters.protocol import ExecutionAdapter
from cavbench.config import RunConfig
from cavbench.errors import RunConfigError
from cavbench.evaluation.evaluator import DeterministicEvaluator
from cavbench.evaluation.metrics import aggregate
from cavbench.evaluation.results import EvaluationResult, MetricSummary
from cavbench.manifest import build_manifest, make_run_id
from cavbench.runtime.environment import BenchmarkEnvironment
from cavbench.runtime.session import AdapterSession
from cavbench.runtime.tools import ToolFacade
from cavbench.runtime.trace import EpisodeTrace
from cavbench.scenarios.loader import load_builtin_pack
from cavbench.scenarios.models import ScenarioDefinition, ScenarioPack


@dataclass(frozen=True)
class CompletedRun:
    run_id: str
    manifest: Mapping[str, Any]
    traces: Mapping[str, EpisodeTrace]
    evaluations: Mapping[str, EvaluationResult]
    metrics: MetricSummary


def select_scenarios(pack: ScenarioPack, config: RunConfig) -> tuple[str, ...]:
    ids = list(config.scenario_ids) if config.scenario_ids else list(pack.scenario_ids)
    unknown = set(ids) - set(pack.scenario_ids)
    if unknown:
        raise RunConfigError(f"Unknown scenario id(s) for pack {pack.pack_id!r}: {sorted(unknown)}")
    if config.families:
        unknown_families = set(config.families) - set(pack.families())
        if unknown_families:
            raise RunConfigError(f"Unknown family filter(s): {sorted(unknown_families)}")
        ids = [sid for sid in ids if pack.get(sid).family in config.families]
    return tuple(ids)


def _run_episode(
    scenario: ScenarioDefinition, adapter: ExecutionAdapter, *, seed: int, run_id: str
) -> EpisodeTrace:
    env = BenchmarkEnvironment(scenario, seed=seed, run_id=run_id)
    tools = ToolFacade(env)
    session = AdapterSession(scenario.view, tools)
    result = adapter.run(session)
    adapter_report = {
        "adapter_name": adapter.name,
        "adapter_version": adapter.version,
        "final_message": result.final_message,
        "completion_status": result.completion_status,
        **{k: v for k, v in dict(result.metadata).items() if k not in ("adapter_name", "adapter_version")},
    }
    return env.finalize(adapter_report)


class BenchmarkRunner:
    def __init__(self, pack: ScenarioPack | None = None) -> None:
        self._pack = pack
        self._evaluator = DeterministicEvaluator()

    def _resolve_pack(self, config: RunConfig) -> ScenarioPack:
        return self._pack if self._pack is not None else load_builtin_pack(config.pack_id)

    def run(self, config: RunConfig, *, adapter: ExecutionAdapter | None = None) -> CompletedRun:
        pack = self._resolve_pack(config)
        active_adapter = adapter or BASELINE_PROFILES.get(config.profile)
        if active_adapter is None:
            raise RunConfigError(
                f"Unknown profile {config.profile!r}. Known profiles: {sorted(BASELINE_PROFILES)}"
            )
        scenario_ids = select_scenarios(pack, config)
        if not scenario_ids:
            raise RunConfigError("No scenarios selected for this run")

        run_id = make_run_id(pack, active_adapter, config)
        traces: dict[str, EpisodeTrace] = {}
        evaluations: dict[str, EvaluationResult] = {}
        for sid in scenario_ids:
            scenario = pack.get(sid)
            trace = _run_episode(scenario, active_adapter, seed=config.seed, run_id=f"{sid}::{run_id}")
            traces[sid] = trace
            evaluations[sid] = self._evaluator.evaluate(scenario, trace)

        rows = [(pack.get(sid), evaluations[sid]) for sid in scenario_ids]
        metrics = aggregate(rows)
        manifest = build_manifest(pack, active_adapter, config, run_id=run_id)
        return CompletedRun(run_id=run_id, manifest=manifest, traces=traces, evaluations=evaluations, metrics=metrics)

    def ablate(self, config: RunConfig) -> dict[str, CompletedRun]:
        pack = self._resolve_pack(config)
        results: dict[str, CompletedRun] = {}
        for profile_name in CANONICAL_PROFILE_ORDER:
            profile_config = RunConfig(
                pack_id=config.pack_id,
                profile=profile_name,
                scenario_ids=config.scenario_ids,
                families=config.families,
                seed=config.seed,
                output_dir=config.output_dir,
                fail_on_cvsr_below=config.fail_on_cvsr_below,
                command=config.command,
            )
            results[profile_name] = self.run(profile_config, adapter=BASELINE_PROFILES[profile_name])
        return results

    def replay(self, scenario: ScenarioDefinition, trace: EpisodeTrace) -> EvaluationResult:
        """Re-evaluate an existing canonical trace without re-running the adapter."""
        return self._evaluator.evaluate(scenario, trace)
