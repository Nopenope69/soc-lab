"""Shadow inference engine for non-intrusive parallel estimator evaluation.

Allows multiple SOH estimators to evaluate incoming battery telemetry concurrently
in a read-only shadow mode, logging individual predictions, uncertainties, feature
qualities, latencies, inter-estimator disagreements, and reference residuals without
altering the active production state or fused tracker.
"""

from dataclasses import dataclass, field
import json
from pathlib import Path
import time
from typing import Any, Dict, List, Optional, Tuple
import numpy as np

from soh.common.contracts import (
    CycleRecord,
    EstimationStatus,
    FeatureQualityRecord,
    SohEstimate,
)
from soh.estimators.base import SohEstimator


@dataclass
class ShadowEstimatorRecord:
    """Telemetry and prediction log for a single estimator on an individual cycle."""

    estimator_id: str
    model_version: str
    status: EstimationStatus
    soh_c: Optional[float]
    soh_r: Optional[float]
    variance_c: Optional[float]
    variance_r: Optional[float]
    confidence_interval_95_c: Optional[Tuple[float, float]]
    confidence_interval_95_r: Optional[Tuple[float, float]]
    feature_quality: FeatureQualityRecord
    latency_ms: float
    disagreement_from_mean_c: Optional[float]
    reference_residual_c: Optional[float]
    reference_residual_r: Optional[float]


@dataclass
class ShadowTelemetryFrame:
    """Consolidated shadow snapshot across all active estimators for a single cycle."""

    cycle_index: int
    timestamp_s: float
    estimator_records: Dict[str, ShadowEstimatorRecord] = field(default_factory=dict)
    ensemble_mean_c: Optional[float] = None
    ensemble_dispersion_c: Optional[float] = None
    max_pairwise_disagreement_c: Optional[float] = None
    has_reference_ground_truth: bool = False
    ground_truth_soh_c: Optional[float] = None
    ground_truth_soh_r: Optional[float] = None


