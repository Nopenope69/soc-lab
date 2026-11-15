"""Synthetic cycling aging generator.

Produces repeatable, physically grounded aging datasets with known ground truth
under standard Reference Measurement Protocols. Used for algorithm verification,
parameter stress tests, and automated unit testing without external file dependencies.
"""

import math
from typing import List, Optional, Sequence
import numpy as np

from soh.common.contracts import CycleRecord
from soh.common.protocols import CellReferenceSpec
from soh.data.base_loader import SohBatteryData, SohDataset
from soh.degradation.mechanisms import EmpiricalAgingConfig, EmpiricalDegradationModel


class SyntheticAgingGenerator:
    """Generates synthetic battery aging cycles with realistic sensor noise and degradation."""

    def __init__(
        self,
        base_spec: Optional[CellReferenceSpec] = None,
        aging_config: Optional[EmpiricalAgingConfig] = None,
        seed: int = 42,
    ):
        if base_spec is None:
            self.base_spec = CellReferenceSpec(
                cell_id="SYNTH_LFP_2.3AH",
                chemistry="LFP",
                nominal_capacity_ah=2.30,
                v_max=3.65,
                v_min=2.00,
                t_ref_c=25.0,
                nominal_resistance_ohm=0.015,
            )
        else:
            self.base_spec = base_spec

        self.aging_config = aging_config or EmpiricalAgingConfig()
        self.rng = np.random.default_rng(seed)

    def generate_battery(
        self,
        cell_id: str,
        num_cycles: int = 50,
        temp_c: float = 25.0,
        voltage_noise_std_v: float = 0.002,
        randomize_sessions: bool = False,
    ) -> SohBatteryData:
        """Generate full cycle life for an individual synthetic cell.
        
        Args:
            cell_id: Identifier for battery cell.
            num_cycles: Number of cycles to generate.
            temp_c: Ambient operating temperature.
            voltage_noise_std_v: Standard deviation of sensor ADC noise.
            randomize_sessions: If True, introduces variable start/end SOC, CC-CV current
                tapering, and session interruptions to decouple duration from total capacity.
        """
        # Realistic initial manufacturing variance
        bol_cap_mult = self.rng.normal(1.0, 0.015)  # +/- 1.5% capacity spread
        bol_res_mult = self.rng.normal(1.0, 0.03)   # +/- 3% resistance spread

        bol_cap = self.base_spec.nominal_capacity_ah * bol_cap_mult
        bol_res = (self.base_spec.nominal_resistance_ohm or 0.015) * bol_res_mult

        spec = self.base_spec.model_copy(update={"cell_id": cell_id})
        battery = SohBatteryData(
            cell_id=cell_id,
            spec=spec,
            bol_capacity_ah=bol_cap,
            bol_resistance_ohm=bol_res,
        )

        deg_model = EmpiricalDegradationModel(self.aging_config)
        ah_per_cycle = bol_cap * 2.0  # charge + discharge

        for k in range(num_cycles):
            cum_ah = k * ah_per_cycle
            # Compute physical degradation state
            retention = deg_model.predict_capacity_retention(cum_ah, avg_temp_c=temp_c)
            r_growth = deg_model.predict_resistance_growth(cum_ah, avg_temp_c=temp_c)

            true_cap = bol_cap * retention
            true_res = bol_res * r_growth

            # 1. Standard reference HPPC pulse: 10s pulse (2.0A discharge) + 20s relaxation (0.0A)
            # Physical 2-RC parameter values
            r0_k = true_res * 0.50
            r1_k = true_res * 0.25
            tau1_k = 4.0
            r2_k = true_res * 0.25
            tau2_k = 25.0
            vocv_k = 3.32

            # Pulse: 10s at 2.0A discharge
            t_pulse = np.linspace(0.0, 10.0, 50)
            i_pulse = np.full(50, 2.0)
            v_pulse = (
                vocv_k
                - 2.0 * r0_k
                - 2.0 * r1_k * (1.0 - np.exp(-t_pulse / tau1_k))
                - 2.0 * r2_k * (1.0 - np.exp(-t_pulse / tau2_k))
                + self.rng.normal(0, voltage_noise_std_v, 50)
            )

            # Relaxation: 20s at 0.0A
            t_relax = np.linspace(10.2, 30.0, 100)
            i_relax = np.zeros(100)
            v1_end = 2.0 * r1_k * (1.0 - np.exp(-10.0 / tau1_k))
            v2_end = 2.0 * r2_k * (1.0 - np.exp(-10.0 / tau2_k))
            t_rel_from_end = t_relax - 10.0
            v_relax = (
                vocv_k
                - v1_end * np.exp(-t_rel_from_end / tau1_k)
                - v2_end * np.exp(-t_rel_from_end / tau2_k)
                + self.rng.normal(0, voltage_noise_std_v, 100)
            )

            # 2. Charging segment
            n_pts_chg = 200
            if randomize_sessions:
                # Variable starting and ending SOC
                q_start = float(self.rng.uniform(0.10, 0.35))
                q_end = float(self.rng.uniform(0.70, 0.95))
                delta_q = q_end - q_start

                # CC-CV current tapering: nominal -1.15 A with taper near end
                q_rel = np.linspace(q_start, q_end, n_pts_chg)
                # Duration is determined by variable delta_q and randomized current
                chg_duration_s = float(3600.0 * (true_cap * delta_q / 1.15) * self.rng.uniform(0.90, 1.15))
                t_chg = np.linspace(35.0, 35.0 + chg_duration_s, n_pts_chg)

                # Exponential current taper in high SOC region (> 80%)
                i_chg = np.full(n_pts_chg, -1.15)
                taper_mask = q_rel > 0.80
                if np.any(taper_mask):
                    taper_progress = (q_rel[taper_mask] - 0.80) / 0.20
                    i_chg[taper_mask] = -1.15 * np.exp(-1.8 * taper_progress)
            else:
                # Standard Reference Measurement Protocol (RMP) continuous charge
                q_rel = np.linspace(0.05, 0.95, n_pts_chg)
                t_chg = np.linspace(35.0, 35.0 + 3600.0 * (true_cap / 1.15), n_pts_chg)
                i_chg = np.full(n_pts_chg, -1.15)

            # Electrochemical plateau around 45% charging progress
            v_plateau = 3.22 + 0.05 * q_rel + 0.08 / (1.0 + np.exp(-18.0 * (q_rel - 0.45))) + 0.15 * (q_rel ** 4)
            # Terminal voltage: V = V_ocv - I * R (note I < 0 -> -I * R > 0 increases terminal voltage)
            v_chg = v_plateau - i_chg * true_res + self.rng.normal(0, voltage_noise_std_v, n_pts_chg)

            # Combine pulse + relaxation + CC charge
            time_s = np.concatenate([t_pulse, t_relax, t_chg])
            voltage_v = np.clip(np.concatenate([v_pulse, v_relax, v_chg]), spec.v_min, spec.v_max + 0.05)
            current_a = np.concatenate([i_pulse, i_relax, i_chg])
            # Thermal rise: ambient + Joule heating + sensor noise
            joule_heat = (current_a ** 2) * true_res * 2.0
            temp_profile = np.full(len(time_s), temp_c) + joule_heat + self.rng.normal(0, 0.1, len(time_s))

            cycle = CycleRecord(
                cycle_index=k,
                time_s=time_s,
                voltage_v=voltage_v,
                current_a=current_a,
                temp_c=temp_profile,
                ah_throughput=cum_ah,
                measured_capacity_ah=true_cap,
                measured_resistance_ohm=true_res,
            )
            battery.cycles.append(cycle)

        battery.compute_ground_truths()
        return battery

    def generate_cohort(
        self,
        cell_ids: Sequence[str] = ("CELL_A", "CELL_B", "CELL_C"),
        num_cycles: int = 40,
        temp_c: float = 25.0,
        randomize_sessions: bool = False,
    ) -> SohDataset:
        """Generate cohort of synthetic cells for cross-battery testing."""
        dataset = SohDataset()
        for cid in cell_ids:
            bdata = self.generate_battery(
                cid,
                num_cycles=num_cycles,
                temp_c=temp_c,
                randomize_sessions=randomize_sessions,
            )
            dataset.add_battery(bdata)
        return dataset


