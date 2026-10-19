"""BMS State of Charge (SOC) Reference Implementation.

STATUS: GATE-PASSED (Gauntlet V3, Stage V3 & Stage V5 Passed)

Algorithm: E7v3 Confidence-Aware Composite Adaptive Estimator
- Base: 2RC Thevenin Equivalent Circuit with discrete-time hysteresis
- State vector: x = [SOC, i_RC1, i_RC2, h]^T
- Confidence-Aware Start: reset(soc0, soc_std) configures initial P_soc
- Temperature-Scheduled Capacity Q(T) and Hysteresis Amplitude M(T)
- Impedance Adaptation: Recursive Least Squares (RLS) on R0 and R1 during |dI| >= 1 A current transitions
- Observability Gating: Update scaling g_slope = min(1.0, |dOCV/dSOC| / slope_ref)
- Plateau Step Capping: Maximum per-step SOC update bounded to cap_plateau on flat plateau
- Covariance Update: Joseph-form stabilized covariance update using effective Kalman gain

Zero External Dependencies:
Pure Python standard library (no numpy, scipy, pydantic, or yaml required).
Deployable directly into bare-metal, RTOS, or micro-controller environments with Python/MicroPython support.
"""

import bisect
from dataclasses import dataclass, field
import math
from typing import Dict, List, Optional, Tuple


# ==============================================================================
# Model Parameters and Look-Up Tables (calce_a123_v4 + Gauntlet V3 Freeze)
# ==============================================================================

# Temperature Grid (°C) for Tables
TEMPERATURES_C: List[float] = [-7.4, 0.6, 10.3, 20.1, 27.3, 32.0, 41.9, 52.4]

# SOC Grid for 2D Tables
SOC_GRID: List[float] = [0.0, 0.05, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 1.0]

# Temperature-Scheduled C/20 Capacity Q(T) Table (Ah)
# Provenance: D8 Anchor Gap Table (CALCE A123 Cell A1-007)
Q_TABLE_TEMPS_C: List[float] = [20.0, 25.0, 30.0, 40.0, 50.0]
Q_TABLE_AH: List[float] = [
    1.065214687790664,
    1.0635616695823449,
    1.0730061548855323,
    1.0801900610401025,
    1.0809567995408316,
]

# Temperature-Scheduled Hysteresis Amplitude M(T) Table (V)
# Provenance: Stage V0 & V1 Identification Audit
M_TABLE_TEMPS_C: List[float] = [20.0, 25.0, 30.0, 40.0, 50.0]
M_TABLE_V: List[float] = [
    0.02701,
    0.01719,
    0.02436,
    0.02155,
    0.01988,
]

# 2D OCV Table (V) indexed by temperature string
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

# Ohmic Resistance R0 Table (Ohm) per temperature point
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

# RC1 Resistance R1 Table (Ohm) per temperature point
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

# RC1 Time Constant tau1 Table (s) per temperature point
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

# RC2 Resistance R2 Table (Ohm) per temperature point
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

# RC2 Time Constant tau2 Table (s) per temperature point
TAU2_TABLE: Dict[str, float] = {
    "-7.4": 600.0,
    "0.6": 600.0,
    "10.3": 210.41,
    "20.1": 599.98,
    "27.3": 600.0,
    "32.0": 218.24,
    "41.9": 207.27,
    "52.4": 600.0,
}


@dataclass(frozen=True)
class BmsSocParameters:
    """Estimator parameters frozen in Gauntlet V3 Stage V4."""

    # Nominal calibration anchors
    nominal_capacity_ah: float = 1.0635616695823449
    coulombic_efficiency: float = 1.0
    hysteresis_gamma: float = 50.0

    # Frozen Noise Covariances
    process_noise_q_soc: float = 2.0e-09
    process_noise_q_rc: float = 1.1198164932559382e-05
    process_noise_q_hysteresis: float = 0.00017150882346504795
    measurement_noise_r_v: float = 0.0008610323423725228

    # RLS Adaptation Parameters
    e4_rls_forgetting_factor: float = 0.9990
    rls_di_threshold_a: float = 1.0
    rls_theta_min: float = 0.5
    rls_theta_max: float = 2.0

    # Observability Gating & Step Capping
    e5_slope_ref: float = 0.20
    e5_cap_plateau: float = 2.0e-05
    e5_cap_knee: float = 0.01
    e5_sigma_ocv_model_v: float = 0.02

    # Default Initialization Standard Deviations
    initial_soc_std: float = 0.10
    initial_rc_current_std_a: float = 0.10
    initial_hysteresis_std: float = 0.10


