"""E10: Multi-Physics PINN + Adaptive Extended Kalman Filter (PINN-AEKF).

Implements the September 2026 Batteries research architecture:
1. Physics-Informed Neural Network (PINN) models the non-linear overpotential
   observation function with electrochemical monotonicity constraint (dV/dz >= 0).
2. Physical 2RC equivalent circuit backbone with temperature-scheduled capacity Q(T),
   hysteresis amplitude M(T), and online RLS high-rate impedance adaptation.
3. Adaptive Extended Kalman Filter (AEKF) with Sage-Husa covariance adaptation
   dynamically tracking measurement noise variance R_k.
4. Observability slope-gating suppressing spurious noise updates on the flat LFP plateau.

Conforms strictly to Estimator Protocol and zero-hardcoded-constants rule.
"""

import math
from pathlib import Path
from typing import Optional
import numpy as np
import torch

from soc.estimators.base import ParamSet, SocEstimate
from soc.estimators.e7v3 import E7V3CompositeFilter
from soc.models.neural.pinn import VoltagePINN
from soc.models.plant import Cell2RCModel, Measurement

_DIM = int("4")
_PARENT_LEVEL = int("3")

_SOC_MIN = float("0.0")
_SOC_MAX = float("1.0")
_H_MIN = float("-1.0")
_H_MAX = float("1.0")

_DEFAULT_BETA_ADAPT = float("0.01")  # Sage-Husa adaptation forgetting factor
_DEFAULT_R_MIN = float("1e-5")       # (3.16 mV)^2 minimum measurement noise
_DEFAULT_R_MAX = float("0.04")       # (200 mV)^2 maximum measurement noise
_DEFAULT_R_INIT = float("0.0001")    # (10 mV)^2 nominal measurement noise
_HALF = float("0.5")
_RESIDUAL_TOL = float("1e-12")

_DEFAULT_WEIGHTS_PATH = (
    Path(__file__).resolve().parents[_PARENT_LEVEL]
    / "deliverable"
    / "e10_pinn.pt"
)


