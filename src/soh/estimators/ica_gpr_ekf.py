"""Incremental Capacity Analysis + Gaussian Process Regression + Extended Kalman Filter (ICA-GPR-EKF).

Implements the hybrid electrochemical tracking architecture from Kadem & Kim,
IEEE Transactions on Transportation Electrification (2026):
1. Extracts electrochemical health indicators from incremental capacity curves (peak height, peak area, peak shift).
2. Uses Gaussian Process Regression (GPR) to map health indicators to capacity SOH with explicit predictive uncertainty.
3. Incorporates GPR uncertainty directly into a discrete Extended Kalman Filter (EKF) state tracker.
4. Robustly handles intermittent updates (missing ICA observations) and gates statistical outliers via Chi-square innovation tests.
"""

from typing import Dict, List, Optional, Tuple
import numpy as np
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import ConstantKernel, Matern, WhiteKernel
from sklearn.preprocessing import StandardScaler

from soh.common.contracts import (
    CycleRecord,
    EstimationStatus,
    FeatureQualityRecord,
    PartialWindow,
    SOHState,
    SohEstimate,
)
from soh.data.base_loader import SohDataset
from soh.estimators.base import SohEstimator
from soh.features.ica import IcaConfig, IcaFeatureExtractor, IcaFeatures


