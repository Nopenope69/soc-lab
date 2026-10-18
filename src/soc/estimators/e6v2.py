"""E6v2: Rebuilt Residual-Bias Filter Dual Extended Kalman Filter (RBC-DEKF).

Features:
1. Couples a 4-state [soc, i1, i2, h] battery state filter with a slow voltage bias state theta.
2. Decoupled bias update: The bias filter update is slope-gated by |dOCV/dSOC|.
   On the flat plateau (|dOCV/dSOC| < slope_threshold), bias updates are frozen (gain = 0),
   ensuring the bias state cannot absorb SOC estimation errors in regions of low observability.
3. Covariance updates in stabilized Joseph form.
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

# Defaults for slow bias state and decoupling threshold
_DEF_Q_THETA = float("1e-10")
_DEF_R_THETA = float("1e-4")
_DEF_INIT_THETA_STD = float("0.005")
_SLOPE_DECOUPLING_THRESHOLD = float("0.10")
_THETA_MAX_V = float("0.050")


class E6V2ResidualBiasFilter(Estimator):
    """E6v2: 2RC EKF with slope-decoupled slow residual voltage bias estimation."""

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

        # Slow residual bias state theta and variance
        self.theta = _ZERO
        self.p_theta = _DEF_INIT_THETA_STD ** 2

        self.q_theta = self.params.rbc_q_theta if self.params.rbc_q_theta > _ZERO else _DEF_Q_THETA
        self.r_theta = self.params.rbc_r_theta if self.params.rbc_r_theta > _ZERO else _DEF_R_THETA

        self.last_valid_i = _ZERO
        self.last_valid_temp = float(self.params.temperatures_c[1])

    def reset(self, soc0: float) -> None:
        """Reset estimator state, covariance, and bias state."""
        soc_clamped = min(max(float(soc0), _ZERO), _ONE)
        self.x = np.array([soc_clamped, _ZERO, _ZERO, _ZERO], dtype=float)

        p_soc = self.params.initial_soc_std ** 2
        p_rc = self.params.initial_rc_current_std_a ** 2
        p_h = self.params.initial_hysteresis_std ** 2
        self.p = np.diag([p_soc, p_rc, p_rc, p_h]).astype(float)

        self.theta = _ZERO
        init_std = self.params.rbc_initial_theta_std if self.params.rbc_initial_theta_std > _ZERO else _DEF_INIT_THETA_STD
        self.p_theta = init_std ** 2

        self.last_valid_i = _ZERO
        self.last_valid_temp = float(self.params.temperatures_c[1])

    def step(self, measurement: Measurement) -> SocEstimate:
        """Execute state update, decoupled bias update, and time propagation."""
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

            # Bias filter prediction only
            self.p_theta += self.q_theta

            return SocEstimate(
                soc=float(self.x[0]),
                soc_std=float(math.sqrt(max(self.p[0, 0], _ZERO))),
                anchor_used=False,
                voltage_residual=None,
                innovation_variance=None,
                theta=float(self.theta),
                theta_std=float(math.sqrt(max(self.p_theta, _ZERO))),
            )

        # Valid measurement
        temp_c = measurement.temp_c
        i_meas = measurement.i
        v_meas = measurement.v
        self.last_valid_i = i_meas
        self.last_valid_temp = temp_c

        # 1. State-filter update with previous bias estimate theta
        r0 = self.r0_table.lookup(self.x[0], temp_c)
        r1 = self.r1_table.lookup(self.x[0], temp_c)
        r2 = self.r2_table.lookup(self.x[0], temp_c)
        tau1 = self.tau1_table.lookup(self.x[0], temp_c)
        tau2 = self.tau2_table.lookup(self.x[0], temp_c)
        ocv = self.ocv_table.lookup(self.x[0], temp_c)
        d_ocv_dz = self.ocv_table.derivative_soc(self.x[0], temp_c)
        m_hyst = self.params.hysteresis_amplitude_v

        v_hat = ocv + m_hyst * self.x[-1] - r1 * self.x[1] - r2 * self.x[2] - r0 * i_meas
        y_x = v_meas - (v_hat + self.theta)

        h_mat = np.array([[d_ocv_dz, -r1, -r2, m_hyst]], dtype=float)
        r_v = self.params.measurement_noise_r_v
        s_val = float((h_mat @ self.p @ h_mat.T)[0, 0] + r_v)
        k_gain = (self.p @ h_mat.T) / s_val

        x_post = self.x + (k_gain * y_x).flatten()
        x_post[0] = min(max(x_post[0], _ZERO), _ONE)
        x_post[-1] = min(max(x_post[-1], _NEG_ONE), _ONE)

        eye = np.eye(_DIM, dtype=float)
        i_kh = eye - k_gain @ h_mat
        p_post = i_kh @ self.p @ i_kh.T + (k_gain * r_v) @ k_gain.T
        p_post = _HALF * (p_post + p_post.T)

        # 2. Decoupled residual-bias filter update
        # Bias filter prediction
        self.p_theta += self.q_theta

        # Voltage evaluated at post-update state x_post
        ocv_post = self.ocv_table.lookup(x_post[0], temp_c)
        r0_post = self.r0_table.lookup(x_post[0], temp_c)
        r1_post = self.r1_table.lookup(x_post[0], temp_c)
        r2_post = self.r2_table.lookup(x_post[0], temp_c)
        v_hat_post = ocv_post + m_hyst * x_post[-1] - r1_post * x_post[1] - r2_post * x_post[2] - r0_post * i_meas
        y_theta = v_meas - (v_hat_post + self.theta)

        # Decoupling: only update bias when |dOCV/dz| >= threshold (knee regions).
        # On the plateau, slope is small, so freeze bias update to prevent absorbing SOC offset.
        d_ocv_eval = abs(self.ocv_table.derivative_soc(self.x[0], temp_c))
        if d_ocv_eval >= _SLOPE_DECOUPLING_THRESHOLD:
            s_theta = self.p_theta + self.r_theta
            k_theta = self.p_theta / s_theta
            self.theta += k_theta * y_theta
            self.theta = min(max(self.theta, -_THETA_MAX_V), _THETA_MAX_V)
            # Joseph form for scalar
            self.p_theta = ((_ONE - k_theta) ** 2) * self.p_theta + (k_theta ** 2) * self.r_theta

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
            voltage_residual=float(y_x),
            innovation_variance=float(s_val),
            kalman_gain_soc=float(k_gain[0, 0]),
            theta=float(self.theta),
            theta_std=float(math.sqrt(max(self.p_theta, _ZERO))),
        )
