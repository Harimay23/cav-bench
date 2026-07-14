from __future__ import annotations

import json
from pathlib import Path

import pytest

from cavbench.cli import main


def run_cli(args: list[str]) -> int:
    with pytest.raises(SystemExit) as exc_info:
        main(args)
    return exc_info.value.code


def test_help_exits_zero(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["--help"])
    assert exc_info.value.code == 0
    assert "cavbench" in capsys.readouterr().out


def test_invalid_arguments_exit_nonzero() -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["run", "--profile", "not-a-real-profile"])
    assert exc_info.value.code != 0


def test_doctor_is_healthy(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    code = run_cli(["doctor", "--output", str(tmp_path / "runs")])
    out = capsys.readouterr().out
    assert code == 0
    assert "[OK  ]" in out
    assert "[FAIL]" not in out


def test_list_scenarios_profiles_packs(capsys: pytest.CaptureFixture[str]) -> None:
    assert run_cli(["list", "profiles"]) == 0
    profiles_out = capsys.readouterr().out
    assert "direct" in profiles_out and "full_lifecycle" in profiles_out

    assert run_cli(["list", "scenarios"]) == 0
    scenarios_out = capsys.readouterr().out
    assert scenarios_out.count("\n") == 40

    assert run_cli(["list", "packs"]) == 0


def test_validate_builtin_pack() -> None:
    assert run_cli(["validate", "--pack", "core-v1"]) == 0


def test_run_is_deterministic_and_writes_artifacts(tmp_path: Path) -> None:
    output = tmp_path / "runs"
    code = run_cli(["run", "--profile", "direct", "--seed", "0", "--output", str(output)])
    assert code == 0
    run_dirs = list(output.iterdir())
    assert len(run_dirs) == 1
    run_dir = run_dirs[0]
    assert (run_dir / "manifest.json").exists()
    assert (run_dir / "summary.json").exists()
    assert (run_dir / "summary.md").exists()
    assert (run_dir / "evaluations.jsonl").exists()
    assert len(list((run_dir / "traces").glob("*.json"))) == 40

    manifest = json.loads((run_dir / "manifest.json").read_text())
    assert manifest["seed"] == 0
    assert manifest["adapter"]["name"] == "direct"
    assert manifest["scenario_pack"]["id"] == "core-v1"

    summary = json.loads((run_dir / "summary.json").read_text())
    assert summary["metrics"]["overall"]["OSR"] == 0.925


def test_run_threshold_exit_code(tmp_path: Path) -> None:
    output = tmp_path / "runs"
    code = run_cli(["run", "--profile", "direct", "--output", str(output), "--fail-on-cvsr-below", "0.9"])
    assert code == 2  # EXIT_THRESHOLD_FAILED


def test_ablate_writes_all_five_profiles(tmp_path: Path) -> None:
    output = tmp_path / "ablation"
    code = run_cli(["ablate", "--output", str(output)])
    assert code == 0
    assert (output / "summary.json").exists()
    summary = json.loads((output / "summary.json").read_text())
    assert set(summary["profiles"]) == {"direct", "policy_gated", "commit_guarded", "reconciled", "full_lifecycle"}
    assert summary["profiles"]["full_lifecycle"]["metrics"]["overall"]["CVSR"] == 1.0


def test_replay_matches_original_run(tmp_path: Path) -> None:
    output = tmp_path / "runs"
    run_cli(["run", "--profile", "full_lifecycle", "--output", str(output)])
    run_dir = next(output.iterdir())
    trace_path = run_dir / "traces" / "ER-06.json"

    code = run_cli(["replay", "--trace", str(trace_path), "--scenario", "ER-06"])
    assert code == 0