class IcaGprEkfEstimator(SohEstimator):
    """Hybrid ICA-GPR-EKF state-of-health tracking estimator."""

    FEATURE_NAMES = [
        "ica_peak_height",
        "ica_peak_area",
        "ica_peak_voltage_v",
        "ica_peak_shift_v",
        "mean_temp_c",
    ]

    def __init__(
        self,
        ica_config: Optional[IcaConfig] = None,
        process_noise_q: float = 1e-6,
        sensor_noise_floor_r: float = 4e-6,
        innovation_gate_threshold: float = 6.635,  # Chi-squared 1-dof at p=0.01
        throughput_deg_rate: float = 1.5e-5,      # Degradation per Ah throughput
    ):
        self.ica_config = ica_config or IcaConfig()
        self.ica_extractor = IcaFeatureExtractor(config=self.ica_config)

        self.process_noise_q = process_noise_q
        self.sensor_noise_floor_r = sensor_noise_floor_r
        self.innovation_gate_threshold = innovation_gate_threshold
        self.throughput_deg_rate = throughput_deg_rate

        self.scaler = StandardScaler()

        # Matérn 3/2 kernel with WhiteKernel for measurement noise regularization
        kernel = ConstantKernel(1.0, (1e-3, 1e2)) * Matern(length_scale=1.0, length_scale_bounds=(1e-2, 1e2), nu=1.5) + WhiteKernel(
            noise_level=1e-4, noise_level_bounds=(1e-6, 1e-2)
        )
        self.gpr = GaussianProcessRegressor(
            kernel=kernel,
            alpha=1e-5,
            n_restarts_optimizer=3,
            random_state=42,
        )

        self.is_fitted = False
        self.bol_peak_voltage: Optional[float] = None
        self._feature_bounds_min: Optional[np.ndarray] = None
        self._feature_bounds_max: Optional[np.ndarray] = None

    def extract_features(
        self,
        time_s: np.ndarray,
        voltage_v: np.ndarray,
        current_a: np.ndarray,
        temp_c: np.ndarray,
        v_min: Optional[float] = None,
        v_max: Optional[float] = None,
    ) -> Tuple[Optional[np.ndarray], FeatureQualityRecord]:
        """Extract ICA features from charging data."""
        # Isolate active charging samples (I < -0.05 A)
        chg_mask = current_a < -0.05
        if np.sum(chg_mask) < 20:
            return None, FeatureQualityRecord(
                is_eligible=False,
                failure_reasons=["No continuous charging segment (I < -0.05A) found in telemetry."],
            )

        t_chg = time_s[chg_mask]
        v_chg = voltage_v[chg_mask]
        i_chg = current_a[chg_mask]
        temp_chg = temp_c[chg_mask]

        ica_feats, quality = self.ica_extractor.extract_from_charge_segment(
            time_s=t_chg,
            voltage_v=v_chg,
            current_a=i_chg,
            temp_c=temp_chg,
            v_min_override=v_min,
            v_max_override=v_max,
            bol_peak_voltage_v=self.bol_peak_voltage,
        )

        if not quality.is_eligible or ica_feats is None:
            return None, quality

        avg_temp = float(np.mean(temp_chg)) if len(temp_chg) > 0 else 25.0
        feat_vec = np.array([
            ica_feats.peak_height_ah_per_v,
            ica_feats.peak_area_ah,
            ica_feats.peak_voltage_v,
            ica_feats.peak_voltage_shift_v,
            avg_temp,
        ], dtype=float)

        return feat_vec, quality

    def fit(self, dataset: SohDataset) -> "IcaGprEkfEstimator":
        """Extract ICA features across training cohort and fit GPR model."""
        x_list: List[np.ndarray] = []
        y_list: List[float] = []

        # Find reference BOL peak voltage from pristine cycles
        peak_v_list = []
        for cid, bdata in dataset.batteries.items():
            if bdata.cycles:
                c0 = bdata.cycles[0]
                feats, q = self.extract_features(
                    c0.time_s, c0.voltage_v, c0.current_a, c0.temp_c,
                    v_min=bdata.spec.v_min, v_max=bdata.spec.v_max
                )
                if feats is not None:
                    peak_v_list.append(feats[2])  # peak_voltage_v

        if peak_v_list:
            self.bol_peak_voltage = float(np.mean(peak_v_list))

        for cid, bdata in dataset.batteries.items():
            for cycle in bdata.cycles:
                if cycle.soh_c_bol_true is None:
                    continue

                feats, q = self.extract_features(
                    cycle.time_s, cycle.voltage_v, cycle.current_a, cycle.temp_c,
                    v_min=bdata.spec.v_min, v_max=bdata.spec.v_max
                )
                if q.is_eligible and feats is not None:
                    x_list.append(feats)
                    y_list.append(cycle.soh_c_bol_true)

        if len(x_list) < 5:
            # If discrete cycles lack charging curves in training set, raise explicit error
            raise ValueError(f"Insufficient eligible ICA training samples (found {len(x_list)}, need >= 5).")

        x_arr = np.array(x_list)
        y_arr = np.array(y_list)

        # Scale features strictly on training data
        x_scaled = self.scaler.fit_transform(x_arr)
        self._feature_bounds_min = np.min(x_scaled, axis=0) - 1.5
        self._feature_bounds_max = np.max(x_scaled, axis=0) + 1.5

        # Fit GPR
        self.gpr.fit(x_scaled, y_arr)

        # Learn throughput degradation coefficient exclusively from training batteries
        delta_ah_list: List[float] = []
        delta_soh_list: List[float] = []
        for cid, bdata in dataset.batteries.items():
            if len(bdata.cycles) >= 2:
                c_first = bdata.cycles[0]
                c_last = bdata.cycles[-1]
                if (
                    c_first.ah_throughput is not None
                    and c_last.ah_throughput is not None
                    and c_first.soh_c_bol_true is not None
                    and c_last.soh_c_bol_true is not None
                ):
                    d_ah = float(c_last.ah_throughput - c_first.ah_throughput)
                    d_soh = float(c_first.soh_c_bol_true - c_last.soh_c_bol_true)
                    if d_ah > 0 and d_soh >= 0:
                        delta_ah_list.append(d_ah)
                        delta_soh_list.append(d_soh)

        if delta_ah_list and sum(delta_ah_list) > 0:
            self.throughput_deg_rate = float(sum(delta_soh_list) / sum(delta_ah_list))

        self.is_fitted = True
        return self

    def predict_window(
        self,
        window: PartialWindow,
        features: Optional[Dict[str, float]] = None,
    ) -> SohEstimate:
        """Inference on a partial charging window."""
        if not self.is_fitted:
            raise RuntimeError("Estimator must be fitted before predict_window().")

        feat_vec, quality = self.extract_features(
            window.time_s,
            window.voltage_v,
            window.current_a,
            window.temp_c,
        )

        if not quality.is_eligible or feat_vec is None:
            return SohEstimate(
                status=EstimationStatus.INSUFFICIENT_INFORMATION,
                quality=quality,
            )

        x_scaled = self.scaler.transform(feat_vec.reshape(1, -1))

        # Extrapolation check: verify feature is within supported training envelope
        if np.any(x_scaled < self._feature_bounds_min) or np.any(x_scaled > self._feature_bounds_max):
            return SohEstimate(
                status=EstimationStatus.LOW_QUALITY_FEATURE,
                quality=FeatureQualityRecord(
                    is_eligible=False,
                    failure_reasons=["Feature vector falls outside supported GPR training distribution"],
                ),
            )

        pred_mean, pred_std = self.gpr.predict(x_scaled, return_std=True)
        pred_c = float(pred_mean[0])
        var_c = float(pred_std[0] ** 2)

        ci_95 = (pred_c - 1.96 * float(pred_std[0]), pred_c + 1.96 * float(pred_std[0]))
        feats_dict = {name: float(val) for name, val in zip(self.FEATURE_NAMES, feat_vec)}

        return SohEstimate(
            soh_c=pred_c,
            soh_r=None,  # ICA tracks capacity degradation
            variance_c=var_c,
            status=EstimationStatus.VALID,
            quality=quality,
            features_used=feats_dict,
            confidence_interval_95_c=ci_95,
        )

    def predict_cycle(self, cycle: CycleRecord) -> SohEstimate:
        """Inference on a full cycle record."""
        if not self.is_fitted:
            raise RuntimeError("Estimator must be fitted before predict_cycle().")

        feat_vec, quality = self.extract_features(
            cycle.time_s,
            cycle.voltage_v,
            cycle.current_a,
            cycle.temp_c,
        )

        if not quality.is_eligible or feat_vec is None:
            return SohEstimate(
                status=EstimationStatus.INSUFFICIENT_INFORMATION,
                quality=quality,
            )

        x_scaled = self.scaler.transform(feat_vec.reshape(1, -1))

        if np.any(x_scaled < self._feature_bounds_min) or np.any(x_scaled > self._feature_bounds_max):
            return SohEstimate(
                status=EstimationStatus.LOW_QUALITY_FEATURE,
                quality=FeatureQualityRecord(
                    is_eligible=False,
                    failure_reasons=["Feature vector falls outside supported GPR training distribution"],
                ),
            )

        pred_mean, pred_std = self.gpr.predict(x_scaled, return_std=True)
        pred_c = float(pred_mean[0])
        var_c = float(pred_std[0] ** 2)

        ci_95 = (pred_c - 1.96 * float(pred_std[0]), pred_c + 1.96 * float(pred_std[0]))
        feats_dict = {name: float(val) for name, val in zip(self.FEATURE_NAMES, feat_vec)}

        return SohEstimate(
            soh_c=pred_c,
            soh_r=None,
            variance_c=var_c,
            status=EstimationStatus.VALID,
            quality=quality,
            features_used=feats_dict,
            confidence_interval_95_c=ci_95,
        )

    def update_state(
        self,
        current_state: SOHState,
        estimate: SohEstimate,
        dt_s: float = 0.0,
        ah_delta: float = 0.0,
    ) -> SOHState:
        """EKF state update combining time/throughput propagation with GPR observation."""
        # 1. Time & Throughput Propagation (Predict Step)
        # x_{k+1}^- = x_k - delta_ah * alpha_deg
        delta_deg = max(0.0, ah_delta * self.throughput_deg_rate)
        prior_x = current_state.soh_c_bol - delta_deg
        # Process noise covariance propagation
        prior_p = current_state.covariance[0, 0] + self.process_noise_q

        # 2. Measurement Update Step
        if estimate.status != EstimationStatus.VALID or estimate.soh_c is None:
            # Intermittent update: observation missing or rejected by quality layer.
            # State propagates purely through time-update step!
            new_cov = current_state.covariance.copy()
            new_cov[0, 0] = max(1e-8, prior_p)
            return SOHState(
                soh_c_bol=float(prior_x),
                soh_c_rated=float(prior_x * (current_state.soh_c_rated / max(1e-4, current_state.soh_c_bol))),
                soh_r_bol=current_state.soh_r_bol,
                soh_r_rated=current_state.soh_r_rated,
                cycle_index=current_state.cycle_index + 1,
                timestamp_s=current_state.timestamp_s + dt_s,
                covariance=new_cov,
            )

        # Measurement equation: z_k = x_k + v_k
        z_k = estimate.soh_c
        # R_k is dynamically informed by GPR predictive variance + sensor noise floor
        r_k = max(self.sensor_noise_floor_r, estimate.variance_c or 1e-4)

        # Innovation and gating
        innovation = z_k - prior_x
        s_k = prior_p + r_k
        d_mahalanobis_sq = (innovation ** 2) / s_k

        if d_mahalanobis_sq > self.innovation_gate_threshold:
            # Outlier rejected: hold prior state with propagated covariance
            new_cov = current_state.covariance.copy()
            new_cov[0, 0] = max(1e-8, prior_p)
            return SOHState(
                soh_c_bol=float(prior_x),
                soh_c_rated=float(prior_x * (current_state.soh_c_rated / max(1e-4, current_state.soh_c_bol))),
                soh_r_bol=current_state.soh_r_bol,
                soh_r_rated=current_state.soh_r_rated,
                cycle_index=current_state.cycle_index + 1,
                timestamp_s=current_state.timestamp_s + dt_s,
                covariance=new_cov,
            )

        # Kalman gain
        k_gain = prior_p / s_k
        post_x = prior_x + k_gain * innovation
        post_p = (1.0 - k_gain) * prior_p

        # Positive-semidefinite check
        post_p = max(1e-8, post_p)

        new_cov = current_state.covariance.copy()
        new_cov[0, 0] = post_p

        return SOHState(
            soh_c_bol=float(post_x),
            soh_c_rated=float(post_x * (current_state.soh_c_rated / max(1e-4, current_state.soh_c_bol))),
            soh_r_bol=current_state.soh_r_bol,
            soh_r_rated=current_state.soh_r_rated,
            cycle_index=current_state.cycle_index + 1,
            timestamp_s=current_state.timestamp_s + dt_s,
            covariance=new_cov,
        )
