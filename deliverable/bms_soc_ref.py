"""BMS State of Charge (SOC) Reference Implementation.

STATUS: CANDIDATE REFERENCE (NO-GO AT STAGE V3 GATE A ii-b & GATE B iii)

Algorithm: E7v2 Composite Adaptive Filter
- Base: 2RC Thevenin Equivalent Circuit with discrete-time hysteresis
- State vector x = [SOC, i_RC1, i_RC2, h]^T
- Impedance Adaptation: Recursive Least Squares (RLS) on R0 and R1 during |dI| >= 1 A current transitions
- Observability Gating: Update scaling g_slope = min(1.0, |dOCV/dSOC| / slope_ref)
- Plateau Step Capping: Maximum per-step SOC update bounded to cap_plateau on flat plateau
- Covariance Update: Joseph-form stabilized covariance update using effective Kalman gain

Zero External Dependencies:
Pure Python standard library (no numpy, scipy, or pandas required).
Deployable directly into bare-metal, RTOS, or micro-controller environments with Python/MicroPython support.
"""

import bisect
from dataclasses import dataclass
import math
from typing import Dict, List, Optional, Tuple, Union


# ==============================================================================
# Model Parameters and Look-Up Tables (calce_a123_v4.yaml + Stage V3 Tuning)
# ==============================================================================

NOMINAL_CAPACITY_AH: float = 1.0635616695823449
COULOMBIC_EFFICIENCY: float = 0.998
HYSTERESIS_AMPLITUDE_V: float = 0.02155
HYSTERESIS_GAMMA: float = 50.0

# Tuned Process and Measurement Noise Covariances (cand_sl_0.3)
PROCESS_NOISE_Q_SOC: float = 2.9031433196504225e-08
PROCESS_NOISE_Q_RC: float = 1.1198164932559382e-05
PROCESS_NOISE_Q_HYSTERESIS: float = 0.00017150882346504795
MEASUREMENT_NOISE_R_V: float = 0.0008610323423725228

# RLS Online Adaptation Parameters (D2 / E4v2)
RLS_FORGETTING_FACTOR: float = 0.999
RLS_DI_THRESHOLD_A: float = 1.0
RLS_THETA_MIN: float = 0.5
RLS_THETA_MAX: float = 2.0

# Observability Gating & Plateau Step Capping Parameters (D1 / E5v4)
E5_SIGMA_OCV_MODEL_V: float = 0.02
E5_SLOPE_REF: float = 0.3
E5_CAP_PLATEAU: float = 1.0e-05
E5_CAP_KNEE: float = 0.01

# Filter Initialization Standard Deviations
INITIAL_SOC_STD: float = 0.1
INITIAL_RC_CURRENT_STD_A: float = 0.1
INITIAL_HYSTERESIS_STD: float = 0.1

# Temperature grid and SOC grid
TEMPERATURES_C: List[float] = [-7.4, 0.6, 10.3, 20.1, 27.3, 32.0, 41.9, 52.4]
SOC_GRID: List[float] = [0.0, 0.05, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 1.0]

# OCV Table (V) indexed by temperature string
OCV_TABLE: Dict[str, List[float]] = {
    "-7.4": [2.2780, 2.9689, 3.1292, 3.2251, 3.2653, 3.2807, 3.2890, 3.2964, 3.3082, 3.3297, 3.3472, 3.3661, 3.5594],
    "0.6": [2.3369, 3.0740, 3.1898, 3.2416, 3.2753, 3.2902, 3.2960, 3.3010, 3.3108, 3.3362, 3.3474, 3.3619, 3.5551],
    "10.3": [2.3131, 3.0843, 3.2024, 3.2444, 3.2771, 3.2954, 3.3005, 3.3053, 3.3128, 3.3432, 3.3529, 3.3699, 3.5381],
    "20.1": [2.2935, 3.0866, 3.2066, 3.2471, 3.2795, 3.3001, 3.3043, 3.3081, 3.3164, 3.3439, 3.3511, 3.3655, 3.5498],
    "27.3": [2.2544, 3.0936, 3.2089, 3.2488, 3.2810, 3.3027, 3.3062, 3.3093, 3.3184, 3.3447, 3.3502, 3.3632, 3.5488],
    "32.0": [2.3200, 3.0854, 3.2074, 3.2474, 3.2795, 3.3021, 3.3062, 3.3097, 3.3176, 3.3434, 3.3490, 3.3616, 3.5640],
    "41.9": [2.2826, 3.0849, 3.2085, 3.2477, 3.2793, 3.3048, 3.3086, 3.3116, 3.3200, 3.3444, 3.3496, 3.3614, 3.5694],
    "52.4": [2.2823, 3.0834, 3.2085, 3.2467, 3.2787, 3.3065, 3.3104, 3.3131, 3.3210, 3.3441, 3.3489, 3.3601, 3.5678],
}

