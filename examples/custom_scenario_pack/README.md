# Example: a custom scenario pack

A minimal, one-scenario pack demonstrating the scenario-pack extension
point described in `docs/scenario-authoring.md`.

```bash
cavbench validate --path examples/custom_scenario_pack
```

```python
from cavbench.scenarios.loader import load_pack_from_directory
from cavbench.adapters.baselines import BASELINE_PROFILES
from cavbench.runner import BenchmarkRunner
from cavbench.config import RunConfig

pack = load_pack_from_directory("examples/custom_scenario_pack")
runner = BenchmarkRunner(pack=pack)
run = runner.run(RunConfig(profile="direct"), adapter=BASELINE_PROFILES["direct"])
print(run.metrics.overall.to_dict())
```

`EX-01` is `core-v1`'s `ST-01` under a different ID: a fault ships the order
between the read and the cancel attempt. `direct` and `policy_gated` should
fail CVSR (no commit-time guard); `commit_guarded`, `reconciled`, and
`full_lifecycle` should pass.
