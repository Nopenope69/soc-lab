"""Pulse segmentation, transient extraction, and constrained 2-RC ECM identification.

Implements:
1. Current pulse detection and post-pulse relaxation segmentation.
2. Physics-based 2-RC Equivalent Circuit Model fitting with box constraints.
3. Normalized Jacobian conditioning and parameter identifiability testing.
4. Fit residual RMSE and feature quality scoring.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Tuple
import numpy as np
from scipy.optimize import least_squares

from soh.common.contracts import FeatureQualityRecord
from soh.common.units import is_resting


@dataclass
class PulseRecord:
    """Segmented current pulse and subsequent relaxation window."""

    pulse_id: str
    cycle_index: int
    t_pulse_s: np.ndarray
    v_pulse_v: np.ndarray
    i_pulse_a: np.ndarray
    t_relax_s: np.ndarray
    v_relax_v: np.ndarray
    i_relax_a: np.ndarray
    temp_c: float
    i_amplitude_a: float
    pulse_duration_s: float
    relax_duration_s: float


@dataclass
class Ecm2RcParameters:
    """Fitted 2-RC Equivalent Circuit Model parameters."""

    r0_ohm: float
    r1_ohm: float
    tau1_s: float
    r2_ohm: float
    tau2_s: float
    v_ocv_v: float
    fit_rmse_mv: float
    jacobian_condition_number: float
    is_identifiable: bool

    @property
    def c1_f(self) -> float:
        """First RC branch capacitance: C1 = tau1 / R1."""
        return self.tau1_s / max(1e-6, self.r1_ohm)

    @property
    def c2_f(self) -> float:
        """Second RC branch capacitance: C2 = tau2 / R2."""
        return self.tau2_s / max(1e-6, self.r2_ohm)

    @property
    def r_total_ohm(self) -> float:
        """Total polarization resistance: R0 + R1 + R2."""
        return self.r0_ohm + self.r1_ohm + self.r2_ohm


class PulseSegmenter:
    """Segments current pulses and relaxation intervals from telemetry."""

    def __init__(
        self,
        min_pulse_current_a: float = 0.20,
        min_pulse_duration_s: float = 2.0,
        min_relax_duration_s: float = 5.0,
        current_step_threshold_a: float = 0.15,
    ):
        self.min_pulse_current_a = min_pulse_current_a
        self.min_pulse_duration_s = min_pulse_duration_s
        self.min_relax_duration_s = min_relax_duration_s
        self.current_step_threshold_a = current_step_threshold_a

    def detect_pulses(
        self,
        time_s: np.ndarray,
        voltage_v: np.ndarray,
        current_a: np.ndarray,
        temp_c: np.ndarray,
        cycle_index: int = 0,
    ) -> List[PulseRecord]:
        """Detect constant current pulse intervals followed by rest relaxation."""
        n = len(time_s)
        if n < 10:
            return []

        pulses: List[PulseRecord] = []
        in_pulse = False
        pulse_start = 0

        # Current magnitude
        abs_i = np.abs(current_a)

        for i in range(n):
            if not in_pulse:
                if abs_i[i] >= self.min_pulse_current_a:
                    in_pulse = True
                    pulse_start = i
            else:
                # Check for pulse termination (current drops near 0 or large step change)
                is_step_down = abs_i[i] < (self.min_pulse_current_a * 0.5)
                if is_step_down or i == n - 1:
                    in_pulse = False
                    pulse_end = i
                    p_dur = time_s[pulse_end - 1] - time_s[pulse_start]

                    if p_dur >= self.min_pulse_duration_s:
                        # Find relaxation segment immediately following pulse
                        relax_start = pulse_end
                        relax_end = relax_start
                        while relax_end < n and abs_i[relax_end] < (self.min_pulse_current_a * 0.5):
                            relax_end += 1

                        r_dur = (
                            time_s[relax_end - 1] - time_s[relax_start]
                            if relax_end > relax_start
                            else 0.0
                        )

                        if r_dur >= self.min_relax_duration_s:
                            t_p = time_s[pulse_start:pulse_end] - time_s[pulse_start]
                            v_p = voltage_v[pulse_start:pulse_end]
                            i_p = current_a[pulse_start:pulse_end]

                            t_r = time_s[relax_start:relax_end] - time_s[relax_start]
                            v_r = voltage_v[relax_start:relax_end]
                            i_r = current_a[relax_start:relax_end]

                            avg_temp = float(np.mean(temp_c[pulse_start:relax_end]))
                            mean_i = float(np.mean(i_p))

                            rec = PulseRecord(
                                pulse_id=f"p_{cycle_index}_{len(pulses)}",
                                cycle_index=cycle_index,
                                t_pulse_s=t_p,
                                v_pulse_v=v_p,
                                i_pulse_a=i_p,
                                t_relax_s=t_r,
                                v_relax_v=v_r,
                                i_relax_a=i_r,
                                temp_c=avg_temp,
                                i_amplitude_a=mean_i,
                                pulse_duration_s=p_dur,
                                relax_duration_s=r_dur,
                            )
                            pulses.append(rec)

        return pulses


class Ecm2RcFitter:
    """Fits 2-RC Equivalent Circuit Model to pulse transient and relaxation response."""

    def __init__(
        self,
        max_cond_number: float = 1e5,
        max_fit_rmse_mv: float = 15.0,
    ):
        self.max_cond_number = max_cond_number
        self.max_fit_rmse_mv = max_fit_rmse_mv

    def fit_pulse(self, pulse: PulseRecord) -> Tuple[Optional[Ecm2RcParameters], FeatureQualityRecord]:
        """Fit 2-RC model parameters [R0, R1, tau1, R2, tau2, V_ocv] using Trust-Region-Reflective."""
        # Concatenate pulse and relaxation
        t_pulse = pulse.t_pulse_s
        v_pulse = pulse.v_pulse_v
        i_pulse = pulse.i_pulse_a

        t_relax = pulse.t_relax_s + t_pulse[-1] + (t_pulse[1] - t_pulse[0] if len(t_pulse) > 1 else 1.0)
        v_relax = pulse.v_relax_v
        i_relax = pulse.i_relax_a

        t_all = np.concatenate([t_pulse, t_relax])
        v_meas = np.concatenate([v_pulse, v_relax])
        i_all = np.concatenate([i_pulse, i_relax])

        # Pulse duration and polarity determination
        t_pulse_end = t_pulse[-1]
        is_discharge = float(np.mean(v_pulse)) < float(np.mean(v_relax)) if len(v_relax) > 0 else (pulse.i_amplitude_a < 0)
        i_sign = -1.0 if is_discharge else 1.0
        i_mag = abs(pulse.i_amplitude_a)

        # Initial parameter estimates
        # Immediate voltage step estimate: delta_V_step / I
        step_dv = abs(v_pulse[0] - v_relax[-1]) if len(v_relax) > 0 else abs(v_pulse[-1] - v_pulse[0])
        r0_init = float(np.clip(step_dv / max(0.1, i_mag), 0.001, 0.15))
        r1_init = r0_init * 0.5
        tau1_init = 5.0
        r2_init = r0_init * 0.5
        tau2_init = 30.0
        vocv_init = float(v_relax[-1] if len(v_relax) > 0 else v_pulse[0])

        theta0 = np.array([r0_init, r1_init, tau1_init, r2_init, tau2_init, vocv_init], dtype=float)

        # Bounds: R in [1e-4, 0.5], tau1 in [0.2, 50], tau2 in [1.0, 300], Vocv in [1.5, 4.5]
        lower_bounds = np.array([1e-4, 1e-4, 0.2, 1e-4, 1.0, 1.5])
        upper_bounds = np.array([0.50, 0.50, 50.0, 0.50, 300.0, 4.5])

        # Determine signed current trajectory
        # If is_discharge, current is negative; if charge, positive.
        i_signed = np.zeros_like(i_all)
        for idx in range(len(i_all)):
            if abs(i_all[idx]) > 0.02:
                i_signed[idx] = -abs(i_all[idx]) if is_discharge else abs(i_all[idx])
            else:
                i_signed[idx] = 0.0

        # Model forward simulation function supporting variable current profiles
        def model_voltage(theta: np.ndarray) -> np.ndarray:
            r0, r1, tau1, r2, tau2, vocv = theta
            v_sim = np.zeros_like(t_all)

            # Discrete-time recursive integration matching physical 2-RC state-space
            v1 = 0.0
            v2 = 0.0
            v_sim[0] = vocv + i_signed[0] * r0

            tau1_safe = max(1e-3, tau1)
            tau2_safe = max(1e-3, tau2)

            for k in range(1, len(t_all)):
                dt = max(1e-5, t_all[k] - t_all[k - 1])
                ik = i_signed[k]

                alpha1 = float(np.exp(-dt / tau1_safe))
                alpha2 = float(np.exp(-dt / tau2_safe))

                v1 = v1 * alpha1 + ik * r1 * (1.0 - alpha1)
                v2 = v2 * alpha2 + ik * r2 * (1.0 - alpha2)

                v_sim[k] = vocv + ik * r0 + v1 + v2

            return v_sim

        def residuals(theta: np.ndarray) -> np.ndarray:
            return model_voltage(theta) - v_meas

        try:
            res = least_squares(
                residuals,
                theta0,
                bounds=(lower_bounds, upper_bounds),
                method="trf",
                xtol=1e-6,
                ftol=1e-6,
                max_nfev=300,
            )
        except Exception as e:
            quality = FeatureQualityRecord(
                is_eligible=False,
                failure_reasons=[f"Optimization failed: {str(e)}"],
            )
            return None, quality

        theta_opt = res.x
        v_fit = model_voltage(theta_opt)
        rmse_mv = float(np.sqrt(np.mean((v_meas - v_fit) ** 2)) * 1000.0)

        # Parameter identifiability check via normalized Jacobian
        jac = res.jac
        norm_jac = jac * theta_opt.reshape(1, -1)
        j_col_norms = np.linalg.norm(norm_jac, axis=0)

        if np.any(j_col_norms < 1e-12):
            cond_num = float("inf")
        else:
            j_scaled = norm_jac / j_col_norms
            sing_vals = np.linalg.svd(j_scaled, compute_uv=False)
            cond_num = float(sing_vals[0] / max(1e-12, sing_vals[-1]))

        reasons = []
        if rmse_mv > self.max_fit_rmse_mv:
            reasons.append(f"Fit RMSE {rmse_mv:.1f}mV > {self.max_fit_rmse_mv:.1f}mV")
        if cond_num > self.max_cond_number or np.isnan(cond_num) or np.isinf(cond_num):
            reasons.append(f"Jacobian condition number {cond_num:.1e} > {self.max_cond_number:.1e}")

        is_eligible = len(reasons) == 0

        ecm_params = Ecm2RcParameters(
            r0_ohm=float(theta_opt[0]),
            r1_ohm=float(theta_opt[1]),
            tau1_s=float(theta_opt[2]),
            r2_ohm=float(theta_opt[3]),
            tau2_s=float(theta_opt[4]),
            v_ocv_v=float(theta_opt[5]),
            fit_rmse_mv=rmse_mv,
            jacobian_condition_number=cond_num,
            is_identifiable=is_eligible,
        )

        curr_cv = float(np.std(i_pulse) / max(1e-3, abs(np.mean(i_pulse)))) if len(i_pulse) > 1 else 0.0

        quality = FeatureQualityRecord(
            is_eligible=is_eligible,
            jacobian_condition_number=cond_num,
            fit_rmse_mv=rmse_mv,
            current_stability_cv=curr_cv,
            failure_reasons=reasons,
        )

        return ecm_params, quality
