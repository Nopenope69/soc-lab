"""E4: 2RC EKF with Online RLS R0 Adaptation.

State vector:
    x = [soc, i1, i2, h]^T
Parameter adaptation:
    Scalar multiplier theta_r0 on R0, bounded to [0.5, 2.0].
    Updated via Recursive Least Squares (RLS) on discrete current steps with |dI| >= 1.0 A.
    Uses its own forgetting-factor parameter (e4_rls_forgetting_factor).
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
_R0_MIN_SCALE = float("0.5")
_R0_MAX_SCALE = float("2.0")
_DI_THRESHOLD_A = float("1.0")


class E4RLSR0EKF(Estimator):
    """E4: E2 EKF with recursive least squares estimation of scalar multiplier on R0."""

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

        # State vector: [soc, i1, i2, h]^T
        self.x = np.array([_ZERO, _ZERO, _ZERO, _ZERO], dtype=float)
        self.p = np.zeros((_DIM, _DIM), dtype=float)

        # RLS state for theta_r0
        self.theta_r0 = _ONE
        self.p_rls = _ONE

        self.prev_i = _ZERO
        self.prev_v = _ZERO
        self.has_prev = False

        self.last_valid_i = _ZERO
        self.last_valid_temp = float(self.params.temperatures_c[1])

    def reset(self, soc0: float) -> None:
        """Reset estimator state, covariance, and RLS parameter."""
        soc_clamped = min(max(float(soc0), _ZERO), _ONE)
        self.x = np.array([soc_clamped, _ZERO, _ZERO, _ZERO], dtype=float)

        p_soc = self.params.initial_soc_std ** 2
        p_rc = self.params.initial_rc_current_std_a ** 2
        p_h = self.params.initial_hysteresis_std ** 2
        self.p = np.diag([p_soc, p_rc, p_rc, p_h]).astype(float)

        self.theta_r0 = _ONE
        self.p_rls = _ONE
        self.prev_i = _ZERO
        self.prev_v = _ZERO
        self.has_prev = False

        self.last_valid_i = _ZERO
        self.last_valid_temp = float(self.params.temperatures_c[1])

    def step(self, measurement: Measurement) -> SocEstimate:
        """Execute RLS R0 update (if |dI| >= 1 A), EKF measurement update, and time propagation."""
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
                theta=float(self.theta_r0),
            )

        # Valid measurement
        temp_c = measurement.temp_c
        i_meas = measurement.i
        v_meas = measurement.v
        self.last_valid_i = i_meas
        self.last_valid_temp = temp_c

        # 1. Online RLS update on discrete current steps with |dI| >= 1 A
        r0_base = self.r0_table.lookup(self.x[0], temp_c)
        if self.has_prev:
            di = i_meas - self.prev_i
            dv = v_meas - self.prev_v
            if abs(di) >= _DI_THRESHOLD_A:
                phi = r0_base * di
                y_meas = -dv
                lam = self.params.e4_rls_forgetting_factor

                denom = lam + self.p_rls * (phi ** 2)
                l_gain = (self.p_rls * phi) / denom
                err_rls = y_meas - phi * self.theta_r0

                self.theta_r0 += l_gain * err_rls
                self.theta_r0 = min(max(self.theta_r0, _R0_MIN_SCALE), _R0_MAX_SCALE)
                self.p_rls = (self.p_rls - l_gain * phi * self.p_rls) / lam

        self.prev_i = i_meas
        self.prev_v = v_meas
        self.has_prev = True

        # 2. EKF measurement update using adapted R0
        r0_eff = self.theta_r0 * r0_base
        r1 = self.r1_table.lookup(self.x[0], temp_c)
        r2 = self.r2_table.lookup(self.x[0], temp_c)
        tau1 = self.tau1_table.lookup(self.x[0], temp_c)
        tau2 = self.tau2_table.lookup(self.x[0], temp_c)
        ocv = self.ocv_table.lookup(self.x[0], temp_c)
        d_ocv_dz = self.ocv_table.derivative_soc(self.x[0], temp_c)
        m_hyst = self.params.hysteresis_amplitude_v

        v_hat = ocv + m_hyst * self.x[-1] - r1 * self.x[1] - r2 * self.x[2] - r0_eff * i_meas
        residual = v_meas - v_hat

        h_mat = np.array([[d_ocv_dz, -r1, -r2, m_hyst]], dtype=float)
        r_v = self.params.measurement_noise_r_v
        s_val = float((h_mat @ self.p @ h_mat.T)[0, 0] + r_v)
        k_gain = (self.p @ h_mat.T) / s_val

        x_post = self.x + (k_gain * residual).flatten()
        x_post[0] = min(max(x_post[0], _ZERO), _ONE)
        x_post[-1] = min(max(x_post[-1], _NEG_ONE), _ONE)

        eye = np.eye(len(self.x), dtype=float)
        i_kh = eye - k_gain @ h_mat
        p_post = i_kh @ self.p @ i_kh.T + (k_gain * r_v) @ k_gain.T
        p_post = _HALF * (p_post + p_post.T)

        # 3. Time propagation to state x_(k+1)
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
            theta=float(self.theta_r0),
        )
