"""Run Phase 1 SOH Baseline Evaluation and Generate Reports.

Executes Leave-One-Battery-Out (LOBO) cross-validation on synthetic aging cohort
and saves report artifacts to `reports/soh_phase1_baseline_report.md` and
`reports/soh_phase1_baseline_metrics.csv`.
"""

from pathlib import Path
import sys

from soh.benchmarks import BenchmarkReportGenerator, GroupedBatteryEvaluator
from soh.data.synthetic_aging import SyntheticAgingGenerator
from soh.estimators.baseline_ridge import BaselineRidgeEstimator


def main() -> int:
    reports_dir = Path("reports")
    reports_dir.mkdir(parents=True, exist_ok=True)

    print("=================================================================")
    print("           LITHIUM-ION BATTERY SOH ESTIMATION - PHASE 1          ")
    print("=================================================================")
    print("[1/3] Generating multi-battery synthetic cohort (4 cells, 35 cycles each)...")
    generator = SyntheticAgingGenerator(seed=42)
    cohort = generator.generate_cohort(
        cell_ids=["LFP_CELL_01", "LFP_CELL_02", "LFP_CELL_03", "LFP_CELL_04"],
        num_cycles=35,
        temp_c=25.0,
    )
    print(f"      Generated {len(cohort.cell_ids)} cells with total {len(cohort.get_all_cycles())} cycles.")

    print("[2/3] Executing Leave-One-Battery-Out (LOBO) Cross-Validation with Baseline Ridge...")
    evaluator = GroupedBatteryEvaluator()
    result = evaluator.run_lobo_cv(
        dataset=cohort,
        estimator_factory=lambda: BaselineRidgeEstimator(alpha_c=1.0, alpha_r=1.0),
    )

    print("[3/3] Generating benchmark reports...")
    report_md = BenchmarkReportGenerator.render_markdown_report(result, "BaselineRidgeEstimator")
    md_path = reports_dir / "soh_phase1_baseline_report.md"
    md_path.write_text(report_md, encoding="utf-8")
    print(f"      Report written to: {md_path}")

    csv_path = reports_dir / "soh_phase1_baseline_metrics.csv"
    BenchmarkReportGenerator.save_csv_summary(result, csv_path, "BaselineRidgeEstimator")
    print(f"      CSV summary written to: {csv_path}")

    print("\nBenchmark Summary:")
    print("-----------------------------------------------------------------")
    if result.aggregate_metrics_c:
        mc = result.aggregate_metrics_c
        print(f"Capacity SOH (SOH_C)  : RMSE = {mc.rmse*100:.2f}% | MAE = {mc.mae*100:.2f}% | 95% PICP = {mc.picp_95*100:.1f}% | Winkler = {mc.winkler_score_95:.4f}")
    if result.aggregate_metrics_r:
        mr = result.aggregate_metrics_r
        print(f"Resistance SOH (SOH_R): RMSE = {mr.rmse*100:.2f}% | MAE = {mr.mae*100:.2f}% | 95% PICP = {mr.picp_95*100:.1f}% | Winkler = {mr.winkler_score_95:.4f}")
    print("=================================================================")
    return 0


if __name__ == "__main__":
    sys.exit(main())
