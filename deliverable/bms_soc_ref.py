"""BMS State of Charge (SOC) Reference Implementation.

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
Validated against CALCE 20°C to 50°C development envelope. Not field validated.
"""

import bisect
from dataclasses import dataclass, field
import math
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

try:
    from deliverable.calibration import CellCalibration, default_calce_calibration
except ImportError:
    try:
        from calibration import CellCalibration, default_calce_calibration
    except ImportError:
        from .calibration import CellCalibration, default_calce_calibration


# ==============================================================================
# Model Parameters (Backward Compatibility Dataclass)
# ==============================================================================

@dataclass(frozen=True)
class BmsSocParameters:
    """Estimator parameters frozen in Gauntlet V3 Stage V4."""

    # Nominal calibration anchors
    nominal_capacity_ah: float = 1.0635616695823449
    coulombic_efficiency: float = 0.998
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
    status_flags: List[str] = field(default_factory=lambda: ["OK"])
    calibration_id: str = "calce_a123_v4"
    validation_status: str = "DEVELOPMENT_VALIDATED_CALCE_20_50C"


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

    def __init__(self, calibration: Optional[Union[CellCalibration, BmsSocParameters]] = None):
        if calibration is None:
            self.calib = default_calce_calibration()
        elif isinstance(calibration, CellCalibration):
            self.calib = calibration
        elif isinstance(calibration, BmsSocParameters):
            default_cal = default_calce_calibration()
            self.calib = CellCalibration(
                calibration_id=default_cal.calibration_id,
                schema_version=default_cal.schema_version,
                validation_status=default_cal.validation_status,
                temperatures_c=default_cal.temperatures_c,
                soc_grid=default_cal.soc_grid,
                ocv_table=default_cal.ocv_table,
                r0_table=default_cal.r0_table,
                r1_table=default_cal.r1_table,
                tau1_table=default_cal.tau1_table,
                r2_table=default_cal.r2_table,
                tau2_table=default_cal.tau2_table,
                q_table_temps_c=default_cal.q_table_temps_c,
                q_table_ah=default_cal.q_table_ah,
                m_table_temps_c=default_cal.m_table_temps_c,
                m_table_v=default_cal.m_table_v,
                nominal_capacity_ah=calibration.nominal_capacity_ah,
                coulombic_efficiency=calibration.coulombic_efficiency,
                hysteresis_gamma=calibration.hysteresis_gamma,
                process_noise_q_soc=calibration.process_noise_q_soc,
                process_noise_q_rc=calibration.process_noise_q_rc,
                process_noise_q_hysteresis=calibration.process_noise_q_hysteresis,
                measurement_noise_r_v=calibration.measurement_noise_r_v,
                e4_rls_forgetting_factor=calibration.e4_rls_forgetting_factor,
                rls_di_threshold_a=calibration.rls_di_threshold_a,
                rls_theta_min=calibration.rls_theta_min,
                rls_theta_max=calibration.rls_theta_max,
                e5_slope_ref=calibration.e5_slope_ref,
                e5_cap_plateau=calibration.e5_cap_plateau,
                e5_cap_knee=calibration.e5_cap_knee,
                e5_sigma_ocv_model_v=calibration.e5_sigma_ocv_model_v,
                initial_soc_std=calibration.initial_soc_std,
                initial_rc_current_std_a=calibration.initial_rc_current_std_a,
                initial_hysteresis_std=calibration.initial_hysteresis_std,
            )
        else:
            raise TypeError(f"Expected CellCalibration or BmsSocParameters, got {type(calibration)}")

        self.params = self.calib

        # State vector: [soc, i1, i2, h]^T
        self.x: List[float] = [0.0, 0.0, 0.0, 0.0]
        # Covariance matrix 4x4
        self.p: List[List[float]] = [[0.0] * 4 for _ in range(4)]

        # Backup state for finite-state guard
        self.last_good_x: List[float] = [0.0, 0.0, 0.0, 0.0]
        self.last_good_p: List[List[float]] = [[0.0] * 4 for _ in range(4)]

        # RLS State
        self.theta: float = 1.0
        self.p_rls: float = 1.0
        self.prev_i: float = 0.0
        self.prev_v: float = 0.0
        self.has_prev: bool = False

        self.last_valid_i: float = 0.0
        self.last_valid_temp: float = 25.0
        self.stale_current_duration_s: float = 0.0
        self.stale_current_max_s: float = 10.0

    def _lookup_1d(self, temp_c: float, table: Dict[str, float]) -> float:
        temps = self.calib.temperatures_c
        vals = [table[f"{t:.1f}"] if f"{t:.1f}" in table else table[str(t)] for t in temps]
        return interp_1d(temp_c, temps, vals)

    def get_capacity_ah(self, temp_c: float) -> float:
        """Get temperature-scheduled C/20 capacity (Ah) with linear interpolation."""
        return interp_1d(temp_c, self.calib.q_table_temps_c, self.calib.q_table_ah)

    def get_m_hyst(self, temp_c: float) -> float:
        """Get temperature-scheduled hysteresis half-gap (V) with linear interpolation."""
        return interp_1d(temp_c, self.calib.m_table_temps_c, self.calib.m_table_v)

    def reset(self, soc0: float, soc_std: Optional[float] = None) -> None:
        """Confidence-aware state and covariance reset."""
        soc_clamped = min(max(float(soc0), 0.0), 1.0)
        self.x = [soc_clamped, 0.0, 0.0, 0.0]

        p_soc = float(soc_std) ** 2 if (soc_std is not None and float(soc_std) > 0.0) else (self.calib.initial_soc_std ** 2)
        p_rc = self.calib.initial_rc_current_std_a ** 2
        p_h = self.calib.initial_hysteresis_std ** 2

        self.p = [
            [p_soc, 0.0, 0.0, 0.0],
            [0.0, p_rc, 0.0, 0.0],
            [0.0, 0.0, p_rc, 0.0],
            [0.0, 0.0, 0.0, p_h],
        ]

        self.last_good_x = list(self.x)
        self.last_good_p = [list(r) for r in self.p]

        self.theta = 1.0
        self.p_rls = 1.0
        self.prev_i = 0.0
        self.prev_v = 0.0
        self.has_prev = False
        self.last_valid_i = 0.0
        self.last_valid_temp = 25.0
        self.stale_current_duration_s = 0.0

    def step(
        self,
        v: float,
        i: float,
        temp_c: float,
        dt: float,
        capacity_scale: float = 1.0,
    ) -> SocEstimateRef:
        """Execute online adaptation, observability-gated measurement update, and time propagation."""
        flags: List[str] = []

        # 1. dt Validation
        dt_invalid = False
        if not math.isfinite(dt) or dt <= 0.0 or dt > 60.0:
            flags.append("DT_INVALID")
            dt_invalid = True
            dt_eff = min(max(dt if math.isfinite(dt) else 1.0, 1e-4), 60.0)
        else:
            dt_eff = dt

        # 2. Temperature Validation
        if not math.isfinite(temp_c):
            flags.append("TEMP_INVALID")
            temp_eff = self.last_valid_temp
        else:
            temp_eff = temp_c
            self.last_valid_temp = temp_c
            if temp_c < self.calib.temp_min_c or temp_c > self.calib.temp_max_c:
                flags.append("OUT_OF_ENVELOPE")

        # 3. Voltage and Current Signal Checks
        v_missing = not math.isfinite(v)
        i_missing = not math.isfinite(i)

        if v_missing or i_missing:
            flags.append("DROPOUT")

        # Handle Current
        if i_missing:
            flags.append("STALE_CURRENT")
            self.stale_current_duration_s += dt_eff
            if self.stale_current_duration_s > self.stale_current_max_s:
                i_eff = 0.0
            else:
                i_eff = self.last_valid_i
        else:
            self.stale_current_duration_s = 0.0
            self.last_valid_i = i
            i_eff = i
            if i < self.calib.current_min_a or i > self.calib.current_max_a:
                flags.append("I_OUT_OF_RANGE")

        # Handle Voltage
        v_out_of_range = False
        if not v_missing:
            if v < self.calib.voltage_min_v or v > self.calib.voltage_max_v:
                flags.append("V_OUT_OF_RANGE")
                v_out_of_range = True

        # Lookup temperature-scheduled physical parameters
        q_t = self.get_capacity_ah(temp_eff)
        if capacity_scale != 1.0:
            scale_eff = min(max(float(capacity_scale), 0.10), 1.50)
            q_t = q_t * scale_eff
        r0_base = self._lookup_1d(temp_eff, self.calib.r0_table)
        r1_base = self._lookup_1d(temp_eff, self.calib.r1_table)
        tau1 = self._lookup_1d(temp_eff, self.calib.tau1_table)
        r2 = self._lookup_1d(temp_eff, self.calib.r2_table)
        tau2 = self._lookup_1d(temp_eff, self.calib.tau2_table)

        # Measurement Update (if Voltage is valid and present)
        residual = None
        s_val = None
        k_gain_0 = None
        g_slope = 1.0
        delta_soc = 0.0
        x_post = list(self.x)
        p_post = [list(r) for r in self.p]

        if not v_missing:
            m_hyst = self.get_m_hyst(temp_eff)
            ocv = interp_2d_table(self.x[0], temp_eff, self.calib.temperatures_c, self.calib.soc_grid, self.calib.ocv_table)
            d_ocv_dz = ocv_derivative_soc(self.x[0], temp_eff, self.calib.temperatures_c, self.calib.soc_grid, self.calib.ocv_table)

            # Online RLS Adaptation
            if self.has_prev and not i_missing:
                di = i_eff - self.prev_i
                dv = v - self.prev_v
                if abs(di) >= self.calib.rls_di_threshold_a:
                    phi = r0_base * di
                    y_meas = -dv
                    lam = self.calib.e4_rls_forgetting_factor

                    denom = lam + self.p_rls * (phi ** 2)
                    l_gain = (self.p_rls * phi) / denom
                    err_rls = y_meas - phi * self.theta

                    self.theta += l_gain * err_rls
                    self.theta = min(max(self.theta, self.calib.rls_theta_min), self.calib.rls_theta_max)
                    self.p_rls = (self.p_rls - l_gain * phi * self.p_rls) / lam

            if not i_missing:
                self.prev_i = i_eff
                self.prev_v = v
                self.has_prev = True

            r0_eff = self.theta * r0_base
            r1_eff = self.theta * r1_base

            v_hat = ocv + m_hyst * self.x[3] - r1_eff * self.x[1] - r2 * self.x[2] - r0_eff * i_eff
            residual = v - v_hat

            h_vec = [d_ocv_dz, -r1_eff, -r2, m_hyst]
            r_eff = self.calib.measurement_noise_r_v + (self.calib.e5_sigma_ocv_model_v ** 2)

            hp = [sum(h_vec[col] * self.p[col][j] for col in range(4)) for j in range(4)]
            hph = sum(hp[j] * h_vec[j] for j in range(4))
            s_val = hph + r_eff

            ph_t = [sum(self.p[row][col] * h_vec[col] for col in range(4)) for row in range(4)]
            k_gain = [ph_t[row] / s_val for row in range(4)]
            k_gain_0 = k_gain[0]

            delta_x_raw = [k_gain[row] * residual for row in range(4)]
            delta_soc = delta_x_raw[0]

            abs_slope = abs(d_ocv_dz)
            g_slope = min(1.0, abs_slope / self.calib.e5_slope_ref) if self.calib.e5_slope_ref > 0.0 else 1.0
            delta_soc = delta_soc * g_slope

            cap = self.calib.e5_cap_plateau + (self.calib.e5_cap_knee - self.calib.e5_cap_plateau) * g_slope
            if cap > 0.0:
                delta_soc = min(max(delta_soc, -cap), cap)

            x_post = [
                min(max(self.x[0] + delta_soc, 0.0), 1.0),
                self.x[1] + delta_x_raw[1],
                self.x[2] + delta_x_raw[2],
                min(max(self.x[3] + delta_x_raw[3], -1.0), 1.0),
            ]

            k_eff_soc = delta_soc / residual if abs(residual) > 1e-12 else 0.0
            k_eff = [k_eff_soc, k_gain[1], k_gain[2], k_gain[3]]

            m_mat = [[0.0] * 4 for _ in range(4)]
            for row in range(4):
                for col in range(4):
                    diag = 1.0 if row == col else 0.0
                    m_mat[row][col] = diag - k_eff[row] * h_vec[col]

            mp = [[sum(m_mat[row][k] * self.p[k][col] for k in range(4)) for col in range(4)] for row in range(4)]
            mpmt = [[sum(mp[row][k] * m_mat[col][k] for k in range(4)) for col in range(4)] for row in range(4)]

            p_post = [[0.0] * 4 for _ in range(4)]
            for row in range(4):
                for col in range(4):
                    p_post[row][col] = mpmt[row][col] + r_eff * (k_eff[row] * k_eff[col])

            for row in range(4):
                for col in range(row + 1, 4):
                    sym = 0.5 * (p_post[row][col] + p_post[col][row])
                    p_post[row][col] = sym
                    p_post[col][row] = sym

        # Time Propagation
        eta = self.calib.coulombic_efficiency if i_eff < 0 else 1.0
        z_next = x_post[0] - (eta * i_eff * dt_eff) / (3600.0 * q_t)
        f11 = math.exp(-dt_eff / tau1) if tau1 > 0 else 0.0
        f22 = math.exp(-dt_eff / tau2) if tau2 > 0 else 0.0
        i1_next = f11 * x_post[1] + (1.0 - f11) * i_eff
        i2_next = f22 * x_post[2] + (1.0 - f22) * i_eff

        if i_eff == 0.0:
            f33 = 1.0
            h_next = x_post[3]
        else:
            cap_as = q_t * 3600.0
            alpha = abs(eta * i_eff * self.calib.hysteresis_gamma * dt_eff / cap_as)
            f33 = math.exp(-alpha)
            sgn_i = 1.0 if i_eff > 0.0 else -1.0
            h_next = f33 * x_post[3] - (1.0 - f33) * sgn_i

        candidate_x = [
            min(max(z_next, 0.0), 1.0),
            i1_next,
            i2_next,
            min(max(h_next, -1.0), 1.0),
        ]

        d = [1.0, f11, f22, f33]
        q = [
            self.calib.process_noise_q_soc,
            self.calib.process_noise_q_rc,
            self.calib.process_noise_q_rc,
            self.calib.process_noise_q_hysteresis,
        ]
        candidate_p = [[0.0] * 4 for _ in range(4)]
        for row in range(4):
            for col in range(4):
                val = d[row] * p_post[row][col] * d[col]
                if row == col:
                    val += q[row]
                candidate_p[row][col] = val

        for row in range(4):
            for col in range(row + 1, 4):
                sym = 0.5 * (candidate_p[row][col] + candidate_p[col][row])
                candidate_p[row][col] = sym
                candidate_p[col][row] = sym

        # Finite-State Guard
        is_finite_x = all(math.isfinite(val) for val in candidate_x)
        is_finite_p = all(math.isfinite(candidate_p[r][c]) for r in range(4) for c in range(4))
        is_posdef_diag = all(candidate_p[idx][idx] >= 0.0 for idx in range(4))

        if is_finite_x and is_finite_p and is_posdef_diag:
            self.x = candidate_x
            self.p = candidate_p
            self.last_good_x = list(self.x)
            self.last_good_p = [list(r) for r in self.p]
        else:
            flags.append("STATE_RESET")
            self.x = list(self.last_good_x)
            self.p = [list(r) for r in self.last_good_p]

        if not flags:
            flags = ["OK"]

        return SocEstimateRef(
            soc=self.x[0],
            soc_std=math.sqrt(max(self.p[0][0], 0.0)),
            voltage_residual=residual,
            innovation_variance=s_val,
            kalman_gain_soc=k_gain_0,
            theta=self.theta,
            observability_scaling=g_slope,
            delta_soc_applied=delta_soc,
            status_flags=flags,
            calibration_id=self.calib.calibration_id,
            validation_status=self.calib.validation_status,
        )
