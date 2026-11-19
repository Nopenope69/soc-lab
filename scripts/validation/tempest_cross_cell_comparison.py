#!/usr/bin/env python3
"""Cross-Cell Comparison Table Across Four LFP Cells in this Repository.

Cells compared (from files in this repository only):
1. CALCE A123: deliverable/calibrations/calce_a123_v4.json
2. GE105: deliverable/calibrations/ge105_v1.json
3. FlexiPod: deliverable/calibrations/flexipod_100ah_v1.json
4. TEMPEST: reports/validation/tempest_capacity_results.json & tempest_ecm_results.json

Metrics compared:
- Cell format and description
- Cell nominal and measured capacity (Ah) with explicit file sources
- Ohmic resistance R0 with explicit temperature, SOC, and method (not directly comparable)
- Plateau slope dOCV/dSOC across stated SOC window (V/unit and mV/pp)
- Measured hysteresis with explicit definition per cell

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
    print("=" * 115)
    print("FOUR-CELL CROSS-DATASET CHARACTERISATION COMPARISON (REPO-LOCAL FILES ONLY)")
    print("=" * 115)

    rows: List[Dict[str, Any]] = []

    # 1. CALCE A123
    calce_path = REPO_ROOT / "deliverable" / "calibrations" / "calce_a123_v4.json"
    with open(calce_path, "r", encoding="utf-8") as f:
        calce_data = json.load(f)

    calce_cap_ah = calce_data["nominal_capacity_ah"]  # 1.06356 Ah (key: nominal_capacity_ah, line 5)
    calce_r0_ohm = calce_data["r0_table"]["27.3"]      # 0.15851 Ohm (key: r0_table['27.3'], line 25)
    calce_ocv_80 = calce_data["ocv_table"]["27.3"][9]  # SOC 0.80 -> 3.3447 V (key: ocv_table['27.3'], line 38)
    calce_ocv_20 = calce_data["ocv_table"]["27.3"][3]  # SOC 0.20 -> 3.2488 V (key: ocv_table['27.3'], line 32)
    calce_slope = (calce_ocv_80 - calce_ocv_20) / (0.80 - 0.20)
    calce_hyst_mv = calce_data["m_table_v"][1] * 1000.0  # 17.19 mV (key: m_table_v[1], 25C, line 18)

    rows.append({
        "cell_id": "CALCE A123",
        "description": "A123 LiFePO4 cell, format UNVERIFIED; measured capacity 1.0636 Ah (A1-007, 25 C)",
        "form_factor": "format UNVERIFIED",
        "chemistry": "LFP/Graphite",
        "nominal_capacity_ah": "UNVERIFIED",
        "measured_capacity_ah": round(calce_cap_ah, 4),
        "capacity_source": "deliverable/calibrations/calce_a123_v4.json:nominal_capacity_ah",
        "r0_mohm": round(calce_r0_ohm * 1e3, 3),
        "r0_condition": "27.3 °C, SOC-averaged table value (not directly comparable to single-SOC pulses)",
        "r0_source": "deliverable/calibrations/calce_a123_v4.json:r0_table['27.3']",
        "plateau_slope_v_per_unit_soc": round(calce_slope, 4),
        "plateau_slope_mv_per_pp": round(calce_slope * 10.0, 3),
        "plateau_slope_definition": "Linear slope between SOC 0.20 and 0.80 from 27.3 °C OCV table",
        "plateau_slope_source": "deliverable/calibrations/calce_a123_v4.json:ocv_table['27.3']",
        "measured_hysteresis_mv": round(calce_hyst_mv, 2),
        "hysteresis_definition": "Calibration table saturation parameter m_table_v at 25 °C (model parameter)",
        "hysteresis_source": "deliverable/calibrations/calce_a123_v4.json:m_table_v[1]",
    })

    # 2. GE105
    ge105_path = REPO_ROOT / "deliverable" / "calibrations" / "ge105_v1.json"
    with open(ge105_path, "r", encoding="utf-8") as f:
        ge105_data = json.load(f)

    ge105_cap_ah = ge105_data["nominal_capacity_ah"]  # 105.0427 Ah (key: nominal_capacity_ah, line 4)
    ge105_r0_ohm = ge105_data["r0_table"]["25.0"]      # 0.0005815 Ohm (key: r0_table['25.0'], line 28)
    ge105_ocv_80 = ge105_data["ocv_table"]["25.0"][9]  # 3.33755 V (key: ocv_table['25.0'], line 42)
    ge105_ocv_20 = ge105_data["ocv_table"]["25.0"][3]  # 3.25520 V (key: ocv_table['25.0'], line 36)
    ge105_slope = (ge105_ocv_80 - ge105_ocv_20) / (0.80 - 0.20)
    ge105_hyst_mv = ge105_data["m_table_v"][4] * 1000.0  # 31.76 mV (key: m_table_v[4], 25C, line 20)

    rows.append({
        "cell_id": "GE105 (EVE Energy LF105)",
        "description": "EVE Energy LF105 LFP cell (BUGE388..BUGE391)",
        "form_factor": "prismatic (general knowledge of the product; not stated in dataset files)",
        "chemistry": "LFP/Graphite",
        "nominal_capacity_ah": 105.0,
        "measured_capacity_ah": round(ge105_cap_ah, 4),
        "capacity_source": "deliverable/calibrations/ge105_v1.json:nominal_capacity_ah",
        "r0_mohm": round(ge105_r0_ohm * 1e3, 4),
        "r0_condition": "25.0 °C, SOC-averaged table value (not directly comparable to single-SOC pulses)",
        "r0_source": "deliverable/calibrations/ge105_v1.json:r0_table['25.0']",
        "plateau_slope_v_per_unit_soc": round(ge105_slope, 4),
        "plateau_slope_mv_per_pp": round(ge105_slope * 10.0, 3),
        "plateau_slope_definition": "Linear slope between SOC 0.20 and 0.80 from 25.0 °C OCV table",
        "plateau_slope_source": "deliverable/calibrations/ge105_v1.json:ocv_table['25.0']",
        "measured_hysteresis_mv": round(ge105_hyst_mv, 2),
        "hysteresis_definition": "Pseudo-OCV half-gap at 50% SOC between C/15 charge and discharge ramps",
        "hysteresis_source": "deliverable/calibrations/ge105_v1.json:m_table_v[4]",
    })

    # 3. FlexiPod (100 Ah)
    flexi_path = REPO_ROOT / "deliverable" / "calibrations" / "flexipod_100ah_v1.json"
    with open(flexi_path, "r", encoding="utf-8") as f:
        flexi_data = json.load(f)

    flexi_cap_ah = flexi_data["nominal_capacity_ah"]  # 95.1521 Ah (key: nominal_capacity_ah, line 4)
    flexi_r0_ohm = flexi_data["r0_table"]["25.0"]      # 0.000894 Ohm (key: r0_table['25.0'], line 26)
    flexi_ocv_80 = flexi_data["ocv_table"]["25.0"][9]  # 3.33525 V (key: ocv_table['25.0'], line 40)
    flexi_ocv_20 = flexi_data["ocv_table"]["25.0"][3]  # 3.25203 V (key: ocv_table['25.0'], line 34)
    flexi_slope = (flexi_ocv_80 - flexi_ocv_20) / (0.80 - 0.20)
    flexi_hyst_mv = flexi_data["m_table_v"][3] * 1000.0  # 12.01 mV (key: m_table_v[3], 25C, line 18)

    rows.append({
        "cell_id": "FlexiPod (100 Ah)",
        "description": "FlexiPod 100 Ah cell",
        "form_factor": "prismatic (general knowledge of the product; not stated in dataset files)",
        "chemistry": "LFP",
        "nominal_capacity_ah": 100.0,
        "measured_capacity_ah": round(flexi_cap_ah, 4),
        "capacity_source": "deliverable/calibrations/flexipod_100ah_v1.json:nominal_capacity_ah",
        "r0_mohm": round(flexi_r0_ohm * 1e3, 4),
        "r0_condition": "25.0 °C, SOC-averaged table value (not directly comparable to single-SOC pulses)",
        "r0_source": "deliverable/calibrations/flexipod_100ah_v1.json:r0_table['25.0']",
        "plateau_slope_v_per_unit_soc": round(flexi_slope, 4),
        "plateau_slope_mv_per_pp": round(flexi_slope * 10.0, 3),
        "plateau_slope_definition": "Linear slope between SOC 0.20 and 0.80 from 25.0 °C OCV table",
        "plateau_slope_source": "deliverable/calibrations/flexipod_100ah_v1.json:ocv_table['25.0']",
        "measured_hysteresis_mv": round(flexi_hyst_mv, 2),
        "hysteresis_definition": "Calibration table parameter m_table_v at 25 °C",
        "hysteresis_source": "deliverable/calibrations/flexipod_100ah_v1.json:m_table_v[3]",
    })

    # 4. TEMPEST 280 Ah
    tempest_cap_path = REPO_ROOT / "reports" / "validation" / "tempest_capacity_results.json"
    with open(tempest_cap_path, "r", encoding="utf-8") as f:
        t_cap_data = json.load(f)
    t_25_cap = [item for item in t_cap_data["temperature_results"] if item["chamber_temp_c"] == 25][0]

    tempest_ecm_path = REPO_ROOT / "reports" / "validation" / "tempest_ecm_results.json"
    with open(tempest_ecm_path, "r", encoding="utf-8") as f:
        t_ecm_data = json.load(f)
    t_25_r0_55 = [p for p in t_ecm_data["in_sample_pulse_parameters"] if p["temperature_c"] == 25 and p["soc_nominal"] == 0.55][0]["r0_ohm"]
    t_25_slope = t_ecm_data["plateau_slopes_by_temp"]["25"]["slope_v_per_unit_soc"]

    rows.append({
        "cell_id": "TEMPEST 280 Ah ('LIC')",
        "description": "280 Ah LFP prismatic cell (project TEMPEST 'LIC' cell)",
        "form_factor": "prismatic (per LIC_characterisation_readme.txt line 2)",
        "chemistry": "LFP",
        "nominal_capacity_ah": 280.0,
        "measured_capacity_ah": round(t_25_cap["discharge_ah"], 4),
        "capacity_source": "reports/validation/tempest_capacity_results.json:discharge_ah[T=25C]",
        "r0_mohm": round(t_25_r0_55 * 1e3, 4),
        "r0_condition": "25.0 °C, 55% SOC single-pulse fit (mean across 10 SOC points at 25 °C is 0.4183 mOhm; not directly comparable to SOC-averaged tables)",
        "r0_source": "reports/validation/tempest_ecm_results.json:in_sample_pulse_parameters[T=25,SOC=0.55]:r0_ohm",
        "plateau_slope_v_per_unit_soc": round(t_25_slope, 4),
        "plateau_slope_mv_per_pp": round(t_25_slope * 10.0, 3),
        "plateau_slope_definition": "Linear slope between SOC 0.25 (3.2553 V) and 0.75 (3.3246 V) from 25 °C HPPC relaxed OCV",
        "plateau_slope_source": "reports/validation/tempest_ecm_results.json:plateau_slopes_by_temp['25']",
        "measured_hysteresis_mv": None,
        "hysteresis_definition": "N/A (No continuous pseudo-OCV charge/discharge loop in dataset)",
        "hysteresis_source": "UNVERIFIED",
    })

    # Print summary
    print(f"{'Cell Identifier':<25} | {'Nom (Ah)':>10} | {'Meas (Ah)':>11} | {'R0 (mOhm)':>10} | {'Slope (mV/pp)':>13} | {'Hysteresis':<30}")
    print("-" * 115)
    for r in rows:
        nom_str = f"{r['nominal_capacity_ah']}" if isinstance(r['nominal_capacity_ah'], (int, float)) else "UNVERIFIED"
        hyst_str = f"{r['measured_hysteresis_mv']:.2f} mV" if r["measured_hysteresis_mv"] is not None else "N/A"
        print(f"{r['cell_id']:<25} | {nom_str:>10} | {r['measured_capacity_ah']:11.4f} | {r['r0_mohm']:10.4f} | {r['plateau_slope_mv_per_pp']:13.3f} | {hyst_str:<30}")

    output = {
        "disclaimer": "Values are listed as measured under the stated conditions; no inference about size dependence is possible from four cells. Asserting NO causes and NO scaling laws from four points.",
        "cells": rows,
    }

    out_file = REPO_ROOT / "reports" / "validation" / "tempest_cross_cell_comparison.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)
    print(f"\nSaved cross-cell comparison table to {out_file}")

    return output


if __name__ == "__main__":
    build_cross_cell_table()
