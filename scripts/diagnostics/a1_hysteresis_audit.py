"""Script for Task A1: Hysteresis amplitude audit.

Audits C/20 charge and discharge branches for A1-007 and A1-008 across gating
temperatures (20, 25, 30, 40, 50 C).
Calculates raw and corrected voltage gap vs SOC, tabulates at key SOC points,
computes plateau median, and plots curves.
"""

from pathlib import Path
import sys
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

repo_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(repo_root))

from soc.data.calce_loader import get_raw_dir, load_ocv_file
from scripts.evaluate_calce import get_file_paths

GATING_TEMPS = [20, 25, 30, 40, 50]
KEY_SOCS = [0.2, 0.4, 0.5, 0.6, 0.8]

# Old R0 values from calce_a123.yaml and calce_a123_a1008.yaml
OLD_R0 = {
    "A1-007": {
        20: 0.16061,
        25: 0.16024,
        30: 0.15571,
        40: 0.15463,
        50: 0.15454,
    },
    "A1-008": {
        20: 0.17692,
        25: 0.19880,
        30: 0.17852,
        40: 0.17935,
        50: 0.22458,
    }
}

# Old R1 and R2 values from the yaml profiles for DC total resistance comparison
OLD_R_TOTAL = {
    "A1-007": {
        20: 0.16061 + 0.01658 + 0.01524,
        25: 0.16024 + 0.01984 + 0.01999,
        30: 0.15571 + 0.01477 + 0.01777,
        40: 0.15463 + 0.00937 + 0.01445,
        50: 0.15454 + 0.01192 + 0.01931,
    },
    "A1-008": {
        20: 0.17692 + 0.02805 + 0.01825,
        25: 0.19880 + 0.02527 + 0.01878,
        30: 0.17852 + 0.01718 + 0.01642,
        40: 0.17935 + 0.01301 + 0.01819,
        50: 0.22458 + 0.01300 + 0.02047,
    }
}

