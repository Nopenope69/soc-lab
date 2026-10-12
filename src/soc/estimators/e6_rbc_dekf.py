"""E6: Residual Bias Compensation Dual Extended Kalman Filter (RBC-DEKF).

Reference:
    Guo et al. (2026), "Residual Bias Compensation Dual Extended Kalman Filter for
    Physics-Based SOC Estimation in Lithium Iron Phosphate Batteries",
    arXiv:2510.22813v2.

Mathematical Formulation & Equation Mapping:
    1. Discrete-Time State-Space & Residual Bias Model:
       x_{k+1} = f(x_k, u_k) + w_k,        w_k ~ N(0, Q_x)            [Eq. 14]
       theta_{k+1} = theta_k + w_{theta,k}, w_{theta,k} ~ N(0, Q_theta) [Eq. 19]
       z_k = V(x_k, u_k) + theta_k + v_k,   v_k ~ N(0, R_x)            [Eq. 20, 39]
       H^x_k = dV/dx                                                   [Eq. 40]
       H^theta_k = d(V + theta)/dtheta = 1.0                            [Eq. 41]

    2. Step-by-Step Implementation Sequence (Section III):
       Step 1: State-filter prediction and voltage prediction          [Eqs. 21-24]
               x_hat_{k|k-1} = f(x_hat_{k-1|k-1}, u_{k-1})             [Eq. 21]
               P^x_{k|k-1} = F_x P^x_{k-1|k-1} F_x^T + Q_x             [Eq. 22]
               V_hat_k = V(x_hat_{k|k-1}, u_k)                         [Eq. 24]
       Step 2: State-filter update using previous theta_{k-1|k-1}      [Eqs. 25-29]
               y^x_k = z_k - (V_hat_k + theta_hat_{k-1|k-1})           [Eq. 25]
               S^x_k = H^x_k P^x_{k|k-1} (H^x_k)^T + R_x               [Eq. 26]
               K^x_k = P^x_{k|k-1} (H^x_k)^T (S^x_k)^{-1}              [Eq. 27]
               x_hat_{k|k} = x_hat_{k|k-1} + K^x_k y^x_k               [Eq. 28]
               P^x_{k|k} = (I - K^x_k H^x_k) P^x_{k|k-1} (I - K^x_k H^x_k)^T
                           + K^x_k R_x (K^x_k)^T (Joseph form)         [Eq. 29]
       Step 3: Residual-bias filter prediction and voltage prediction  [Eqs. 30-33]
               theta_hat_{k|k-1} = theta_hat_{k-1|k-1}                 [Eq. 30]
               P^theta_{k|k-1} = P^theta_{k-1|k-1} + Q_theta           [Eq. 31]
               V_hat^x_k = V(x_hat_{k|k}, u_k)                         [Eq. 33]
       Step 4: Residual-bias filter update                             [Eqs. 34-38]
               y^theta_k = z_k - (V_hat^x_k + theta_hat_{k|k-1})       [Eq. 34]
               S^theta_k = P^theta_{k|k-1} + R_theta                   [Eq. 35]
               K^theta_k = P^theta_{k|k-1} / S^theta_k                 [Eq. 36]
               theta_hat_{k|k} = theta_hat_{k|k-1} + K^theta_k y^theta_k [Eq. 37]
               P^theta_{k|k} = (1 - K^theta_k)^2 P^theta_{k|k-1}
                               + (K^theta_k)^2 R_theta (Joseph form)   [Eq. 38]

Assumptions (listed explicitly per prompt instructions):
    - Assumption 1 (Model Adaptation): The paper formulates RBC-DEKF on a CPG-SPMT
      electrochemical model. Per task specification, RBC-DEKF is implemented with
      the 2RC equivalent circuit model, supporting 4 states [soc, i1, i2, h] when
      rbc_use_hysteresis_state is true, and 3 states [soc, i1, i2] when false.
    - Assumption 2 (Timing Alignment): Step 1 propagates state from step k-1 to k
      under excitation u_k over dt, and evaluates terminal voltage prediction V_hat_k.
      Step 2 corrects this state using measurement z_k and previous bias theta_{k-1|k-1}.
      Step 3 predicts bias and evaluates V_hat^x_k at the updated state x_{k|k}.
      Step 4 updates bias on z_k. The post-update state x_{k|k} aligns with truth at step k.
    - Assumption 3 (Bias Decoupling): Bias Jacobian H^theta = 1.0 (Eq. 41). The bias does
      not enter electrochemical state dynamics (Eq. 14) or state Jacobian H^x (Eq. 40).
    - Assumption 4 (Dropout Handling): On dropped samples (dropout=True or NaN), both
      state and bias filters execute predict-only (Eqs. 21-22 and 30-31) and bypass updates.
    - Assumption 5 (Covariance Numerics): Covariances are updated in Joseph stabilized form
      (Eqs. 29, 38) with explicit symmetrization to maintain positive semi-definiteness.
"""

