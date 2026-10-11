"""E1: 2RC Equivalent Circuit Model with Extended Kalman Filter (no hysteresis).

State vector:
    x = [soc, i1, i2]^T
Dynamics:
    soc_{k+1} = soc_k - (eta(i_k) * dt / (3600 * Q)) * i_k
    i1_{k+1} = exp(-dt / tau1) * i1_k + (1 - exp(-dt / tau1)) * i_k
    i2_{k+1} = exp(-dt / tau2) * i2_k + (1 - exp(-dt / tau2)) * i_k
Observation:
    v_k = OCV(soc_k, T_k) - R1 * i1_k - R2 * i2_k - R0 * i_k
Covariance update:
    Joseph form: P^+ = (I - K*H) * P^- * (I - K*H)^T + K * R_v * K^T
"""

import math
from typing import Optional
import numpy as np

from soc.estimators.base import Estimator, ParamSet, SocEstimate
from soc.models.cell_2rc import Cell2RCModel
from soc.models.plant import Measurement
from soc.models.tables import InterpolatedTable2D


class E1ExtendedKalmanFilter(Estimator):
    """E1: 2RC equivalent circuit model with Extended Kalman Filter."""

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

        # State vector: [soc, i1, i2]^T
        self.x = np.array([float(0), float(0), float(0)], dtype=float)
        # Covariance matrix: 3x3
        self.p = np.zeros((len(self.x), len(self.x)), dtype=float)

        self.last_valid_i = float(0)
        self.last_valid_temp = float(self.params.temperatures_c[1])

    def reset(self, soc0: float) -> None:
        """Reset estimator state and covariance."""
        soc_clamped = min(max(float(soc0), float(0)), float(1))
        self.x = np.array([soc_clamped, float(0), float(0)], dtype=float)

        # Initialize covariance P
        p_soc = self.params.initial_soc_std ** 2
        p_rc = self.params.initial_rc_current_std_a ** 2
        self.p = np.diag([p_soc, p_rc, p_rc]).astype(float)

        self.last_valid_i = float(0)
        self.last_valid_temp = float(self.params.temperatures_c[1])

    def step(self, measurement: Measurement) -> SocEstimate:
        """Execute EKF measurement update then time propagation for x_(k+1)."""
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

            self.x = np.array([min(max(z_next, float(0)), float(1)), i1_next, i2_next], dtype=float)

            # Propagate covariance
            f11 = math.exp(-dt / tau1)
            f22 = math.exp(-dt / tau2)
            f_mat = np.diag([float(1), f11, f22])
            q_mat = np.diag([
                self.params.process_noise_q_soc,
                self.params.process_noise_q_rc,
                self.params.process_noise_q_rc,
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

        r0 = self.r0_table.lookup(soc_prior, temp_c)
        r1 = self.r1_table.lookup(soc_prior, temp_c)
        r2 = self.r2_table.lookup(soc_prior, temp_c)
        tau1 = self.tau1_table.lookup(soc_prior, temp_c)
        tau2 = self.tau2_table.lookup(soc_prior, temp_c)
        ocv = self.ocv_table.lookup(soc_prior, temp_c)
        d_ocv_dz = self.ocv_table.derivative_soc(soc_prior, temp_c)

        # Predicted terminal voltage
        v_hat = ocv - r1 * i1_prior - r2 * i2_prior - r0 * i_meas
        residual = v_meas - v_hat

        # Observation matrix H: 1x3
        h_mat = np.array([[d_ocv_dz, -r1, -r2]], dtype=float)

        # Innovation covariance S
        r_v = self.params.measurement_noise_r_v
        s_val = float((h_mat @ self.p @ h_mat.T)[0, 0] + r_v)

        # Kalman gain K: 3x1
        k_gain = (self.p @ h_mat.T) / s_val

        # State correction
        x_post = self.x + (k_gain * residual).flatten()
        # Clamp SOC to [0, 1]
        x_post[0] = min(max(x_post[0], float(0)), float(1))

        # Joseph form covariance update: P = (I - K*H)*P*(I - K*H)^T + K*R_v*K^T
        eye = np.eye(len(self.x), dtype=float)
        i_kh = eye - k_gain @ h_mat
        p_post = i_kh @ self.p @ i_kh.T + (k_gain * r_v) @ k_gain.T
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

        self.x = np.array([min(max(z_next, float(0)), float(1)), i1_next, i2_next], dtype=float)

        # Propagate covariance P
        f11 = math.exp(-dt / tau1)
        f22 = math.exp(-dt / tau2)
        f_mat = np.diag([float(1), f11, f22])
        q_mat = np.diag([
            self.params.process_noise_q_soc,
            self.params.process_noise_q_rc,
            self.params.process_noise_q_rc,
        ])
        self.p = f_mat @ p_post @ f_mat.T + q_mat
        self.p = (self.p + self.p.T) / 2

        return SocEstimate(
            soc=float(self.x[0]),
            soc_std=float(math.sqrt(max(self.p[0, 0], float(0)))),
            anchor_used=False,
            voltage_residual=float(residual),
            innovation_variance=float(s_val),
        )
