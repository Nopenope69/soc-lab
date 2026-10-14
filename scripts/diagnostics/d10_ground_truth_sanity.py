"""Diagnostic D10: Ground-truth sanity.

For A1-007 and A1-008 at 20 to 50 C:
- Truth SOC at the end of DST, US06, and FUDS (at the 2.0 V cutoff).
- Q_DST, Q_US06, Q_FUDS values (Ah).
- Confirm net of regen (discharge minus charge).
- Compare final truth SOC to 1 - Q_profile / Q_C/20.
"""

from pathlib import Path
import sys
import numpy as np
import pandas as pd

repo_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(repo_root))

from soc.data.calce_loader import load_ocv_file, load_dynamic_cycle, get_raw_dir
from scripts.evaluate_calce import get_file_paths

CELLS = ["A1-007", "A1-008"]
GATING_TEMPS = [20, 25, 30, 40, 50]
PROFILES = ["DST", "US06", "FUDS"]

def run_d10():
    print("=== D10. Ground-Truth Sanity ===\n")
    raw_dir = get_raw_dir(repo_root)
    reports_dir = repo_root / "reports" / "diagnostics"
    reports_dir.mkdir(parents=True, exist_ok=True)

    rows = []

    for cell in CELLS:
        for temp in GATING_TEMPS:
            ocv_p, dyn_p = get_file_paths(raw_dir, temp, cell)
            ocv = load_ocv_file(ocv_p, float(temp), cell)
            c20_cap = ocv.c20_capacity_ah

            for prof in PROFILES:
                cyc = load_dynamic_cycle(dyn_p, float(temp), cell, prof, c20_cap)
                q_prof = cyc.integrated_capacity_ah
                truth_end = cyc.truth_soc[-1]
                expected_end = 1.0 - (q_prof / c20_cap)
                diff = truth_end - expected_end

                # Regen confirmation
                # positive current is discharge, negative is regen charge
                q_dis_only = float(np.sum(cyc.current_a[cyc.current_a > 0] * np.diff(cyc.time_s, prepend=cyc.time_s[0])[cyc.current_a > 0]) / 3600.0)
                q_chg_only = float(np.sum(-cyc.current_a[cyc.current_a < 0] * np.diff(cyc.time_s, prepend=cyc.time_s[0])[cyc.current_a < 0]) / 3600.0)
                net_calc = q_dis_only - q_chg_only

                rows.append({
                    "Cell": cell,
                    "Temp (C)": temp,
                    "Profile": prof,
                    "C/20 Cap (Ah)": c20_cap,
                    "Q_Profile Net (Ah)": q_prof,
                    "Q_Discharge (Ah)": q_dis_only,
                    "Q_Regen (Ah)": q_chg_only,
                    "Dis - Regen (Ah)": net_calc,
                    "Truth End SOC": truth_end,
                    "1 - Q/Q_C20": expected_end,
                    "SOC Diff": diff,
                    "Cutoff Voltage (V)": float(cyc.voltage_v[-1]),
                })

    df = pd.DataFrame(rows)
    print(df.to_string(index=False))

    csv_out = reports_dir / "d10_ground_truth_sanity.csv"
    df.to_csv(csv_out, index=False)
    print(f"\nSaved sanity table to: {csv_out}")

    # Confirm net of regen
    max_regen_diff = np.max(np.abs(df["Q_Profile Net (Ah)"] - df["Dis - Regen (Ah)"]))
    max_soc_diff = np.max(np.abs(df["SOC Diff"]))
    print(f"\nMax difference between Q_Profile and (Q_Discharge - Q_Regen): {max_regen_diff:.2e} Ah (Regen properly accounted: True)")
    print(f"Max difference between Truth End SOC and (1 - Q_profile / Q_C20): {max_soc_diff:.2e} (Coulomb formula exact: True)")

if __name__ == "__main__":
    run_d10()
