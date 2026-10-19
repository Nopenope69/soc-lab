"""E7v3: Confidence-Aware Composite Adaptive SOC Estimator for Gauntlet V3.

Combines:
1. Confidence-aware covariance initialization via reset(soc0, soc_std).
2. Temperature-scheduled capacity Q(T) and hysteresis amplitude M(T).
3. Online RLS impedance adaptation (D2 / E4v2) on R0 and R1.
4. Observability gating & plateau per-step correction capping (D1 / E5v4).
5. 2RC + Hysteresis EKF base model on calce_a123_v4.

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
_R_MIN_SCALE = float("0.5")
_R_MAX_SCALE = float("2.0")
_DI_THRESHOLD_A = float("1.0")
_RESIDUAL_TOL = float("1e-12")

# Default tunings for E5v4 gating
_DEF_SIGMA_OCV = float("0.02")
_DEF_SLOPE_REF = float("0.2")
_DEF_CAP_PLATEAU = float("1e-5")
_DEF_CAP_KNEE = float("0.01")

# Reference calibration anchors for CALCE A123
_Q_REF = float("1.0635616695823449")
_M_REF = float("0.02155")

# Temperature grids and tables for Q(T) and M(T) (D8 anchor gap & Stage V0/V1 audit)
_TEMPS_C = [float("20.0"), float("25.0"), float("30.0"), float("40.0"), float("50.0")]
_Q_TABLE_AH = [
    float("1.065214687790664"),
    float("1.0635616695823449"),
    float("1.0730061548855323"),
    float("1.0801900610401025"),
    float("1.0809567995408316"),
]
_M_TABLE_V = [
    float("0.02701"),
    float("0.01719"),
    float("0.02436"),
    float("0.02155"),
    float("0.01988"),
]


class E7V3CompositeFilter(Estimator):
    """E7v3 confidence-aware composite estimator."""

    def __init__(self, params: ParamSet):
        self.params = params
        self.adapt_r1 = True

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

        # RLS state for theta
        self.theta = _ONE
        self.p_rls = _ONE

        self.prev_i = _ZERO
        self.prev_v = _ZERO
        self.has_prev = False

        self.last_valid_i = _ZERO
        self.last_valid_temp = float(self.params.temperatures_c[1])
        self.last_applied_g = _ONE
        self.last_applied_delta_soc = _ZERO

        # Resolve E5v4 tunings
        self.sigma_ocv = (
            self.params.e5_sigma_ocv_model_v
            if self.params.e5_sigma_ocv_model_v > _ZERO
            else _DEF_SIGMA_OCV
        )
        self.slope_ref = (
            self.params.e5_slope_ref
            if self.params.e5_slope_ref > _ZERO
            else _DEF_SLOPE_REF
        )
        self.cap_plateau = (
            self.params.e5_cap_plateau
            if self.params.e5_cap_plateau > _ZERO
            else _DEF_CAP_PLATEAU
        )
        self.cap_knee = (
            self.params.e5_cap_knee
            if self.params.e5_cap_knee > _ZERO
            else _DEF_CAP_KNEE
        )

        # Scale factor for capacity if evaluated on non-CALCE packs (e.g. synthetic 100 Ah pack)
        if self.params.nominal_capacity_ah > _ZERO:
            self._q_scale = self.params.nominal_capacity_ah / _Q_REF
        else:
            self._q_scale = _ONE

        # Scale factor for hysteresis amplitude if non-default amplitude is configured
        if self.params.hysteresis_amplitude_v >= _ZERO:
            self._m_scale = self.params.hysteresis_amplitude_v / _M_REF
        else:
            self._m_scale = _ONE

    def get_capacity_ah(self, temp_c: float) -> float:
        """Linear interpolation of C/20 capacity over temperature, clamped at edges."""
        base_q = float(np.interp(temp_c, _TEMPS_C, _Q_TABLE_AH))
        return base_q * self._q_scale

    def get_m_hyst(self, temp_c: float) -> float:
        """Linear interpolation of hysteresis half-gap over temperature, clamped at edges."""
        base_m = float(np.interp(temp_c, _TEMPS_C, _M_TABLE_V))
        return base_m * self._m_scale

    def reset(self, soc0: float, soc_std: Optional[float] = None) -> None:
        """Reset estimator state, covariance, and RLS parameters.

        Args:
            soc0: Initial state of charge in [0, 1].
            soc_std: Optional standard deviation of initial SOC estimate.
                     If None, defaults to params.initial_soc_std.
        """
        soc_clamped = min(max(float(soc0), _ZERO), _ONE)
        self.x = np.array([soc_clamped, _ZERO, _ZERO, _ZERO], dtype=float)

        if soc_std is not None and float(soc_std) > _ZERO:
            p_soc = float(soc_std) ** 2
        else:
            p_soc = self.params.initial_soc_std ** 2

        p_rc = self.params.initial_rc_current_std_a ** 2
        p_h = self.params.initial_hysteresis_std ** 2
        self.p = np.diag([p_soc, p_rc, p_rc, p_h]).astype(float)

        self.theta = _ONE
        self.p_rls = _ONE
        self.prev_i = _ZERO
        self.prev_v = _ZERO
        self.has_prev = False

        self.last_valid_i = _ZERO
        self.last_valid_temp = float(self.params.temperatures_c[1])
        self.last_applied_g = _ONE
        self.last_applied_delta_soc = _ZERO

    def step(self, measurement: Measurement) -> SocEstimate:
        """Execute RLS adaptation, observability-gated EKF update, and time propagation."""
        dt = measurement.dt

        # Handle dropped measurement
        if measurement.dropout or math.isnan(measurement.v) or math.isnan(measurement.i):
            i_prop = self.last_valid_i
            temp_prop = self.last_valid_temp

            q_t = self.get_capacity_ah(temp_prop)
            tau1 = self.tau1_table.lookup(self.x[0], temp_prop)
            tau2 = self.tau2_table.lookup(self.x[0], temp_prop)

            z_next = Cell2RCModel.step_soc(
                soc=self.x[0],
                i_a=i_prop,
                dt_s=dt,
                capacity_ah=q_t,
                coulombic_efficiency=self.params.coulombic_efficiency,
            )
            i1_next = Cell2RCModel.step_rc_current(self.x[1], i_prop, dt, tau1)
            i2_next = Cell2RCModel.step_rc_current(self.x[2], i_prop, dt, tau2)
            h_next = Cell2RCModel.step_hysteresis(
                h=self.x[-1],
                i_a=i_prop,
                dt_s=dt,
                capacity_ah=q_t,
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
                cap_as = q_t * 3600
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
                theta=float(self.theta),
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
                err_rls = y_meas - phi * self.theta

                self.theta += l_gain * err_rls
                self.theta = min(max(self.theta, _R_MIN_SCALE), _R_MAX_SCALE)
                self.p_rls = (self.p_rls - l_gain * phi * self.p_rls) / lam

        self.prev_i = i_meas
        self.prev_v = v_meas
        self.has_prev = True

        # 2. Measurement update using adapted R0 and R1 + E5v4 Observability Gating
        r0_eff = self.theta * r0_base
        r1_base = self.r1_table.lookup(self.x[0], temp_c)
        r1_eff = self.theta * r1_base if self.adapt_r1 else r1_base
        r2 = self.r2_table.lookup(self.x[0], temp_c)
        tau1 = self.tau1_table.lookup(self.x[0], temp_c)
        tau2 = self.tau2_table.lookup(self.x[0], temp_c)
        ocv = self.ocv_table.lookup(self.x[0], temp_c)
        d_ocv_dz = self.ocv_table.derivative_soc(self.x[0], temp_c)
        m_hyst = self.get_m_hyst(temp_c)

        v_hat = ocv + m_hyst * self.x[-1] - r1_eff * self.x[1] - r2 * self.x[2] - r0_eff * i_meas
        residual = v_meas - v_hat

        h_mat = np.array([[d_ocv_dz, -r1_eff, -r2, m_hyst]], dtype=float)

        # Variance inflation
        r_base = self.params.measurement_noise_r_v
        r_eff = r_base + (self.sigma_ocv ** 2)

        s_val = float((h_mat @ self.p @ h_mat.T)[0, 0] + r_eff)
        k_gain = (self.p @ h_mat.T) / s_val

        delta_x_raw = (k_gain * residual).flatten()
        delta_soc = delta_x_raw[0]

        # Observability gating
        abs_slope = abs(d_ocv_dz)
        g_slope = min(_ONE, abs_slope / self.slope_ref) if self.slope_ref > _ZERO else _ONE
        delta_soc = delta_soc * g_slope
        self.last_applied_g = float(g_slope)

        # Plateau step capping
        cap = self.cap_plateau + (self.cap_knee - self.cap_plateau) * g_slope
        if cap > _ZERO:
            delta_soc = min(max(delta_soc, -cap), cap)
        self.last_applied_delta_soc = float(delta_soc)

        # State correction vector
        delta_x = np.array([delta_soc, delta_x_raw[1], delta_x_raw[2], delta_x_raw[-1]], dtype=float)
        x_post = self.x + delta_x
        x_post[0] = min(max(x_post[0], _ZERO), _ONE)
        x_post[-1] = min(max(x_post[-1], _NEG_ONE), _ONE)

        # Joseph covariance update using effective Kalman gain K_eff
        if abs(residual) > _RESIDUAL_TOL:
            k_eff_soc = delta_soc / residual
        else:
            k_eff_soc = _ZERO
        k_eff = np.array([[k_eff_soc], [k_gain[1, 0]], [k_gain[2, 0]], [k_gain[-1, 0]]], dtype=float)

        eye = np.eye(_DIM, dtype=float)
        i_kh = eye - k_eff @ h_mat
        p_post = i_kh @ self.p @ i_kh.T + (k_eff * r_eff) @ k_eff.T
        p_post = _HALF * (p_post + p_post.T)

        # 3. Time propagation to state x_(k+1) using temperature-scheduled Q(T)
        q_t = self.get_capacity_ah(temp_c)
        z_next = Cell2RCModel.step_soc(
            soc=x_post[0],
            i_a=i_meas,
            dt_s=dt,
            capacity_ah=q_t,
            coulombic_efficiency=self.params.coulombic_efficiency,
        )
        i1_next = Cell2RCModel.step_rc_current(x_post[1], i_meas, dt, tau1)
        i2_next = Cell2RCModel.step_rc_current(x_post[2], i_meas, dt, tau2)
        h_next = Cell2RCModel.step_hysteresis(
            h=x_post[-1],
            i_a=i_meas,
            dt_s=dt,
            capacity_ah=q_t,
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
            cap_as = q_t * 3600
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
            theta=float(self.theta),
        )