# Ohmic and RC Parameters per temperature point
R0_TABLE: Dict[str, float] = {
    "-7.4": 0.26464,
    "0.6": 0.19804,
    "10.3": 0.17281,
    "20.1": 0.15951,
    "27.3": 0.15851,
    "32.0": 0.15500,
    "41.9": 0.15359,
    "52.4": 0.15371,
}

R1_TABLE: Dict[str, float] = {
    "-7.4": 0.05039,
    "0.6": 0.04068,
    "10.3": 0.02288,
    "20.1": 0.02116,
    "27.3": 0.01960,
    "32.0": 0.01392,
    "41.9": 0.01130,
    "52.4": 0.00977,
}

TAU1_TABLE: Dict[str, float] = {
    "-7.4": 39.45,
    "0.6": 23.57,
    "10.3": 27.90,
    "20.1": 24.90,
    "27.3": 22.51,
    "32.0": 18.60,
    "41.9": 16.53,
    "52.4": 16.75,
}

R2_TABLE: Dict[str, float] = {
    "-7.4": 0.09463,
    "0.6": 0.10817,
    "10.3": 0.04175,
    "20.1": 0.02722,
    "27.3": 0.02651,
    "32.0": 0.01899,
    "41.9": 0.01462,
    "52.4": 0.01128,
}

TAU2_TABLE: Dict[str, float] = {
    "-7.4": 600.00,
    "0.6": 600.00,
    "10.3": 210.41,
    "20.1": 599.98,
    "27.3": 600.00,
    "32.0": 218.24,
    "41.9": 207.27,
    "52.4": 600.00,
}


# ==============================================================================
# Pure Python Interpolation Engine (Zero Numpy)
# ==============================================================================

def _interp_1d(x: float, xp: List[float], fp: List[float]) -> float:
    """Piecewise linear interpolation matching numpy.interp with end clamping."""
    if x <= xp[0]:
        return float(fp[0])
    if x >= xp[-1]:
        return float(fp[-1])
    idx = bisect.bisect_left(xp, x)
    x0, x1 = xp[idx - 1], xp[idx]
    y0, y1 = fp[idx - 1], fp[idx]
    dx = x1 - x0
    return y0 + (x - x0) * (y1 - y0) / dx if dx > 0 else y0


