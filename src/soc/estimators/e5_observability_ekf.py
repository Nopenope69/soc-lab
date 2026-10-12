"""E5: Observability-Gated Extended Kalman Filter (Observability-EKF).

Reference:
    Shi et al. (2026), "Fisher Information Guided State of Charge Estimation for
    Lithium Iron Phosphate Batteries", Energy and AI.

Mathematical Formulation & Adaptation:
    State vector:
        x = [soc, i1, i2, h]^T
    Observation:
        v_k = OCV(soc_k, T_k) + M * h_k - R1 * i1_k - R2 * i2_k - R0 * i_k
    Observation matrix:
        H = [d_OCV/dz, -R1, -R2, M]

    Observability-Gated Voltage Trust:
    (a) Measurement variance inflation:
        R_eff = R_v + sigma_ocv_model^2   (if e5_enable_r_inflation else R_v)
        S = H P H^T + R_eff
        K = P H^T S^{-1}
    (b) Slope-based observability gating:
        Raw SOC correction: delta_soc_raw = K[0] * residual
        Observability gain: g = min(1.0, |d_OCV/dz| / slope_ref)
        delta_soc_gated = delta_soc_raw * g   (if e5_enable_slope_gating else delta_soc_raw)
    (c) Per-step correction cap:
        delta_soc_capped = clip(delta_soc_gated, -delta_soc_max, delta_soc_max)
        (if e5_enable_step_cap else delta_soc_gated)

    Covariance Consistency:
        K_eff = [delta_soc_capped / residual, K[1], K[2], K[3]]^T  (for residual != 0)
        P^+ = (I - K_eff H) P (I - K_eff H)^T + K_eff R_eff K_eff^T   (Joseph form)

Assumptions (differences from Shi et al., 2026):
    - Assumption 1 (Discrete-Time EKF Adaptation): Shi et al. propose a continuous
      Fisher-information weighting framework. E5 adapts this principle into a
      discrete-time Extended Kalman Filter with a 2RC equivalent circuit model and
      one-state hysteresis.
    - Assumption 2 (State-Selective Gating): The observability gating and step capping
      are applied specifically to the SOC correction state. The RC polarization currents
      (i1, i2) and hysteresis state (h) retain full Kalman gain corrections to maintain
      dynamic voltage tracking.
    - Assumption 3 (Covariance Consistency via Effective Gain): An effective gain K_eff
      is computed to update the error covariance P via Joseph form. When corrections on the
      flat plateau are suppressed (g -> 0), K_eff[0] -> 0, preventing artificial collapse
      of SOC error covariance.
    - Assumption 4 (Additive Model Uncertainty): Model uncertainty in the plateau OCV is
      formulated as an additive variance term sigma_ocv_model^2 added to measurement noise
      variance R_v.
    - Assumption 5 (Non-linear Step Capping): Per-step correction capping bounds single-step
      perturbations during severe transient voltage dynamics or measurement noise spikes.
    - Assumption 6 (Dropout Handling): On dropped samples (dropout=True or NaN), E5 executes
      time propagation only (predict-only) identical to E2.
"""

import math
from typing import Optional
import numpy as np

from soc.estimators.base import Estimator, ParamSet, SocEstimate
from soc.models.cell_2rc import Cell2RCModel
from soc.models.plant import Measurement
from soc.models.tables import InterpolatedTable2D


