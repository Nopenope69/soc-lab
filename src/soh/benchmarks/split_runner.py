"""Grouped battery-level cross-validation runner.

Enforces strict physical separation between cells to guarantee zero data leakage.
Supports Leave-One-Battery-Out (LOBO) evaluation and uncertainty scoring.
"""

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple
import numpy as np

from soh.benchmarks.metrics import SohEvaluationMetrics, evaluate_soh_predictions
from soh.common.contracts import EstimationStatus, SohEstimate
from soh.data.base_loader import SohDataset
from soh.data.window_extractor import PartialChargeWindowExtractor
from soh.estimators.base import SohEstimator


@dataclass
class CellEvaluationSummary:
    """Evaluation summary for an individual held-out cell."""

    cell_id: str
    metrics_c: SohEvaluationMetrics
    metrics_r: SohEvaluationMetrics
    predictions_c: List[float] = field(default_factory=list)
    ground_truth_c: List[float] = field(default_factory=list)
    predictions_r: List[float] = field(default_factory=list)
    ground_truth_r: List[float] = field(default_factory=list)


@dataclass
class LoboValidationResult:
    """Overall results from Leave-One-Battery-Out cross validation."""

    per_cell: Dict[str, CellEvaluationSummary] = field(default_factory=dict)
    aggregate_metrics_c: Optional[SohEvaluationMetrics] = None
    aggregate_metrics_r: Optional[SohEvaluationMetrics] = None


class GroupedBatteryEvaluator:
    """Evaluates SOH estimators using grouped Leave-One-Battery-Out cross-validation."""

    def __init__(self, extractor: Optional[PartialChargeWindowExtractor] = None):
        self.extractor = extractor or PartialChargeWindowExtractor()

    def run_lobo_cv(
        self,
        dataset: SohDataset,
        estimator_factory: Callable[[], SohEstimator],
    ) -> LoboValidationResult:
        """Run Leave-One-Battery-Out cross-validation across all cells in dataset."""
        cell_ids = dataset.cell_ids
        if len(cell_ids) < 2:
            raise ValueError(f"Need at least 2 distinct batteries for LOBO CV (found {len(cell_ids)}).")

        result = LoboValidationResult()

        all_yt_c, all_yp_c, all_lb_c, all_ub_c = [], [], [], []
        all_yt_r, all_yp_r, all_lb_r, all_ub_r = [], [], [], []

        for held_out_id in cell_ids:
            train_ids = [cid for cid in cell_ids if cid != held_out_id]
            train_ds, test_ds = dataset.split_by_battery(train_cell_ids=train_ids, test_cell_ids=[held_out_id])

            # 1. Instantiate fresh estimator and fit ONLY on training cohort
            estimator = estimator_factory()
            estimator.fit(train_ds)

            # 2. Evaluate strictly on held-out cell
            test_battery = test_ds.batteries[held_out_id]
            cell_yt_c, cell_yp_c, cell_lb_c, cell_ub_c = [], [], [], []
            cell_yt_r, cell_yp_r, cell_lb_r, cell_ub_r = [], [], [], []

            for cycle in test_battery.cycles:
                if cycle.soh_c_bol_true is None:
                    continue

                estimates: List[SohEstimate] = []
                if hasattr(estimator, "predict_cycle"):
                    est = estimator.predict_cycle(cycle)
                    estimates.append(est)
                else:
                    windows = self.extractor.extract_windows_from_cycle(
                        cycle, nominal_capacity_ah=test_battery.spec.nominal_capacity_ah
                    )
                    for win, is_eligible in windows:
                        if is_eligible:
                            est = estimator.predict_window(win)
                            estimates.append(est)

                for est in estimates:
                    if est.status == EstimationStatus.VALID and est.soh_c is not None:
                        # Capacity SOH
                        cell_yt_c.append(cycle.soh_c_bol_true)
                        cell_yp_c.append(est.soh_c)
                        if est.confidence_interval_95_c is not None:
                            cell_lb_c.append(est.confidence_interval_95_c[0])
                            cell_ub_c.append(est.confidence_interval_95_c[1])
                        else:
                            cell_lb_c.append(est.soh_c - 0.05)
                            cell_ub_c.append(est.soh_c + 0.05)

                        # Resistance SOH
                        true_r = cycle.soh_r_bol_true if cycle.soh_r_bol_true is not None else 1.0
                        pred_r = est.soh_r if est.soh_r is not None else 1.0
                        cell_yt_r.append(true_r)
                        cell_yp_r.append(pred_r)
                        if est.confidence_interval_95_r is not None:
                            cell_lb_r.append(est.confidence_interval_95_r[0])
                            cell_ub_r.append(est.confidence_interval_95_r[1])
                        else:
                            cell_lb_r.append(pred_r - 0.05)
                            cell_ub_r.append(pred_r + 0.05)

            if len(cell_yt_c) > 0:
                metrics_c = evaluate_soh_predictions(cell_yt_c, cell_yp_c, cell_lb_c, cell_ub_c)
                metrics_r = evaluate_soh_predictions(cell_yt_r, cell_yp_r, cell_lb_r, cell_ub_r)

                result.per_cell[held_out_id] = CellEvaluationSummary(
                    cell_id=held_out_id,
                    metrics_c=metrics_c,
                    metrics_r=metrics_r,
                    predictions_c=cell_yp_c,
                    ground_truth_c=cell_yt_c,
                    predictions_r=cell_yp_r,
                    ground_truth_r=cell_yt_r,
                )

                all_yt_c.extend(cell_yt_c)
                all_yp_c.extend(cell_yp_c)
                all_lb_c.extend(cell_lb_c)
                all_ub_c.extend(cell_ub_c)

                all_yt_r.extend(cell_yt_r)
                all_yp_r.extend(cell_yp_r)
                all_lb_r.extend(cell_lb_r)
                all_ub_r.extend(cell_ub_r)

        if len(all_yt_c) > 0:
            result.aggregate_metrics_c = evaluate_soh_predictions(
                all_yt_c, all_yp_c, all_lb_c, all_ub_c
            )
            result.aggregate_metrics_r = evaluate_soh_predictions(
                all_yt_r, all_yp_r, all_lb_r, all_ub_r
            )

        return result