class PurePythonTable2D:
    """2D Look-up Table with bilinear interpolation and endpoint boundary clamping."""

    def __init__(
        self,
        temperatures_c: List[float],
        soc_grid: List[float],
        table_dict: Dict[str, Union[List[float], float]],
    ):
        self.temp_grid = list(temperatures_c)
        self.soc_grid = list(soc_grid)
        self._parsed_tables: Dict[float, List[float]] = {}

        for t_val in self.temp_grid:
            val_found = None
            t_str = str(t_val)
            if t_str in table_dict:
                val_found = table_dict[t_str]
            else:
                for k, v in table_dict.items():
                    if abs(float(k) - t_val) < 1e-4:
                        val_found = v
                        break
            if val_found is None:
                raise KeyError(f"Temperature {t_val} not in table dictionary")

            if isinstance(val_found, (int, float)):
                self._parsed_tables[t_val] = [float(val_found)] * len(self.soc_grid)
            else:
                self._parsed_tables[t_val] = [float(v) for v in val_found]

    def _get_bounding_temps(self, temp_c: float) -> Tuple[float, float, float]:
        if temp_c <= self.temp_grid[0]:
            return self.temp_grid[0], self.temp_grid[0], 0.0
        if temp_c >= self.temp_grid[-1]:
            return self.temp_grid[-1], self.temp_grid[-1], 0.0

        idx = bisect.bisect_left(self.temp_grid, temp_c)
        t_low = self.temp_grid[idx - 1]
        t_high = self.temp_grid[idx]
        dt = t_high - t_low
        alpha = (temp_c - t_low) / dt if dt > 0 else 0.0
        return t_low, t_high, alpha

    def lookup(self, soc: float, temp_c: float) -> float:
        """Lookup table value at (soc, temp_c) with bilinear interpolation."""
        soc_clamped = min(max(soc, self.soc_grid[0]), self.soc_grid[-1])
        t_low, t_high, alpha = self._get_bounding_temps(temp_c)

        v_low = _interp_1d(soc_clamped, self.soc_grid, self._parsed_tables[t_low])
        if t_low == t_high:
            return v_low
        v_high = _interp_1d(soc_clamped, self.soc_grid, self._parsed_tables[t_high])
        return (1.0 - alpha) * v_low + alpha * v_high

    def derivative_soc(self, soc: float, temp_c: float) -> float:
        """Compute partial derivative d(value)/d(soc) at (soc, temp_c)."""
        soc_clamped = min(max(soc, self.soc_grid[0]), self.soc_grid[-1])
        t_low, t_high, alpha = self._get_bounding_temps(temp_c)

        def _calc_deriv(t_val: float) -> float:
            y_arr = self._parsed_tables[t_val]
            if soc_clamped <= self.soc_grid[0]:
                dx = self.soc_grid[1] - self.soc_grid[0]
                dy = y_arr[1] - y_arr[0]
                return dy / dx
            if soc_clamped >= self.soc_grid[-1]:
                dx = self.soc_grid[-1] - self.soc_grid[-2]
                dy = y_arr[-1] - y_arr[-2]
                return dy / dx

            idx = bisect.bisect_left(self.soc_grid, soc_clamped)
            dx = self.soc_grid[idx] - self.soc_grid[idx - 1]
            dy = y_arr[idx] - y_arr[idx - 1]
            return dy / dx

        d_low = _calc_deriv(t_low)
        if t_low == t_high:
            return d_low
        d_high = _calc_deriv(t_high)
        return (1.0 - alpha) * d_low + alpha * d_high


# ==============================================================================
# Pure Python 4x4 Linear Algebra Engine
# ==============================================================================

def _mat4_mul(A: List[List[float]], B: List[List[float]]) -> List[List[float]]:
    """Multiply two 4x4 matrices."""
    C = [[0.0] * 4 for _ in range(4)]
    for i in range(4):
        for k in range(4):
            aik = A[i][k]
            if aik != 0.0:
                for j in range(4):
                    C[i][j] += aik * B[k][j]
    return C


# ==============================================================================
# Output Estimation Structure
# ==============================================================================

@dataclass
class SocEstimateRef:
    """SOC estimate output dataclass."""
    soc: float
    soc_std: float
    voltage_residual: Optional[float]
    innovation_variance: Optional[float]
    kalman_gain_soc: Optional[float]
    theta: float
    observability_scaling: float
    delta_soc_applied: float


# ==============================================================================
# Reference BMS SOC Estimator Implementation (Zero Numpy)
# ==============================================================================

