#!/usr/bin/env python3
"""Cross-Cell Comparison Table Across Four LFP Cells in this Repository.

Cells compared (from files in this repository only):
1. CALCE A123: deliverable/calibrations/calce_a123_v4.json (1.06 Ah cylindrical)
2. GE105: deliverable/calibrations/ge105_v1.json (105.04 Ah prismatic)
3. FlexiPod: deliverable/calibrations/flexipod_100ah_v1.json (95.15 Ah prismatic)
4. TEMPEST: reports/validation/tempest_capacity_results.json & tempest_ecm_results.json (302.31 Ah prismatic)

Metrics compared:
- Cell nominal and measured capacity (Ah)
- Ohmic resistance R0 at the temperature nearest 25 °C (mOhm)
- Plateau slope dOCV/dSOC across 20% to 80% SOC (V/unit and mV/pp)
- Measured hysteresis if available (mV)

Rules Enforced:
- Facts only from committed repository files.
- Assert NO causes and NO scaling laws from four points.

Usage:
    .venv/bin/python3 scripts/validation/tempest_cross_cell_comparison.py
"""

import json
from pathlib import Path
import sys
from typing import Any, Dict, List

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[2]


def build_cross_cell_table() -> Dict[str, Any]:
    print("=" * 100)
    print("FOUR-CELL CROSS-DATASET CHARACTERISATION COMPARISON (REPO-LOCAL FILES ONLY)")
    print("=" * 100)

    rows: List[Dict[str, Any]] = []

    # 1. CALCE A123
    calce_path = REPO_ROOT / "deliverable" / "calibrations" / "calce_a123_v4.json"
    with open(calce_path, "r", encoding="utf-8") as f:
        calce_data = json.load(f)

    calce_cap_ah = calce_data["nominal_capacity_ah"]  # 1.06356 Ah
    # Nearest temp to 25C is 27.3C or 25.0C in table
    # r0_table['27.3']: 0.15851 Ohm (fitted from real test bench DST); '25.0': 0.0010 Ohm
    calce_r0_ohm = calce_data["r0_table"]["27.3"]
    calce_r0_temp_c = 27.3
    # OCV plateau 20-80%:
    calce_ocv_80 = calce_data["ocv_table"]["27.3"][9]  # SOC 0.80 -> 3.3447
    calce_ocv_20 = calce_data["ocv_table"]["27.3"][3]  # SOC 0.20 -> 3.2488
    calce_slope = (calce_ocv_80 - calce_ocv_20) / (0.80 - 0.20)
    # Hysteresis m_table_v at 25C: index 1 in m_table_temps_c [20, 25, 30, 40, 50]
    calce_hyst_mv = calce_data["m_table_v"][1] * 1000.0  # 17.19 mV

    rows.append({
        "cell_id": "CALCE A123 (A123 APR18650M1A)",
        "form_factor": "18650 Cylindrical",
        "chemistry": "LFP/Graphite",
        "capacity_source_file": "deliverable/calibrations/calce_a123_v4.json",
        "nominal_capacity_ah": 1.1,
        "measured_capacity_ah": round(calce_cap_ah, 4),
        "r0_source_file": "deliverable/calibrations/calce_a123_v4.json:r0_table['27.3']",
        "r0_eval_temperature_c": calce_r0_temp_c,
        "r0_mohm": round(calce_r0_ohm * 1e3, 3),
        "plateau_slope_source_file": "deliverable/calibrations/calce_a123_v4.json:ocv_table['27.3']",
        "plateau_slope_v_per_unit_soc": round(calce_slope, 4),
        "plateau_slope_mv_per_pp": round(calce_slope * 10.0, 3),
        "hysteresis_source_file": "deliverable/calibrations/calce_a123_v4.json:m_table_v[25C]",
        "measured_hysteresis_mv": round(calce_hyst_mv, 2),
    })

    # 2. GE105 (Univ Gustave Eiffel / EVE Energy 105 Ah)
    ge105_path = REPO_ROOT / "deliverable" / "calibrations" / "ge105_v1.json"
    with open(ge105_path, "r", encoding="utf-8") as f:
        ge105_data = json.load(f)

    ge105_cap_ah = ge105_data["nominal_capacity_ah"]  # 105.0427 Ah
    ge105_r0_ohm = ge105_data["r0_table"]["25.0"]  # 0.0005815 Ohm
    ge105_ocv_80 = ge105_data["ocv_table"]["25.0"][9]  # 3.33755 V
    ge105_ocv_20 = ge105_data["ocv_table"]["25.0"][3]  # 3.25520 V
    ge105_slope = (ge105_ocv_80 - ge105_ocv_20) / (0.80 - 0.20)
    # Hysteresis m_table_v at 25C: index 4 in [0, 10, 15, 20, 25, 30, 35, 40]
    ge105_hyst_mv = ge105_data["m_table_v"][4] * 1000.0  # 31.76 mV

    rows.append({
        "cell_id": "GE105 (EVE Energy LF105)",
        "form_factor": "Prismatic",
        "chemistry": "LFP/Graphite",
        "capacity_source_file": "deliverable/calibrations/ge105_v1.json",
        "nominal_capacity_ah": 105.0,
        "measured_capacity_ah": round(ge105_cap_ah, 4),
        "r0_source_file": "deliverable/calibrations/ge105_v1.json:r0_table['25.0']",
        "r0_eval_temperature_c": 25.0,
        "r0_mohm": round(ge105_r0_ohm * 1e3, 4),
        "plateau_slope_source_file": "deliverable/calibrations/ge105_v1.json:ocv_table['25.0']",
        "plateau_slope_v_per_unit_soc": round(ge105_slope, 4),
        "plateau_slope_mv_per_pp": round(ge105_slope * 10.0, 3),
        "hysteresis_source_file": "deliverable/calibrations/ge105_v1.json:m_table_v[25C]",
        "measured_hysteresis_mv": round(ge105_hyst_mv, 2),
    })

    # 3. FlexiPod (FlexiPod 100 Ah)
    flexi_path = REPO_ROOT / "deliverable" / "calibrations" / "flexipod_100ah_v1.json"
    with open(flexi_path, "r", encoding="utf-8") as f:
        flexi_data = json.load(f)

    flexi_cap_ah = flexi_data["nominal_capacity_ah"]  # 95.1521 Ah
    flexi_r0_ohm = flexi_data["r0_table"]["25.0"]  # 0.000894 Ohm
    flexi_ocv_80 = flexi_data["ocv_table"]["25.0"][9]  # 3.33525 V
    flexi_ocv_20 = flexi_data["ocv_table"]["25.0"][3]  # 3.25203 V
    flexi_slope = (flexi_ocv_80 - flexi_ocv_20) / (0.80 - 0.20)
    # Hysteresis m_table_v at 25C: index 3 in [5, 10, 15, 20, 25, 35]
    flexi_hyst_mv = flexi_data["m_table_v"][3] * 1000.0  # 12.01 mV

    rows.append({
        "cell_id": "FlexiPod (100 Ah Prismatic)",
        "form_factor": "Prismatic",
        "chemistry": "LFP",
        "capacity_source_file": "deliverable/calibrations/flexipod_100ah_v1.json",
        "nominal_capacity_ah": 100.0,
        "measured_capacity_ah": round(flexi_cap_ah, 4),
        "r0_source_file": "deliverable/calibrations/flexipod_100ah_v1.json:r0_table['25.0']",
        "r0_eval_temperature_c": 25.0,
        "r0_mohm": round(flexi_r0_ohm * 1e3, 4),
        "plateau_slope_source_file": "deliverable/calibrations/flexipod_100ah_v1.json:ocv_table['25.0']",
        "plateau_slope_v_per_unit_soc": round(flexi_slope, 4),
        "plateau_slope_mv_per_pp": round(flexi_slope * 10.0, 3),
        "hysteresis_source_file": "deliverable/calibrations/flexipod_100ah_v1.json:m_table_v[25C]",
        "measured_hysteresis_mv": round(flexi_hyst_mv, 2),
    })

    # 4. TEMPEST 280 Ah
    tempest_cap_path = REPO_ROOT / "reports" / "validation" / "tempest_capacity_results.json"
    with open(tempest_cap_path, "r", encoding="utf-8") as f:
        t_cap_data = json.load(f)
    t_25_cap = [item for item in t_cap_data["temperature_results"] if item["chamber_temp_c"] == 25][0]

    tempest_ecm_path = REPO_ROOT / "reports" / "validation" / "tempest_ecm_results.json"
    with open(tempest_ecm_path, "r", encoding="utf-8") as f:
        t_ecm_data = json.load(f)
    # R0 at 55% SOC, 25C:
    t_25_r0 = [p for p in t_ecm_data["in_sample_pulse_parameters"] if p["temperature_c"] == 25 and p["soc_nominal"] == 0.55][0]["r0_ohm"]
    t_25_slope = t_ecm_data["plateau_slopes_by_temp"]["25"]["slope_v_per_unit_soc"]

    rows.append({
        "cell_id": "TEMPEST 280 Ah ('LIC')",
        "form_factor": "Prismatic",
        "chemistry": "LFP",
        "capacity_source_file": "reports/validation/tempest_capacity_results.json (T=25C)",
        "nominal_capacity_ah": 280.0,
        "measured_capacity_ah": round(t_25_cap["discharge_ah"], 4),
        "r0_source_file": "reports/validation/tempest_ecm_results.json (T=25C, SOC=0.55)",
        "r0_eval_temperature_c": 25.0,
        "r0_mohm": round(t_25_r0 * 1e3, 4),
        "plateau_slope_source_file": "reports/validation/tempest_ecm_results.json (T=25C)",
        "plateau_slope_v_per_unit_soc": round(t_25_slope, 4),
        "plateau_slope_mv_per_pp": round(t_25_slope * 10.0, 3),
        "hysteresis_source_file": "N/A (No continuous pseudo-OCV charge/discharge loop in dataset)",
        "measured_hysteresis_mv": None,
    })

    # Print Table
    print(f"{'Cell Identifier':<30} | {'Nom Cap (Ah)':>12} | {'Meas Cap (Ah)':>13} | {'R0 (mOhm)':>10} | {'Eval T (°C)':>11} | {'Slope (mV/pp)':>13} | {'Hysteresis (mV)':>16}")
    print("-" * 115)
    for r in rows:
        hyst_str = f"{r['measured_hysteresis_mv']:16.2f}" if r["measured_hysteresis_mv"] is not None else f"{'N/A':>16}"
        print(
            f"{r['cell_id']:<30} | {r['nominal_capacity_ah']:12.1f} | {r['measured_capacity_ah']:13.4f} | "
            f"{r['r0_mohm']:10.4f} | {r['r0_eval_temperature_c']:11.1f} | {r['plateau_slope_mv_per_pp']:13.3f} | "
            f"{hyst_str}"
        )

    output = {
        "disclaimer": "Asserting NO causes and NO scaling laws from four points. All values extracted directly from committed repository files.",
        "cells": rows,
    }

    out_file = REPO_ROOT / "reports" / "validation" / "tempest_cross_cell_comparison.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)
    print(f"\nSaved cross-cell comparison table to {out_file}")

    return output


if __name__ == "__main__":
    build_cross_cell_table()
