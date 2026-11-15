"""Robustness tests for the report generator handling edge cases."""

import math
import pytest

from soc.eval.report import ReportGenerator, MANDATORY_HEADER
from soc.harness.runner import RunResult


def test_report_generator_handles_nan_and_inf_without_raising():
    """Verify that report generator handles NaN, Inf, and strange floats gracefully.

    Prompt requirement:
    'Add a test that the report generator handles inf, NaN and a missing estimator without raising.'
    """
    res_nan_inf = RunResult(
        scenario="smoke",
        estimator="E2",
        variant="matched",
        profile="automotive",
        config_hash="abc123hash",
        git_commit="deadbeef",
        noise_seed=42,
        seed_index=0,
        duration_s=180.0,
        n_samples_kept=180,
        n_dropped=0,
        drift_evaluated=False,
        placeholder_count=50,
        assumed_count=10,
        temp_clamp_warnings=0,
        rmse=float("nan"),
        mae=float("nan"),
        max_abs_error=float("nan"),
        p95_error=float("nan"),
        plateau_rmse_20_80=float("nan"),
        converge_time_2pct=float("inf"),
        converge_time_5pct=float("inf"),
        drift_24h=float("nan"),
        post_reversal_error_60s=float("nan"),
        ms_per_step_mean=float("nan"),
        ms_per_step_median=float("nan"),
        voltage_residual_rmse=float("nan"),
        mean_nis=float("nan"),
        pass_all_bars=False,
        failed_bars="t2_dynamic_rmse_max",
    )

    # Must generate report without raising any exceptions
    report = ReportGenerator.generate_report([res_nan_inf])

    assert isinstance(report, str)
    assert MANDATORY_HEADER in report
    # NaN must render as n/a
    assert "n/a" in report
    # Inf must render as never
    assert "never" in report
    # Unimplemented estimators must be listed
    assert "E3" in report
    assert "not implemented" in report


def test_report_generator_handles_missing_estimators_and_empty_results():
    """Verify report generator functions when estimators are missing or empty."""
    # Only E1 present (E0 and E2 missing)
    res_e1_only = RunResult(
        scenario="smoke",
        estimator="E1",
        variant="matched",
        profile="automotive",
        config_hash="hash1",
        git_commit="commit1",
        noise_seed=42,
        seed_index=0,
        duration_s=180.0,
        n_samples_kept=180,
        n_dropped=0,
        drift_evaluated=True,
        placeholder_count=20,
        assumed_count=5,
        temp_clamp_warnings=0,
        rmse=0.01,
        mae=0.008,
        max_abs_error=0.015,
        p95_error=0.012,
        plateau_rmse_20_80=0.01,
        converge_time_2pct=1.0,
        converge_time_5pct=1.0,
        drift_24h=0.001,
        post_reversal_error_60s=0.005,
        ms_per_step_mean=0.08,
        ms_per_step_median=0.07,
        voltage_residual_rmse=0.002,
        mean_nis=0.5,
        pass_all_bars=True,
        failed_bars="",
    )

    report = ReportGenerator.generate_report([res_e1_only])
    assert "E1" in report
    assert "PASS" in report

    # Empty results list
    empty_report = ReportGenerator.generate_report([])
    assert MANDATORY_HEADER in empty_report


def test_load_results_from_csv_and_cli_report(tmp_path):
    """Verify loading RunResult objects from CSV and rendering reports via CLI."""
    import csv
    from soc.cli import main

    csv_path = tmp_path / "tiny_results.csv"
    report_path = tmp_path / "tiny_report.md"

    # Write a tiny fixture CSV with 1 row
    fieldnames = [
        "scenario", "estimator", "variant", "profile", "config_hash", "git_commit",
        "noise_seed", "seed_index", "duration_s", "n_samples_kept", "n_dropped",
        "drift_evaluated", "placeholder_count", "assumed_count", "temp_clamp_warnings",
        "rmse", "mae", "max_abs_error", "p95_error", "plateau_rmse_20_80",
        "converge_time_2pct", "converge_time_5pct", "drift_24h", "post_reversal_error_60s",
        "ms_per_step_mean", "ms_per_step_median", "voltage_residual_rmse", "mean_nis",
        "pass_all_bars", "failed_bars", "dirty", "reversal_count", "error_rise",
        "anchor_count", "samples_anchored", "first_anchor_time_s", "err_pre_anchor",
        "err_post_anchor", "clean_rmse", "signed_rmse_rise", "rmse_rise",
        "clean_max_error", "max_error_rise", "max_abs_error_post_warmup",
        "soc_min", "soc_max", "fraction_on_plateau", "spike_detected",
        "spike_time_s", "spike_true_soc", "spike_error", "mean_signed_error",
        "truth_soc_min", "truth_soc_max", "is_invalid_extreme", "diagnostic_telemetry",
    ]

    row_data = {
        "scenario": "fixture_test",
        "estimator": "E7v3",
        "variant": "matched",
        "profile": "automotive",
        "config_hash": "testcfg123",
        "git_commit": "abcdef0",
        "noise_seed": "42",
        "seed_index": "0",
        "duration_s": "60.0",
        "n_samples_kept": "60",
        "n_dropped": "0",
        "drift_evaluated": "True",
        "placeholder_count": "10",
        "assumed_count": "5",
        "temp_clamp_warnings": "0",
        "rmse": "0.005",
        "mae": "0.004",
        "max_abs_error": "0.010",
        "p95_error": "0.008",
        "plateau_rmse_20_80": "0.005",
        "converge_time_2pct": "1.0",
        "converge_time_5pct": "1.0",
        "drift_24h": "0.0005",
        "post_reversal_error_60s": "0.002",
        "ms_per_step_mean": "0.5",
        "ms_per_step_median": "0.5",
        "voltage_residual_rmse": "0.001",
        "mean_nis": "0.1",
        "pass_all_bars": "True",
        "failed_bars": "",
        "dirty": "False",
        "reversal_count": "0",
        "spike_detected": "False",
        "is_invalid_extreme": "False",
        "diagnostic_telemetry": "None",
    }

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerow(row_data)

    # 1. Direct loader check
    results = ReportGenerator.load_results_from_csv(csv_path)
    assert len(results) == 1
    assert results[0].scenario == "fixture_test"
    assert results[0].estimator == "E7v3"
    assert results[0].rmse == 0.005
    assert results[0].pass_all_bars is True

    # 2. CLI report invocation
    with pytest.raises(SystemExit) as excinfo:
        main(["report", "--csv", str(csv_path), "--output", str(report_path)])
    assert excinfo.value.code == 0
    assert report_path.exists()
    content = report_path.read_text(encoding="utf-8")
    assert MANDATORY_HEADER in content
    assert "fixture_test" in content
    assert "E7v3" in content