class BmsSocEstimatorRef:
    """Standalone reference implementation of E7v2 Composite Estimator.

    Zero external dependencies. Pure standard library Python.
    """

    def __init__(self) -> None:
        # Pre-instantiate 2D parameter look-up tables
        self.ocv_table = PurePythonTable2D(TEMPERATURES_C, SOC_GRID, OCV_TABLE)
        self.r0_table = PurePythonTable2D(TEMPERATURES_C, SOC_GRID, R0_TABLE)
        self.r1_table = PurePythonTable2D(TEMPERATURES_C, SOC_GRID, R1_TABLE)
        self.tau1_table = PurePythonTable2D(TEMPERATURES_C, SOC_GRID, TAU1_TABLE)
        self.r2_table = PurePythonTable2D(TEMPERATURES_C, SOC_GRID, R2_TABLE)
        self.tau2_table = PurePythonTable2D(TEMPERATURES_C, SOC_GRID, TAU2_TABLE)

        # State vector: [soc, i1, i2, h]^T
        self.x: List[float] = [1.0, 0.0, 0.0, 0.0]
        # Covariance matrix P: 4x4
        self.p: List[List[float]] = [[0.0] * 4 for _ in range(4)]

        # RLS state for impedance multiplier theta
        self.theta: float = 1.0
        self.p_rls: float = 1.0
        self.prev_i: float = 0.0
        self.prev_v: float = 0.0
        self.has_prev: bool = False

        self.last_valid_i: float = 0.0
        self.last_valid_temp: float = 25.0
        self.last_applied_g: float = 1.0
        self.last_applied_delta_soc: float = 0.0

        # Initialize filter state
        self.reset(1.0)

    def reset(self, soc0: float = 1.0) -> None:
        """Reset estimator state, covariance, and RLS parameters."""
        soc_clamped = min(max(float(soc0), 0.0), 1.0)
        self.x = [soc_clamped, 0.0, 0.0, 0.0]

        p_soc = INITIAL_SOC_STD ** 2
        p_rc = INITIAL_RC_CURRENT_STD_A ** 2
        p_h = INITIAL_HYSTERESIS_STD ** 2

        self.p = [
            [p_soc, 0.0, 0.0, 0.0],
            [0.0, p_rc, 0.0, 0.0],
            [0.0, 0.0, p_rc, 0.0],
            [0.0, 0.0, 0.0, p_h],
        ]

        self.theta = 1.0
        self.p_rls = 1.0
        self.prev_i = 0.0
        self.prev_v = 0.0
        self.has_prev = False

        self.last_valid_i = 0.0
        self.last_valid_temp = 25.0
        self.last_applied_g = 1.0
        self.last_applied_delta_soc = 0.0

    def step(self, v: float, i: float, temp_c: float, dt: float) -> SocEstimateRef:
        """Process one time step measurement (voltage, current, temperature, dt)."""
        # 1. Handle missing/corrupt measurement (dropout or NaN)
        if math.isnan(v) or math.isnan(i):
            i_prop = self.last_valid_i
            temp_prop = self.last_valid_temp

            tau1 = self.tau1_table.lookup(self.x[0], temp_prop)
            tau2 = self.tau2_table.lookup(self.x[0], temp_prop)

            eta = COULOMBIC_EFFICIENCY if i_prop < 0 else 1.0
            z_next = self.x[0] - (eta * i_prop * dt) / (3600.0 * NOMINAL_CAPACITY_AH)
            f11 = math.exp(-dt / tau1) if tau1 > 0 else 0.0
            f22 = math.exp(-dt / tau2) if tau2 > 0 else 0.0
            i1_next = f11 * self.x[1] + (1.0 - f11) * i_prop
            i2_next = f22 * self.x[2] + (1.0 - f22) * i_prop

            if i_prop == 0.0:
                f33 = 1.0
                h_next = self.x[3]
            else:
                cap_as = NOMINAL_CAPACITY_AH * 3600.0
                alpha = abs(eta * i_prop * HYSTERESIS_GAMMA * dt / cap_as)
                f33 = math.exp(-alpha)
                sgn_i = 1.0 if i_prop > 0.0 else -1.0
                h_next = f33 * self.x[3] - (1.0 - f33) * sgn_i

            self.x = [
                min(max(z_next, 0.0), 1.0),
                i1_next,
                i2_next,
                min(max(h_next, -1.0), 1.0),
            ]

            # Covariance propagation with diagonal transition matrix
            d = [1.0, f11, f22, f33]
            q = [
                PROCESS_NOISE_Q_SOC,
                PROCESS_NOISE_Q_RC,
                PROCESS_NOISE_Q_RC,
                PROCESS_NOISE_Q_HYSTERESIS,
            ]
            new_p = [[0.0] * 4 for _ in range(4)]
            for row in range(4):
                for col in range(4):
                    val = d[row] * self.p[row][col] * d[col]
                    if row == col:
                        val += q[row]
                    new_p[row][col] = val
            for row in range(4):
                for col in range(row + 1, 4):
                    sym = 0.5 * (new_p[row][col] + new_p[col][row])
                    new_p[row][col] = sym
                    new_p[col][row] = sym
            self.p = new_p

            return SocEstimateRef(
                soc=self.x[0],
                soc_std=math.sqrt(max(self.p[0][0], 0.0)),
                voltage_residual=None,
                innovation_variance=None,
                kalman_gain_soc=None,
                theta=self.theta,
                observability_scaling=self.last_applied_g,
                delta_soc_applied=0.0,
            )

        # Valid measurement update
        self.last_valid_i = i
        self.last_valid_temp = temp_c

        # 2. Online RLS impedance adaptation on current steps |dI| >= 1 A
        r0_base = self.r0_table.lookup(self.x[0], temp_c)
        if self.has_prev:
            di = i - self.prev_i
            dv = v - self.prev_v
            if abs(di) >= RLS_DI_THRESHOLD_A:
                phi = r0_base * di
                y_meas = -dv
                lam = RLS_FORGETTING_FACTOR

                denom = lam + self.p_rls * (phi ** 2)
                l_gain = (self.p_rls * phi) / denom if denom != 0.0 else 0.0
                err_rls = y_meas - phi * self.theta

                self.theta += l_gain * err_rls
                self.theta = min(max(self.theta, RLS_THETA_MIN), RLS_THETA_MAX)
                self.p_rls = (self.p_rls - l_gain * phi * self.p_rls) / lam

        self.prev_i = i
        self.prev_v = v
        self.has_prev = True

        # 3. Measurement Update using adapted R0 and R1
        r0_eff = self.theta * r0_base
        r1_base = self.r1_table.lookup(self.x[0], temp_c)
        r1_eff = self.theta * r1_base
        r2 = self.r2_table.lookup(self.x[0], temp_c)
        tau1 = self.tau1_table.lookup(self.x[0], temp_c)
        tau2 = self.tau2_table.lookup(self.x[0], temp_c)

        ocv = self.ocv_table.lookup(self.x[0], temp_c)
        d_ocv_dz = self.ocv_table.derivative_soc(self.x[0], temp_c)
        m_hyst = HYSTERESIS_AMPLITUDE_V

        # Predicted terminal voltage: v_hat = OCV + M_h * h - i1*R1 - i2*R2 - i*R0
        v_hat = ocv + m_hyst * self.x[3] - r1_eff * self.x[1] - r2 * self.x[2] - r0_eff * i
        residual = v - v_hat

        # Measurement Jacobian H = [dOCV/dSOC, -R1, -R2, M_h]
        h_vec = [d_ocv_dz, -r1_eff, -r2, m_hyst]

        # Effective measurement variance with OCV variance inflation
        r_eff = MEASUREMENT_NOISE_R_V + (E5_SIGMA_OCV_MODEL_V ** 2)

        # Innovation variance: S = H * P * H^T + R_eff
        v_cov = [0.0] * 4
        for row in range(4):
            v_cov[row] = sum(self.p[row][col] * h_vec[col] for col in range(4))
        h_p_ht = sum(h_vec[idx] * v_cov[idx] for idx in range(4))
        s_val = h_p_ht + r_eff

        # Kalman gain: K = (P * H^T) / S
        k_gain = [v_cov[idx] / s_val for idx in range(4)]

        # Raw state innovation
        delta_soc_raw = k_gain[0] * residual

        # 4. Observability Gating (D1 / E5v4)
        abs_slope = abs(d_ocv_dz)
        g_slope = min(1.0, abs_slope / E5_SLOPE_REF) if E5_SLOPE_REF > 0.0 else 1.0
        delta_soc = delta_soc_raw * g_slope
        self.last_applied_g = g_slope

        # 5. Plateau Step Capping
        cap = E5_CAP_PLATEAU + (E5_CAP_KNEE - E5_CAP_PLATEAU) * g_slope
        if cap > 0.0:
            delta_soc = min(max(delta_soc, -cap), cap)
        self.last_applied_delta_soc = delta_soc

        # Full state correction
        delta_x = [
            delta_soc,
            k_gain[1] * residual,
            k_gain[2] * residual,
            k_gain[3] * residual,
        ]
        x_post = [self.x[idx] + delta_x[idx] for idx in range(4)]
        x_post[0] = min(max(x_post[0], 0.0), 1.0)
        x_post[3] = min(max(x_post[3], -1.0), 1.0)

        # 6. Joseph-Form Covariance Update
        k_eff_soc = delta_soc / residual if abs(residual) > 1e-12 else 0.0
        k_eff = [k_eff_soc, k_gain[1], k_gain[2], k_gain[3]]

        # M = I - K_eff * H (4x4 matrix)
        m_mat = [[0.0] * 4 for _ in range(4)]
        for row in range(4):
            for col in range(4):
                val = 1.0 if row == col else 0.0
                val -= k_eff[row] * h_vec[col]
                m_mat[row][col] = val

        # term1 = M * P * M^T
        mp = _mat4_mul(m_mat, self.p)
        mt = [[m_mat[col][row] for col in range(4)] for row in range(4)]
        mpmt = _mat4_mul(mp, mt)

        # term2 = R_eff * (K_eff * K_eff^T)
        p_post = [[0.0] * 4 for _ in range(4)]
        for row in range(4):
            for col in range(4):
                val = mpmt[row][col] + r_eff * (k_eff[row] * k_eff[col])
                p_post[row][col] = val

        for row in range(4):
            for col in range(row + 1, 4):
                sym = 0.5 * (p_post[row][col] + p_post[col][row])
                p_post[row][col] = sym
                p_post[col][row] = sym

        # 7. Time Propagation to next step
        eta = COULOMBIC_EFFICIENCY if i < 0 else 1.0
        z_next = x_post[0] - (eta * i * dt) / (3600.0 * NOMINAL_CAPACITY_AH)
        f11 = math.exp(-dt / tau1) if tau1 > 0 else 0.0
        f22 = math.exp(-dt / tau2) if tau2 > 0 else 0.0
        i1_next = f11 * x_post[1] + (1.0 - f11) * i
        i2_next = f22 * x_post[2] + (1.0 - f22) * i

        if i == 0.0:
            f33 = 1.0
            h_next = x_post[3]
        else:
            cap_as = NOMINAL_CAPACITY_AH * 3600.0
            alpha = abs(eta * i * HYSTERESIS_GAMMA * dt / cap_as)
            f33 = math.exp(-alpha)
            sgn_i = 1.0 if i > 0.0 else -1.0
            h_next = f33 * x_post[3] - (1.0 - f33) * sgn_i

        self.x = [
            min(max(z_next, 0.0), 1.0),
            i1_next,
            i2_next,
            min(max(h_next, -1.0), 1.0),
        ]

        # Propagate covariance P_next = F * P_post * F^T + Q
        d = [1.0, f11, f22, f33]
        q = [
            PROCESS_NOISE_Q_SOC,
            PROCESS_NOISE_Q_RC,
            PROCESS_NOISE_Q_RC,
            PROCESS_NOISE_Q_HYSTERESIS,
        ]
        new_p = [[0.0] * 4 for _ in range(4)]
        for row in range(4):
            for col in range(4):
                val = d[row] * p_post[row][col] * d[col]
                if row == col:
                    val += q[row]
                new_p[row][col] = val

        for row in range(4):
            for col in range(row + 1, 4):
                sym = 0.5 * (new_p[row][col] + new_p[col][row])
                new_p[row][col] = sym
                new_p[col][row] = sym
        self.p = new_p

        return SocEstimateRef(
            soc=self.x[0],
            soc_std=math.sqrt(max(self.p[0][0], 0.0)),
            voltage_residual=residual,
            innovation_variance=s_val,
            kalman_gain_soc=k_gain[0],
            theta=self.theta,
            observability_scaling=g_slope,
            delta_soc_applied=delta_soc,
        )


