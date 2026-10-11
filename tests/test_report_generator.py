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
