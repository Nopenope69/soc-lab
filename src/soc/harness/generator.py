"""Duty cycle profile generator driven solely by configuration parameters."""

from dataclasses import dataclass
from typing import List

from soc.assumptions.loader import (
    ANCHOR_EVAL_CHARGE_CURRENT_A,
    ANCHOR_EVAL_CHARGE_DURATION_S,
    ANCHOR_EVAL_DISCHARGE_CURRENT_A,
    ANCHOR_EVAL_DISCHARGE_DURATION_S,
    ANCHOR_EVAL_REST_DURATION_S,
    ANCHOR_EVAL_TAPER_CURRENT_A,
    ANCHOR_EVAL_TAPER_DURATION_S,
)
from soc.assumptions.schema import Assumptions


@dataclass(frozen=True)
class DutyStep:
    """Single step of synthetic duty cycle."""

    i_app: float
    temp_c: float
    dt: float


class DutyCycleGenerator:
    """Config-driven generator converting duty assumptions into duty steps."""

    @staticmethod
    def generate(assumptions: Assumptions) -> List[DutyStep]:
        """Generate duty cycle steps adhering strictly to assumptions.duty parameters."""
        duty = assumptions.duty
        plant = assumptions.plant
        sensors = assumptions.sensors

        dt_s = float(sensors.sample_period_s.value)
        total_time_s = float(duty.total_duration_s.value)
        ambient_temp_c = float(duty.ambient_temperature_c.value)

        # C-rate to current conversion using plant capacity
        cap_ah = float(plant.nominal_capacity_Ah.value)
        c_rate = float(duty.pulse_c_rate.value)
        i_pulse = c_rate * cap_ah

        pulse_dur_s = float(duty.pulse_duration_s.value)
        rest_dur_s = float(duty.rest_duration_s.value)
        ratio = float(duty.charge_discharge_ratio.value)
        soc_min = float(duty.soc_min_limit.value)
        soc_max = float(duty.soc_max_limit.value)

        cycle_type = str(duty.cycle_type.value)

        # Number of steps
        num_steps = int(total_time_s / dt_s)
        steps: List[DutyStep] = []

        if cycle_type == "static" or cycle_type == "static_ocv":
            for _ in range(num_steps):
                steps.append(DutyStep(i_app=float(0), temp_c=ambient_temp_c, dt=dt_s))
            return steps

        if cycle_type == "knee_crossing":
            # Continuous discharge across lower knee
            for _ in range(num_steps):
                steps.append(DutyStep(i_app=i_pulse, temp_c=ambient_temp_c, dt=dt_s))
            return steps

        if cycle_type == "rest_relaxation":
            # Pulse discharge then sustained rest
            for step_idx in range(num_steps):
                t_elapsed = step_idx * dt_s
                if t_elapsed < pulse_dur_s:
                    current = i_pulse
                else:
                    current = float(0)
                steps.append(DutyStep(i_app=current, temp_c=ambient_temp_c, dt=dt_s))
            return steps

        if cycle_type == "anchor_evaluation":
            # 1. Charge phase to reach full-charge voltage
            # 2. Current taper phase (taper current <= 2.0 A) to trigger full-charge anchor
            # 3. Discharge phase into plateau
            # 4. Sustained rest phase (>= 600 s) to trigger rest anchor
            t_chg = ANCHOR_EVAL_CHARGE_DURATION_S
            t_taper = t_chg + ANCHOR_EVAL_TAPER_DURATION_S
            t_dischg = t_taper + ANCHOR_EVAL_DISCHARGE_DURATION_S
            for step_idx in range(num_steps):
                t_elapsed = step_idx * dt_s
                if t_elapsed < t_chg:
                    current = ANCHOR_EVAL_CHARGE_CURRENT_A
                elif t_elapsed < t_taper:
                    current = ANCHOR_EVAL_TAPER_CURRENT_A
                elif t_elapsed < t_dischg:
                    current = ANCHOR_EVAL_DISCHARGE_CURRENT_A
                else:
                    current = float(0)
                steps.append(DutyStep(i_app=current, temp_c=ambient_temp_c, dt=dt_s))
            return steps

        if cycle_type == "plateau_stress" or cycle_type == "minor_loops":
            # Oscillate between soc_min and soc_max with reversals and optional rest intervals
            sim_soc = float(duty.initial_soc.value)
            direction = 1  # 1 = discharging, -1 = charging
            rest_timer = float(0)
            in_rest = False
            for _ in range(num_steps):
                if in_rest:
                    steps.append(DutyStep(i_app=float(0), temp_c=ambient_temp_c, dt=dt_s))
                    rest_timer = rest_timer + dt_s
                    if rest_timer >= rest_dur_s:
                        in_rest = False
                        rest_timer = float(0)
                    continue

                if direction == 1 and sim_soc <= soc_min:
                    direction = -1
                    if rest_dur_s > float(0):
                        in_rest = True
                        rest_timer = dt_s
                        steps.append(DutyStep(i_app=float(0), temp_c=ambient_temp_c, dt=dt_s))
                        continue
                elif direction == -1 and sim_soc >= soc_max:
                    direction = 1
                    if rest_dur_s > float(0):
                        in_rest = True
                        rest_timer = dt_s
                        steps.append(DutyStep(i_app=float(0), temp_c=ambient_temp_c, dt=dt_s))
                        continue

                if direction == 1:
                    current = i_pulse
                else:
                    current = -i_pulse / ratio

                steps.append(DutyStep(i_app=current, temp_c=ambient_temp_c, dt=dt_s))
                # Propagate simulated SOC: dSOC = -eta * I * dt / (3600 * Q)
                eta_gen = (
                    float(plant.coulombic_efficiency.value)
                    if current < float(0)
                    else float(1)
                )
                sim_soc = sim_soc - (eta_gen * current * dt_s) / (float(3600) * cap_ah)
            return steps

        # Default: standard pulse train (discharge -> rest -> charge -> rest)
        cycle_period = pulse_dur_s + rest_dur_s + pulse_dur_s + rest_dur_s
        for step_idx in range(num_steps):
            t_in_cycle = (step_idx * dt_s) % cycle_period if cycle_period > 0 else float(0)
            if t_in_cycle < pulse_dur_s:
                current = i_pulse
            elif t_in_cycle < pulse_dur_s + rest_dur_s:
                current = float(0)
            elif t_in_cycle < pulse_dur_s + rest_dur_s + pulse_dur_s:
                current = -i_pulse / ratio
            else:
                current = float(0)
            steps.append(DutyStep(i_app=current, temp_c=ambient_temp_c, dt=dt_s))

        return steps
