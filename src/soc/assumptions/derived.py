"""Computation of derived quantities from resolved assumptions in one place."""

import hashlib
from typing import Any, Dict, List, Tuple
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
    hex_len = 2 * 2 * 2
    hash_slice = scenario_hash[:hex_len]
    hash_int = int(f"0x{hash_slice}", 0)
    combined = (base_seed ^ hash_int) & (1000 * 1000 * 1000 * 2 - 1)
    return int(combined)


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
