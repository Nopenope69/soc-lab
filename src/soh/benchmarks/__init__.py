"""SOH benchmarking harness, uncertainty metrics, and report generators."""

from soh.benchmarks.metrics import (
    SohEvaluationMetrics,
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
from soh.benchmarks.report import BenchmarkReportGenerator
from soh.benchmarks.split_runner import (
    CellEvaluationSummary,
    GroupedBatteryEvaluator,
    LoboValidationResult,
)

__all__ = [
    "BenchmarkReportGenerator",
    "CellEvaluationSummary",
    "GroupedBatteryEvaluator",
    "LoboValidationResult",
    "SohEvaluationMetrics",
    "compute_mae",
    "compute_max_error",
    "compute_mpiw",
    "compute_percentile_error",
    "compute_picp",
    "compute_r2",
    "compute_rmse",
    "compute_winkler_score",
    "evaluate_soh_predictions",
]
