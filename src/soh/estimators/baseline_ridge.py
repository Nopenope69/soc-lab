"""Conventional regularized Ridge regression baseline for SOH estimation.

Serves as the empirical benchmark model (Phase 1). Extracts statistical and
duration-based charging features, fits standardized Ridge regression models for
SOH_C and SOH_R, and provides analytical prediction intervals.
"""

from typing import Dict, List, Optional, Tuple
import numpy as np
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler

from soh.common.contracts import (
    EstimationStatus,
    FeatureQualityRecord,
    PartialWindow,
    SOHState,
    SohEstimate,
)
from soh.common.eligibility import WindowEligibilityConfig, WindowEvaluator
from soh.data.base_loader import SohDataset
from soh.data.window_extractor import PartialChargeWindowExtractor
from soh.estimators.base import SohEstimator


class BaselineRidgeEstimator(SohEstimator):
    """Conventional Ridge regression baseline with analytical prediction intervals."""

    def __init__(
        self,
        alpha_c: float = 1.0,
        alpha_r: float = 1.0,
        eval_config: Optional[WindowEligibilityConfig] = None,
        include_duration: bool = True,
    ):
        self.alpha_c = alpha_c
        self.alpha_r = alpha_r
        self.eval_config = eval_config or WindowEligibilityConfig()
        self.include_duration = include_duration
        self.evaluator = WindowEvaluator()
        self.extractor = PartialChargeWindowExtractor(eval_config=self.eval_config)

        self.scaler = StandardScaler()
        self.model_c = Ridge(alpha=self.alpha_c)
        self.model_r = Ridge(alpha=self.alpha_r)

        self.is_fitted = False
        if self.include_duration:
            self.feature_names = [
                "mean_voltage",
                "delta_v",
                "duration_s",
                "v_initial",
                "delta_v_per_s",
                "temp_avg",
            ]
        else:
            self.feature_names = [
                "mean_voltage",
                "delta_v",
                "v_initial",
                "delta_v_per_s",
                "temp_avg",
            ]

        # Uncertainty covariance matrices in scaled feature space
        self._xtx_inv_c: Optional[np.ndarray] = None
        self._xtx_inv_r: Optional[np.ndarray] = None
        self._sigma2_res_c: float = 1e-4
        self._sigma2_res_r: float = 1e-4

    def extract_features_from_window(self, window: PartialWindow) -> np.ndarray:
        """Extract statistical feature vector from window."""
        mean_v = float(np.mean(window.voltage_v)) if len(window.voltage_v) > 0 else 0.0
        delta_v = window.delta_v
        duration = window.duration_s
        v_init = float(window.voltage_v[0]) if len(window.voltage_v) > 0 else 3.2
        dv_dt = delta_v / max(1.0, duration)
        temp_avg = float(np.mean(window.temp_c)) if len(window.temp_c) > 0 else 25.0

        if self.include_duration:
            return np.array([mean_v, delta_v, duration, v_init, dv_dt, temp_avg], dtype=float)
        else:
            return np.array([mean_v, delta_v, v_init, dv_dt, temp_avg], dtype=float)

    def fit(self, dataset: SohDataset) -> "BaselineRidgeEstimator":
        """Extract features across all eligible training windows and fit Ridge models."""
        x_list: List[np.ndarray] = []
        y_c_list: List[float] = []
        y_r_list: List[float] = []

        for cid, bdata in dataset.batteries.items():
            for cycle in bdata.cycles:
                if cycle.soh_c_bol_true is None:
                    continue

                windows = self.extractor.extract_windows_from_cycle(
                    cycle, nominal_capacity_ah=bdata.spec.nominal_capacity_ah
                )
                for win, is_eligible in windows:
                    if is_eligible:
                        feats = self.extract_features_from_window(win)
                        x_list.append(feats)
                        y_c_list.append(cycle.soh_c_bol_true)
                        # SOH_R fallback if resistance ground truth exists
                        soh_r_val = cycle.soh_r_bol_true if cycle.soh_r_bol_true is not None else 1.0
                        y_r_list.append(soh_r_val)

        if len(x_list) < 5:
            raise ValueError(f"Insufficient eligible training samples (found {len(x_list)}, need >= 5).")

        x_arr = np.array(x_list)
        y_c_arr = np.array(y_c_list)
        y_r_arr = np.array(y_r_list)

        # Fit scaler strictly on training data
        x_scaled = self.scaler.fit_transform(x_arr)

        # Fit Ridge models
        self.model_c.fit(x_scaled, y_c_arr)
        self.model_r.fit(x_scaled, y_r_arr)

        # Calculate residual variances and covariance matrices for uncertainty
        preds_c = self.model_c.predict(x_scaled)
        preds_r = self.model_r.predict(x_scaled)

        n_samples, n_features = x_scaled.shape
        dof = max(1, n_samples - n_features)

        self._sigma2_res_c = float(np.sum((y_c_arr - preds_c) ** 2) / dof)
        self._sigma2_res_r = float(np.sum((y_r_arr - preds_r) ** 2) / dof)

        # (X^T X + alpha * I)^(-1)
        xtx = x_scaled.T @ x_scaled
        self._xtx_inv_c = np.linalg.pinv(xtx + self.alpha_c * np.eye(n_features))
        self._xtx_inv_r = np.linalg.pinv(xtx + self.alpha_r * np.eye(n_features))

        self.is_fitted = True
        return self

    def predict_window(
        self,
        window: PartialWindow,
        features: Optional[Dict[str, float]] = None,
    ) -> SohEstimate:
        """Inference on a partial window with eligibility checking."""
        if not self.is_fitted:
            raise RuntimeError("Estimator must be fitted before predict_window().")

        quality = self.evaluator.evaluate_partial_charge_window(window, self.eval_config)
        if not quality.is_eligible:
            return SohEstimate(
                status=EstimationStatus.INSUFFICIENT_INFORMATION,
                quality=quality,
            )

        raw_x = self.extract_features_from_window(window)
        x_scaled = self.scaler.transform(raw_x.reshape(1, -1))

        # Point predictions
        pred_c = float(self.model_c.predict(x_scaled)[0])
        pred_r = float(self.model_r.predict(x_scaled)[0])

        # Analytical prediction variance: sigma^2 * (1 + x^T (X^T X + alpha I)^(-1) x)
        xtx_inv_c = self._xtx_inv_c if self._xtx_inv_c is not None else np.eye(6)
        xtx_inv_r = self._xtx_inv_r if self._xtx_inv_r is not None else np.eye(6)
        var_c = self._sigma2_res_c * (1.0 + float((x_scaled @ xtx_inv_c @ x_scaled.T).item()))
        var_r = self._sigma2_res_r * (1.0 + float((x_scaled @ xtx_inv_r @ x_scaled.T).item()))

        std_c = float(np.sqrt(max(1e-8, var_c)))
        std_r = float(np.sqrt(max(1e-8, var_r)))

        ci_95_c = (pred_c - 1.96 * std_c, pred_c + 1.96 * std_c)
        ci_95_r = (pred_r - 1.96 * std_r, pred_r + 1.96 * std_r)

        feats_dict = {name: float(val) for name, val in zip(self.feature_names, raw_x)}

        return SohEstimate(
            soh_c=pred_c,
            soh_r=pred_r,
            variance_c=var_c,
            variance_r=var_r,
            status=EstimationStatus.VALID,
            quality=quality,
            features_used=feats_dict,
            confidence_interval_95_c=ci_95_c,
            confidence_interval_95_r=ci_95_r,
        )

    def predict_cycle(self, cycle: CycleRecord) -> SohEstimate:
        """Inference on a full cycle by extracting the charging window."""
        windows = self.extractor.extract_windows_from_cycle(cycle)
        for win, is_eligible in windows:
            if is_eligible:
                return self.predict_window(win)
        return SohEstimate(
            status=EstimationStatus.INSUFFICIENT_INFORMATION,
            quality=FeatureQualityRecord(
                is_eligible=False,
                failure_reasons=["No eligible charging window found in cycle."],
            ),
        )

    def update_state(
        self,
        current_state: SOHState,
        estimate: SohEstimate,
        dt_s: float = 0.0,
    ) -> SOHState:
        """Discrete state update combining prior state and new measurement."""
        if estimate.status != EstimationStatus.VALID or estimate.soh_c is None:
            # Retain existing state
            return current_state

        # Simple discrete Kalman / covariance update
        meas_z = np.array([estimate.soh_c, estimate.soh_r if estimate.soh_r is not None else current_state.soh_r_bol])
        r_meas = np.diag([
            max(1e-6, estimate.variance_c or 1e-4),
            max(1e-6, estimate.variance_r or 1e-4),
        ])

        p_prior = current_state.covariance + np.diag([1e-6, 1e-6])  # process drift
        # Kalman gain: K = P_prior * (P_prior + R)^(-1)
        k_gain = p_prior @ np.linalg.inv(p_prior + r_meas)

        prior_x = np.array([current_state.soh_c_bol, current_state.soh_r_bol])
        innovation = meas_z - prior_x
        new_x = prior_x + k_gain @ innovation
        new_p = (np.eye(2) - k_gain) @ p_prior

        return SOHState(
            soh_c_bol=float(new_x[0]),
            soh_c_rated=float(new_x[0] * (current_state.soh_c_rated / max(1e-4, current_state.soh_c_bol))),
            soh_r_bol=float(new_x[1]),
            soh_r_rated=current_state.soh_r_rated,
            cycle_index=current_state.cycle_index + 1,
            timestamp_s=current_state.timestamp_s + dt_s,
            covariance=new_p,
        )
