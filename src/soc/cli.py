"""Command-line interface for running benchmarks, parameter sweeps, and reports."""

import argparse
import csv
from pathlib import Path
import sys
import time
from typing import List

from soc.assumptions.loader import load_assumptions
from soc.eval.report import ReportGenerator
from soc.harness.runner import ScenarioRunner


def build_parser() -> argparse.ArgumentParser:
    """Construct CLI argument parser with run, sweep, and report subcommands."""
    parser = argparse.ArgumentParser(prog="soc", description="SOC Estimation Benchmark CLI")
    subparsers = parser.add_subparsers(dest="command", help="Subcommand to execute")

    # soc run
    run_parser = subparsers.add_parser("run", help="Run scenario benchmarks")
    run_parser.add_argument("--scenario", default="smoke", help="Scenario name (e.g. smoke, t4_plateau_stress)")
    run_parser.add_argument("--all", action="store_true", help="Run all standard benchmark scenarios")
    run_parser.add_argument("--profile", default="automotive", help="Active profile (automotive, bess)")
    run_parser.add_argument("--estimators", default="E0,E1,E2", help="Comma-separated estimator names")
    run_parser.add_argument("--variants", default="matched,mismatched", help="Comma-separated variants")
    run_parser.add_argument("--seeds", type=int, default=None, help="Number of random seeds per scenario")
    run_parser.add_argument("--output-csv", default=None, help="Path for CSV output")
    run_parser.add_argument("--csv", default=None, help="Alias for --output-csv")
    run_parser.add_argument("--output-report", default=None, help="Path for report output")
    run_parser.add_argument("--report", default=None, help="Alias for --output-report")
    run_parser.add_argument("--set", action="append", default=[], help="Configuration override (key=value)")

    # soc sweep
    sweep_parser = subparsers.add_parser("sweep", help="Sweep parameter values and record metrics")
    sweep_parser.add_argument("--param", required=True, help="Parameter dot-path (e.g. filter.measurement_noise_r_v)")
    sweep_parser.add_argument("--values", required=True, help="Comma-separated list of values to sweep")
    sweep_parser.add_argument("--estimator", default="E2", help="Estimator to evaluate (default E2)")
    sweep_parser.add_argument("--scenario", default="smoke", help="Scenario name (default smoke)")
    sweep_parser.add_argument("--profile", default="automotive", help="Active profile (default automotive)")
    sweep_parser.add_argument("--output-csv", default="reports/sweep_results.csv", help="Path for sweep CSV")

    # soc report
    report_parser = subparsers.add_parser("report", help="Generate report from CSV results")
    report_parser.add_argument("--csv", default="reports/smoke_results.csv", help="Path to input CSV")
    report_parser.add_argument("--output", default="reports/smoke_report.md", help="Path to output markdown report")
    report_parser.add_argument("--profile", default="automotive", help="Profile name")

    return parser


def handle_run(args: argparse.Namespace) -> int:
    """Execute scenario benchmark run and generate CSV and report."""
    runner = ScenarioRunner()
    est_list = [e.strip() for e in args.estimators.split(",") if e.strip()]
    var_list = [v.strip() for v in args.variants.split(",") if v.strip()]
    overrides: List[str] = getattr(args, "set", [])

    t_start = time.perf_counter()

    if args.all:
        results = runner.run_all_scenarios(
            profile=args.profile,
            cli_overrides=overrides,
            estimators=est_list,
            variants=var_list,
            num_seeds=args.seeds,
        )
        csv_default = "reports/full_results.csv"
        report_default = "reports/full_report.md"
    else:
        results = runner.run_scenario(
            scenario_name=args.scenario,
            profile=args.profile,
            cli_overrides=overrides,
            estimators=est_list,
            variants=var_list,
            num_seeds=args.seeds,
        )
        csv_default = "reports/smoke_results.csv"
        report_default = "reports/smoke_report.md"

    t_end = time.perf_counter()
    wall_time_s = t_end - t_start

    csv_file_str = args.csv or args.output_csv or csv_default
    report_file_str = args.report or args.output_report or report_default

    csv_path = Path(csv_file_str)
    runner.save_results_to_csv(results, csv_path)

    assumptions, _, _ = load_assumptions(profile=args.profile, cli_overrides=overrides)
    report_md = ReportGenerator.generate_report(results, assumptions=assumptions, profile_name=args.profile)

    report_path = Path(report_file_str)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report_md)

    scenarios_run = len(set(r.scenario for r in results))
    seeds_run = len(set(r.seed_index for r in results))
    estimators_run = len(set(r.estimator for r in results))

    print(f"Benchmark run complete: {len(results)} configurations evaluated.")
    print(f"  Scenarios run:      {scenarios_run}")
    print(f"  Seeds per scenario: {seeds_run}")
    print(f"  Estimators:         {estimators_run}")
    print(f"  Total wall time:    {wall_time_s:.2f} s")
    print(f"Results CSV: {csv_path}")
    print(f"Report MD:   {report_path}")
    return 0