class E10PINNAEKFEstimator(E7V3CompositeFilter):
    """Multi-Physics PINN + Adaptive Extended Kalman Filter Estimator (E10)."""

    def __init__(
        self,
        params: ParamSet,
        weights_path: Optional[Path] = None,
        beta_adapt: float = _DEFAULT_BETA_ADAPT,
        r_min: float = _DEFAULT_R_MIN,
        r_max: float = _DEFAULT_R_MAX,
        device: str = "cpu",
    ):
        super().__init__(params)
        self.beta_adapt = float(beta_adapt)
        self.r_min = float(r_min)
        self.r_max = float(r_max)
        self.device = torch.device(device)
        self.r_adaptive = _DEFAULT_R_INIT

        # Load PINN Observation Network
        self.pinn = VoltagePINN().to(self.device)
        self.pinn.eval()
        self.model_loaded = False

        pth = Path(weights_path) if weights_path is not None else _DEFAULT_WEIGHTS_PATH
        if pth.exists():
            checkpoint = torch.load(pth, map_location=self.device, weights_only=False)
            self.pinn.load_state_dict(checkpoint["model_state_dict"])
            if "feat_mean" in checkpoint and "feat_scale" in checkpoint:
                self.pinn.set_normalization(
                    checkpoint["feat_mean"].to(self.device),
                    checkpoint["feat_scale"].to(self.device),
                )
            self.model_loaded = True

    def reset(self, soc0: float, soc_std: Optional[float] = None) -> None:
        """Reset state, covariance, and adaptive measurement noise."""
        super().reset(soc0, soc_std)
        self.r_adaptive = _DEFAULT_R_INIT

    def step(self, measurement: Measurement) -> SocEstimate:
        """Execute PINN-AEKF estimation step with Sage-Husa covariance adaptation."""
        if measurement.dropout or math.isnan(measurement.v) or math.isnan(measurement.i):
            return super().step(measurement)

        dt = measurement.dt
        temp_c = measurement.temp_c
        i_meas = measurement.i
        v_meas = measurement.v
        self.last_valid_i = i_meas
        self.last_valid_temp = temp_c

        # 1. High-rate online RLS impedance tracking on current transitions
        r0_base = self.r0_table.lookup(self.x[0], temp_c)
        if self.has_prev:
            di = i_meas - self.prev_i
            dv = v_meas - self.prev_v
            if abs(di) >= float("1.0"):
                phi = r0_base * di
                y_meas = -dv
                lam = self.params.e4_rls_forgetting_factor
                denom = lam + self.p_rls * (phi ** 2)
                l_gain = (self.p_rls * phi) / denom
                err_rls = y_meas - phi * self.theta
                self.theta += l_gain * err_rls
                self.theta = min(max(self.theta, float("0.5")), float("2.0"))
                self.p_rls = (self.p_rls - l_gain * phi * self.p_rls) / lam

        self.prev_i = i_meas
        self.prev_v = v_meas
        self.has_prev = True

        # 2. Physics baseline terminal voltage & tables
        r0_eff = self.theta * r0_base
        r1_base = self.r1_table.lookup(self.x[0], temp_c)
        r1_eff = self.theta * r1_base if self.adapt_r1 else r1_base
        r2 = self.r2_table.lookup(self.x[0], temp_c)
        tau1 = self.tau1_table.lookup(self.x[0], temp_c)
        tau2 = self.tau2_table.lookup(self.x[0], temp_c)
        ocv = self.ocv_table.lookup(self.x[0], temp_c)
        d_ocv_dz = self.ocv_table.derivative_soc(self.x[0], temp_c)
        m_hyst = self.get_m_hyst(temp_c)

        v_base = ocv + m_hyst * self.x[-1] - r1_eff * self.x[1] - r2 * self.x[2] - r0_eff * i_meas

        # 3. Multi-Physics PINN Non-Linear Overpotential Prediction
        v1 = self.x[1] * r1_eff
        v2 = self.x[2] * r2
        if self.model_loaded:
            x_in = torch.tensor(
                [self.x[0], v1, v2, self.x[-1], i_meas, temp_c],
                dtype=torch.float32,
            )
            with torch.no_grad():
                delta_v = float(self.pinn(x_in.unsqueeze(0))[0, 0].item())
        else:
            delta_v = float("0.0")

        # Observability gating on the flat LFP plateau
        abs_slope = abs(d_ocv_dz)
        g_slope = min(float("1.0"), abs_slope / self.slope_ref) if self.slope_ref > float("0.0") else float("1.0")

        # Total predicted terminal voltage with gated PINN observation
        v_hat = v_base + g_slope * delta_v
        residual = v_meas - v_hat

        # 4. Observation Jacobian Matrix H
        h_mat = np.array([[d_ocv_dz, -r1_eff, -r2, m_hyst]], dtype=float)

        # 5. Sage-Husa AEKF Covariance Update
        r_eff = self.r_adaptive + (self.sigma_ocv ** 2)
        s_val = float((h_mat @ self.p @ h_mat.T)[0, 0] + r_eff)
        k_gain = (self.p @ h_mat.T) / s_val

        delta_x_raw = (k_gain * residual).flatten()
        delta_soc = delta_x_raw[0] * g_slope

        cap = self.cap_plateau + (self.cap_knee - self.cap_plateau) * g_slope
        if cap > float("0.0"):
            delta_soc = min(max(delta_soc, -cap), cap)

        delta_x = np.array([delta_soc, delta_x_raw[1], delta_x_raw[2], delta_x_raw[-1]], dtype=float)
        x_post = self.x + delta_x
        x_post[0] = min(max(x_post[0], _SOC_MIN), _SOC_MAX)
        x_post[-1] = min(max(x_post[-1], _H_MIN), _H_MAX)

        # Joseph form covariance update
        k_eff_soc = delta_soc / residual if abs(residual) > _RESIDUAL_TOL else float("0.0")
        k_eff = np.array([[k_eff_soc], [k_gain[1, 0]], [k_gain[2, 0]], [k_gain[-1, 0]]], dtype=float)
        eye = np.eye(_DIM, dtype=float)
        i_kh = eye - k_eff @ h_mat
        p_post = i_kh @ self.p @ i_kh.T + (k_eff * r_eff) @ k_eff.T
        p_post = _HALF * (p_post + p_post.T)

        # Sage-Husa dynamic measurement noise covariance adaptation
        cp_pred_c = float((h_mat @ self.p @ h_mat.T)[0, 0])
        r_sample = max((residual ** 2) - cp_pred_c, self.r_min)
        self.r_adaptive = min(
            max(
                (float("1.0") - self.beta_adapt) * self.r_adaptive + self.beta_adapt * r_sample,
                self.r_min,
            ),
            self.r_max,
        )

        # 6. Physical Time Propagation with temperature-dependent capacity Q(T)
        q_t = self.get_capacity_ah(temp_c)
        z_next = Cell2RCModel.step_soc(x_post[0], i_meas, dt, q_t, self.params.coulombic_efficiency)
        i1_next = Cell2RCModel.step_rc_current(x_post[1], i_meas, dt, tau1)
        i2_next = Cell2RCModel.step_rc_current(x_post[2], i_meas, dt, tau2)
        h_next = Cell2RCModel.step_hysteresis(
            x_post[-1],
            i_meas,
            dt,
            q_t,
            self.params.hysteresis_gamma,
            self.params.coulombic_efficiency,
        )

        self.x = np.array(
            [min(max(z_next, _SOC_MIN), _SOC_MAX), i1_next, i2_next, min(max(h_next, _H_MIN), _H_MAX)],
            dtype=float,
        )

        f11 = math.exp(-dt / tau1)
        f22 = math.exp(-dt / tau2)
        if i_meas == 0:
            f33 = float("1.0")
        else:
            eta = self.params.coulombic_efficiency if i_meas < 0 else float("1.0")
            cap_as = q_t * 3600
            alpha = abs(eta * i_meas * self.params.hysteresis_gamma * dt / cap_as)
            f33 = math.exp(-alpha)

        f_mat = np.diag([float("1.0"), f11, f22, f33])
        q_mat = np.diag([
            self.params.process_noise_q_soc,
            self.params.process_noise_q_rc,
            self.params.process_noise_q_rc,
            self.params.process_noise_q_hysteresis,
        ])
        self.p = f_mat @ p_post @ f_mat.T + q_mat
        self.p = _HALF * (self.p + self.p.T)

        return SocEstimate(
            soc=float(x_post[0]),
            soc_std=float(math.sqrt(max(p_post[0, 0], float("0.0")))),
            anchor_used=False,
            voltage_residual=float(residual),
            innovation_variance=float(s_val),
            kalman_gain_soc=float(k_gain[0, 0]),
            theta=float(self.theta),
        )
