"""Computation of derived quantities from resolved assumptions in one place."""

import copy
import hashlib
from typing import Any, Dict, List, Tuple
from soc.assumptions.loader import PERCENT_FACTOR
from soc.assumptions.schema import Assumptions


def get_coulomb_capacity_as(nominal_capacity_ah: float) -> float:
    """Convert nominal capacity from Ampere-hours to Ampere-seconds (Coulombs).

    Uses exact 3600 s/h conversion factor.
    """
    return nominal_capacity_ah * 3600


def get_derived_capacitances(
    r1_ohm: float, tau1_s: float, r2_ohm: float, tau2_s: float
) -> Tuple[float, float]:
    """Compute RC branch capacitances C1 and C2 in Farads from R and tau.

    C = tau / R. Computed dynamically, never stored twice.
    """
    c1_f = tau1_s / r1_ohm
    c2_f = tau2_s / r2_ohm
    return c1_f, c2_f


def derive_scenario_seed(base_seed: int, scenario_hash: str) -> int:
    """Derive a reproducible, scenario-specific integer seed for numpy generators.

    Combines base integer seed with the SHA-256 hash string of the scenario config.
    """
    hash_int = int(f"0x{scenario_hash}", 0)
    return int(base_seed ^ hash_int)


def compute_derived_quantities(assumptions: Assumptions) -> Dict[str, Any]:
    """Calculate all secondary electrochemical and operational parameters."""
    cap_ah = assumptions.plant.nominal_capacity_Ah.value
    cap_as = get_coulomb_capacity_as(cap_ah)

    r1_val = assumptions.plant.r1_table_ohm.value
    tau1_val = assumptions.plant.tau1_table_s.value
    r2_val = assumptions.plant.r2_table_ohm.value
    tau2_val = assumptions.plant.tau2_table_s.value

    # If tables are dicts keyed by temperature, compute per temperature
    c1_derived: Dict[str, Any] = {}
    c2_derived: Dict[str, Any] = {}

    if isinstance(r1_val, dict) and isinstance(tau1_val, dict):
        for temp_k in r1_val:
            if temp_k in tau1_val:
                r1_item = r1_val[temp_k]
                t1_item = tau1_val[temp_k]
                if isinstance(r1_item, (int, float)) and isinstance(t1_item, (int, float)):
                    c1_derived[temp_k] = t1_item / r1_item
    elif isinstance(r1_val, (int, float)) and isinstance(tau1_val, (int, float)):
        c1_derived["default"] = tau1_val / r1_val

    if isinstance(r2_val, dict) and isinstance(tau2_val, dict):
        for temp_k in r2_val:
            if temp_k in tau2_val:
                r2_item = r2_val[temp_k]
                t2_item = tau2_val[temp_k]
                if isinstance(r2_item, (int, float)) and isinstance(t2_item, (int, float)):
                    c2_derived[temp_k] = t2_item / r2_item
    elif isinstance(r2_val, (int, float)) and isinstance(tau2_val, (int, float)):
        c2_derived["default"] = tau2_val / r2_val

    return {
        "capacity_As": cap_as,
        "c1_farad": c1_derived,
        "c2_farad": c2_derived,
    }


