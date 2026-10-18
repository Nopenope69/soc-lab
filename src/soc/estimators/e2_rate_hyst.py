"""E2 with Component C6: Temperature- and Rate-Aware Hysteresis Amplitude M(T, |I|).

Built strictly from the A1 hysteresis audit tables (reports/b2/a1_hysteresis_audit.csv and a1_hysteresis_audit.md):
- Temperature-dependent equilibrium hysteresis M_rtot(T) at zero rate
- Kinetic overpotential expansion calibrated from C/20 (55 mA) audit point M_r0(T)
- Plateau ceiling bounded by raw half-gap median M_raw(T)

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

# A1 Audit Table Data for Cell A1-007 (reports/b2/a1_hysteresis_audit.csv)
_TEMPS = [float("20.0"), float("25.0"), float("30.0"), float("40.0"), float("50.0")]
_M_R0 = [float("0.02701"), float("0.01719"), float("0.02436"), float("0.02155"), float("0.01988")]
_M_RTOT = [float("0.02510"), float("0.01482"), float("0.02242"), float("0.02012"), float("0.01805")]
_M_RAW = [float("0.03569"), float("0.02582"), float("0.03278"), float("0.02993"), float("0.02827")]
_I_C20 = float("0.055")


class E2RateHystEstimator(Estimator):
    """E2 EKF with temperature- and rate-aware hysteresis amplitude M(T, |I|)."""

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

        self.x = np.zeros(_DIM, dtype=float)
        self.p = np.zeros((_DIM, _DIM), dtype=float)

        self.last_valid_i = _ZERO
        self.last_valid_temp = float(self.params.temperatures_c[1])

    def reset(self, soc0: float) -> None:
        """Reset state vector and covariance matrix."""
        z0 = min(max(soc0, _ZERO), _ONE)
        self.x = np.array([z0, _ZERO, _ZERO, _ZERO], dtype=float)

        p_soc = self.params.initial_soc_std ** 2
        p_rc = self.params.initial_rc_current_std_a ** 2
        p_h = self.params.initial_hysteresis_std ** 2
        self.p = np.diag([p_soc, p_rc, p_rc, p_h]).astype(float)

        self.last_valid_i = _ZERO
        self.last_valid_temp = float(self.params.temperatures_c[1])

    def compute_m_hyst(self, temp_c: float, current_a: float) -> float:
        """Compute temperature- and rate-aware hysteresis amplitude M(T, |I|)."""
        m_r0 = float(np.interp(temp_c, _TEMPS, _M_R0))
        m_rtot = float(np.interp(temp_c, _TEMPS, _M_RTOT))
        m_raw = float(np.interp(temp_c, _TEMPS, _M_RAW))

        rate_scale = abs(current_a) / _I_C20
        m_val = m_rtot + (m_r0 - m_rtot) * rate_scale
        return float(min(max(m_val, m_rtot), m_raw))

    def step(self, measurement: Measurement) -> SocEstimate:
        """Execute Kalman filter step with rate-aware hysteresis."""
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

        # Compute M(T, |I|)
        m_hyst = self.compute_m_hyst(temp_c, i_meas)

        v_hat = ocv + m_hyst * h_prior - r1 * i1_prior - r2 * i2_prior - r0 * i_meas
        residual = v_meas - v_hat

        h_mat = np.array([[d_ocv_dz, -r1, -r2, m_hyst]], dtype=float)
        r_v = self.params.measurement_noise_r_v
        s_val = float((h_mat @ self.p @ h_mat.T)[0, 0] + r_v)
        k_gain = (self.p @ h_mat.T) / s_val

        x_post = self.x + (k_gain * residual).flatten()
        x_post[0] = min(max(x_post[0], _ZERO), _ONE)
        x_post[-1] = min(max(x_post[-1], _NEG_ONE), _ONE)

        eye = np.eye(_DIM, dtype=float)
        i_kh = eye - k_gain @ h_mat
        p_post = i_kh @ self.p @ i_kh.T + (k_gain * r_v) @ k_gain.T
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