class E5ObservabilityEKF(Estimator):
    """E5: 2RC equivalent circuit model with observability-gated EKF."""

    def __init__(self, params: ParamSet):
        self.params = params
        temps = list(self.params.temperatures_c)
        socs = list(self.params.soc_grid)

        # 2D parameter look-up tables
        self.ocv_table = InterpolatedTable2D(temps, socs, self.params.ocv_table)
        self.r0_table = InterpolatedTable2D(temps, socs, self.params.r0_table)
        self.r1_table = InterpolatedTable2D(temps, socs, self.params.r1_table)
        self.tau1_table = InterpolatedTable2D(temps, socs, self.params.tau1_table)
        self.r2_table = InterpolatedTable2D(temps, socs, self.params.r2_table)
        self.tau2_table = InterpolatedTable2D(temps, socs, self.params.tau2_table)

        # State vector: [soc, i1, i2, h]^T
        self.x = np.array([float(0), float(0), float(0), float(0)], dtype=float)
        # Covariance matrix: 4x4
        self.p = np.zeros((len(self.x), len(self.x)), dtype=float)

        self.last_valid_i = float(0)
        self.last_valid_temp = float(self.params.temperatures_c[1])
        self.last_applied_g = float(1)
        self.last_applied_delta_soc = float(0)

    def reset(self, soc0: float) -> None:
        """Reset estimator state and covariance."""
        soc_clamped = min(max(float(soc0), float(0)), float(1))
        self.x = np.array([soc_clamped, float(0), float(0), float(0)], dtype=float)

        # Initialize covariance P: diag([P_soc, P_rc, P_rc, P_h])
        p_soc = self.params.initial_soc_std ** 2
        p_rc = self.params.initial_rc_current_std_a ** 2
        p_h = self.params.initial_hysteresis_std ** 2
        self.p = np.diag([p_soc, p_rc, p_rc, p_h]).astype(float)

        self.last_valid_i = float(0)
        self.last_valid_temp = float(self.params.temperatures_c[1])
        self.last_applied_g = float(1)
        self.last_applied_delta_soc = float(0)

    def step(self, measurement: Measurement) -> SocEstimate:
        """Execute observability-gated EKF update and propagation."""
        dt = measurement.dt

        # Handle dropped measurement
        if measurement.dropout or math.isnan(measurement.v) or math.isnan(measurement.i):
            i_prop = self.last_valid_i
            temp_prop = self.last_valid_temp

            tau1 = self.tau1_table.lookup(self.x[0], temp_prop)
            tau2 = self.tau2_table.lookup(self.x[0], temp_prop)

            # Time propagation only
            z_next = Cell2RCModel.step_soc(
                soc=self.x[0],
                i_a=i_prop,
                dt_s=dt,
                capacity_ah=self.params.nominal_capacity_ah,
                coulombic_efficiency=self.params.coulombic_efficiency,
            )
            i1_next = Cell2RCModel.step_rc_current(self.x[1], i_prop, dt, tau1)
            i2_next = Cell2RCModel.step_rc_current(self.x[2], i_prop, dt, tau2)
            h_next = Cell2RCModel.step_hysteresis(
                h=self.x[-1],
                i_a=i_prop,
                dt_s=dt,
                capacity_ah=self.params.nominal_capacity_ah,
                gamma=self.params.hysteresis_gamma,
                coulombic_efficiency=self.params.coulombic_efficiency,
            )

            self.x = np.array([
                min(max(z_next, float(0)), float(1)),
                i1_next,
                i2_next,
                min(max(h_next, float(-1)), float(1)),
            ], dtype=float)

            # Transition Jacobian F
            f11 = math.exp(-dt / tau1)
            f22 = math.exp(-dt / tau2)
            if i_prop == float(0):
                f33 = float(1)
            else:
                eta = self.params.coulombic_efficiency if i_prop < float(0) else float(1)
                cap_as = self.params.nominal_capacity_ah * 3600
                alpha = abs(eta * i_prop * self.params.hysteresis_gamma * dt / cap_as)
                f33 = math.exp(-alpha)

            f_mat = np.diag([float(1), f11, f22, f33])
            q_mat = np.diag([
                self.params.process_noise_q_soc,
                self.params.process_noise_q_rc,
                self.params.process_noise_q_rc,
                self.params.process_noise_q_hysteresis,
            ])
            self.p = f_mat @ self.p @ f_mat.T + q_mat
            self.p = (self.p + self.p.T) / 2

            return SocEstimate(
                soc=float(self.x[0]),
                soc_std=float(math.sqrt(max(self.p[0, 0], float(0)))),
                anchor_used=False,
                voltage_residual=None,
                innovation_variance=None,
            )

        # Valid measurement: update last valid inputs
        self.last_valid_i = measurement.i
        self.last_valid_temp = measurement.temp_c
        temp_c = measurement.temp_c
        i_meas = measurement.i
        v_meas = measurement.v

        # 1. Measurement update (correction of prior x_k)
        soc_prior = self.x[0]
        i1_prior = self.x[1]
        i2_prior = self.x[2]
        h_prior = self.x[-1]

        r0 = self.r0_table.lookup(soc_prior, temp_c)
        r1 = self.r1_table.lookup(soc_prior, temp_c)
        r2 = self.r2_table.lookup(soc_prior, temp_c)
        tau1 = self.tau1_table.lookup(soc_prior, temp_c)
        tau2 = self.tau2_table.lookup(soc_prior, temp_c)
        ocv = self.ocv_table.lookup(soc_prior, temp_c)
        d_ocv_dz = self.ocv_table.derivative_soc(soc_prior, temp_c)
        m_hyst = self.params.hysteresis_amplitude_v

        # Predicted terminal voltage
        v_hat = ocv + m_hyst * h_prior - r1 * i1_prior - r2 * i2_prior - r0 * i_meas
        residual = v_meas - v_hat

        # Observation matrix H: 1x4
        h_mat = np.array([[d_ocv_dz, -r1, -r2, m_hyst]], dtype=float)

        # (a) Measurement variance inflation
        r_base = self.params.measurement_noise_r_v
        if self.params.e5_enable_r_inflation:
            r_eff = r_base + (self.params.e5_sigma_ocv_model_v ** 2)
        else:
            r_eff = r_base

        # Innovation covariance S
        s_val = float((h_mat @ self.p @ h_mat.T)[0, 0] + r_eff)

        # Kalman gain K: 4x1
        k_gain = (self.p @ h_mat.T) / s_val

        # Raw state correction
        delta_x_raw = (k_gain * residual).flatten()
        delta_soc = delta_x_raw[0]

        # (b) Slope-based observability gating
        g_slope = float(1)
        if self.params.e5_enable_slope_gating and self.params.e5_slope_ref > float(0):
            abs_slope = abs(d_ocv_dz)
            g_slope = min(float(1), abs_slope / self.params.e5_slope_ref)
            delta_soc = delta_soc * g_slope

        self.last_applied_g = float(g_slope)

        # (c) Per-step correction cap
        if self.params.e5_enable_step_cap:
            if self.params.e5_use_observability_cap:
                cap_plateau = self.params.e5_cap_plateau
                cap_knee = self.params.e5_cap_knee
                cap = cap_plateau + (cap_knee - cap_plateau) * g_slope
            else:
                cap = self.params.e5_max_soc_step

            if cap > float(0):
                delta_soc = min(max(delta_soc, -cap), cap)

        self.last_applied_delta_soc = float(delta_soc)

        # State correction vector
        delta_x = np.array([
            delta_soc,
            delta_x_raw[1],
            delta_x_raw[2],
            delta_x_raw[-1],
        ], dtype=float)

        x_post = self.x + delta_x
        # Clamp SOC to [0, 1] and h to [-1, 1]
        x_post[0] = min(max(x_post[0], float(0)), float(1))
        x_post[-1] = min(max(x_post[-1], float(-1)), float(1))

        # Effective Kalman gain for Joseph covariance update
        k_eff = np.copy(k_gain)
        if abs(residual) > float(0):
            k_eff[0, 0] = delta_soc / residual
        else:
            k_eff[0, 0] = k_gain[0, 0] * g_slope

        # Joseph form covariance update: P = (I - K_eff*H)*P*(I - K_eff*H)^T + K_eff*R_eff*K_eff^T
        eye = np.eye(len(self.x), dtype=float)
        i_kh = eye - k_eff @ h_mat
        p_post = i_kh @ self.p @ i_kh.T + (k_eff * r_eff) @ k_eff.T
        p_post = (p_post + p_post.T) / 2

        # 2. Time propagation (prediction to state x_(k+1))
        z_next = Cell2RCModel.step_soc(
            soc=x_post[0],
            i_a=i_meas,
            dt_s=dt,
            capacity_ah=self.params.nominal_capacity_ah,
            coulombic_efficiency=self.params.coulombic_efficiency,
        )
        i1_next = Cell2RCModel.step_rc_current(x_post[1], i_meas, dt, tau1)
        i2_next = Cell2RCModel.step_rc_current(x_post[2], i_meas, dt, tau2)
        h_next = Cell2RCModel.step_hysteresis(
            h=x_post[-1],
            i_a=i_meas,
            dt_s=dt,
            capacity_ah=self.params.nominal_capacity_ah,
            gamma=self.params.hysteresis_gamma,
            coulombic_efficiency=self.params.coulombic_efficiency,
        )

        self.x = np.array([
            min(max(z_next, float(0)), float(1)),
            i1_next,
            i2_next,
            min(max(h_next, float(-1)), float(1)),
        ], dtype=float)

        # Propagate covariance P
        f11 = math.exp(-dt / tau1)
        f22 = math.exp(-dt / tau2)
        if i_meas == float(0):
            f33 = float(1)
        else:
            eta = self.params.coulombic_efficiency if i_meas < float(0) else float(1)
            cap_as = self.params.nominal_capacity_ah * 3600
            alpha = abs(eta * i_meas * self.params.hysteresis_gamma * dt / cap_as)
            f33 = math.exp(-alpha)

        f_mat = np.diag([float(1), f11, f22, f33])
        q_mat = np.diag([
            self.params.process_noise_q_soc,
            self.params.process_noise_q_rc,
            self.params.process_noise_q_rc,
            self.params.process_noise_q_hysteresis,
        ])
        self.p = f_mat @ p_post @ f_mat.T + q_mat
        self.p = (self.p + self.p.T) / 2

        return SocEstimate(
            soc=float(self.x[0]),
            soc_std=float(math.sqrt(max(self.p[0, 0], float(0)))),
            anchor_used=False,
            voltage_residual=float(residual),
            innovation_variance=float(s_val),
            kalman_gain_soc=float(k_eff[0, 0]),
        )