class NonlinearAgingGenerator:
    """Generates independent non-power-law degradation trajectories.
    
    Employs a 3-stage degradation profile that deliberately departs from the
    calibrated EmpiricalDegradationModel power law (y = 1 - a * Ah^z):
    1. Initial rapid SEI passivation: Delta_Q_pass * (1 - exp(-k_pass * N))
    2. Linear steady-state wear: k_linear * N * Arrhenius(T)
    3. Sigmoidal knee-point rollover near EOL: Delta_Q_knee / (1 + exp(-(N - N_knee) / w))
    
    Used to audit whether estimators overfit model-consistent synthetic generating functions.
    """

    def __init__(
        self,
        base_spec: Optional[CellReferenceSpec] = None,
        seed: int = 42,
    ):
        if base_spec is None:
            self.base_spec = CellReferenceSpec(
                cell_id="SYNTH_NONLINEAR_2.3AH",
                chemistry="LFP",
                nominal_capacity_ah=2.30,
                v_max=3.65,
                v_min=2.00,
                t_ref_c=25.0,
                nominal_resistance_ohm=0.015,
            )
        else:
            self.base_spec = base_spec
        self.rng = np.random.default_rng(seed)

    def evaluate_retention(
        self,
        cycle_index: int,
        temp_c: float = 25.0,
        n_knee: Optional[float] = None,
    ) -> Tuple[float, float]:
        """Compute non-power-law capacity retention and resistance growth."""
        n = float(cycle_index)
        t_k = 273.15 + temp_c
        t_ref_k = 298.15
        arrh = math.exp(-32000.0 / 8.314 * (1.0 / t_k - 1.0 / t_ref_k))

        # 1. Early rapid passivation (0.5% in first 5 cycles)
        q_pass = 0.005 * (1.0 - math.exp(-0.25 * n))

        # 2. Linear cyclic wear
        q_linear = 0.00035 * n * arrh

        # 3. Non-linear rollover / knee-point
        knee_pt = 35.0 if n_knee is None else float(n_knee)
        w_knee = max(2.0, knee_pt * 0.12)
        q_knee = 0.040 / (1.0 + math.exp(-max(-10.0, min(10.0, (n - knee_pt) / w_knee))))

        total_fade = q_pass + q_linear + q_knee
        soh_c = max(0.40, min(1.0, 1.0 - total_fade))

        # Non-power-law resistance: exponential saturation + quadratic aging
        r_growth = 1.0 + 0.02 * math.sqrt(n) + 0.15 * ((n / max(1.0, knee_pt)) ** 2.0)
        soh_r = 1.0 / max(1.0, r_growth)

        return soh_c, soh_r

    def generate_battery(
        self,
        cell_id: str,
        num_cycles: int = 50,
        temp_c: float = 25.0,
        n_knee: Optional[float] = None,
    ) -> SohBatteryData:
        """Generate non-power-law battery life trajectory."""
        bol_cap = self.base_spec.nominal_capacity_ah * self.rng.normal(1.0, 0.01)
        bol_res = (self.base_spec.nominal_resistance_ohm or 0.015) * self.rng.normal(1.0, 0.02)

        spec = self.base_spec.model_copy(update={"cell_id": cell_id})
        battery = SohBatteryData(
            cell_id=cell_id,
            spec=spec,
            bol_capacity_ah=bol_cap,
            bol_resistance_ohm=bol_res,
        )

        ah_per_cycle = bol_cap * 2.0
        knee_val = (0.70 * num_cycles) if (n_knee is None and num_cycles > 50) else (35.0 if n_knee is None else n_knee)
        for k in range(num_cycles):
            cum_ah = k * ah_per_cycle
            soh_c_true, soh_r_true = self.evaluate_retention(k, temp_c=temp_c, n_knee=knee_val)

            true_cap = bol_cap * soh_c_true
            true_res = bol_res / max(1e-4, soh_r_true)

            # Synthesize lightweight cycle telemetry
            t_pts = np.linspace(0, 3600, 100)
            v_pts = np.linspace(3.0, 3.65, 100)
            i_pts = np.full_like(t_pts, -1.0)  # Charge
            temp_pts = np.full_like(t_pts, temp_c)

            rec = CycleRecord(
                cycle_index=k,
                time_s=t_pts,
                voltage_v=v_pts,
                current_a=i_pts,
                temp_c=temp_pts,
                ah_throughput=cum_ah,
                measured_capacity_ah=true_cap,
                measured_resistance_ohm=true_res,
                soh_c_bol_true=soh_c_true,
                soh_c_rated_true=soh_c_true,
                soh_r_bol_true=soh_r_true,
                soh_r_rated_true=soh_r_true,
                metadata={
                    "temp_c_avg": temp_c,
                    "current_a_avg": 1.0,
                    "soc_avg": 0.50,
                    "trajectory_type": "independent_nonlinear_three_stage",
                },
            )
            battery.cycles.append(rec)

        return battery

    def generate_cohort(
        self,
        conditions: Optional[Sequence[Tuple[str, float]]] = None,
        num_cycles: int = 50,
    ) -> SohDataset:
        """Generate cohort of independent non-power-law synthetic cells."""
        if conditions is None:
            conditions = [
                ("NONLINEAR_CELL_25C", 25.0),
                ("NONLINEAR_CELL_40C", 40.0),
                ("NONLINEAR_CELL_15C", 15.0),
                ("NONLINEAR_CELL_30C", 30.0),
            ]
        dataset = SohDataset()
        for cid, temp_c in conditions:
            battery = self.generate_battery(cid, num_cycles=num_cycles, temp_c=temp_c)
            dataset.add_battery(battery)
        return dataset
