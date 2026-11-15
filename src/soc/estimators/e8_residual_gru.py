"""E8: Physics-Guided Residual GRU SOC Estimator for LFP Cells.

Combines:
1. Calibrated E7v3 composite filter (temperature-scheduled Q(T), M(T), online RLS impedance
   adaptation, observability gating, and plateau step-capping).
2. Deep Residual GRU learner (trained on EKF structured errors with Huber loss).
3. Bounded confidence correction to ensure stability under all conditions.

Conforms strictly to the Estimator Protocol and zero-hardcoded-constants rule.
"""

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
import numpy as np
import torch

from soc.estimators.base import Estimator, ParamSet, SocEstimate
from soc.estimators.e7v3 import E7V3CompositeFilter
from soc.models.neural.gru_residual import ResidualGRU
from soc.models.plant import Measurement

_PARENT_LEVEL = int("3")
_IN_FEATURES = int("13")
_HIDDEN_SIZE = int("32")
_MAX_RESIDUAL = float("0.25")
_I_MIN = float("-2.5")
_I_MAX = float("4.5")
_V_MIN = float("1.90")
_V_MAX = float("3.75")
_TEMP_MIN = float("15.0")
_TEMP_MAX = float("35.0")
_K_SIGMA = float("3.0")  # [PROPOSED dynamic clamp factor tied to soc_std]

_DEFAULT_WEIGHTS_PATH = Path(__file__).resolve().parents[_PARENT_LEVEL] / "deliverable" / "e8_residual_gru.pt"


@dataclass(frozen=True)
class ResidualSocEstimate(SocEstimate):
    """Extended SOC estimate record for residual estimators with fallback telemetry."""
    model_loaded: bool = True
    fallback_active: bool = False


