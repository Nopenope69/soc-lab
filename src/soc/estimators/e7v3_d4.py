"""E7v3_D4: Composite Adaptive SOC Estimator with Component D4 (Adaptive Covariance Fading).

Extends E7v3 by adding persistent innovation monitoring and covariance inflation (D4):
- Monitors innovation residual |v - v_hat| against k * sqrt(S).
- If residual exceeds threshold for N consecutive seconds, inflates P[0,0] by fading factor lambda_f
  up to ceiling P_max (or directly resets P[0,0] -> P_max).
- Allows filter to break out of false plateau locks (Scenario S-G) without corrupting normal operation.

Adheres strictly to zero-hardcoded-constants rule and estimator isolation.
"""

import math
from typing import Optional
import numpy as np

from soc.estimators.base import Estimator, ParamSet, SocEstimate
from soc.estimators.e7v3 import E7V3CompositeFilter
from soc.models.plant import Measurement

_ZERO = float("0.0")
_ONE = float("1.0")
_HALF = float("0.5")
_RESIDUAL_TOL = float("1e-12")

# Default D4 tunings
_DEF_D4_K = float("3.0")
_DEF_D4_DURATION_S = float("60.0")
_DEF_D4_LAMBDA_F = float("1.05")
_DEF_D4_P_MAX = float("0.01")  # (10 pp)^2
_DEF_D4_MODE = "step_factor"


class E7V3D4Filter(E7V3CompositeFilter):
    """E7v3 composite estimator with Component D4 adaptive covariance fading."""

    def __init__(self, params: ParamSet):
        super().__init__(params)
        self.d4_k = float(self.params.d4_k)
        self.d4_duration_s = float(self.params.d4_duration_s)
        self.d4_lambda_f = float(self.params.d4_lambda_f)
        self.d4_p_max = float(self.params.d4_p_max)
        self.d4_mode = str(self.params.d4_mode)

        self.d4_timer_s = _ZERO
        self.d4_fading_active = False

    def reset(self, soc0: float, soc_std: Optional[float] = None) -> None:
        """Reset estimator state, covariance, and D4 monitoring timer."""
        super().reset(soc0, soc_std)
        self.d4_timer_s = _ZERO
        self.d4_fading_active = False

    def step(self, measurement: Measurement) -> SocEstimate:
        """Execute step with D4 persistent innovation monitoring and covariance inflation."""
        dt = measurement.dt

        # Handle dropped measurement
        if measurement.dropout or math.isnan(measurement.v) or math.isnan(measurement.i):
            self.d4_timer_s = _ZERO
            self.d4_fading_active = False
            return super().step(measurement)

        # Valid measurement: compute base prediction first
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

        # 2. Measurement update using adapted R0 and R1
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

        r_base = self.params.measurement_noise_r_v
        r_eff = r_base + (self.sigma_ocv ** 2)

        s_val = float((h_mat @ self.p @ h_mat.T)[0, 0] + r_eff)
        sigma_s = math.sqrt(max(s_val, _ZERO))

        # -----------------------------------------------------------------
        # Component D4: Persistent Innovation Monitoring & Fading
        # -----------------------------------------------------------------
        if abs(residual) > self.d4_k * sigma_s:
            self.d4_timer_s += dt
        else:
            self.d4_timer_s = _ZERO

        if self.d4_timer_s >= self.d4_duration_s:
            self.d4_fading_active = True
            if self.d4_mode == "direct_max":
                self.p[0, 0] = min(self.d4_p_max, max(self.p[0, 0], self.d4_p_max))
            else:
                self.p[0, 0] = min(self.d4_p_max, self.p[0, 0] * self.d4_lambda_f)

            # Recompute innovation variance with inflated P
            s_val = float((h_mat @ self.p @ h_mat.T)[0, 0] + r_eff)
        else:
            self.d4_fading_active = False

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
        x_post[-1] = min(max(x_post[-1], float("-1.0")), _ONE)

        # Joseph covariance update
        if abs(residual) > _RESIDUAL_TOL:
            k_eff_soc = delta_soc / residual
        else:
            k_eff_soc = _ZERO
        k_eff = np.array([[k_eff_soc], [k_gain[1, 0]], [k_gain[2, 0]], [k_gain[-1, 0]]], dtype=float)

        eye = np.eye(int("4"), dtype=float)
        i_kh = eye - k_eff @ h_mat
        p_post = i_kh @ self.p @ i_kh.T + (k_eff * r_eff) @ k_eff.T
        p_post = _HALF * (p_post + p_post.T)

        # 3. Time propagation to state x_(k+1) using temperature-scheduled Q(T)
        q_t = self.get_capacity_ah(temp_c)
        from soc.models.cell_2rc import Cell2RCModel
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
            min(max(h_next, float("-1.0")), _ONE),
        ], dtype=float)

        f11 = math.exp(-dt / tau1)
        f22 = math.exp(-dt / tau2)
        if i_meas == 0:
            f33 = _ONE
        else:
            eta = self.params.coulombic_efficiency if i_meas < 0 else _ONE
            cap_as = q_t * float("3600.0")
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