@dataclass
class SocEstimateRef:
    """Estimated SOC and operational telemetry returned by step()."""

    soc: float
    soc_std: float
    voltage_residual: Optional[float] = None
    innovation_variance: Optional[float] = None
    kalman_gain_soc: Optional[float] = None
    theta: float = 1.0
    observability_scaling: float = 1.0
    delta_soc_applied: float = 0.0


# ==============================================================================
# Standalone Mathematical Utilities
# ==============================================================================

def interp_1d(x: float, xp: List[float], fp: List[float]) -> float:
    """Linear 1D interpolation with flat boundary clamping matching np.interp."""
    if x <= xp[0]:
        return fp[0]
    if x >= xp[-1]:
        return fp[-1]
    idx = bisect.bisect_left(xp, x)
    x0, x1 = xp[idx - 1], xp[idx]
    y0, y1 = fp[idx - 1], fp[idx]
    return y0 + (x - x0) * (y1 - y0) / (x1 - x0)


def interp_2d_table(
    soc: float,
    temp_c: float,
    temps: List[float],
    socs: List[float],
    table: Dict[str, List[float]],
) -> float:
    """Bilinear 2D interpolation over temperature and SOC grids matching InterpolatedTable2D."""
    s_clamped = min(max(soc, socs[0]), socs[-1])
    if temp_c <= temps[0]:
        t_low, t_high, alpha_t = temps[0], temps[0], 0.0
    elif temp_c >= temps[-1]:
        t_low, t_high, alpha_t = temps[-1], temps[-1], 0.0
    else:
        idx = bisect.bisect_left(temps, temp_c)
        t_low = temps[idx - 1]
        t_high = temps[idx]
        alpha_t = (temp_c - t_low) / (t_high - t_low) if t_high != t_low else 0.0

    key_low = f"{t_low:.1f}" if f"{t_low:.1f}" in table else str(t_low)
    v_low = interp_1d(s_clamped, socs, table[key_low])
    if t_low == t_high:
        return v_low
    key_high = f"{t_high:.1f}" if f"{t_high:.1f}" in table else str(t_high)
    v_high = interp_1d(s_clamped, socs, table[key_high])
    return (1.0 - alpha_t) * v_low + alpha_t * v_high


def ocv_derivative_soc(
    soc: float,
    temp_c: float,
    temps: List[float],
    socs: List[float],
    table: Dict[str, List[float]],
) -> float:
    """Compute partial derivative dOCV/dSOC matching InterpolatedTable2D.derivative_soc."""
    s_clamped = min(max(soc, socs[0]), socs[-1])
    if temp_c <= temps[0]:
        t_low, t_high, alpha_t = temps[0], temps[0], 0.0
    elif temp_c >= temps[-1]:
        t_low, t_high, alpha_t = temps[-1], temps[-1], 0.0
    else:
        idx = bisect.bisect_left(temps, temp_c)
        t_low = temps[idx - 1]
        t_high = temps[idx]
        alpha_t = (temp_c - t_low) / (t_high - t_low) if t_high != t_low else 0.0

    def _calc_deriv(t_val: float) -> float:
        key = f"{t_val:.1f}" if f"{t_val:.1f}" in table else str(t_val)
        y_arr = table[key]
        if s_clamped <= socs[0]:
            return (y_arr[1] - y_arr[0]) / (socs[1] - socs[0])
        if s_clamped >= socs[-1]:
            return (y_arr[-1] - y_arr[-2]) / (socs[-1] - socs[-2])
        idx = bisect.bisect_left(socs, s_clamped)
        return (y_arr[idx] - y_arr[idx - 1]) / (socs[idx] - socs[idx - 1])

    d_low = _calc_deriv(t_low)
    if t_low == t_high:
        return d_low
    d_high = _calc_deriv(t_high)
    return (1.0 - alpha_t) * d_low + alpha_t * d_high