def get_effective_estimator_parameters(assumptions: Assumptions) -> Dict[str, Any]:
    """Extract estimator parameters with mismatch scaling applied, leaving plant intact.

    Defaults to a copy of plant parameters if explicit estimator parameters are None.
    Applies percentage deviations defined in estimator_model.mismatch.
    """
    mismatch = assumptions.estimator_model.mismatch

    # 1. Capacity
    if assumptions.estimator_model.nominal_capacity_Ah is not None:
        cap_val = float(assumptions.estimator_model.nominal_capacity_Ah.value)
    else:
        plant_cap = float(assumptions.plant.nominal_capacity_Ah.value)
        cap_scale = 1 + (float(mismatch.capacity_pct.value) / PERCENT_FACTOR)
        cap_val = plant_cap * cap_scale

    # Helper for scaling table or scalar by percentage
    def _scale_table_or_scalar(val: Any, pct: float) -> Any:
        scale = 1 + (pct / PERCENT_FACTOR)
        if isinstance(val, dict):
            return {k: float(v) * scale for k, v in val.items()}
        elif isinstance(val, (int, float)):
            return float(val) * scale
        return val

    # 2. R0
    if assumptions.estimator_model.r0_table_ohm is not None:
        r0_val = copy.deepcopy(assumptions.estimator_model.r0_table_ohm.value)
    else:
        r0_val = _scale_table_or_scalar(
            assumptions.plant.r0_table_ohm.value, float(mismatch.r0_pct.value)
        )

    # 3. R1 and tau1
    if assumptions.estimator_model.r1_table_ohm is not None:
        r1_val = copy.deepcopy(assumptions.estimator_model.r1_table_ohm.value)
    else:
        r1_val = _scale_table_or_scalar(
            assumptions.plant.r1_table_ohm.value, float(mismatch.r1_pct.value)
        )

    if assumptions.estimator_model.tau1_table_s is not None:
        tau1_val = copy.deepcopy(assumptions.estimator_model.tau1_table_s.value)
    else:
        tau1_val = _scale_table_or_scalar(
            assumptions.plant.tau1_table_s.value, float(mismatch.tau1_pct.value)
        )

    # 4. R2 and tau2
    if assumptions.estimator_model.r2_table_ohm is not None:
        r2_val = copy.deepcopy(assumptions.estimator_model.r2_table_ohm.value)
    else:
        r2_val = _scale_table_or_scalar(
            assumptions.plant.r2_table_ohm.value, float(mismatch.r2_pct.value)
        )

    if assumptions.estimator_model.tau2_table_s is not None:
        tau2_val = copy.deepcopy(assumptions.estimator_model.tau2_table_s.value)
    else:
        tau2_val = _scale_table_or_scalar(
            assumptions.plant.tau2_table_s.value, float(mismatch.tau2_pct.value)
        )

    # 5. OCV table (with mV offset)
    ocv_offset_v = float(mismatch.ocv_offset_mv.value) / 1000
    plant_ocv = assumptions.plant.ocv_table_v.value
    est_ocv: Dict[str, List[float]] = {}
    if isinstance(plant_ocv, dict):
        for temp_k, v_list in plant_ocv.items():
            if isinstance(v_list, list):
                est_ocv[temp_k] = [float(v) + ocv_offset_v for v in v_list]

    # 6. Hysteresis
    if assumptions.estimator_model.hysteresis_amplitude_v is not None:
        h_amp = float(assumptions.estimator_model.hysteresis_amplitude_v.value)
    else:
        h_amp_plant = float(assumptions.plant.hysteresis_amplitude_v.value)
        h_amp_scale = 1 + (float(mismatch.hysteresis_amplitude_pct.value) / PERCENT_FACTOR)
        h_amp = h_amp_plant * h_amp_scale

    if assumptions.estimator_model.hysteresis_gamma is not None:
        h_gamma = float(assumptions.estimator_model.hysteresis_gamma.value)
    else:
        h_gamma_plant = float(assumptions.plant.hysteresis_gamma.value)
        h_gamma_scale = 1 + (float(mismatch.hysteresis_gamma_pct.value) / PERCENT_FACTOR)
        h_gamma = h_gamma_plant * h_gamma_scale

    # 7. Efficiency
    if assumptions.estimator_model.coulombic_efficiency is not None:
        eta_val = float(assumptions.estimator_model.coulombic_efficiency.value)
    else:
        eta_val = float(assumptions.plant.coulombic_efficiency.value)

    return {
        "nominal_capacity_Ah": cap_val,
        "coulombic_efficiency": eta_val,
        "temperatures_c": copy.deepcopy(assumptions.plant.temperatures_c.value),
        "soc_grid": copy.deepcopy(assumptions.plant.soc_grid.value),
        "ocv_table_v": est_ocv,
        "r0_table_ohm": r0_val,
        "r1_table_ohm": r1_val,
        "tau1_table_s": tau1_val,
        "r2_table_ohm": r2_val,
        "tau2_table_s": tau2_val,
        "hysteresis_amplitude_v": h_amp,
        "hysteresis_gamma": h_gamma,
    }
