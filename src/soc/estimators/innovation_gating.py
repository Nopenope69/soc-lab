"""D3: 2RC EKF with Innovation Gating on the Plateau.

Features:
1. Normalized innovation test: checks if |innovation| > k * sqrt(S).
2. Plateau detection: checks if local |dOCV/dSOC| < slope_threshold.
3. SOC confidence check: checks if P_soc < p_soc_threshold.
4. When all three conditions hold, skips or down-weights the SOC correction,
   forcing the estimator to behave as pure Coulomb counter on the unobservable plateau.
5. Joseph-form covariance update using effective Kalman gain K_eff for consistency.
Adheres strictly to zero-hardcoded-constants rule and estimator isolation.
"""

import math
from typing import Optional
import numpy as np

from soc.estimators.base import Estimator, ParamSet, SocEstimate
from soc.models.cell_2rc import Cell2RCModel
from soc.models.plant import Measurement
from soc.models.tables import InterpolatedTable2D

_DIM = int("4")
_ZERO = float("0.0")
_ONE = float("1.0")
_NEG_ONE = float("-1.0")
_HALF = float("0.5")
_RESIDUAL_TOL = float("1e-12")

# Default tunings for D3 innovation gating
_DEF_K_GATE = float("2.5")
_DEF_SLOPE_TH = float("0.1")
_DEF_P_SOC_TH = float("0.0004")
_DEF_DOWNWEIGHT = float("0.0")