# ==============================================================================
# Standalone Estimator Class
# ==============================================================================

class BmsSocEstimatorRef:
    """Production-grade reference implementation of the E7v3 SOC Estimator."""

    def __init__(self, params: Optional[BmsSocParameters] = None):
        self.params = params if params is not None else BmsSocParameters()

        # State vector: [soc, i1, i2, h]^T
        self.x: List[float] = [0.0, 0.0, 0.0, 0.0]
        # Covariance matrix 4x4
        self.p: List[List[float]] = [[0.0] * 4 for _ in range(4)]

        # RLS State
        self.theta: float = 1.0
        self.p_rls: float = 1.0
        self.prev_i: float = 0.0
        self.prev_v: float = 0.0
        self.has_prev: bool = False

        self.last_valid_i: float = 0.0
        self.last_valid_temp: float = 25.0

    def get_capacity_ah(self, temp_c: float) -> float:
        """Get temperature-scheduled C/20 capacity (Ah) with linear interpolation."""
        return interp_1d(temp_c, Q_TABLE_TEMPS_C, Q_TABLE_AH)

    def get_m_hyst(self, temp_c: float) -> float:
        """Get temperature-scheduled hysteresis half-gap (V) with linear interpolation."""
        return interp_1d(temp_c, M_TABLE_TEMPS_C, M_TABLE_V)

    def reset(self, soc0: float, soc_std: Optional[float] = None) -> None:
        """Confidence-aware state and covariance reset.

        Args:
            soc0: Initial SOC in [0.0, 1.0].
            soc_std: Standard deviation of initial SOC estimate.
                     - For known/anchored start: set to max(0.5 pp, CV-taper gap(T)).
                     - For unknown start: set to 0.10 (10 pp).
                     - If None, defaults to params.initial_soc_std.
        """
        soc_clamped = min(max(float(soc0), 0.0), 1.0)
        self.x = [soc_clamped, 0.0, 0.0, 0.0]

        p_soc = float(soc_std) ** 2 if (soc_std is not None and float(soc_std) > 0.0) else (self.params.initial_soc_std ** 2)
        p_rc = self.params.initial_rc_current_std_a ** 2
        p_h = self.params.initial_hysteresis_std ** 2

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

    def step(self, v: float, i: float, temp_c: float, dt: float) -> SocEstimateRef:
        """Execute online adaptation, observability-gated measurement update, and time propagation.

        Args:
            v: Terminal voltage (V). Pass math.nan if measurement is dropped.
            i: Terminal current (A, positive = discharge, negative = charge).
            temp_c: Cell surface temperature (°C).
            dt: Time step duration (seconds).

        Returns:
            SocEstimateRef: Dataclass with estimated SOC and diagnostic telemetry.
        """
        # Handle dropped measurement
        if math.isnan(v) or math.isnan(i):
            i_prop = self.last_valid_i
            temp_prop = self.last_valid_temp

            q_t = self.get_capacity_ah(temp_prop)
            r0 = interp_1d(temp_prop, TEMPERATURES_C, [R0_TABLE[f"{t:.1f}"] for t in TEMPERATURES_C])
            r1 = interp_1d(temp_prop, TEMPERATURES_C, [R1_TABLE[f"{t:.1f}"] for t in TEMPERATURES_C])
            tau1 = interp_1d(temp_prop, TEMPERATURES_C, [TAU1_TABLE[f"{t:.1f}"] for t in TEMPERATURES_C])
            r2 = interp_1d(temp_prop, TEMPERATURES_C, [R2_TABLE[f"{t:.1f}"] for t in TEMPERATURES_C])
            tau2 = interp_1d(temp_prop, TEMPERATURES_C, [TAU2_TABLE[f"{t:.1f}"] for t in TEMPERATURES_C])

            eta = self.params.coulombic_efficiency if i_prop < 0 else 1.0
            z_next = self.x[0] - (eta * i_prop * dt) / (3600.0 * q_t)
            f11 = math.exp(-dt / tau1) if tau1 > 0 else 0.0
            f22 = math.exp(-dt / tau2) if tau2 > 0 else 0.0
            i1_next = f11 * self.x[1] + (1.0 - f11) * i_prop
            i2_next = f22 * self.x[2] + (1.0 - f22) * i_prop

            if i_prop == 0.0:
                f33 = 1.0
                h_next = self.x[3]
            else:
                cap_as = q_t * 3600.0
                alpha = abs(eta * i_prop * self.params.hysteresis_gamma * dt / cap_as)
                f33 = math.exp(-alpha)
                sgn_i = 1.0 if i_prop > 0.0 else -1.0
                h_next = f33 * self.x[3] - (1.0 - f33) * sgn_i

            self.x = [min(max(z_next, 0.0), 1.0), i1_next, i2_next, min(max(h_next, -1.0), 1.0)]

            d = [1.0, f11, f22, f33]
            q = [
                self.params.process_noise_q_soc,
                self.params.process_noise_q_rc,
                self.params.process_noise_q_rc,
                self.params.process_noise_q_hysteresis,
            ]
            new_p = [[0.0] * 4 for _ in range(4)]
            for row in range(4):
                for col in range(4):
                    val = d[row] * self.p[row][col] * d[col]
                    if row == col:
                        val += q[row]
                    new_p[row][col] = val
            self.p = new_p

            return SocEstimateRef(
                soc=self.x[0],
                soc_std=math.sqrt(max(self.p[0][0], 0.0)),
                theta=self.theta,
            )

        # Valid measurement
        self.last_valid_i = i
        self.last_valid_temp = temp_c

        # 1. Temperature-scheduled parameter lookups
        q_t = self.get_capacity_ah(temp_c)
        m_hyst = self.get_m_hyst(temp_c)

        r0_base = interp_1d(temp_c, TEMPERATURES_C, [R0_TABLE[f"{t:.1f}"] for t in TEMPERATURES_C])
        r1_base = interp_1d(temp_c, TEMPERATURES_C, [R1_TABLE[f"{t:.1f}"] for t in TEMPERATURES_C])
        tau1 = interp_1d(temp_c, TEMPERATURES_C, [TAU1_TABLE[f"{t:.1f}"] for t in TEMPERATURES_C])
        r2 = interp_1d(temp_c, TEMPERATURES_C, [R2_TABLE[f"{t:.1f}"] for t in TEMPERATURES_C])
        tau2 = interp_1d(temp_c, TEMPERATURES_C, [TAU2_TABLE[f"{t:.1f}"] for t in TEMPERATURES_C])

        ocv = interp_2d_table(self.x[0], temp_c, TEMPERATURES_C, SOC_GRID, OCV_TABLE)
        d_ocv_dz = ocv_derivative_soc(self.x[0], temp_c, TEMPERATURES_C, SOC_GRID, OCV_TABLE)

        # 2. Online RLS Impedance Adaptation on Discrete Current Steps
        if self.has_prev:
            di = i - self.prev_i
            dv = v - self.prev_v
            if abs(di) >= self.params.rls_di_threshold_a:
                phi = r0_base * di
                y_meas = -dv
                lam = self.params.e4_rls_forgetting_factor

                denom = lam + self.p_rls * (phi ** 2)
                l_gain = (self.p_rls * phi) / denom
                err_rls = y_meas - phi * self.theta

                self.theta += l_gain * err_rls
                self.theta = min(max(self.theta, self.params.rls_theta_min), self.params.rls_theta_max)
                self.p_rls = (self.p_rls - l_gain * phi * self.p_rls) / lam

        self.prev_i = i
        self.prev_v = v
        self.has_prev = True

        # Effective scaled resistances
        r0_eff = self.theta * r0_base
        r1_eff = self.theta * r1_base

        # 3. Model Predicted Voltage and Innovation
        v_hat = ocv + m_hyst * self.x[3] - r1_eff * self.x[1] - r2 * self.x[2] - r0_eff * i
        residual = v - v_hat

        # Observation matrix H = [dOCV/dz, -R1_eff, -R2, M_hyst]
        h_vec = [d_ocv_dz, -r1_eff, -r2, m_hyst]

        # Effective measurement variance with OCV model uncertainty
        r_eff = self.params.measurement_noise_r_v + (self.params.e5_sigma_ocv_model_v ** 2)

        # Innovation variance: S = H * P * H^T + R_eff
        hp = [sum(h_vec[col] * self.p[col][j] for col in range(4)) for j in range(4)]
        hph = sum(hp[j] * h_vec[j] for j in range(4))
        s_val = hph + r_eff

        # Kalman gain vector: K = (P * H^T) / S
        ph_t = [sum(self.p[row][col] * h_vec[col] for col in range(4)) for row in range(4)]
        k_gain = [ph_t[row] / s_val for row in range(4)]

        # Raw state corrections
        delta_x_raw = [k_gain[row] * residual for row in range(4)]
        delta_soc = delta_x_raw[0]

        # 4. Observability Gating
        abs_slope = abs(d_ocv_dz)
        g_slope = min(1.0, abs_slope / self.params.e5_slope_ref) if self.params.e5_slope_ref > 0.0 else 1.0
        delta_soc = delta_soc * g_slope

        # 5. Plateau Step Capping
        cap = self.params.e5_cap_plateau + (self.params.e5_cap_knee - self.params.e5_cap_plateau) * g_slope
        if cap > 0.0:
            delta_soc = min(max(delta_soc, -cap), cap)

        # 6. Posterior State Vector
        x_post = [
            min(max(self.x[0] + delta_soc, 0.0), 1.0),
            self.x[1] + delta_x_raw[1],
            self.x[2] + delta_x_raw[2],
            min(max(self.x[3] + delta_x_raw[3], -1.0), 1.0),
        ]

        # 7. Joseph-Form Stabilized Covariance Update
        k_eff_soc = delta_soc / residual if abs(residual) > 1e-12 else 0.0
        k_eff = [k_eff_soc, k_gain[1], k_gain[2], k_gain[3]]

        # Compute M_mat = (I - K_eff * H)
        m_mat = [[0.0] * 4 for _ in range(4)]
        for row in range(4):
            for col in range(4):
                diag = 1.0 if row == col else 0.0
                m_mat[row][col] = diag - k_eff[row] * h_vec[col]

        # P_post = M * P * M^T + K_eff * R_eff * K_eff^T
        mp = [[sum(m_mat[row][k] * self.p[k][col] for k in range(4)) for col in range(4)] for row in range(4)]
        mpmt = [[sum(mp[row][k] * m_mat[col][k] for k in range(4)) for col in range(4)] for row in range(4)]

        p_post = [[0.0] * 4 for _ in range(4)]
        for row in range(4):
            for col in range(4):
                p_post[row][col] = mpmt[row][col] + r_eff * (k_eff[row] * k_eff[col])

        # Symmetrize
        for row in range(4):
            for col in range(row + 1, 4):
                sym = 0.5 * (p_post[row][col] + p_post[col][row])
                p_post[row][col] = sym
                p_post[col][row] = sym

        # 8. Time Propagation to Next Sample x_(k+1) using Scheduled Q(T)
        eta = self.params.coulombic_efficiency if i < 0 else 1.0
        z_next = x_post[0] - (eta * i * dt) / (3600.0 * q_t)
        f11 = math.exp(-dt / tau1) if tau1 > 0 else 0.0
        f22 = math.exp(-dt / tau2) if tau2 > 0 else 0.0
        i1_next = f11 * x_post[1] + (1.0 - f11) * i
        i2_next = f22 * x_post[2] + (1.0 - f22) * i

        if i == 0.0:
            f33 = 1.0
            h_next = x_post[3]
        else:
            cap_as = q_t * 3600.0
            alpha = abs(eta * i * self.params.hysteresis_gamma * dt / cap_as)
            f33 = math.exp(-alpha)
            sgn_i = 1.0 if i > 0.0 else -1.0
            h_next = f33 * x_post[3] - (1.0 - f33) * sgn_i

        self.x = [
            min(max(z_next, 0.0), 1.0),
            i1_next,
            i2_next,
            min(max(h_next, -1.0), 1.0),
        ]

        # Covariance Propagation: P_(k+1) = F * P_post * F^T + Q
        d = [1.0, f11, f22, f33]
        q = [
            self.params.process_noise_q_soc,
            self.params.process_noise_q_rc,
            self.params.process_noise_q_rc,
            self.params.process_noise_q_hysteresis,
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
