"""Unit tests for SOH metrics, LOBO cross-validation, and report generation."""

from pathlib import Path
import numpy as np
import pytest

from soh.benchmarks import (
    BenchmarkReportGenerator,
    GroupedBatteryEvaluator,
    compute_mae,
    compute_max_error,
    compute_mpiw,
    compute_percentile_error,
    compute_picp,
    compute_r2,
    compute_rmse,
    compute_winkler_score,
    evaluate_soh_predictions,
)
from soh.data.synthetic_aging import SyntheticAgingGenerator
from soh.estimators.baseline_ridge import BaselineRidgeEstimator


def test_metric_computations():
    """Verify accuracy and interval metrics against known mathematical values."""
    y_true = np.array([1.0, 0.95, 0.90, 0.85, 0.80])
    y_pred = np.array([0.99, 0.94, 0.91, 0.84, 0.81])
    lower = y_pred - 0.05
    upper = y_pred + 0.05

    rmse = compute_rmse(y_true, y_pred)
    mae = compute_mae(y_true, y_pred)
    max_err = compute_max_error(y_true, y_pred)
    p95 = compute_percentile_error(y_true, y_pred, 95.0)
    r2 = compute_r2(y_true, y_pred)

    assert rmse == pytest.approx(0.01)
    assert mae == pytest.approx(0.01)
    assert max_err == pytest.approx(0.01)
    assert r2 > 0.90

    # Coverage test: all y_true are within [pred - 0.05, pred + 0.05]
    picp = compute_picp(y_true, lower, upper)
    assert picp == 1.0

    mpiw = compute_mpiw(lower, upper)
    assert mpiw == pytest.approx(0.10)

    winkler = compute_winkler_score(y_true, lower, upper, alpha=0.05)
    # When all points are inside, Winkler score equals mean interval width
    assert winkler == pytest.approx(0.10)


def test_winkler_penalizes_out_of_bounds():
    """Verify Winkler score penalizes points outside prediction intervals."""
    y_true = np.array([1.0, 0.50])  # second point is far outside [0.85, 0.95]
    lower = np.array([0.90, 0.85])
    upper = np.array([1.00, 0.95])

    winkler = compute_winkler_score(y_true, lower, upper, alpha=0.05)
    # width = 0.10, penalty for point 2 = (2/0.05)*(0.85 - 0.50) = 40 * 0.35 = 14.0
    # mean winkler = (0.10 + (0.10 + 14.0)) / 2 = 7.10
    assert winkler == pytest.approx(7.10)


def test_lobo_cv_runner_and_report_generation(tmp_path: Path):
    """Verify end-to-end Leave-One-Battery-Out CV runner and reporting."""
    generator = SyntheticAgingGenerator(seed=202)
    cohort = generator.generate_cohort(cell_ids=["B_A", "B_B", "B_C"], num_cycles=20)

    evaluator = GroupedBatteryEvaluator()
    res = evaluator.run_lobo_cv(
        dataset=cohort,
        estimator_factory=lambda: BaselineRidgeEstimator(alpha_c=1.0, alpha_r=1.0),
    )

    assert len(res.per_cell) == 3
    assert res.aggregate_metrics_c is not None
    assert res.aggregate_metrics_c.rmse < 0.05  # < 5% error on baseline
    assert res.aggregate_metrics_c.picp_95 >= 0.70

    # Verify report formatting
    report_md = BenchmarkReportGenerator.render_markdown_report(res, "BaselineRidgeEstimator")
    assert "Aggregate Cohort Metrics" in report_md
    assert "Capacity (SOH_C)" in report_md

    # Verify CSV export
    csv_file = tmp_path / "soh_benchmark.csv"
    BenchmarkReportGenerator.save_csv_summary(res, csv_file, "BaselineRidgeEstimator")
    assert csv_file.exists()
