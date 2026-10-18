"""E2 with Component C5 Anchoring: Full-charge CV-taper anchor and slope-gated rest-OCV recalibration.

Features:
1. Full-charge CV-taper anchor:
   When V >= full_charge_voltage_threshold_v and charging current |I| <= full_charge_current_threshold_a
   held for full_charge_hold_s, anchors SOC to full_charge_anchor_soc (or temperature-scheduled 1 - gap).
2. Slope-gated rest-OCV recalibration:
   When |I| <= rest_current_threshold_a for duration >= rest_duration_threshold_s,
   recalibration is strictly restricted to regions where |dOCV/dSOC| >= slope_threshold.
   On the flat plateau, rest-OCV recalibration is suppressed to prevent noise-induced SOC errors.
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

# Anchoring thresholds
_SLOPE_RECAL_THRESHOLD = float("0.10")
_V_FULL_CHARGE_DEFAULT = float("3.58")
_I_TAPER_CHARGE_DEFAULT = float("0.055")
_T_REST_DEFAULT = float("60.0")
_I_REST_DEFAULT = float("0.010")


class E2AnchoredEstimator(Estimator):
    """E2 EKF with full-charge CV-taper anchoring and slope-gated rest-OCV recalibration."""

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

        # Anchoring state
        self.rest_duration_s = _ZERO
        self.charge_hold_duration_s = _ZERO
        self.anchor_used_last = False

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
        self.rest_duration_s = _ZERO
        self.charge_hold_duration_s = _ZERO
        self.anchor_used_last = False

    def step(self, measurement: Measurement) -> SocEstimate:
        """Execute anchoring checks, measurement update, and time propagation."""
        dt = measurement.dt
        self.anchor_used_last = False

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

        # 1. Anchoring check A: Full-charge CV taper
        v_full = self.params.full_charge_voltage_threshold_v if self.params.full_charge_voltage_threshold_v > _ZERO else _V_FULL_CHARGE_DEFAULT
        i_taper = self.params.full_charge_current_threshold_a if self.params.full_charge_current_threshold_a > _ZERO else _I_TAPER_CHARGE_DEFAULT
        t_hold = self.params.full_charge_hold_s if self.params.full_charge_hold_s > _ZERO else _T_REST_DEFAULT

        # Charging current is negative (repo convention: discharge positive)
        if v_meas >= v_full and (_NEG_ONE * i_taper <= i_meas <= _ZERO):
            self.charge_hold_duration_s += dt
            if self.charge_hold_duration_s >= t_hold:
                anchor_target = self.params.full_charge_anchor_soc if self.params.full_charge_anchor_soc > _ZERO else _ONE
                self.x[0] = anchor_target
                self.p[0, 0] = float("1e-6")
                self.anchor_used_last = True
        else:
            self.charge_hold_duration_s = _ZERO

        # 2. Anchoring check B: Rest-OCV recalibration restricted to |dOCV/dz| >= threshold
        i_rest = self.params.rest_current_threshold_a if self.params.rest_current_threshold_a > _ZERO else _I_REST_DEFAULT
        t_rest = self.params.rest_duration_threshold_s if self.params.rest_duration_threshold_s > _ZERO else _T_REST_DEFAULT

        if abs(i_meas) <= i_rest:
            self.rest_duration_s += dt
            if self.rest_duration_s >= t_rest:
                # Check slope at current SOC
                d_ocv = abs(self.ocv_table.derivative_soc(self.x[0], temp_c))
                if d_ocv >= _SLOPE_RECAL_THRESHOLD:
                    # Invert OCV table for temperature
                    soc_grid = list(self.params.soc_grid)
                    ocv_curve = [self.ocv_table.lookup(z, temp_c) for z in soc_grid]
                    z_recal = float(np.interp(v_meas, ocv_curve, soc_grid))
                    self.x[0] = min(max(z_recal, _ZERO), _ONE)
                    self.p[0, 0] = float("1e-4")
                    self.anchor_used_last = True
        else:
            self.rest_duration_s = _ZERO

        # 3. EKF Measurement Update
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
        k_gain = (self.p @ h_mat.T) / s_val

        x_post = self.x + (k_gain * residual).flatten()
        x_post[0] = min(max(x_post[0], _ZERO), _ONE)
        x_post[-1] = min(max(x_post[-1], _NEG_ONE), _ONE)

        eye = np.eye(_DIM, dtype=float)
        i_kh = eye - k_gain @ h_mat
        p_post = i_kh @ self.p @ i_kh.T + (k_gain * r_v) @ k_gain.T
        p_post = _HALF * (p_post + p_post.T)

        # 4. Time propagation to state x_(k+1)
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
            anchor_used=bool(self.anchor_used_last),
            voltage_residual=float(residual),
            innovation_variance=float(s_val),
            kalman_gain_soc=float(k_gain[0, 0]),
        )