class ShadowInferenceEngine:
    """Non-intrusive multi-model observer for online shadow validation."""

    def __init__(self):
        self.estimators: Dict[str, Tuple[SohEstimator, str]] = {}
        self.history: List[ShadowTelemetryFrame] = []

    def register_estimator(
        self,
        estimator_id: str,
        estimator: SohEstimator,
        model_version: str = "1.0.0",
    ) -> "ShadowInferenceEngine":
        """Register a candidate estimator for shadow evaluation."""
        self.estimators[estimator_id] = (estimator, model_version)
        return self

    def process_cycle(self, cycle: CycleRecord) -> ShadowTelemetryFrame:
        """Execute all registered estimators against cycle telemetry in shadow mode."""
        timestamp = float(cycle.metadata.get("timestamp_start", cycle.cycle_index * 3600.0)) if cycle.metadata else float(cycle.cycle_index * 3600.0)
        has_gt = cycle.soh_c_bol_true is not None
        gt_c = float(cycle.soh_c_bol_true) if has_gt else None
        gt_r = float(cycle.soh_r_bol_true) if cycle.soh_r_bol_true is not None else None

        frame = ShadowTelemetryFrame(
            cycle_index=cycle.cycle_index,
            timestamp_s=timestamp,
            has_reference_ground_truth=has_gt,
            ground_truth_soh_c=gt_c,
            ground_truth_soh_r=gt_r,
        )

        valid_c_preds: Dict[str, float] = {}
        raw_results: Dict[str, Tuple[SohEstimate, str, float]] = {}

        # 1. Execute each estimator independently
        for est_id, (est, version) in self.estimators.items():
            t0 = time.perf_counter()
            try:
                pred = est.predict_cycle(cycle)
            except Exception as e:
                pred = SohEstimate(
                    status=EstimationStatus.INSUFFICIENT_INFORMATION,
                    quality=FeatureQualityRecord(is_eligible=False, failure_reasons=[str(e)]),
                )
            t1 = time.perf_counter()
            latency_ms = (t1 - t0) * 1000.0

            raw_results[est_id] = (pred, version, latency_ms)
            if pred.status == EstimationStatus.VALID and pred.soh_c is not None:
                valid_c_preds[est_id] = float(pred.soh_c)

        # 2. Compute inter-estimator disagreement metrics
        ensemble_mean_c = None
        dispersion_c = None
        max_disagree_c = None

        if len(valid_c_preds) >= 2:
            vals = list(valid_c_preds.values())
            ensemble_mean_c = float(np.mean(vals))
            dispersion_c = float(np.std(vals))
            max_disagree_c = float(np.max(vals) - np.min(vals))
        elif len(valid_c_preds) == 1:
            ensemble_mean_c = list(valid_c_preds.values())[0]
            dispersion_c = 0.0
            max_disagree_c = 0.0

        frame.ensemble_mean_c = ensemble_mean_c
        frame.ensemble_dispersion_c = dispersion_c
        frame.max_pairwise_disagreement_c = max_disagree_c

        # 3. Assemble shadow records
        for est_id, (pred, version, lat) in raw_results.items():
            sc = float(pred.soh_c) if pred.soh_c is not None else None
            sr = float(pred.soh_r) if pred.soh_r is not None else None

            res_c = (sc - gt_c) if (sc is not None and gt_c is not None) else None
            res_r = (sr - gt_r) if (sr is not None and gt_r is not None) else None

            disagree = abs(sc - ensemble_mean_c) if (sc is not None and ensemble_mean_c is not None) else None

            q = pred.quality if pred.quality is not None else FeatureQualityRecord(is_eligible=(pred.status == EstimationStatus.VALID))

            rec = ShadowEstimatorRecord(
                estimator_id=est_id,
                model_version=version,
                status=pred.status,
                soh_c=sc,
                soh_r=sr,
                variance_c=pred.variance_c,
                variance_r=pred.variance_r,
                confidence_interval_95_c=pred.confidence_interval_95_c,
                confidence_interval_95_r=pred.confidence_interval_95_r,
                feature_quality=q,
                latency_ms=lat,
                disagreement_from_mean_c=disagree,
                reference_residual_c=res_c,
                reference_residual_r=res_r,
            )
            frame.estimator_records[est_id] = rec

        self.history.append(frame)
        return frame

    def get_shadow_summary(self) -> Dict[str, Any]:
        """Compute aggregate summary metrics across shadow history."""
        if not self.history:
            return {"total_frames": 0}

        estimator_stats: Dict[str, Dict[str, Any]] = {}
        for est_id in self.estimators:
            estimator_stats[est_id] = {
                "valid_count": 0,
                "latencies_ms": [],
                "disagreements_c": [],
                "residuals_c": [],
                "residuals_r": [],
            }

        dispersions = []
        max_spreads = []

        for frame in self.history:
            if frame.ensemble_dispersion_c is not None:
                dispersions.append(frame.ensemble_dispersion_c)
            if frame.max_pairwise_disagreement_c is not None:
                max_spreads.append(frame.max_pairwise_disagreement_c)

            for est_id, rec in frame.estimator_records.items():
                stats = estimator_stats[est_id]
                stats["latencies_ms"].append(rec.latency_ms)
                if rec.status == EstimationStatus.VALID and rec.soh_c is not None:
                    stats["valid_count"] += 1
                if rec.disagreement_from_mean_c is not None:
                    stats["disagreements_c"].append(rec.disagreement_from_mean_c)
                if rec.reference_residual_c is not None:
                    stats["residuals_c"].append(rec.reference_residual_c)
                if rec.reference_residual_r is not None:
                    stats["residuals_r"].append(rec.reference_residual_r)

        summary: Dict[str, Any] = {
            "total_frames": len(self.history),
            "mean_ensemble_dispersion_c_pct": float(np.mean(dispersions) * 100.0) if dispersions else 0.0,
            "max_ensemble_spread_c_pct": float(np.max(max_spreads) * 100.0) if max_spreads else 0.0,
            "estimators": {},
        }

        for est_id, s in estimator_stats.items():
            res_c = np.array(s["residuals_c"], dtype=float) if s["residuals_c"] else np.array([])
            res_r = np.array(s["residuals_r"], dtype=float) if s["residuals_r"] else np.array([])
            dis_c = np.array(s["disagreements_c"], dtype=float) if s["disagreements_c"] else np.array([])
            lats = np.array(s["latencies_ms"], dtype=float) if s["latencies_ms"] else np.array([0.0])

            summary["estimators"][est_id] = {
                "valid_evaluations": s["valid_count"],
                "mean_latency_ms": float(np.mean(lats)),
                "p95_latency_ms": float(np.percentile(lats, 95)) if len(lats) > 0 else 0.0,
                "mean_disagreement_c_pct": float(np.mean(dis_c) * 100.0) if len(dis_c) > 0 else 0.0,
                "rmse_ref_c_pct": float(np.sqrt(np.mean(res_c ** 2)) * 100.0) if len(res_c) > 0 else None,
                "mae_ref_c_pct": float(np.mean(np.abs(res_c)) * 100.0) if len(res_c) > 0 else None,
                "rmse_ref_r_pct": float(np.sqrt(np.mean(res_r ** 2)) * 100.0) if len(res_r) > 0 else None,
            }

        return summary

    def get_detailed_disagreement_analysis(self) -> Dict[str, Any]:
        """Perform comprehensive root-cause analysis of inter-estimator disagreement."""
        if not self.history:
            return {"error": "No shadow frames recorded"}

        est_ids = sorted(list(self.estimators.keys()))
        n_frames = len(self.history)

        # 1. Pairwise disagreement matrix
        pairwise_diffs: Dict[str, Dict[str, Dict[str, float]]] = {}
        for i, id_a in enumerate(est_ids):
            pairwise_diffs[id_a] = {}
            for j, id_b in enumerate(est_ids):
                if i == j:
                    continue
                diffs = []
                preds_a = []
                preds_b = []
                for f in self.history:
                    ra = f.estimator_records.get(id_a)
                    rb = f.estimator_records.get(id_b)
                    if (
                        ra and rb
                        and ra.status == EstimationStatus.VALID and ra.soh_c is not None
                        and rb.status == EstimationStatus.VALID and rb.soh_c is not None
                    ):
                        diffs.append(abs(ra.soh_c - rb.soh_c) * 100.0)
                        preds_a.append(ra.soh_c)
                        preds_b.append(rb.soh_c)

                if diffs:
                    arr_diff = np.array(diffs, dtype=float)
                    corr = float(np.corrcoef(preds_a, preds_b)[0, 1]) if len(preds_a) > 2 and np.std(preds_a) > 1e-6 and np.std(preds_b) > 1e-6 else 1.0
                    pairwise_diffs[id_a][id_b] = {
                        "mean_abs_diff_pct": float(np.mean(arr_diff)),
                        "max_abs_diff_pct": float(np.max(arr_diff)),
                        "pearson_corr": corr,
                        "sample_count": len(diffs),
                    }

        # 2. Linear vs Knee-Point Phase Stratification
        # Split history into linear phase (first 70%) and knee-point phase (last 30%)
        split_idx = int(n_frames * 0.70)
        linear_disp = [f.ensemble_dispersion_c * 100.0 for f in self.history[:split_idx] if f.ensemble_dispersion_c is not None]
        knee_disp = [f.ensemble_dispersion_c * 100.0 for f in self.history[split_idx:] if f.ensemble_dispersion_c is not None]

        # 3. Error-Disagreement Correlation
        dispersions = []
        ensemble_errors = []
        for f in self.history:
            if f.ensemble_dispersion_c is not None and f.ground_truth_soh_c is not None and f.ensemble_mean_c is not None:
                dispersions.append(f.ensemble_dispersion_c * 100.0)
                ensemble_errors.append(abs(f.ensemble_mean_c - f.ground_truth_soh_c) * 100.0)

        err_disagree_corr = (
            float(np.corrcoef(dispersions, ensemble_errors)[0, 1])
            if len(dispersions) > 2 and np.std(dispersions) > 1e-6 and np.std(ensemble_errors) > 1e-6
            else 0.0
        )

        return {
            "total_frames": n_frames,
            "pairwise_matrix": pairwise_diffs,
            "phase_stratification": {
                "linear_phase_mean_dispersion_pct": float(np.mean(linear_disp)) if linear_disp else 0.0,
                "knee_phase_mean_dispersion_pct": float(np.mean(knee_disp)) if knee_disp else 0.0,
                "dispersion_increase_factor": (float(np.mean(knee_disp)) / max(1e-4, float(np.mean(linear_disp)))) if linear_disp and knee_disp else 1.0,
            },
            "error_dispersion_correlation": err_disagree_corr,
        }

    def to_dict(self) -> Dict[str, Any]:
        """Serialize shadow telemetry history and summary to dictionary."""
        return {
            "summary": self.get_shadow_summary(),
            "frames": [
                {
                    "cycle_index": f.cycle_index,
                    "timestamp_s": f.timestamp_s,
                    "ensemble_mean_c": f.ensemble_mean_c,
                    "ensemble_dispersion_c": f.ensemble_dispersion_c,
                    "max_pairwise_disagreement_c": f.max_pairwise_disagreement_c,
                    "has_reference_ground_truth": f.has_reference_ground_truth,
                    "ground_truth_soh_c": f.ground_truth_soh_c,
                    "ground_truth_soh_r": f.ground_truth_soh_r,
                    "records": {
                        est_id: {
                            "estimator_id": r.estimator_id,
                            "model_version": r.model_version,
                            "status": r.status.value if hasattr(r.status, "value") else str(r.status),
                            "soh_c": r.soh_c,
                            "soh_r": r.soh_r,
                            "variance_c": r.variance_c,
                            "variance_r": r.variance_r,
                            "confidence_interval_95_c": list(r.confidence_interval_95_c) if r.confidence_interval_95_c else None,
                            "confidence_interval_95_r": list(r.confidence_interval_95_r) if r.confidence_interval_95_r else None,
                            "latency_ms": r.latency_ms,
                            "disagreement_from_mean_c": r.disagreement_from_mean_c,
                            "reference_residual_c": r.reference_residual_c,
                            "reference_residual_r": r.reference_residual_r,
                        }
                        for est_id, r in f.estimator_records.items()
                    },
                }
                for f in self.history
            ],
        }

    def to_json(self, indent: int = 2) -> str:
        """Serialize shadow telemetry history to JSON string."""
        return json.dumps(self.to_dict(), indent=indent)

    def save_log(self, filepath: Path) -> None:
        """Save shadow telemetry log to JSON file."""
        filepath.parent.mkdir(parents=True, exist_ok=True)
        filepath.write_text(self.to_json())