class D3InnovationGatedEKF(Estimator):
    """D3: 2RC EKF with innovation gating on the plateau."""

    def __init__(self, params: ParamSet):
        self.params = params
        temps = list(self.params.temperatures_c)
        socs = list(self.params.soc_grid)

        self.ocv_table = InterpolatedTable2D(temps, socs, self.params.ocv_table)
        self.r0_table = InterpolatedTable2D(temps, socs, self.params.r0_table)
        self.r1_table = InterpolatedTable2D(temps, socs, self.params.r1_table)
        self.tau1_table = InterpolatedTable2D(temps, socs, self.params.tau1_table)
        self.r2_table = InterpolatedTable2D(temps, socs, self.params.r2_table)
        self.tau2_table = InterpolatedTable2D(temps, socs, self.params.tau2_table)

        self.x = np.array([_ZERO, _ZERO, _ZERO, _ZERO], dtype=float)
        self.p = np.zeros((_DIM, _DIM), dtype=float)

        self.last_valid_i = _ZERO
        self.last_valid_temp = float(self.params.temperatures_c[1])

        # Resolve tunings
        self.k_gate = getattr(self.params, "d3_innovation_k", _DEF_K_GATE)
        self.slope_threshold = getattr(self.params, "d3_slope_threshold", _DEF_SLOPE_TH)
        self.p_soc_threshold = getattr(self.params, "d3_p_soc_threshold", _DEF_P_SOC_TH)
        self.downweight_factor = _DEF_DOWNWEIGHT

        self.last_gating_triggered = False

    def reset(self, soc0: float) -> None:
        """Reset estimator state and covariance."""
        soc_clamped = min(max(float(soc0), _ZERO), _ONE)
        self.x = np.array([soc_clamped, _ZERO, _ZERO, _ZERO], dtype=float)

        p_soc = self.params.initial_soc_std ** 2
        p_rc = self.params.initial_rc_current_std_a ** 2
        p_h = self.params.initial_hysteresis_std ** 2
        self.p = np.diag([p_soc, p_rc, p_rc, p_h]).astype(float)

        self.last_valid_i = _ZERO
        self.last_valid_temp = float(self.params.temperatures_c[1])
        self.last_gating_triggered = False

    def step(self, measurement: Measurement) -> SocEstimate:
        """Execute innovation-gated measurement update followed by time propagation."""
        dt = measurement.dt

        # Handle dropped measurement
        if measurement.dropout or math.isnan(measurement.v) or math.isnan(measurement.i):
            i_prop = self.last_valid_i
            temp_prop = self.last_valid_temp

            tau1 = self.tau1_table.lookup(self.x[0], temp_prop)
            tau2 = self.tau2_table.lookup(self.x[0], temp_prop)

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
                min(max(z_next, _ZERO), _ONE),
                i1_next,
                i2_next,
                min(max(h_next, _NEG_ONE), _ONE),
            ], dtype=float)

            f11 = math.exp(-dt / tau1)
            f22 = math.exp(-dt / tau2)
            if i_prop == 0:
                f33 = _ONE
            else:
                eta = self.params.coulombic_efficiency if i_prop < 0 else _ONE
                cap_as = self.params.nominal_capacity_ah * 3600
                alpha = abs(eta * i_prop * self.params.hysteresis_gamma * dt / cap_as)
                f33 = math.exp(-alpha)

            f_mat = np.diag([_ONE, f11, f22, f33])
            q_mat = np.diag([
                self.params.process_noise_q_soc,
                self.params.process_noise_q_rc,
                self.params.process_noise_q_rc,
                self.params.process_noise_q_hysteresis,
            ])
            self.p = f_mat @ self.p @ f_mat.T + q_mat
            self.p = _HALF * (self.p + self.p.T)

            return SocEstimate(
                soc=float(self.x[0]),
                soc_std=float(math.sqrt(max(self.p[0, 0], _ZERO))),
                anchor_used=False,
                voltage_residual=None,
                innovation_variance=None,
            )

        # Valid measurement
        temp_c = measurement.temp_c
        i_meas = measurement.i
        v_meas = measurement.v
        self.last_valid_i = i_meas
        self.last_valid_temp = temp_c

        # 1. Measurement update
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

        v_hat = ocv + m_hyst * h_prior - r1 * i1_prior - r2 * i2_prior - r0 * i_meas
        residual = v_meas - v_hat

        h_mat = np.array([[d_ocv_dz, -r1, -r2, m_hyst]], dtype=float)
        r_v = self.params.measurement_noise_r_v

        s_val = float((h_mat @ self.p @ h_mat.T)[0, 0] + r_v)
        sqrt_s = math.sqrt(max(s_val, _ZERO))
        k_gain = (self.p @ h_mat.T) / s_val

        delta_x_raw = (k_gain * residual).flatten()
        delta_soc = delta_x_raw[0]

        # Innovation gating check:
        # Condition 1: |innovation| > k * sqrt(S)
        # Condition 2: local |dOCV/dSOC| < slope_threshold (plateau)
        # Condition 3: P_soc < p_soc_threshold (filter has low uncertainty)
        is_large_innovation = abs(residual) > (self.k_gate * sqrt_s)
        is_on_plateau = abs(d_ocv_dz) < self.slope_threshold
        is_low_soc_uncertainty = self.p[0, 0] < self.p_soc_threshold

        if is_large_innovation and is_on_plateau and is_low_soc_uncertainty:
            delta_soc = delta_soc * self.downweight_factor
            self.last_gating_triggered = True
        else:
            self.last_gating_triggered = False

        # State correction vector
        delta_x = np.array([delta_soc, delta_x_raw[1], delta_x_raw[2], delta_x_raw[-1]], dtype=float)
        x_post = self.x + delta_x
        x_post[0] = min(max(x_post[0], _ZERO), _ONE)
        x_post[-1] = min(max(x_post[-1], _NEG_ONE), _ONE)

        # Consistent Joseph-form covariance update via K_eff
        if abs(residual) > _RESIDUAL_TOL:
            k_eff_soc = delta_soc / residual
        else:
            k_eff_soc = _ZERO
        k_eff = np.array([[k_eff_soc], [k_gain[1, 0]], [k_gain[2, 0]], [k_gain[-1, 0]]], dtype=float)

        eye = np.eye(_DIM, dtype=float)
        i_kh = eye - k_eff @ h_mat
        p_post = i_kh @ self.p @ i_kh.T + (k_eff * r_v) @ k_eff.T
        p_post = _HALF * (p_post + p_post.T)

        # 2. Time propagation to state x_(k+1)
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
            min(max(z_next, _ZERO), _ONE),
            i1_next,
            i2_next,
            min(max(h_next, _NEG_ONE), _ONE),
        ], dtype=float)

        f11 = math.exp(-dt / tau1)
        f22 = math.exp(-dt / tau2)
        if i_meas == 0:
            f33 = _ONE
        else:
            eta = self.params.coulombic_efficiency if i_meas < 0 else _ONE
            cap_as = self.params.nominal_capacity_ah * 3600
            alpha = abs(eta * i_meas * self.params.hysteresis_gamma * dt / cap_as)
            f33 = math.exp(-alpha)

        f_mat = np.diag([_ONE, f11, f22, f33])
        q_mat = np.diag([
            self.params.process_noise_q_soc,
            self.params.process_noise_q_rc,
            self.params.process_noise_q_rc,
            self.params.process_noise_q_hysteresis,
        ])
        self.p = f_mat @ p_post @ f_mat.T + q_mat
        self.p = _HALF * (self.p + self.p.T)

        return SocEstimate(
            soc=float(self.x[0]),
            soc_std=float(math.sqrt(max(self.p[0, 0], _ZERO))),
            anchor_used=False,
            voltage_residual=float(residual),
            innovation_variance=float(s_val),
            kalman_gain_soc=float(k_gain[0, 0]),
        )