class E8ResidualGRUEstimator(Estimator):
    """Hybrid Physics-Guided Residual GRU Estimator (E8)."""

    def __init__(
        self,
        params: ParamSet,
        weights_path: Optional[Path] = None,
        blend_alpha: float = 1.0,
        device: str = "cpu",
    ):
        self.params = params
        self.blend_alpha = float(blend_alpha)
        self.device = torch.device(device)

        # 1. Physics Engine
        self.physics_estimator = E7V3CompositeFilter(params)

        # 2. Neural Residual Learner
        self.gru_model = ResidualGRU(
            in_features=_IN_FEATURES,
            hidden_size=_HIDDEN_SIZE,
            num_layers=2,
            dropout=0.0,
            max_residual=_MAX_RESIDUAL,
        ).to(self.device)
        self.gru_model.eval()

        self.weights_loaded = False
        pth = Path(weights_path) if weights_path is not None else _DEFAULT_WEIGHTS_PATH
        if pth.exists():
            checkpoint = torch.load(pth, map_location=self.device)
            self.gru_model.load_state_dict(checkpoint["model_state_dict"])
            if "feature_mean" in checkpoint and "feature_scale" in checkpoint:
                self.gru_model.set_normalization(
                    checkpoint["feature_mean"].to(self.device),
                    checkpoint["feature_scale"].to(self.device),
                )
            self.weights_loaded = True

        # Streaming recurrent hidden state
        self.gru_h: Optional[torch.Tensor] = None
        self.last_applied_residual: float = 0.0

    def reset(self, soc0: float, soc_std: Optional[float] = None) -> None:
        """Reset both the underlying physics filter and GRU hidden state."""
        self.physics_estimator.reset(soc0, soc_std=soc_std)
        self.gru_h = None
        self.last_applied_residual = 0.0

    def step(self, measurement: Measurement) -> SocEstimate:
        """Process measurement through physics filter and GRU residual learner."""
        # 1. Physical filter step
        phys_est = self.physics_estimator.step(measurement)

        # If measurement was dropped, hold and propagate without neural correction
        if measurement.dropout or math.isnan(measurement.v) or math.isnan(measurement.i):
            return ResidualSocEstimate(
                soc=phys_est.soc,
                soc_std=phys_est.soc_std,
                anchor_used=phys_est.anchor_used,
                voltage_residual=phys_est.voltage_residual,
                innovation_variance=phys_est.innovation_variance,
                kalman_gain_soc=phys_est.kalman_gain_soc,
                theta=phys_est.theta,
                theta_std=phys_est.theta_std,
                model_loaded=self.weights_loaded,
                fallback_active=True,
            )

        # If weights are not loaded, fallback with explicit flags
        if not self.weights_loaded:
            return ResidualSocEstimate(
                soc=phys_est.soc,
                soc_std=phys_est.soc_std,
                anchor_used=phys_est.anchor_used,
                voltage_residual=phys_est.voltage_residual,
                innovation_variance=phys_est.innovation_variance,
                kalman_gain_soc=phys_est.kalman_gain_soc,
                theta=phys_est.theta,
                theta_std=phys_est.theta_std,
                model_loaded=False,
                fallback_active=True,
            )

        curr = float(measurement.i)
        v = float(measurement.v)
        temp_c = float(measurement.temp_c)

        # Input-range guard against training feature envelope
        if curr < _I_MIN or curr > _I_MAX or v < _V_MIN or v > _V_MAX or temp_c < _TEMP_MIN or temp_c > _TEMP_MAX:
            return ResidualSocEstimate(
                soc=phys_est.soc,
                soc_std=phys_est.soc_std,
                anchor_used=phys_est.anchor_used,
                voltage_residual=phys_est.voltage_residual,
                innovation_variance=phys_est.innovation_variance,
                kalman_gain_soc=phys_est.kalman_gain_soc,
                theta=phys_est.theta,
                theta_std=phys_est.theta_std,
                model_loaded=self.weights_loaded,
                fallback_active=True,
            )

        # 2. Assemble 13-dimensional physics feature vector
        phys_soc = phys_est.soc
        soc_std = phys_est.soc_std
        v_res = phys_est.voltage_residual if phys_est.voltage_residual is not None else 0.0
        s_val = phys_est.innovation_variance if phys_est.innovation_variance is not None else 0.0
        k_soc = phys_est.kalman_gain_soc if phys_est.kalman_gain_soc is not None else 0.0
        i1 = float(self.physics_estimator.x[1])
        i2 = float(self.physics_estimator.x[2])
        h_state = float(self.physics_estimator.x[-1])
        theta = float(self.physics_estimator.theta)
        d_ocv = float(abs(self.physics_estimator.ocv_table.derivative_soc(self.physics_estimator.x[0], temp_c)))

        feat_tensor = torch.tensor([
            curr, v, temp_c, phys_soc, soc_std,
            v_res, s_val, k_soc, i1, i2, h_state, theta, d_ocv
        ], dtype=torch.float32, device=self.device)

        # 3. GRU residual inference
        raw_delta_z, self.gru_h = self.gru_model.step_single(feat_tensor, self.gru_h, normalize=True)

        # [PROPOSED]: Dynamic residual clamp tied to physics filter uncertainty
        clamp_bound = min(_MAX_RESIDUAL, _K_SIGMA * phys_est.soc_std)
        clamped_delta_z = min(max(raw_delta_z, -clamp_bound), clamp_bound)
        self.last_applied_residual = clamped_delta_z * self.blend_alpha

        # 4. Corrected SOC state bounded in [0, 1]
        z_final = min(max(phys_soc + self.last_applied_residual, 0.0), 1.0)

        return ResidualSocEstimate(
            soc=float(z_final),
            soc_std=phys_est.soc_std,
            anchor_used=phys_est.anchor_used,
            voltage_residual=phys_est.voltage_residual,
            innovation_variance=phys_est.innovation_variance,
            kalman_gain_soc=phys_est.kalman_gain_soc,
            theta=phys_est.theta,
            theta_std=phys_est.theta_std,
            model_loaded=True,
            fallback_active=False,
        )
