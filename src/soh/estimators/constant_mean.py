"""Constant training-mean predictor baseline.

Provides the ground-floor statistical reference: predicting the empirical mean of the
training cohort with training sample variance. Any machine learning or physical estimator
must decisively outperform this naive predictor to demonstrate genuine learning.
"""

from typing import Dict, Optional
import numpy as np

from soh.common.contracts import (
    EstimationStatus,
    FeatureQualityRecord,
    PartialWindow,
    SOHState,
    SohEstimate,
)
from soh.data.base_loader import SohDataset
from soh.estimators.base import SohEstimator


class ConstantMeanEstimator(SohEstimator):
    """Predicts constant training-set mean for SOH_C and SOH_R with sample variance."""

    def __init__(self):
        self.mean_c: float = 1.0
        self.var_c: float = 1e-4
        self.mean_r: float = 1.0
        self.var_r: float = 1e-4
        self.is_fitted: bool = False

    def fit(self, dataset: SohDataset) -> "ConstantMeanEstimator":
        """Compute empirical mean and variance strictly on training cohort."""
        c_vals = []
        r_vals = []

        for cid, bdata in dataset.batteries.items():
            for cycle in bdata.cycles:
                if cycle.soh_c_bol_true is not None:
                    c_vals.append(cycle.soh_c_bol_true)
                if cycle.soh_r_bol_true is not None:
                    r_vals.append(cycle.soh_r_bol_true)

        if len(c_vals) < 2:
            raise ValueError(f"Need at least 2 training cycles, got {len(c_vals)}")

        self.mean_c = float(np.mean(c_vals))
        self.var_c = float(np.var(c_vals, ddof=1))

        if r_vals:
            self.mean_r = float(np.mean(r_vals))
            self.var_r = float(np.var(r_vals, ddof=1))
        else:
            self.mean_r = 1.0
            self.var_r = 1e-4

        self.is_fitted = True
        return self

    def predict_window(
        self,
        window: PartialWindow,
        features: Optional[Dict[str, float]] = None,
    ) -> SohEstimate:
        """Return training mean prediction."""
        if not self.is_fitted:
            raise RuntimeError("Estimator must be fitted before predict_window().")

        std_c = float(np.sqrt(max(1e-12, self.var_c)))
        std_r = float(np.sqrt(max(1e-12, self.var_r)))

        return SohEstimate(
            soh_c=self.mean_c,
            soh_r=self.mean_r,
            variance_c=self.var_c,
            variance_r=self.var_r,
            status=EstimationStatus.VALID,
            quality=FeatureQualityRecord(is_eligible=True),
            confidence_interval_95_c=(self.mean_c - 1.96 * std_c, self.mean_c + 1.96 * std_c),
            confidence_interval_95_r=(self.mean_r - 1.96 * std_r, self.mean_r + 1.96 * std_r),
        )

    def predict_cycle(self, cycle) -> SohEstimate:
        """Inference on cycle."""
        if not self.is_fitted:
            raise RuntimeError("Estimator must be fitted before predict_cycle().")

        std_c = float(np.sqrt(max(1e-12, self.var_c)))
        std_r = float(np.sqrt(max(1e-12, self.var_r)))

        return SohEstimate(
            soh_c=self.mean_c,
            soh_r=self.mean_r,
            variance_c=self.var_c,
            variance_r=self.var_r,
            status=EstimationStatus.VALID,
            quality=FeatureQualityRecord(is_eligible=True),
            confidence_interval_95_c=(self.mean_c - 1.96 * std_c, self.mean_c + 1.96 * std_c),
            confidence_interval_95_r=(self.mean_r - 1.96 * std_r, self.mean_r + 1.96 * std_r),
        )

    def update_state(
        self,
        current_state: SOHState,
        estimate: SohEstimate,
        dt_s: float = 0.0,
    ) -> SOHState:
        """Return static mean state."""
        return SOHState(
            soh_c_bol=self.mean_c,
            soh_c_rated=self.mean_c,
            soh_r_bol=self.mean_r,
            covariance=np.diag([self.var_c, self.var_r]),
        )
