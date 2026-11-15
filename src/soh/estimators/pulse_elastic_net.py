"""2-RC ECM Pulse Response ElasticNet SOH Estimator.

Implements the embedded estimation paradigm from Navidi et al., Applied Energy (2026):
1. Extracts interpretable physical 2-RC ECM parameters and pulse dynamics.
2. Fits regularized ElasticNet regression models for dual SOH_C and SOH_R targets.
3. Produces calibrated uncertainty intervals.
4. Implements SupportsEmbeddedExport to generate lightweight C headers for BMS microcontrollers.
"""

from pathlib import Path
from typing import Dict, List, Optional, Tuple
import numpy as np
from sklearn.linear_model import ElasticNet
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
from soh.estimators.base import SohEstimator, SupportsEmbeddedExport
from soh.features.pulse_ecm import Ecm2RcFitter, Ecm2RcParameters, PulseRecord, PulseSegmenter


class PulseElasticNetEstimator(SohEstimator, SupportsEmbeddedExport):
    """2-RC ECM Pulse Response ElasticNet SOH Estimator."""

    FEATURE_NAMES = [
        "r0_ohm",
        "r1_ohm",
        "c1_f",
        "r2_ohm",
        "c2_f",
        "r_total_ohm",
        "tau1_s",
        "tau2_s",
        "i_amplitude_a",
        "temp_c",
        "v_initial_v",
    ]

    def __init__(
        self,
        alpha_c: float = 0.05,
        l1_ratio_c: float = 0.5,
        alpha_r: float = 0.05,
        l1_ratio_r: float = 0.5,
        max_cond_number: float = 1e5,
        max_fit_rmse_mv: float = 15.0,
    ):
        self.alpha_c = alpha_c
        self.l1_ratio_c = l1_ratio_c
        self.alpha_r = alpha_r
        self.l1_ratio_r = l1_ratio_r

        self.segmenter = PulseSegmenter()
        self.fitter = Ecm2RcFitter(max_cond_number=max_cond_number, max_fit_rmse_mv=max_fit_rmse_mv)

        self.scaler = StandardScaler()
        self.model_c = ElasticNet(alpha=self.alpha_c, l1_ratio=self.l1_ratio_c, random_state=42)
        self.model_r = ElasticNet(alpha=self.alpha_r, l1_ratio=self.l1_ratio_r, random_state=42)

        self.is_fitted = False
        self._sigma2_res_c: float = 1e-4
        self._sigma2_res_r: float = 1e-4
        self._xtx_inv_c: Optional[np.ndarray] = None
        self._xtx_inv_r: Optional[np.ndarray] = None

    def extract_features_from_ecm(
        self,
        params: Ecm2RcParameters,
        pulse: PulseRecord,
    ) -> np.ndarray:
        """Extract 11-dimensional feature vector from fitted ECM and pulse metadata."""
        v_init = float(pulse.v_pulse_v[0]) if len(pulse.v_pulse_v) > 0 else 3.3
        return np.array([
            params.r0_ohm,
            params.r1_ohm,
            params.c1_f,
            params.r2_ohm,
            params.c2_f,
            params.r_total_ohm,
            params.tau1_s,
            params.tau2_s,
            abs(pulse.i_amplitude_a),
            pulse.temp_c,
            v_init,
        ], dtype=float)

    def fit(self, dataset: SohDataset) -> "PulseElasticNetEstimator":
        """Extract pulse ECM features across training cohort and fit ElasticNet models."""
        x_list: List[np.ndarray] = []
        y_c_list: List[float] = []
        y_r_list: List[float] = []

        for cid, bdata in dataset.batteries.items():
            for cycle in bdata.cycles:
                if cycle.soh_c_bol_true is None:
                    continue

                pulses = self.segmenter.detect_pulses(
                    cycle.time_s,
                    cycle.voltage_v,
                    cycle.current_a,
                    cycle.temp_c,
                    cycle_index=cycle.cycle_index,
                )

                for p in pulses:
                    params, quality = self.fitter.fit_pulse(p)
                    if quality.is_eligible and params is not None:
                        feats = self.extract_features_from_ecm(params, p)
                        x_list.append(feats)
                        y_c_list.append(cycle.soh_c_bol_true)
                        soh_r_val = cycle.soh_r_bol_true if cycle.soh_r_bol_true is not None else 1.0
                        y_r_list.append(soh_r_val)

        if len(x_list) < 5:
            raise ValueError(f"Insufficient eligible pulse samples (found {len(x_list)}, need >= 5).")

        x_arr = np.array(x_list)
        y_c_arr = np.array(y_c_list)
        y_r_arr = np.array(y_r_list)

        # Scale features strictly on training data
        x_scaled = self.scaler.fit_transform(x_arr)

        self.model_c.fit(x_scaled, y_c_arr)
        self.model_r.fit(x_scaled, y_r_arr)

        preds_c = self.model_c.predict(x_scaled)
        preds_r = self.model_r.predict(x_scaled)

        n_samples, n_features = x_scaled.shape
        dof = max(1, n_samples - n_features)

        self._sigma2_res_c = float(np.sum((y_c_arr - preds_c) ** 2) / dof)
        self._sigma2_res_r = float(np.sum((y_r_arr - preds_r) ** 2) / dof)

        xtx = x_scaled.T @ x_scaled
        self._xtx_inv_c = np.linalg.pinv(xtx + self.alpha_c * np.eye(n_features))
        self._xtx_inv_r = np.linalg.pinv(xtx + self.alpha_r * np.eye(n_features))

        self.is_fitted = True
        return self

    def predict_pulse(self, pulse: PulseRecord) -> SohEstimate:
        """Inference on a single pulse record."""
        if not self.is_fitted:
            raise RuntimeError("Estimator must be fitted before predict_pulse().")

        params, quality = self.fitter.fit_pulse(pulse)
        if not quality.is_eligible or params is None:
            return SohEstimate(
                status=EstimationStatus.LOW_QUALITY_FEATURE,
                quality=quality,
            )

        raw_x = self.extract_features_from_ecm(params, pulse)
        x_scaled = self.scaler.transform(raw_x.reshape(1, -1))

        pred_c = float(self.model_c.predict(x_scaled)[0])
        pred_r = float(self.model_r.predict(x_scaled)[0])

        xtx_c = self._xtx_inv_c if self._xtx_inv_c is not None else np.eye(11)
        xtx_r = self._xtx_inv_r if self._xtx_inv_r is not None else np.eye(11)

        var_c = self._sigma2_res_c * (1.0 + float((x_scaled @ xtx_c @ x_scaled.T).item()))
        var_r = self._sigma2_res_r * (1.0 + float((x_scaled @ xtx_r @ x_scaled.T).item()))

        std_c = float(np.sqrt(max(1e-8, var_c)))
        std_r = float(np.sqrt(max(1e-8, var_r)))

        ci_95_c = (pred_c - 1.96 * std_c, pred_c + 1.96 * std_c)
        ci_95_r = (pred_r - 1.96 * std_r, pred_r + 1.96 * std_r)

        feats_dict = {name: float(val) for name, val in zip(self.FEATURE_NAMES, raw_x)}

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

    def predict_window(
        self,
        window: PartialWindow,
        features: Optional[Dict[str, float]] = None,
    ) -> SohEstimate:
        """Inference from a telemetry window: attempts pulse detection first."""
        if not self.is_fitted:
            raise RuntimeError("Estimator must be fitted before predict_window().")

        pulses = self.segmenter.detect_pulses(
            window.time_s,
            window.voltage_v,
            window.current_a,
            window.temp_c,
            cycle_index=window.cycle_index,
        )

        if not pulses:
            # Window does not contain a detectable pulse step
            return SohEstimate(
                status=EstimationStatus.INSUFFICIENT_INFORMATION,
                quality=FeatureQualityRecord(
                    is_eligible=False,
                    failure_reasons=["No qualified current pulse step found in window"],
                ),
            )

        # Predict using the first qualified pulse
        return self.predict_pulse(pulses[0])

    def predict_cycle(self, cycle: "CycleRecord") -> SohEstimate:
        """Inference on a complete cycle record by extracting pulse transients."""
        if not self.is_fitted:
            raise RuntimeError("Estimator must be fitted before predict_cycle().")

        pulses = self.segmenter.detect_pulses(
            cycle.time_s,
            cycle.voltage_v,
            cycle.current_a,
            cycle.temp_c,
            cycle_index=cycle.cycle_index,
        )

        if not pulses:
            return SohEstimate(
                status=EstimationStatus.INSUFFICIENT_INFORMATION,
                quality=FeatureQualityRecord(
                    is_eligible=False,
                    failure_reasons=["No qualified current pulse step found in cycle"],
                ),
            )

        return self.predict_pulse(pulses[0])

    def update_state(
        self,
        current_state: SOHState,
        estimate: SohEstimate,
        dt_s: float = 0.0,
    ) -> SOHState:
        """Kalman filter update step incorporating new pulse estimate."""
        if estimate.status != EstimationStatus.VALID or estimate.soh_c is None:
            return current_state

        meas_z = np.array([estimate.soh_c, estimate.soh_r if estimate.soh_r is not None else current_state.soh_r_bol])
        r_meas = np.diag([
            max(1e-6, estimate.variance_c or 1e-4),
            max(1e-6, estimate.variance_r or 1e-4),
        ])

        p_prior = current_state.covariance + np.diag([1e-6, 1e-6])
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

    def export_c_header(self, destination: Path) -> None:
        """Export model coefficients and standard scaler parameters to a C header."""
        if not self.is_fitted:
            raise RuntimeError("Cannot export unfitted model to C header.")

        destination.parent.mkdir(parents=True, exist_ok=True)
        means = self.scaler.mean_
        scales = self.scaler.scale_
        coefs_c = self.model_c.coef_
        intercept_c = self.model_c.intercept_
        coefs_r = self.model_r.coef_
        intercept_r = self.model_r.intercept_

        n_feats = len(self.FEATURE_NAMES)

        lines = [
            "/**",
            " * Auto-generated 2-RC ECM Pulse ElasticNet SOH Estimator Header",
            " * Microcontroller deployment: fixed feature inference without external libraries.",
            " */",
            "",
            "#ifndef SOH_PULSE_ELASTICNET_H",
            "#define SOH_PULSE_ELASTICNET_H",
            "",
            f"#define SOH_ECM_NUM_FEATURES {n_feats}",
            "",
            "/* Feature means for StandardScaler */",
            f"static const float SOH_SCALER_MEAN[{n_feats}] = {{ "
            + ", ".join(f"{m:.8e}f" for m in means)
            + " };",
            "",
            "/* Feature scales (stds) for StandardScaler */",
            f"static const float SOH_SCALER_SCALE[{n_feats}] = {{ "
            + ", ".join(f"{s:.8e}f" for s in scales)
            + " };",
            "",
            "/* Model weights for Capacity SOH (SOH_C) */",
            f"static const float SOH_C_COEFS[{n_feats}] = {{ "
            + ", ".join(f"{c:.8e}f" for c in coefs_c)
            + " };",
            f"static const float SOH_C_INTERCEPT = {intercept_c:.8e}f;",
            "",
            "/* Model weights for Resistance SOH (SOH_R) */",
            f"static const float SOH_R_COEFS[{n_feats}] = {{ "
            + ", ".join(f"{r:.8e}f" for r in coefs_r)
            + " };",
            f"static const float SOH_R_INTERCEPT = {intercept_r:.8e}f;",
            "",
            "/**",
            " * Lightweight embedded inference function.",
            " * Computes point estimates in O(N) operations.",
            " */",
            "static inline void soh_predict_pulse(",
            "    const float raw_features[SOH_ECM_NUM_FEATURES],",
            "    float* out_soh_c,",
            "    float* out_soh_r",
            ") {",
            "    float dot_c = SOH_C_INTERCEPT;",
            "    float dot_r = SOH_R_INTERCEPT;",
            "    for (int i = 0; i < SOH_ECM_NUM_FEATURES; ++i) {",
            "        float x_norm = (raw_features[i] - SOH_SCALER_MEAN[i]) / SOH_SCALER_SCALE[i];",
            "        dot_c += SOH_C_COEFS[i] * x_norm;",
            "        dot_r += SOH_R_COEFS[i] * x_norm;",
            "    }",
            "    if (out_soh_c) *out_soh_c = dot_c;",
            "    if (out_soh_r) *out_soh_r = dot_r;",
            "}",
            "",
            "#endif /* SOH_PULSE_ELASTICNET_H */",
            "",
        ]

        destination.write_text("\n".join(lines), encoding="utf-8")
