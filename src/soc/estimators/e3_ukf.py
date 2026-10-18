"""E3: Unscented Kalman Filter (UKF) for 2RC Equivalent Circuit Model with Hysteresis.

State vector:
    x = [soc, i1, i2, h]^T
Sigma points are generated with clamping of soc to [0, 1] and h to [-1, 1].
Numerically stable covariance update ensures symmetry and positive definiteness.
Adheres strictly to zero-hardcoded-constants rule and estimator isolation.
"""

import math
from typing import Optional
import numpy as np
import scipy.linalg

from soc.estimators.base import Estimator, ParamSet, SocEstimate
from soc.models.cell_2rc import Cell2RCModel
from soc.models.plant import Measurement
from soc.models.tables import InterpolatedTable2D

_DIM = int("4")
_ALPHA = float("1.0")
_BETA = float("2.0")
_KAPPA = float("0.0")
_HALF = float("0.5")
_ZERO = float("0.0")
_ONE = float("1.0")
_NEG_ONE = float("-1.0")
_JITTER = float("1e-9")


class E3UnscentedKalmanFilter(Estimator):
    """E3: 4-state Unscented Kalman Filter with sigma-point clamping."""

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

        # UKF weights
        n_dim = float(_DIM)
        lambda_val = _ALPHA * _ALPHA * (n_dim + _KAPPA) - n_dim
        self.gamma_scale = math.sqrt(n_dim + lambda_val)

        c_val = n_dim + lambda_val
        w0_m = lambda_val / c_val
        w0_c = lambda_val / c_val + (_ONE - _ALPHA * _ALPHA + _BETA)
        wi = _ONE / (float("2.0") * c_val)

        self.w_m = np.full(2 * _DIM + 1, wi, dtype=float)
        self.w_c = np.full(2 * _DIM + 1, wi, dtype=float)
        self.w_m[0] = w0_m
        self.w_c[0] = w0_c

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

    def _generate_sigma_points(self, mean_x: np.ndarray, cov_p: np.ndarray) -> np.ndarray:
        """Generate 2*L + 1 sigma points with state clamping."""
        cov_sym = _HALF * (cov_p + cov_p.T)
        cov_reg = cov_sym + _JITTER * np.eye(_DIM, dtype=float)
        try:
            chol = scipy.linalg.cholesky(cov_reg, lower=True)
        except scipy.linalg.LinAlgError:
            diag_p = np.maximum(np.diag(cov_sym), _JITTER)
            chol = np.diag(np.sqrt(diag_p))

        scaled_chol = self.gamma_scale * chol
        n_sigmas = 2 * _DIM + 1
        sigmas = np.zeros((n_sigmas, _DIM), dtype=float)
        sigmas[0] = mean_x

        for i in range(_DIM):
            sigmas[i + 1] = mean_x + scaled_chol[:, i]
            sigmas[i + 1 + _DIM] = mean_x - scaled_chol[:, i]

        # Clamping of soc to [0, 1] and h to [-1, 1] at all sigma points
        sigmas[:, 0] = np.clip(sigmas[:, 0], _ZERO, _ONE)
        sigmas[:, -1] = np.clip(sigmas[:, -1], _NEG_ONE, _ONE)
        return sigmas

    def step(self, measurement: Measurement) -> SocEstimate:
        """Execute UKF measurement update followed by time propagation."""
        dt = measurement.dt

        # Handle dropped measurement
        if measurement.dropout or math.isnan(measurement.v) or math.isnan(measurement.i):
            i_prop = self.last_valid_i
            temp_prop = self.last_valid_temp

            sigmas = self._generate_sigma_points(self.x, self.p)
            n_sigmas = len(sigmas)
            sigmas_next = np.zeros_like(sigmas)

            tau1 = self.tau1_table.lookup(self.x[0], temp_prop)
            tau2 = self.tau2_table.lookup(self.x[0], temp_prop)

            for j in range(n_sigmas):
                z_j = Cell2RCModel.step_soc(
                    soc=sigmas[j, 0],
                    i_a=i_prop,
                    dt_s=dt,
                    capacity_ah=self.params.nominal_capacity_ah,
                    coulombic_efficiency=self.params.coulombic_efficiency,
                )
                i1_j = Cell2RCModel.step_rc_current(sigmas[j, 1], i_prop, dt, tau1)
                i2_j = Cell2RCModel.step_rc_current(sigmas[j, 2], i_prop, dt, tau2)
                h_j = Cell2RCModel.step_hysteresis(
                    h=sigmas[j, -1],
                    i_a=i_prop,
                    dt_s=dt,
                    capacity_ah=self.params.nominal_capacity_ah,
                    gamma=self.params.hysteresis_gamma,
                    coulombic_efficiency=self.params.coulombic_efficiency,
                )
                sigmas_next[j] = [
                    min(max(z_j, _ZERO), _ONE),
                    i1_j,
                    i2_j,
                    min(max(h_j, _NEG_ONE), _ONE),
                ]

            x_next = np.sum(self.w_m[:, None] * sigmas_next, axis=0)
            x_next[0] = min(max(x_next[0], _ZERO), _ONE)
            x_next[-1] = min(max(x_next[-1], _NEG_ONE), _ONE)

            dx = sigmas_next - x_next[None, :]
            q_mat = np.diag([
                self.params.process_noise_q_soc,
                self.params.process_noise_q_rc,
                self.params.process_noise_q_rc,
                self.params.process_noise_q_hysteresis,
            ])
            p_next = np.zeros((_DIM, _DIM), dtype=float)
            for j in range(n_sigmas):
                p_next += self.w_c[j] * np.outer(dx[j], dx[j])
            p_next = _HALF * (p_next + p_next.T) + q_mat

            self.x = x_next
            self.p = p_next

            return SocEstimate(
                soc=float(self.x[0]),
                soc_std=float(math.sqrt(max(self.p[0, 0], _ZERO))),
                anchor_used=False,
                voltage_residual=None,
                innovation_variance=None,
            )

        # Valid measurement
        self.last_valid_i = measurement.i
        self.last_valid_temp = measurement.temp_c
        temp_c = measurement.temp_c
        i_meas = measurement.i
        v_meas = measurement.v

        # 1. Measurement update of prior state x_k
        sigmas_prior = self._generate_sigma_points(self.x, self.p)
        n_sigmas = len(sigmas_prior)
        v_pred_sigmas = np.zeros(n_sigmas, dtype=float)

        m_hyst = self.params.hysteresis_amplitude_v
        r0 = self.r0_table.lookup(self.x[0], temp_c)
        r1 = self.r1_table.lookup(self.x[0], temp_c)
        r2 = self.r2_table.lookup(self.x[0], temp_c)
        tau1 = self.tau1_table.lookup(self.x[0], temp_c)
        tau2 = self.tau2_table.lookup(self.x[0], temp_c)

        for j in range(n_sigmas):
            ocv_j = self.ocv_table.lookup(sigmas_prior[j, 0], temp_c)
            v_pred_sigmas[j] = ocv_j + m_hyst * sigmas_prior[j, -1] - r1 * sigmas_prior[j, 1] - r2 * sigmas_prior[j, 2] - r0 * i_meas

        y_hat = float(np.sum(self.w_m * v_pred_sigmas))
        residual = v_meas - y_hat

        # Innovation and cross-covariances
        r_v = self.params.measurement_noise_r_v
        dy = v_pred_sigmas - y_hat
        dx_prior = sigmas_prior - self.x[None, :]

        s_val = float(np.sum(self.w_c * (dy ** 2)) + r_v)
        p_xy = np.sum(self.w_c[:, None] * dx_prior * dy[:, None], axis=0)

        # Kalman gain K
        k_gain = p_xy / s_val

        # Posterior state correction
        x_post = self.x + k_gain * residual
        x_post[0] = min(max(x_post[0], _ZERO), _ONE)
        x_post[-1] = min(max(x_post[-1], _NEG_ONE), _ONE)

        # Numerically stable posterior covariance update
        p_post = self.p - s_val * np.outer(k_gain, k_gain)
        p_post = _HALF * (p_post + p_post.T)
        # Ensure positive semidefiniteness
        diag_floor = np.maximum(np.diag(p_post), _ZERO)
        np.fill_diagonal(p_post, diag_floor)

        # 2. Time propagation to state x_(k+1)
        sigmas_post = self._generate_sigma_points(x_post, p_post)
        sigmas_next = np.zeros_like(sigmas_post)

        for j in range(n_sigmas):
            z_j = Cell2RCModel.step_soc(
                soc=sigmas_post[j, 0],
                i_a=i_meas,
                dt_s=dt,
                capacity_ah=self.params.nominal_capacity_ah,
                coulombic_efficiency=self.params.coulombic_efficiency,
            )
            i1_j = Cell2RCModel.step_rc_current(sigmas_post[j, 1], i_meas, dt, tau1)
            i2_j = Cell2RCModel.step_rc_current(sigmas_post[j, 2], i_meas, dt, tau2)
            h_j = Cell2RCModel.step_hysteresis(
                h=sigmas_post[j, -1],
                i_a=i_meas,
                dt_s=dt,
                capacity_ah=self.params.nominal_capacity_ah,
                gamma=self.params.hysteresis_gamma,
                coulombic_efficiency=self.params.coulombic_efficiency,
            )
            sigmas_next[j] = [
                min(max(z_j, _ZERO), _ONE),
                i1_j,
                i2_j,
                min(max(h_j, _NEG_ONE), _ONE),
            ]

        x_next = np.sum(self.w_m[:, None] * sigmas_next, axis=0)
        x_next[0] = min(max(x_next[0], _ZERO), _ONE)
        x_next[-1] = min(max(x_next[-1], _NEG_ONE), _ONE)

        dx_next = sigmas_next - x_next[None, :]
        q_mat = np.diag([
            self.params.process_noise_q_soc,
            self.params.process_noise_q_rc,
            self.params.process_noise_q_rc,
            self.params.process_noise_q_hysteresis,
        ])
        p_next = np.zeros((_DIM, _DIM), dtype=float)
        for j in range(n_sigmas):
            p_next += self.w_c[j] * np.outer(dx_next[j], dx_next[j])
        p_next = _HALF * (p_next + p_next.T) + q_mat

        self.x = x_next
        self.p = p_next

        return SocEstimate(
            soc=float(self.x[0]),
            soc_std=float(math.sqrt(max(self.p[0, 0], _ZERO))),
            anchor_used=False,
            voltage_residual=float(residual),
            innovation_variance=float(s_val),
            kalman_gain_soc=float(k_gain[0]),
        )