def run_a1_audit():
    raw_dir = get_raw_dir(repo_root)
    out_dir = repo_root / "reports" / "b2"
    out_dir.mkdir(parents=True, exist_ok=True)

    soc_dense = np.linspace(0.01, 0.99, 1000)
    plateau_mask = (soc_dense >= 0.2) & (soc_dense <= 0.8)

    all_rows = []

    for cell in ["A1-007", "A1-008"]:
        fig, ax = plt.subplots(figsize=(9, 6))

        for t in GATING_TEMPS:
            ocv_p, _ = get_file_paths(raw_dir, t, cell)
            ocv = load_ocv_file(ocv_p, float(t), cell)

            dis_soc, dis_v = ocv.discharge_soc, ocv.discharge_v
            chg_soc, chg_v = ocv.charge_soc, ocv.charge_v

            # Sort monotonically
            idx_d = np.argsort(dis_soc)
            idx_c = np.argsort(chg_soc)
            d_soc, d_v = dis_soc[idx_d], dis_v[idx_d]
            c_soc, c_v = chg_soc[idx_c], chg_v[idx_c]

            v_chg_interp = np.interp(soc_dense, c_soc, c_v)
            v_dis_interp = np.interp(soc_dense, d_soc, d_v)
            raw_gap = v_chg_interp - v_dis_interp  # Full gap in Volts

            # Expected ohmic drop across full gap at 55 mA
            r0 = OLD_R0[cell][t]
            i_c20 = 0.055  # 55 mA
            ohmic_drop_full = 2.0 * i_c20 * r0  # Full gap drop = I_chg*R0 - (-I_dis*R0) = 2*I*R0
            corrected_gap_r0 = raw_gap - ohmic_drop_full

            r_tot = OLD_R_TOTAL[cell][t]
            tot_drop_full = 2.0 * i_c20 * r_tot
            corrected_gap_rtot = raw_gap - tot_drop_full

            # Plot raw gap and corrected gap
            ax.plot(soc_dense, raw_gap * 1000.0, label=f"{t}°C Raw (R0={r0:.3f}Ω)")
            ax.plot(soc_dense, corrected_gap_r0 * 1000.0, linestyle="--", label=f"{t}°C Corr (55mA R0)")

            # Extract at key SOCs
            v_chg_keys = np.interp(KEY_SOCS, c_soc, c_v)
            v_dis_keys = np.interp(KEY_SOCS, d_soc, d_v)
            raw_gap_keys = (v_chg_keys - v_dis_keys) * 1000.0  # mV
            corr_gap_r0_keys = raw_gap_keys - (ohmic_drop_full * 1000.0)

            plat_med_raw = float(np.median(raw_gap[plateau_mask])) * 1000.0
            plat_med_corr_r0 = float(np.median(corrected_gap_r0[plateau_mask])) * 1000.0
            plat_med_half_corr_r0 = plat_med_corr_r0 / 2.0  # Proposed M in mV

            plat_med_corr_rtot = float(np.median(corrected_gap_rtot[plateau_mask])) * 1000.0
            plat_med_half_corr_rtot = plat_med_corr_rtot / 2.0

            row = {
                "cell": cell,
                "temp_c": t,
                "r0_ohm": r0,
                "ohmic_drop_full_mv": ohmic_drop_full * 1000.0,
                "raw_gap_0_2_mv": raw_gap_keys[0],
                "raw_gap_0_4_mv": raw_gap_keys[1],
                "raw_gap_0_5_mv": raw_gap_keys[2],
                "raw_gap_0_6_mv": raw_gap_keys[3],
                "raw_gap_0_8_mv": raw_gap_keys[4],
                "raw_plateau_median_mv": plat_med_raw,
                "raw_half_gap_median_mv": plat_med_raw / 2.0,
                "corr_gap_0_2_mv": corr_gap_r0_keys[0],
                "corr_gap_0_4_mv": corr_gap_r0_keys[1],
                "corr_gap_0_5_mv": corr_gap_r0_keys[2],
                "corr_gap_0_6_mv": corr_gap_r0_keys[3],
                "corr_gap_0_8_mv": corr_gap_r0_keys[4],
                "corr_plateau_median_mv": plat_med_corr_r0,
                "proposed_M_mv": plat_med_half_corr_r0,
                "proposed_M_rtot_mv": plat_med_half_corr_rtot,
            }
            all_rows.append(row)

        ax.set_title(f"Cell {cell}: C/20 Charge-Discharge Voltage Gap vs SOC")
        ax.set_xlabel("SOC")
        ax.set_ylabel("Voltage Gap (mV)")
        ax.set_xlim(0.0, 1.0)
        ax.set_ylim(0.0, 150.0)
        ax.grid(True, alpha=0.3)
        ax.legend(loc="upper right", fontsize=8)
        fig.tight_layout()
        plot_path = out_dir / f"a1_voltage_gap_vs_soc_{cell.lower().replace('-', '')}.png"
        fig.savefig(plot_path, dpi=150)
        plt.close(fig)
        print(f"Saved plot: {plot_path}")

    df_res = pd.DataFrame(all_rows)
    csv_path = out_dir / "a1_hysteresis_audit.csv"
    df_res.to_csv(csv_path, index=False)
    print(f"Saved audit CSV: {csv_path}")

    print("\n=== Summary Table: Raw and Corrected Gaps (mV) ===")
    cols_to_print = [
        "cell", "temp_c", "r0_ohm", "ohmic_drop_full_mv",
        "raw_plateau_median_mv", "raw_half_gap_median_mv",
        "corr_plateau_median_mv", "proposed_M_mv", "proposed_M_rtot_mv"
    ]
    print(df_res[cols_to_print].to_string(index=False))

    print("\n=== Key SOC Points Raw Gap (mV) ===")
    raw_cols = ["cell", "temp_c", "raw_gap_0_2_mv", "raw_gap_0_4_mv", "raw_gap_0_5_mv", "raw_gap_0_6_mv", "raw_gap_0_8_mv"]
    print(df_res[raw_cols].to_string(index=False))

    print("\n=== Key SOC Points Corrected Gap (mV) (using 55 mA * R0) ===")
    corr_cols = ["cell", "temp_c", "corr_gap_0_2_mv", "corr_gap_0_4_mv", "corr_gap_0_5_mv", "corr_gap_0_6_mv", "corr_gap_0_8_mv"]
    print(df_res[corr_cols].to_string(index=False))

if __name__ == "__main__":
    run_a1_audit()