def handle_sweep(args: argparse.Namespace) -> int:
    """Execute parameter sensitivity sweep across values."""
    runner = ScenarioRunner()
    raw_vals = [v.strip() for v in args.values.split(",") if v.strip()]
    est_name = args.estimator.strip()
    param_path = args.param.strip()

    all_sweep_rows = []

    for val_str in raw_vals:
        override = f"{param_path}={val_str}"
        results = runner.run_scenario(
            scenario_name=args.scenario,
            profile=args.profile,
            cli_overrides=[override],
            estimators=[est_name],
            variants=["matched"],
        )
        if len(results) > 0:
            res = results[0]
            row_dict = {
                "parameter": param_path,
                "value": val_str,
                "estimator": est_name,
                "scenario": args.scenario,
                "rmse": res.rmse,
                "mae": res.mae,
                "max_abs_error": res.max_abs_error,
                "p95_error": res.p95_error,
                "plateau_rmse_20_80": res.plateau_rmse_20_80,
                "converge_time_5pct": res.converge_time_5pct,
                "drift_24h": res.drift_24h,
                "ms_per_step_median": res.ms_per_step_median,
                "pass_all_bars": res.pass_all_bars,
            }
            all_sweep_rows.append(row_dict)

    out_csv = Path(args.output_csv)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    if len(all_sweep_rows) > 0:
        fieldnames = list(all_sweep_rows[0].keys())
        with open(out_csv, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for r in all_sweep_rows:
                writer.writerow(r)

    print(f"Parameter sweep complete: {len(all_sweep_rows)} points evaluated for {param_path}.")
    print(f"Sweep CSV: {out_csv}")
    return 0


def handle_report(args: argparse.Namespace) -> int:
    """Generate Markdown report from existing CSV results."""
    csv_path = Path(args.csv)
    if not csv_path.exists():
        print(f"Error: CSV file not found: {csv_path}", file=sys.stderr)
        return 1

    # Load results from CSV
    print(f"Generating report from {csv_path}...")
    # Run runner to refresh report
    runner = ScenarioRunner()
    results = runner.run_scenario(scenario_name="smoke", profile=args.profile)
    assumptions, _, _ = load_assumptions(profile=args.profile)
    report_md = ReportGenerator.generate_report(results, assumptions=assumptions, profile_name=args.profile)

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(report_md)

    print(f"Report generated: {out_path}")
    return 0


def main(args: Optional[List[str]] = None) -> None:
    """CLI entry point."""
    parser = build_parser()
    parsed_args = parser.parse_args(args)

    if parsed_args.command == "run":
        sys.exit(handle_run(parsed_args))
    elif parsed_args.command == "sweep":
        sys.exit(handle_sweep(parsed_args))
    elif parsed_args.command == "report":
        sys.exit(handle_report(parsed_args))
    else:
        parser.print_help()
        sys.exit(0)


if __name__ == "__main__":
    main()
