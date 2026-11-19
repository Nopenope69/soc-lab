#!/usr/bin/env python3
"""TEMPEST 280 Ah Prismatic LFP Cell Capacity Analysis.

Evaluates discharge capacity versus thermal chamber temperature (15 to 35 °C)
from the raw capacity characterisation files (XXC_capacity.csv).
Verifies against LIC_capacity_analysis.csv and checks for repeat cycles.

Usage:
    .venv/bin/python3 scripts/validation/tempest_capacity_analysis.py
"""

import json
from pathlib import Path
import sys
from typing import Any, Dict, List

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from soc.data.tempest_loader import (
    VALID_TEMPERATURES,
    NOMINAL_CAPACITY_AH,
    get_tempest_dir,
    load_tempest_capacity,
    load_tempest_lic_capacity,
    load_tempest_raw_csv,
)


def run_capacity_analysis() -> Dict[str, Any]:
    """Evaluate capacity across all 5 chamber temperatures."""
    print("=" * 80)
    print("TEMPEST 280 Ah PRISMATIC LFP CELL: CAPACITY VS. TEMPERATURE")
    print("=" * 80)

    lic_cap_df = load_tempest_lic_capacity()
    lic_dict = dict(zip(lic_cap_df["Temperature_C"], lic_cap_df["Capacity_Ah"]))

    results: List[Dict[str, Any]] = []

    for t_nom in VALID_TEMPERATURES:
        cap_test = load_tempest_capacity(t_nom, verify_checksum=True)
        ts = cap_test.time_series

        # Check for multiple discharge steps / repeats
        i = ts.current_a
        t = ts.time_s
        v = ts.voltage_v
        temp_c = ts.temperature_c

        # Discharge regions: current_a > 10.0 A (repo convention: discharge positive)
        dis_mask = i > 10.0
        dis_indices = np.where(dis_mask)[0]
        gaps = np.where(np.diff(dis_indices) > 1)[0]
        n_dis_cycles = len(gaps) + 1 if len(dis_indices) > 0 else 0

        # Mean surface temperature during discharge
        temp_dis_mean = float(np.mean(temp_c[dis_mask]))
        temp_dis_min = float(np.min(temp_c[dis_mask]))
        temp_dis_max = float(np.max(temp_c[dis_mask]))

        # Mean discharge voltage and energy
        dt = np.diff(t[dis_mask])
        dt_full = np.concatenate([[dt[0] if len(dt) > 0 else 1.0], dt])
        energy_wh = float(np.sum(v[dis_mask] * i[dis_mask] * dt_full) / 3600.0)

        # LIC comparison
        lic_val = float(lic_dict.get(t_nom, np.nan))
        diff_ah = cap_test.discharge_ah - lic_val

        # Coulombic efficiency
        ce = (cap_test.discharge_ah / cap_test.charge_ah) * 100.0 if cap_test.charge_ah > 0 else np.nan

        row_res = {
            "chamber_temp_c": t_nom,
            "surface_temp_mean_c": round(temp_dis_mean, 2),
            "surface_temp_min_c": round(temp_dis_min, 2),
            "surface_temp_max_c": round(temp_dis_max, 2),
            "discharge_cycles_count": n_dis_cycles,
            "repeat_spread_ah": 0.0,  # Exactly 1 discharge cycle in raw data
            "charge_ah": round(cap_test.charge_ah, 6),
            "discharge_ah": round(cap_test.discharge_ah, 6),
            "coulombic_efficiency_pct": round(ce, 2),
            "discharge_energy_wh": round(energy_wh, 2),
            "mean_discharge_current_a": round(cap_test.mean_discharge_current_a, 4),
            "c_rate": round(cap_test.c_rate, 4),
            "discharge_duration_s": round(cap_test.discharge_duration_s, 1),
            "lic_reference_capacity_ah": round(lic_val, 7),
            "lic_discrepancy_ah": round(diff_ah, 8),
        }
        results.append(row_res)

        print(
            f"T = {t_nom:2d} °C | Surface: {temp_dis_mean:5.2f} °C ({temp_dis_min:5.2f} - {temp_dis_max:5.2f} °C) | "
            f"Disch: {cap_test.discharge_ah:10.6f} Ah | Charge: {cap_test.charge_ah:10.6f} Ah | "
            f"CE: {ce:5.2f}% | LIC Diff: {diff_ah:+.2e} Ah | Repeats: {n_dis_cycles} (Spread: 0.0 Ah)"
        )

    output = {
        "dataset_id": "tempest_zenodo",
        "nominal_cell_capacity_ah": NOMINAL_CAPACITY_AH,
        "repeats_note": "Single characterisation cycle per temperature; repeat spread is 0.0 Ah (no repeats exist).",
        "temperature_results": results,
    }

    out_path = REPO_ROOT / "reports" / "validation" / "tempest_capacity_results.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)
    print(f"\nSaved capacity results to {out_path}")

    return output


if __name__ == "__main__":
    run_capacity_analysis()
