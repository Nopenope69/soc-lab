"""Benchmark report generator.

Outputs Markdown reports and CSV summary tables from LOBO validation results.
"""

from pathlib import Path
from typing import Optional
import pandas as pd

from soh.benchmarks.split_runner import LoboValidationResult


class BenchmarkReportGenerator:
    """Generates structured benchmark summaries in Markdown and CSV."""

    @staticmethod
    def render_markdown_report(
        result: LoboValidationResult,
        estimator_name: str = "BaselineRidgeEstimator",
    ) -> str:
        """Render a formatted Markdown benchmark report."""
        lines = [
            f"# SOH Benchmark Report: {estimator_name}",
            "",
            "## 1. Aggregate Cohort Metrics",
            "",
            "| Target | Samples | RMSE (%) | MAE (%) | Max Error (%) | 95th Pct Error (%) | R² | PICP (95%) | MPIW | Winkler Score |",
            "|---|---|---|---|---|---|---|---|---|---|",
        ]

        if result.aggregate_metrics_c:
            mc = result.aggregate_metrics_c
            lines.append(
                f"| **Capacity (SOH_C)** | {mc.sample_count} | {mc.rmse*100:.2f}% | {mc.mae*100:.2f}% | "
                f"{mc.max_error*100:.2f}% | {mc.percentile_95_error*100:.2f}% | {mc.r2:.4f} | "
                f"{mc.picp_95*100:.1f}% | {mc.mpiw_95:.4f} | {mc.winkler_score_95:.4f} |"
            )

        if result.aggregate_metrics_r:
            mr = result.aggregate_metrics_r
            lines.append(
                f"| **Resistance (SOH_R)** | {mr.sample_count} | {mr.rmse*100:.2f}% | {mr.mae*100:.2f}% | "
                f"{mr.max_error*100:.2f}% | {mr.percentile_95_error*100:.2f}% | {mr.r2:.4f} | "
                f"{mr.picp_95*100:.1f}% | {mr.mpiw_95:.4f} | {mr.winkler_score_95:.4f} |"
            )

        lines.extend([
            "",
            "## 2. Leave-One-Battery-Out (LOBO) Per-Cell Performance",
            "",
            "| Cell ID | Samples | SOH_C RMSE (%) | SOH_C MAE (%) | SOH_C PICP (95%) | SOH_R RMSE (%) | SOH_R MAE (%) | SOH_R PICP (95%) |",
            "|---|---|---|---|---|---|---|---|",
        ])

        for cid, cell_summary in sorted(result.per_cell.items()):
            mc = cell_summary.metrics_c
            mr = cell_summary.metrics_r
            lines.append(
                f"| `{cid}` | {mc.sample_count} | {mc.rmse*100:.2f}% | {mc.mae*100:.2f}% | "
                f"{mc.picp_95*100:.1f}% | {mr.rmse*100:.2f}% | {mr.mae*100:.2f}% | {mr.picp_95*100:.1f}% |"
            )

        lines.append("")
        return "\n".join(lines)

    @staticmethod
    def save_csv_summary(
        result: LoboValidationResult,
        csv_path: Path,
        estimator_name: str = "BaselineRidgeEstimator",
    ) -> None:
        """Export per-cell evaluation metrics to CSV."""
        rows = []
        for cid, cell_summary in result.per_cell.items():
            mc = cell_summary.metrics_c
            mr = cell_summary.metrics_r
            rows.append({
                "estimator": estimator_name,
                "cell_id": cid,
                "samples": mc.sample_count,
                "soh_c_rmse": mc.rmse,
                "soh_c_mae": mc.mae,
                "soh_c_max_error": mc.max_error,
                "soh_c_picp_95": mc.picp_95,
                "soh_c_mpiw_95": mc.mpiw_95,
                "soh_c_winkler": mc.winkler_score_95,
                "soh_r_rmse": mr.rmse,
                "soh_r_mae": mr.mae,
                "soh_r_max_error": mr.max_error,
                "soh_r_picp_95": mr.picp_95,
                "soh_r_mpiw_95": mr.mpiw_95,
                "soh_r_winkler": mr.winkler_score_95,
            })
        df = pd.DataFrame(rows)
        csv_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(csv_path, index=False)