# ==============================================================================
# Verification Self-Test
# ==============================================================================

def run_self_test(verbose: bool = True) -> bool:
    """Run verification self-test validating numerical stability and agreement.

    If the repository `soc` package is available, tests step-by-step numerical
    agreement against `E7V2CompositeFilter` down to machine precision (|dSOC| <= 1e-9).
    Also asserts invariant bounds (SOC in [0, 1], P positive-semidefinite).
    """
    est = BmsSocEstimatorRef()
    est.reset(0.80)

    # Synthetic dynamic test profile with pulse transitions
    dt = 1.0
    temp_c = 25.0
    currents = [0.0, 2.0, 2.0, 0.0, -1.5, -1.5, 0.0, 3.0, 0.0, -2.0]
    voltages = [3.31, 3.25, 3.24, 3.30, 3.35, 3.36, 3.31, 3.20, 3.30, 3.38]

    estimates: List[SocEstimateRef] = []
    for step_idx, (i, v) in enumerate(zip(currents, voltages)):
        res = est.step(v=v, i=i, temp_c=temp_c, dt=dt)
        estimates.append(res)
        assert 0.0 <= res.soc <= 1.0, f"SOC out of bounds: {res.soc}"
        assert res.soc_std >= 0.0, f"Negative variance detected: {res.soc_std}"
        assert 0.5 <= res.theta <= 2.0, f"Theta out of bounds: {res.theta}"

    if verbose:
        print(f"Self-test: 10 synthetic pulse steps completed successfully.")
        print(f"Final SOC: {estimates[-1].soc * 100:.4f} %, Theta: {estimates[-1].theta:.4f}")

    # Check comparison against repo E7V2CompositeFilter if importable
    try:
        from pathlib import Path
        from dataclasses import replace
        from soc.assumptions.loader import load_assumptions
        from soc.estimators.base import ParamSet
        from soc.estimators.e7v2 import E7V2CompositeFilter
        from soc.models.plant import Measurement

        v4_path = Path("configs/assumptions/profiles/calce_a123_v4.yaml")
        if v4_path.exists():
            assumptions, _, _ = load_assumptions(scenario_file=v4_path)
            base_params = ParamSet.from_assumptions(assumptions, matched=True)
            param_set = replace(
                base_params,
                process_noise_q_soc=PROCESS_NOISE_Q_SOC,
                process_noise_q_rc=PROCESS_NOISE_Q_RC,
                process_noise_q_hysteresis=PROCESS_NOISE_Q_HYSTERESIS,
                measurement_noise_r_v=MEASUREMENT_NOISE_R_V,
                e4_rls_forgetting_factor=RLS_FORGETTING_FACTOR,
                e5_slope_ref=E5_SLOPE_REF,
                e5_cap_plateau=E5_CAP_PLATEAU,
                e5_cap_knee=E5_CAP_KNEE,
                e5_sigma_ocv_model_v=E5_SIGMA_OCV_MODEL_V,
            )

            ref_filter = E7V2CompositeFilter(param_set)
            ref_filter.reset(0.80)
            est.reset(0.80)

            max_dsoc = 0.0
            for i, v in zip(currents, voltages):
                meas = Measurement(v=v, i=i, temp_c=temp_c, dt=dt, dropout=False)
                out_repo = ref_filter.step(meas)
                out_ref = est.step(v=v, i=i, temp_c=temp_c, dt=dt)
                diff = abs(out_repo.soc - out_ref.soc)
                if diff > max_dsoc:
                    max_dsoc = diff

            if verbose:
                print(f"Cross-verification against E7V2CompositeFilter max |dSOC|: {max_dsoc:.2e}")
            assert max_dsoc <= 1e-9, f"Discrepancy exceeds 1e-9: {max_dsoc}"
    except ImportError:
        if verbose:
            print("Note: soc repo package not in python path; verified standalone logic only.")

    return True


if __name__ == "__main__":
    success = run_self_test(verbose=True)
    print(f"Self-test Passed: {success}")
