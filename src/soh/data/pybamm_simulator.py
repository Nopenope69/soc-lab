"""Electrochemical battery degradation dataset generator using PyBaMM.

Simulates physics-based degradation (solvent diffusion-limited SEI growth,
electrolyte resistance increase, and loss of lithium inventory) under
controlled temperature, C-rate, and cycling protocols using PyBaMM SPM/SPMe.
"""

from dataclasses import dataclass
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import numpy as np

try:
    import pybamm
except ImportError:
    pybamm = None

from soh.common.contracts import CycleRecord
from soh.common.protocols import CellReferenceSpec, ReferenceProvenance, ReferenceProvenanceType
from soh.data.base_loader import SohBatteryData, SohDataset


@dataclass
class PybammSimulationConfig:
    """Configuration for PyBaMM degradation simulation run."""

    num_cycles: int = 15
    ambient_temp_c: float = 25.0
    c_rate: float = 1.0
    chemistry_param: str = "Chen2020"  # LG M50T 21700 cell
    sei_model: str = "solvent-diffusion limited"  # "solvent-diffusion limited" or "ec reaction limited"
    sei_solvent_diffusivity: Optional[float] = 1.5e-19
    r_sei_growth_factor: float = 1.5e7  # Resistance growth coupling [1/m]


class PybammDegradationSimulator:
    """Generates standard SohDataset instances using PyBaMM electrochemical models."""

    def __init__(self, cache_dir: Optional[Path] = None):
        self.cache_dir = cache_dir

    def simulate_cell(
        self,
        cell_id: str,
        config: PybammSimulationConfig,
    ) -> SohBatteryData:
        """Simulate cycling degradation for a single cell and return SohBatteryData."""
        if pybamm is None:
            raise ImportError("pybamm is required for PyBaMM degradation simulation.")
        model = pybamm.lithium_ion.SPM({"SEI": config.sei_model})
        param = pybamm.ParameterValues(config.chemistry_param)

        t_amb_k = 273.15 + config.ambient_temp_c
        param["Ambient temperature [K]"] = t_amb_k
        param["Initial temperature [K]"] = t_amb_k

        if config.sei_solvent_diffusivity is not None and "SEI solvent diffusivity [m2.s-1]" in param:
            param["SEI solvent diffusivity [m2.s-1]"] = config.sei_solvent_diffusivity

        nom_cap_ah = float(param["Nominal cell capacity [A.h]"])
        nom_res_ohm = 0.020  # Nominal pristine resistance estimate

        spec = CellReferenceSpec(
            cell_id=cell_id,
            chemistry="NMC",
            nominal_capacity_ah=nom_cap_ah,
            v_max=4.20,
            v_min=3.00,
            t_ref_c=25.0,
            nominal_resistance_ohm=nom_res_ohm,
            provenance=ReferenceProvenance(
                provenance_type=ReferenceProvenanceType.ELECTROCHEMICAL_MODEL,
                calibration_dataset_id=f"PyBaMM_{config.chemistry_param}_{config.sei_model}",
                description="Electrochemical single-particle simulation with SEI degradation kinetics",
            ),
        )

        battery = SohBatteryData(
            cell_id=cell_id,
            spec=spec,
            bol_capacity_ah=nom_cap_ah,
            bol_resistance_ohm=nom_res_ohm,
        )

        exp_cycle = (
            f"Discharge at {config.c_rate}C until 3.0V",
            "Rest for 2 minutes",
            f"Charge at {config.c_rate}C until 4.2V",
            "Hold at 4.2V until C/20",
            "Rest for 2 minutes",
        )
        experiment = pybamm.Experiment([exp_cycle] * config.num_cycles)
        sim = pybamm.Simulation(model, parameter_values=param, experiment=experiment)
        sol = sim.solve()

        cum_throughput_ah = 0.0
        bol_sei_thickness_m = 5.0e-9

        for k, cycle_sol in enumerate(sol.cycles):
            t_pts = cycle_sol["Time [s]"].entries
            v_pts = cycle_sol["Voltage [V]"].entries
            i_pts = cycle_sol["Current [A]"].entries

            # Subsample telemetry to ~100 points per cycle for lightweight memory profile
            step = max(1, len(t_pts) // 100)
            t_sub = t_pts[::step]
            v_sub = v_pts[::step]
            i_sub = i_pts[::step]
            temp_sub = np.full_like(t_sub, config.ambient_temp_c)

            sei_thick = float(cycle_sol["X-averaged negative SEI thickness [m]"].entries[-1])
            cap_lost_ah = float(cycle_sol["Loss of capacity to negative SEI [A.h]"].entries[-1])

            if k == 0:
                bol_sei_thickness_m = float(cycle_sol["X-averaged negative SEI thickness [m]"].entries[0])

            # Ground truth metrics
            soh_c_bol = max(0.0, min(1.0, 1.0 - (cap_lost_ah / nom_cap_ah)))
            delta_sei = max(0.0, sei_thick - bol_sei_thickness_m)
            soh_r_bol = max(0.0, min(1.0, 1.0 / (1.0 + config.r_sei_growth_factor * delta_sei)))

            cycle_duration = float(t_pts[-1] - t_pts[0])
            cycle_throughput = float(np.sum(np.abs(i_pts[1:] * np.diff(t_pts))) / 3600.0)
            cum_throughput_ah += cycle_throughput

            rec = CycleRecord(
                cycle_index=k,
                time_s=t_sub - t_sub[0],
                voltage_v=v_sub,
                current_a=i_sub,
                temp_c=temp_sub,
                ah_throughput=cum_throughput_ah,
                measured_capacity_ah=nom_cap_ah * soh_c_bol,
                measured_resistance_ohm=nom_res_ohm / max(1e-3, soh_r_bol),
                soh_c_bol_true=soh_c_bol,
                soh_c_rated_true=soh_c_bol,
                soh_r_bol_true=soh_r_bol,
                soh_r_rated_true=soh_r_bol,
                metadata={
                    "timestamp_start": float(t_pts[0]),
                    "duration_s": cycle_duration,
                    "temp_c_avg": config.ambient_temp_c,
                    "current_a_avg": float(np.mean(np.abs(i_sub))),
                    "soc_avg": 0.50,
                    "sei_thickness_nm": sei_thick * 1e9,
                },
            )
            battery.cycles.append(rec)

        return battery

    def generate_cohort(
        self,
        conditions: Optional[List[Tuple[str, float, float]]] = None,
        num_cycles: int = 15,
        sei_model: str = "solvent-diffusion limited",
        chemistry_param: str = "Chen2020",
        sei_solvent_diffusivity: Optional[float] = 1.5e-19,
    ) -> SohDataset:
        """Generate a multi-cell cohort spanning multiple temperatures and C-rates.
        
        Args:
            conditions: List of (cell_id, temp_c, c_rate) tuples.
            num_cycles: Number of cycles per cell.
            sei_model: "solvent-diffusion limited" or "ec reaction limited".
            chemistry_param: "Chen2020" (LG M50T) or "Marquis2019".
            sei_solvent_diffusivity: Diffusion coefficient override [m^2 / s].
        """
        if conditions is None:
            conditions = [
                ("PYBAMM_CELL_25C_1C", 25.0, 1.0),
                ("PYBAMM_CELL_45C_1C", 45.0, 1.0),
                ("PYBAMM_CELL_15C_1C", 15.0, 1.0),
                ("PYBAMM_CELL_25C_05C", 25.0, 0.5),
            ]

        dataset = SohDataset()
        for cid, temp_c, c_rate in conditions:
            cfg = PybammSimulationConfig(
                num_cycles=num_cycles,
                ambient_temp_c=temp_c,
                c_rate=c_rate,
                chemistry_param=chemistry_param,
                sei_model=sei_model,
                sei_solvent_diffusivity=sei_solvent_diffusivity,
            )
            battery = self.simulate_cell(cell_id=cid, config=cfg)
            dataset.add_battery(battery)

        return dataset
