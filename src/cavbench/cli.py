"""The `cavbench` command-line interface."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from cavbench.adapters.baselines import BASELINE_PROFILES, CANONICAL_PROFILE_ORDER
from cavbench.config import RunConfig
from cavbench.errors import CavBenchError
from cavbench.reports.writer import write_ablation, write_run
from cavbench.runner import BenchmarkRunner
from cavbench.runtime.trace import EpisodeTrace
from cavbench.scenarios.loader import load_builtin_pack, load_pack_from_directory
from cavbench.version import __version__

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_THRESHOLD_FAILED = 2


def _cmd_doctor(args: argparse.Namespace) -> int:
    checks: list[tuple[str, bool, str]] = []

    checks.append(("package import", True, f"cavbench {__version__}"))

    try:
        pack = load_builtin_pack("core-v1")
        detail = f"{len(pack)} scenarios, digest {pack.digest[:16]}..."
        checks.append(("built-in scenario pack loads and validates", True, detail))
    except Exception as exc:  # noqa: BLE001 - doctor reports any failure
        checks.append(("built-in scenario pack loads and validates", False, str(exc)))

    try:
        output_probe = Path(args.output or "runs") / ".cavbench-doctor-probe"
        output_probe.parent.mkdir(parents=True, exist_ok=True)
        output_probe.write_text("ok")
        output_probe.unlink()
        checks.append(("output directory is writeable", True, str(Path(args.output or "runs").resolve())))
    except OSError as exc:
        checks.append(("output directory is writeable", False, str(exc)))

    if args.check_reporting:
        try:
            import matplotlib  # type: ignore[import-not-found]  # noqa: F401
            import pandas  # type: ignore[import-untyped]  # noqa: F401

            checks.append(("optional reporting extras installed", True, "pandas + matplotlib available"))
        except ImportError as exc:
            checks.append(("optional reporting extras installed", False, str(exc)))

    ok = True
    for name, passed, detail in checks:
        symbol = "OK  " if passed else "FAIL"
        print(f"[{symbol}] {name}: {detail}")
        ok = ok and passed

    return EXIT_OK if ok else EXIT_ERROR


def _cmd_list(args: argparse.Namespace) -> int:
    if args.target == "profiles":
        for name in CANONICAL_PROFILE_ORDER:
            print(name)
        return EXIT_OK
    if args.target == "packs":
        print("core-v1")
        print("framework-v1")
        return EXIT_OK
    if args.target == "scenarios":
        pack = load_builtin_pack(args.pack)
        for sid in pack.scenario_ids:
            scenario = pack.get(sid)
            print(f"{sid}\t{scenario.family}\t{scenario.view.title}")
        return EXIT_OK
    print(f"Unknown list target: {args.target}", file=sys.stderr)
    return EXIT_ERROR


def _cmd_validate(args: argparse.Namespace) -> int:
    try:
        if args.path:
            pack = load_pack_from_directory(Path(args.path))
        else:
            pack = load_builtin_pack(args.pack)
    except CavBenchError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return EXIT_ERROR
    print(f"OK: pack {pack.pack_id!r} v{pack.pack_version} -- {len(pack)} scenarios valid, digest {pack.digest}")
    return EXIT_OK


def _cmd_run(args: argparse.Namespace) -> int:
    config = RunConfig(
        pack_id=args.pack,
        profile=args.profile,
        scenario_ids=tuple(args.scenario or ()),
        families=tuple(args.family or ()),
        seed=args.seed,
        output_dir=Path(args.output),
        fail_on_cvsr_below=args.fail_on_cvsr_below,
        command="cavbench " + " ".join(sys.argv[1:]),
    )
    runner = BenchmarkRunner()
    try:
        run = runner.run(config)
    except CavBenchError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return EXIT_ERROR

    run_dir = write_run(config.output_dir, run)
    overall = run.metrics.overall.to_dict()
    print(f"Wrote run {run.run_id} to {run_dir}")
    print(f"OSR={overall['OSR']:.3f} PAOSR={overall['PAOSR']:.3f} CVSR={overall['CVSR']:.3f} VG={overall['VG']:.3f}")

    if config.fail_on_cvsr_below is not None and overall["CVSR"] < config.fail_on_cvsr_below:
        print(f"THRESHOLD FAILED: CVSR {overall['CVSR']:.3f} < {config.fail_on_cvsr_below:.3f}", file=sys.stderr)
        return EXIT_THRESHOLD_FAILED
    return EXIT_OK


def _cmd_ablate(args: argparse.Namespace) -> int:
    config = RunConfig(
        pack_id=args.pack,
        scenario_ids=tuple(args.scenario or ()),
        families=tuple(args.family or ()),
        seed=args.seed,
        output_dir=Path(args.output),
        command="cavbench " + " ".join(sys.argv[1:]),
    )
    runner = BenchmarkRunner()
    try:
        runs = runner.ablate(config)
    except CavBenchError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return EXIT_ERROR

    ablation_dir = write_ablation(config.output_dir, runs, profile_order=CANONICAL_PROFILE_ORDER)
    print(f"Wrote ablation to {ablation_dir}")
    for profile_name in CANONICAL_PROFILE_ORDER:
        overall = runs[profile_name].metrics.overall.to_dict()
        print(
            f"  {profile_name:16s} OSR={overall['OSR']:.3f} PAOSR={overall['PAOSR']:.3f} "
            f"CVSR={overall['CVSR']:.3f} VG={overall['VG']:.3f}"
        )
    return EXIT_OK


def _cmd_replay(args: argparse.Namespace) -> int:
    pack = load_builtin_pack(args.pack)
    scenario = pack.get(args.scenario)
    trace_data = json.loads(Path(args.trace).read_text())
    trace = EpisodeTrace.from_dict(trace_data)
    runner = BenchmarkRunner()
    evaluation = runner.replay(scenario, trace)
    print(json.dumps(evaluation.to_dict(), indent=2, sort_keys=True))
    return EXIT_OK


def _cmd_report(args: argparse.Namespace) -> int:
    run_dir = Path(args.run_dir)
    summary_path = run_dir / "summary.json"
    if not summary_path.exists():
        print(f"ERROR: {summary_path} not found", file=sys.stderr)
        return EXIT_ERROR
    summary = json.loads(summary_path.read_text())
    print(json.dumps(summary["metrics"], indent=2, sort_keys=True))
    return EXIT_OK


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="cavbench", description="CAV-Bench: Commit-Time Action Validity Benchmark")
    parser.add_argument("--version", action="version", version=f"cavbench {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p_doctor = sub.add_parser("doctor", help="check that the installation is healthy")
    p_doctor.add_argument("--output", default="runs")
    p_doctor.add_argument("--check-reporting", action="store_true")
    p_doctor.set_defaults(func=_cmd_doctor)

    p_list = sub.add_parser("list", help="list scenarios, profiles, or packs")
    p_list.add_argument("target", choices=["scenarios", "profiles", "packs"])
    p_list.add_argument("--pack", default="core-v1")
    p_list.set_defaults(func=_cmd_list)

    p_validate = sub.add_parser("validate", help="validate a scenario pack")
    p_validate.add_argument("--pack", default="core-v1")
    p_validate.add_argument("--path", default=None, help="validate a pack directory instead of a built-in pack")
    p_validate.set_defaults(func=_cmd_validate)

    p_run = sub.add_parser("run", help="run one profile over a scenario pack")
    p_run.add_argument("--pack", default="core-v1")
    p_run.add_argument("--profile", default="direct", choices=sorted(BASELINE_PROFILES))
    p_run.add_argument("--scenario", action="append", help="restrict to one scenario id (repeatable)")
    p_run.add_argument("--family", action="append", help="restrict to one scenario family (repeatable)")
    p_run.add_argument("--seed", type=int, default=0)
    p_run.add_argument("--output", default="runs")
    p_run.add_argument("--fail-on-cvsr-below", type=float, default=None)
    p_run.set_defaults(func=_cmd_run)

    p_ablate = sub.add_parser("ablate", help="run the canonical five-profile ablation")
    p_ablate.add_argument("--pack", default="core-v1")
    p_ablate.add_argument("--scenario", action="append")
    p_ablate.add_argument("--family", action="append")
    p_ablate.add_argument("--seed", type=int, default=0)
    p_ablate.add_argument("--output", default="runs/ablation")
    p_ablate.set_defaults(func=_cmd_ablate)

    p_replay = sub.add_parser("replay", help="re-evaluate an existing trace without re-running the adapter")
    p_replay.add_argument("--trace", required=True)
    p_replay.add_argument("--scenario", required=True)
    p_replay.add_argument("--pack", default="core-v1")
    p_replay.set_defaults(func=_cmd_replay)

    p_report = sub.add_parser("report", help="print metrics from an existing run directory")
    p_report.add_argument("--run-dir", required=True)
    p_report.set_defaults(func=_cmd_report)

    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        exit_code = args.func(args)
    except CavBenchError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        exit_code = EXIT_ERROR
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
