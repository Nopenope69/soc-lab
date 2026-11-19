#!/usr/bin/env python3
"""TEMPEST 280 Ah: Comparison of Identified Parameters with Dataset LIC Analysis Outputs.

Compares:
1. Capacity vs. Temperature:
   - File compared: reports/validation/tempest_capacity_results.json vs. $SOC_DATA_DIR/tempest_280ah/LIC_capacity_analysis.csv
   - Units: Ah vs. Ah (no unit conversion).
2. Ohmic Resistance (R0) vs. SOC and Temperature:
   - File compared: reports/validation/tempest_ecm_results.json vs. $SOC_DATA_DIR/tempest_280ah/LIC_hppc_analysis.csv
   - Units: Ohm vs. Ohm (1 mOhm = 1e-3 Ohm, 1 uOhm = 1e-6 Ohm).
3. Relaxed Open-Circuit Voltage (OCV) vs. SOC and Temperature:
   - File compared: reports/validation/tempest_ecm_results.json vs. $SOC_DATA_DIR/tempest_280ah/LIC_entropy_analysis.csv
   - Units: V vs. V (no unit conversion).

Usage:
    .venv/bin/python3 scripts/validation/tempest_lic_comparison.py
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
    load_tempest_lic_capacity,
    load_tempest_lic_entropy,
    load_tempest_lic_hppc,
)


def run_lic_comparison() -> Dict[str, Any]:
    print("=" * 80)
    print("TEMPEST 280 Ah: PARAMETER RECONCILIATION AGAINST DATASET LIC_* FILES")
    print("=" * 80)

    # 1. Capacity Comparison
    cap_res_file = REPO_ROOT / "reports" / "validation" / "tempest_capacity_results.json"
    with open(cap_res_file, "r", encoding="utf-8") as f:
        cap_results = json.load(f)

    lic_cap_df = load_tempest_lic_capacity()
    cap_comparison_rows: List[Dict[str, Any]] = []

    print("\n--- 1. Discharge Capacity vs. Temperature Comparison ---")
    print(f"Files compared: reports/validation/tempest_capacity_results.json vs. LIC_capacity_analysis.csv")
    print(f"Unit conversion: None (both in Ampere-hours, Ah)\n")
    print(f"{'Chamber T (°C)':>14} | {'Our Discharge Ah':>18} | {'LIC Reference Ah':>18} | {'Discrepancy (Ah)':>18} | {'Diff (%)':>10}")
    print("-" * 88)

    for item in cap_results["temperature_results"]:
        t = item["chamber_temp_c"]
        our_ah = item["discharge_ah"]
        lic_ah = float(lic_cap_df[lic_cap_df["Temperature_C"] == t]["Capacity_Ah"].iloc[0])
        diff_ah = our_ah - lic_ah
        diff_pct = (diff_ah / lic_ah) * 100.0

        row = {
            "temperature_c": t,
            "our_discharge_ah": round(our_ah, 7),
            "lic_reference_ah": round(lic_ah, 7),
            "discrepancy_ah": round(diff_ah, 8),
            "discrepancy_pct": round(diff_pct, 6),
        }
        cap_comparison_rows.append(row)
        print(f"{t:14d} | {our_ah:18.7f} | {lic_ah:18.7f} | {diff_ah:+18.2e} | {diff_pct:+10.6f}%")

    # 2. Ohmic Resistance (R0) Comparison
    ecm_res_file = REPO_ROOT / "reports" / "validation" / "tempest_ecm_results.json"
    with open(ecm_res_file, "r", encoding="utf-8") as f:
        ecm_results = json.load(f)

    lic_hppc_df = load_tempest_lic_hppc()
    our_params_df = pd.DataFrame(ecm_results["in_sample_pulse_parameters"])

    merged_r0 = pd.merge(
        our_params_df,
        lic_hppc_df,
        left_on=["temperature_c", "soc_nominal"],
        right_on=["Temperature_C", "SoC"],
    )

    merged_r0["r0_diff_ohm"] = merged_r0["r0_ohm"] - merged_r0["R0_Ohm"]
    merged_r0["r0_diff_uohm"] = merged_r0["r0_diff_ohm"] * 1e6
    merged_r0["r0_diff_pct"] = (merged_r0["r0_diff_ohm"] / merged_r0["R0_Ohm"]) * 100.0

    print("\n--- 2. Ohmic Resistance (R0) vs. Temperature and SOC Comparison ---")
    print(f"Files compared: reports/validation/tempest_ecm_results.json vs. LIC_hppc_analysis.csv")
    print(f"Unit conversion: 1 mOhm = 1e-3 Ohm, 1 uOhm = 1e-6 Ohm\n")

    r0_comparison_rows: List[Dict[str, Any]] = []
    for t in VALID_TEMPERATURES:
        print(f"Temperature: {t} °C")
        print(f"{'SOC':>6} | {'Our R0 (mOhm)':>14} | {'LIC R0 (mOhm)':>14} | {'Diff (uOhm)':>14} | {'Diff (%)':>10}")
        print("-" * 66)
        sub = merged_r0[merged_r0["temperature_c"] == t]
        for _, r in sub.iterrows():
            row = {
                "temperature_c": int(r["temperature_c"]),
                "soc_nominal": float(r["soc_nominal"]),
                "our_r0_ohm": round(float(r["r0_ohm"]), 8),
                "lic_r0_ohm": round(float(r["R0_Ohm"]), 8),
                "diff_uohm": round(float(r["r0_diff_uohm"]), 3),
                "diff_pct": round(float(r["r0_diff_pct"]), 3),
            }
            r0_comparison_rows.append(row)
            print(f"{r['soc_nominal']:6.2f} | {r['r0_ohm']*1e3:14.4f} | {r['R0_Ohm']*1e3:14.4f} | {r['r0_diff_uohm']:+14.3f} | {r['r0_diff_pct']:+10.3f}%")
        print()

    mean_r0_uohm = float(np.mean(np.abs(merged_r0["r0_diff_uohm"])))
    max_r0_uohm = float(np.max(np.abs(merged_r0["r0_diff_uohm"])))
    mean_r0_pct = float(np.mean(np.abs(merged_r0["r0_diff_pct"])))
    print(f"Overall R0 Comparison Summary across 50 Points:")
    print(f"  - Mean Absolute Discrepancy: {mean_r0_uohm:.3f} uOhm ({mean_r0_pct:.2f}%)")
    print(f"  - Max Absolute Discrepancy:  {max_r0_uohm:.3f} uOhm")

    # 3. OCV vs. LIC Entropy Analysis Comparison
    lic_entropy_df = load_tempest_lic_entropy()
    entropy_comparison_rows: List[Dict[str, Any]] = []

    print("\n--- 3. Relaxed OCV Comparison Against LIC_entropy_analysis.csv ---")
    print(f"Files compared: reports/validation/tempest_ecm_results.json vs. LIC_entropy_analysis.csv")
    print(f"Unit conversion: None (both in Volts, V)\n")
    print(f"{'SOC':>6} | {'Chamber T (°C)':>14} | {'Our OCV (V)':>14} | {'LIC Entropy OCV (V)':>20} | {'Diff (mV)':>12}")
    print("-" * 74)

    # In LIC_entropy_analysis.csv, columns are Voltage_at_15C_V, Voltage_at_25C_V, Voltage_at_35C_V
    col_map = {15: "Voltage_at_15C_V", 25: "Voltage_at_25C_V", 35: "Voltage_at_35C_V"}
    diffs_ocv_mv: List[float] = []

    for _, erow in lic_entropy_df.iterrows():
        soc_val = float(erow["SoC"])
        # Find matching SOC in our ecm results (nearest)
        for t, col_name in col_map.items():
            lic_ocv = float(erow[col_name])
            sub = our_params_df[(our_params_df["temperature_c"] == t) & (np.isclose(our_params_df["soc_nominal"], soc_val, atol=0.06))]
            if len(sub) > 0:
                our_ocv = float(sub.iloc[0]["ocv_v"])
                diff_mv = (our_ocv - lic_ocv) * 1000.0
                diffs_ocv_mv.append(abs(diff_mv))
                row = {
                    "soc": soc_val,
                    "temperature_c": t,
                    "our_ocv_v": round(our_ocv, 4),
                    "lic_ocv_v": round(lic_ocv, 4),
                    "diff_mv": round(diff_mv, 3),
                }
                entropy_comparison_rows.append(row)
                print(f"{soc_val:6.2f} | {t:14d} | {our_ocv:14.4f} | {lic_ocv:20.4f} | {diff_mv:+12.2f}")

    mean_ocv_diff_mv = float(np.mean(diffs_ocv_mv)) if diffs_ocv_mv else 0.0

    output = {
        "dataset_id": "tempest_zenodo",
        "capacity_comparison": {
            "source_files": [
                "reports/validation/tempest_capacity_results.json",
                "$SOC_DATA_DIR/tempest_280ah/LIC_capacity_analysis.csv",
            ],
            "units": "Ah (no conversion)",
            "rows": cap_comparison_rows,
        },
        "r0_comparison": {
            "source_files": [
                "reports/validation/tempest_ecm_results.json",
                "$SOC_DATA_DIR/tempest_280ah/LIC_hppc_analysis.csv",
            ],
            "units": "Ohm (1 mOhm = 1e-3 Ohm, 1 uOhm = 1e-6 Ohm)",
            "mean_abs_diff_uohm": round(mean_r0_uohm, 3),
            "max_abs_diff_uohm": round(max_r0_uohm, 3),
            "mean_abs_diff_pct": round(mean_r0_pct, 3),
            "rows": r0_comparison_rows,
        },
        "ocv_entropy_comparison": {
            "source_files": [
                "reports/validation/tempest_ecm_results.json",
                "$SOC_DATA_DIR/tempest_280ah/LIC_entropy_analysis.csv",
            ],
            "units": "V (no conversion)",
            "mean_abs_diff_mv": round(mean_ocv_diff_mv, 3),
            "rows": entropy_comparison_rows,
        },
    }

    out_file = REPO_ROOT / "reports" / "validation" / "tempest_lic_comparison.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)
    print(f"\nSaved LIC parameter comparison to {out_file}")

    return output


if __name__ == "__main__":
    run_lic_comparison()
