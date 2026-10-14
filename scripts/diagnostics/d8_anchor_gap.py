"""Diagnostic D8: Anchor gap between OCV test and dynamic profiles.

Examines the CV charge taper in Step 3 of the A1-007 OCV test:
- Dynamic profiles start after CV taper cut off at 55 mA (0.055 A).
- OCV test CV taper continued to 10 mA (0.010 A) before the C/20 discharge.
- Integrates current in Step 3 between 0.055 A and 0.010 A.
- Divides by C/20 capacity to find the delta SOC gap (pp) per temperature.
- Evaluates whether truth SOC can resolve a 2 pp accuracy bar.
"""

from pathlib import Path
import sys
import numpy as np
import pandas as pd

repo_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(repo_root))

from soc.data.calce_loader import load_ocv_file, get_raw_dir, find_channel_sheet
from scripts.evaluate_calce import get_file_paths

GATING_TEMPS = [20, 25, 30, 40, 50]

def run_d8():
    print("=== D8. Anchor Gap Between OCV Test and Dynamic Profiles ===\n")
    raw_dir = get_raw_dir(repo_root)
    reports_dir = repo_root / "reports" / "diagnostics"
    reports_dir.mkdir(parents=True, exist_ok=True)

    results = []

    for temp in GATING_TEMPS:
        ocv_p, _ = get_file_paths(raw_dir, temp, "A1-007")
        ocv_data = load_ocv_file(ocv_p, float(temp), "A1-007")
        c20_cap = ocv_data.c20_capacity_ah

        # Read raw excel Step 3
        df_raw = pd.read_excel(ocv_p, sheet_name=find_channel_sheet(pd.ExcelFile(ocv_p).sheet_names))
        # Step 3 is CV charge
        # In raw cycler data, charge current is POSITIVE (+I in raw Arbin files, discharge is -I)
        step3 = df_raw[df_raw["Step_Index"] == 3].copy()
        
        # Check current values
        i_step3 = step3["Current(A)"].values
        t_step3 = step3["Test_Time(s)"].values
        v_step3 = step3["Voltage(V)"].values

        # In Arbin, charge current is positive. When tapering down to 0.010 A:
        # Find points where current <= 0.055 A
        mask_taper = (i_step3 <= 0.055) & (i_step3 >= 0.009)
        if np.any(mask_taper):
            t_sub = t_step3[mask_taper]
            i_sub = i_step3[mask_taper]
            v_sub = v_step3[mask_taper]
            
            # Trapezoidal integration of capacity: sum 0.5 * (i1 + i2) * dt / 3600
            dt = np.diff(t_sub)
            i_mid = 0.5 * (i_sub[:-1] + i_sub[1:])
            delta_q_ah = float(np.sum(i_mid * dt) / 3600.0)
            taper_duration_s = float(t_sub[-1] - t_sub[0])
            start_v = float(v_sub[0])
            end_v = float(v_sub[-1])
        else:
            delta_q_ah = 0.0
            taper_duration_s = 0.0
            start_v = 0.0
            end_v = 0.0

        gap_soc_pp = (delta_q_ah / c20_cap) * 100.0

        results.append({
            "Temp (C)": temp,
            "C/20 Cap (Ah)": c20_cap,
            "Taper Q (55->10 mA) (Ah)": delta_q_ah,
            "Taper Time (s)": taper_duration_s,
            "Delta SOC Gap (pp)": gap_soc_pp,
            "Start V": start_v,
            "End V": end_v,
        })

    df = pd.DataFrame(results)
    print(df.to_string(index=False))

    csv_out = reports_dir / "d8_anchor_gap.csv"
    df.to_csv(csv_out, index=False)
    print(f"\nSaved anchor gap table to: {csv_out}")

    mean_gap = df["Delta SOC Gap (pp)"].mean()
    max_gap = df["Delta SOC Gap (pp)"].max()
    print(f"\nMean SOC anchor gap across gating temperatures: {mean_gap:.2f} pp (Max: {max_gap:.2f} pp)")
    print(f"Can truth SOC resolve a 2 pp accuracy bar? "
          f"{'NO - systematic initialization offset of ~' + f'{mean_gap:.2f} pp consumes or exceeds the entire 2 pp budget!' if mean_gap > 1.0 else 'YES'}")

if __name__ == "__main__":
    run_d8()