import math
from typing import List, Optional, Tuple
import numpy as np

from soc.estimators.base import Estimator, ParamSet, SocEstimate
from soc.models.cell_2rc import Cell2RCModel
from soc.models.plant import Measurement
from soc.models.tables import InterpolatedTable2D


class E6RBCDEKF(Estimator):
    """Residual Bias Compensation Dual Extended Kalman Filter (RBC-DEKF).

    Couples a battery state filter with an independent residual voltage bias filter.
    """

    def __init__(self, params: ParamSet):
        self.params = params
        self.use_hysteresis = bool(self.params.rbc_use_hysteresis_state)

        temps = list(self.params.temperatures_c)
        socs = list(self.params.soc_grid)

        # 2D look-up tables
        self.ocv_table = InterpolatedTable2D(temps, socs, self.params.ocv_table)
        self.r0_table = InterpolatedTable2D(temps, socs, self.params.r0_table)
        self.r1_table = InterpolatedTable2D(temps, socs, self.params.r1_table)
        self.tau1_table = InterpolatedTable2D(temps, socs, self.params.tau1_table)
        self.r2_table = InterpolatedTable2D(temps, socs, self.params.r2_table)
        self.tau2_table = InterpolatedTable2D(temps, socs, self.params.tau2_table)

        # State vector: [soc, i1, i2, h]^T (4 states) or [soc, i1, i2]^T (3 states)
        if self.use_hysteresis:
            self.x = np.array([float(0), float(0), float(0), float(0)], dtype=float)
        else:
            self.x = np.array([float(0), float(0), float(0)], dtype=float)

        self.p = np.zeros((len(self.x), len(self.x)), dtype=float)

        # Residual voltage bias state theta and covariance P_theta (Eqs. 19, 31)
        self.theta = float(0)
        self.p_theta = float(0)

        self.last_valid_i = float(0)
        self.last_valid_temp = float(self.params.temperatures_c[1])
        self.last_execution_order: List[str] = []

    def reset(self, soc0: float) -> None:
        """Reset estimator state, bias, and covariance matrices."""
        soc_clamped = min(max(float(soc0), float(0)), float(1))

        if self.use_hysteresis:
            self.x = np.array([soc_clamped, float(0), float(0), float(0)], dtype=float)
            p_soc = self.params.initial_soc_std ** 2
            p_rc = self.params.initial_rc_current_std_a ** 2
            p_h = self.params.initial_hysteresis_std ** 2
            self.p = np.diag([p_soc, p_rc, p_rc, p_h]).astype(float)
        else:
            self.x = np.array([soc_clamped, float(0), float(0)], dtype=float)
            p_soc = self.params.initial_soc_std ** 2
            p_rc = self.params.initial_rc_current_std_a ** 2
            self.p = np.diag([p_soc, p_rc, p_rc]).astype(float)

        # Initialize residual voltage bias and covariance
        self.theta = float(0)
        self.p_theta = float(self.params.rbc_initial_theta_std ** 2)

        self.last_valid_i = float(0)
        self.last_valid_temp = float(self.params.temperatures_c[1])
        self.last_execution_order = []

    def _compute_model_voltage(self, state: np.ndarray, i_app: float, temp_c: float) -> Tuple[float, float, float, float]:
        """Compute modeled terminal voltage V(x, u) without bias [Eqs. 24, 33, 39]."""
        soc_val = state[0]
        i1_val = state[1]
        i2_val = state[2]

        r0 = self.r0_table.lookup(soc_val, temp_c)
        r1 = self.r1_table.lookup(soc_val, temp_c)
        r2 = self.r2_table.lookup(soc_val, temp_c)
        ocv = self.ocv_table.lookup(soc_val, temp_c)

        if self.use_hysteresis:
            h_val = state[-1]
            m_hyst = self.params.hysteresis_amplitude_v
            v_model = ocv + m_hyst * h_val - r1 * i1_val - r2 * i2_val - r0 * i_app
        else:
            v_model = ocv - r1 * i1_val - r2 * i2_val - r0 * i_app

        return v_model, r0, r1, r2

    def step_1_state_predict(self, dt: float, i_prop: float, temp_prop: float) -> float:
        """Step 1: State-filter prediction and voltage prediction [Eqs. 21-24]."""
        tau1 = self.tau1_table.lookup(self.x[0], temp_prop)
        tau2 = self.tau2_table.lookup(self.x[0], temp_prop)

        # State dynamics prediction (Eq. 21)
        z_next = Cell2RCModel.step_soc(
            soc=self.x[0],
            i_a=i_prop,
            dt_s=dt,
            capacity_ah=self.params.nominal_capacity_ah,
            coulombic_efficiency=self.params.coulombic_efficiency,
        )
        i1_next = Cell2RCModel.step_rc_current(self.x[1], i_prop, dt, tau1)
        i2_next = Cell2RCModel.step_rc_current(self.x[2], i_prop, dt, tau2)

        if self.use_hysteresis:
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

            # Transition Jacobian F_x
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
        else:
            self.x = np.array([
                min(max(z_next, float(0)), float(1)),
                i1_next,
                i2_next,
            ], dtype=float)

            f11 = math.exp(-dt / tau1)
            f22 = math.exp(-dt / tau2)
            f_mat = np.diag([float(1), f11, f22])
            q_mat = np.diag([
                self.params.process_noise_q_soc,
                self.params.process_noise_q_rc,
                self.params.process_noise_q_rc,
            ])

        # State error covariance prediction (Eq. 22)
        self.p = f_mat @ self.p @ f_mat.T + q_mat
        self.p = (self.p + self.p.T) / 2

        # Predicted terminal voltage V_hat_k (Eqs. 23-24)
        v_hat, _, _, _ = self._compute_model_voltage(self.x, i_prop, temp_prop)
        self.last_execution_order.append("state_predict")
        return v_hat

    def step_2_state_update(
        self,
        v_meas: float,
        v_hat: float,
        i_prop: float,
        temp_prop: float,
        theta_prev: float,
    ) -> Tuple[float, float, float]:
        """Step 2: State-filter update using previous bias estimate [Eqs. 25-29]."""
        # Innovation using previous bias theta_{k-1|k-1} (Eq. 25)
        y_x = v_meas - (v_hat + theta_prev)

        # Observation Jacobian H_x (Eq. 40)
        d_ocv_dz = self.ocv_table.derivative_soc(self.x[0], temp_prop)
        r1 = self.r1_table.lookup(self.x[0], temp_prop)
        r2 = self.r2_table.lookup(self.x[0], temp_prop)

        if self.use_hysteresis:
            m_hyst = self.params.hysteresis_amplitude_v
            h_mat = np.array([[d_ocv_dz, -r1, -r2, m_hyst]], dtype=float)
        else:
            h_mat = np.array([[d_ocv_dz, -r1, -r2]], dtype=float)

        # Innovation covariance S_x (Eq. 26)
        r_x = self.params.measurement_noise_r_v
        s_val = float((h_mat @ self.p @ h_mat.T)[0, 0] + r_x)

        # Kalman gain K_x (Eq. 27)
        k_gain = (self.p @ h_mat.T) / s_val

        # State correction (Eq. 28)
        self.x = self.x + (k_gain * y_x).flatten()
        self.x[0] = min(max(self.x[0], float(0)), float(1))
        if self.use_hysteresis:
            self.x[-1] = min(max(self.x[-1], float(-1)), float(1))

        # Joseph stabilized covariance update (Eq. 29)
        eye = np.eye(len(self.x), dtype=float)
        i_kh = eye - k_gain @ h_mat
        self.p = i_kh @ self.p @ i_kh.T + (k_gain * r_x) @ k_gain.T
        self.p = (self.p + self.p.T) / 2

        self.last_execution_order.append("state_update")
        return float(y_x), float(s_val), float(k_gain[0, 0])

    def step_3_bias_predict(self, i_prop: float, temp_prop: float) -> float:
        """Step 3: Residual-bias filter prediction & voltage prediction using x_hat_{k|k} [Eqs. 30-33]."""
        # Bias time update (Eq. 30)
        # theta_hat_{k|k-1} = theta_hat_{k-1|k-1} (value retained)

        # Bias error covariance time update (Eq. 31)
        self.p_theta = self.p_theta + self.params.rbc_q_theta

        # Predicted terminal voltage using newly updated state estimate x_hat_{k|k} (Eqs. 32-33)
        v_hat_x, _, _, _ = self._compute_model_voltage(self.x, i_prop, temp_prop)
        self.last_execution_order.append("bias_predict")
        return v_hat_x

    def step_4_bias_update(self, v_meas: float, v_hat_x: float) -> Tuple[float, float, float]:
        """Step 4: Residual-bias filter update using new state estimate [Eqs. 34-38]."""
        # Bias innovation using new state prediction V_hat^x_k (Eq. 34)
        y_theta = v_meas - (v_hat_x + self.theta)

        # Innovation variance with H_theta = 1.0 (Eq. 35, 41)
        r_theta = self.params.rbc_r_theta
        s_theta = self.p_theta + r_theta

        # Bias Kalman gain (Eq. 36)
        k_theta = self.p_theta / s_theta

        # Bias correction (Eq. 37)
        self.theta = self.theta + k_theta * y_theta

        # Bias Joseph stabilized covariance update (Eq. 38)
        # P_theta = (1 - K_theta)^2 * P_theta + (K_theta)^2 * R_theta
        self.p_theta = ((float(1) - k_theta) ** 2) * (self.p_theta) + (k_theta ** 2) * r_theta

        self.last_execution_order.append("bias_update")
        return float(y_theta), float(s_theta), float(k_theta)

    def step(self, measurement: Measurement) -> SocEstimate:
        """Execute four-step RBC-DEKF sequence on incoming measurement."""
        dt = measurement.dt
        self.last_execution_order = []

        # Handle dropped measurement
        if measurement.dropout or math.isnan(measurement.v) or math.isnan(measurement.i):
            i_prop = self.last_valid_i
            temp_prop = self.last_valid_temp

            # Predict-only for both state filter and residual bias filter (Eqs. 21-22, 30-31)
            _ = self.step_1_state_predict(dt, i_prop, temp_prop)
            _ = self.step_3_bias_predict(i_prop, temp_prop)

            return SocEstimate(
                soc=float(self.x[0]),
                soc_std=float(math.sqrt(max(self.p[0, 0], float(0)))),
                anchor_used=False,
                voltage_residual=None,
                innovation_variance=None,
                kalman_gain_soc=None,
                theta=float(self.theta),
                theta_std=float(math.sqrt(max(self.p_theta, float(0)))),
            )

        # Valid measurement: update last valid inputs
        self.last_valid_i = measurement.i
        self.last_valid_temp = measurement.temp_c
        temp_c = measurement.temp_c
        i_meas = measurement.i
        v_meas = measurement.v

        # Preserve previous bias estimate theta_{k-1|k-1} for Step 2
        theta_prev = self.theta

        # Four-step sequence per Section III and user design contract:
        # 1. State-filter prediction and voltage prediction (Eqs. 21-24)
        v_hat = self.step_1_state_predict(dt, i_meas, temp_c)

        # 2. State-filter update using previous theta_{k-1|k-1} (Eqs. 25-29)
        y_x, s_x, k_soc = self.step_2_state_update(v_meas, v_hat, i_meas, temp_c, theta_prev)

        # 3. Residual-bias filter prediction and voltage prediction using x_hat_{k|k} (Eqs. 30-33)
        v_hat_x = self.step_3_bias_predict(i_meas, temp_c)

        # 4. Residual-bias filter update using new state estimate (Eqs. 34-38)
        _, _, _ = self.step_4_bias_update(v_meas, v_hat_x)

        return SocEstimate(
            soc=float(self.x[0]),
            soc_std=float(math.sqrt(max(self.p[0, 0], float(0)))),
            anchor_used=False,
            voltage_residual=float(y_x),
            innovation_variance=float(s_x),
            kalman_gain_soc=float(k_soc),
            theta=float(self.theta),
            theta_std=float(math.sqrt(max(self.p_theta, float(0)))),
        )
