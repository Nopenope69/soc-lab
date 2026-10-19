"""Stage V0 Errata and Reconciliation Script.

Computes exact numbers for:
1. E0 S-F worst-case verification.
2. Stage 1 summary vs table numbers check.
3. Gamma sensitivity analysis for gamma in {1, 10, 50} on S-A and S-B.
4. Exact S-B convergence times (time to |err| <= 1.0 pp) for E2 tune_2.
5. Local minimum plateau slopes vs mean slope and voltage-implied SOC error floors.
"""

import sys
import pickle
from pathlib import Path
from dataclasses import replace
import numpy as np
import pandas as pd
import yaml

repo_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo_root / "src"))
sys.path.insert(0, str(repo_root))

from soc.estimators.e0_coulomb import E0CoulombCounting
from soc.estimators.e2_ekf_hysteresis import E2EKFHysteresis
from soc.estimators.base import ParamSet, Measurement
from scripts.gauntlet_scenarios import (
    prepare_scenario_data,
    init_estimator_state,
    run_stream_slice,
    evaluate_estimator_on_scenarios,
)

def run_v0():
    print("="*60)
    print("STAGE V0: RECONCILE AND ERRATA")
    print("="*60)

    # Load frozen v3 checkpoint and parameters
    ckpt_path = repo_root / "reports" / "gauntlet" / ".stage2_checkpoint.pkl"
    with open(ckpt_path, "rb") as f:
        ckpt = pickle.load(f)

    p_e0 = ckpt["best_by_estimator"]["E0"]["params"]
    p_e2 = ckpt["best_by_estimator"]["E2"]["params"]

    # -------------------------------------------------------------
    # 1. E0 S-F Worst-Case Analysis
    # -------------------------------------------------------------
    print("\n--- 1. E0 S-F Evaluation ---")
    e0_sf_by_t = {}
    for t in [20, 25, 30, 40, 50]:
        d = prepare_scenario_data(t, profile="DST", cell_id="A1-007")
        res = evaluate_estimator_on_scenarios(lambda p: E0CoulombCounting(p), p_e0, d)
        e0_sf_by_t[t] = res
        print(f"T={t:2d}C: S-F Mean RMSE = {res['sf_mean_rmse_pp']:.3f} pp, Worst Error = {res['sf_worst_err_pp']:.3f} pp")

    heldout_sf_worst_e0 = max(e0_sf_by_t[40]["sf_worst_err_pp"], e0_sf_by_t[50]["sf_worst_err_pp"])
    all_sf_worst_e0 = max(e0_sf_by_t[t]["sf_worst_err_pp"] for t in [20, 30, 40, 50])
    print(f"E0 Held-out (40, 50 C) S-F Worst Error: {heldout_sf_worst_e0:.3f} pp")
    print(f"E0 All Decision Temps S-F Worst Error: {all_sf_worst_e0:.3f} pp")

    # -------------------------------------------------------------
    # 2. Stage 1 Model Gate Check
    # -------------------------------------------------------------
    print("\n--- 2. Stage 1 Model Gate Table ---")
    csv_s1 = repo_root / "reports" / "gauntlet" / "stage1_model_gate.csv"
    df_s1 = pd.read_csv(csv_s1)
    df_r2 = df_s1[df_s1["rung"] == "Rung 2 (W-mid restricted)"]
    print(df_r2[["temp_nominal", "mid_bias_mv", "mid_rmse_mv", "gate_pass"]].to_string(index=False))

    # -------------------------------------------------------------
    # 3. Gamma Sensitivity Analysis (gamma in {1, 10, 50})
    # -------------------------------------------------------------
    print("\n--- 3. Gamma Sensitivity Analysis ---")
    gamma_results = []
    gammas = [1.0, 10.0, 50.0]
    temps = [20, 25, 30, 40, 50]

    for g in gammas:
        p_g = replace(p_e2, hysteresis_gamma=g)
        for t in temps:
            d = prepare_scenario_data(t, profile="DST", cell_id="A1-007")
            n = len(d.truth_soc)
            # S-A
            est_sa = E2EKFHysteresis(p_g)
            init_estimator_state(est_sa, d.truth_soc[0], 0.0, 0.0, 0.0)
            soc_sa = run_stream_slice(est_sa, d, 0, n)
            err_sa_pp = (soc_sa - d.truth_soc) * 100.0
            rmse_sa = float(np.sqrt(np.mean(err_sa_pp ** 2)))

            # S-B
            sb_target_socs = [0.80, 0.60, 0.40, 0.20]
            sb_offsets_pp = [-10.0, -5.0, +5.0, +10.0]
            sb_rmses = []
            for z_target in sb_target_socs:
                cross_idx = np.where(d.truth_soc <= z_target)[0]
                if len(cross_idx) == 0:
                    continue
                k0 = int(cross_idx[0])
                for off_pp in sb_offsets_pp:
                    off_frac = off_pp / 100.0
                    z_init = min(max(float(d.truth_soc[k0] + off_frac), 0.0), 1.0)
                    est_sb = E2EKFHysteresis(p_g)
                    init_estimator_state(
                        est_sb,
                        soc0=z_init,
                        i1=d.i1_truth[k0],
                        i2=d.i2_truth[k0],
                        h=d.h_truth[k0],
                    )
                    soc_sb = run_stream_slice(est_sb, d, k0, n)
                    truth_window = d.truth_soc[k0:]
                    err_sb_pp = (soc_sb - truth_window) * 100.0
                    sb_rmses.append(float(np.sqrt(np.mean(err_sb_pp ** 2))))

            mean_sb_rmse = float(np.mean(sb_rmses))
            gamma_results.append({
                "gamma": g,
                "temp_c": t,
                "is_suspect": (t == 25),
                "sa_rmse_pp": rmse_sa,
                "sb_mean_rmse_pp": mean_sb_rmse,
            })
            print(f"gamma={g:4.1f} | T={t:2d}C | S-A RMSE={rmse_sa:.3f} pp | S-B Mean RMSE={mean_sb_rmse:.3f} pp")

    df_gamma = pd.DataFrame(gamma_results)

    # -------------------------------------------------------------
    # 4. Convergence Time in S-B Cases
    # -------------------------------------------------------------
    print("\n--- 4. S-B Convergence Time Analysis (E2 tune_2) ---")
    conv_records = []
    for t in [20, 25, 30, 40, 50]:
        d = prepare_scenario_data(t, profile="DST", cell_id="A1-007")
        n = len(d.truth_soc)
        sb_target_socs = [0.80, 0.60, 0.40, 0.20]
        sb_offsets_pp = [-10.0, -5.0, +5.0, +10.0]

        for z_target in sb_target_socs:
            cross_idx = np.where(d.truth_soc <= z_target)[0]
            if len(cross_idx) == 0:
                continue
            k0 = int(cross_idx[0])
            for off_pp in sb_offsets_pp:
                off_frac = off_pp / 100.0
                z_init = min(max(float(d.truth_soc[k0] + off_frac), 0.0), 1.0)
                est_sb = E2EKFHysteresis(p_e2)
                init_estimator_state(
                    est_sb,
                    soc0=z_init,
                    i1=d.i1_truth[k0],
                    i2=d.i2_truth[k0],
                    h=d.h_truth[k0],
                )
                soc_sb = run_stream_slice(est_sb, d, k0, n)
                truth_window = d.truth_soc[k0:]
                time_window = d.time_s[k0:] - d.time_s[k0]
                err_sb_pp = np.abs((soc_sb - truth_window) * 100.0)

                # Time to reach and stay <= 1.0 pp
                below_1 = err_sb_pp <= 1.0
                # Find first time below 1.0 pp
                idx_below_1 = np.where(below_1)[0]
                if len(idx_below_1) > 0:
                    t_first_1 = float(time_window[idx_below_1[0]])
                else:
                    t_first_1 = np.nan

                # Time to reach <= 2.0 pp
                idx_below_2 = np.where(err_sb_pp <= 2.0)[0]
                if len(idx_below_2) > 0:
                    t_first_2 = float(time_window[idx_below_2[0]])
                else:
                    t_first_2 = np.nan

                conv_records.append({
                    "temp_c": t,
                    "target_soc": z_target,
                    "offset_pp": off_pp,
                    "duration_s": float(time_window[-1]),
                    "final_err_pp": float(err_sb_pp[-1]),
                    "max_err_pp": float(np.max(err_sb_pp)),
                    "t_reach_2pp_s": t_first_2,
                    "t_reach_1pp_s": t_first_1,
                })

    df_conv = pd.DataFrame(conv_records)
    large_offsets = df_conv[df_conv["offset_pp"].abs() == 10.0]
    print(f"Convergence for +/-10 pp offsets (all cases):")
    print(f"  Reached <= 2.0 pp within 600s: {(large_offsets['t_reach_2pp_s'] <= 600.0).sum()}/{len(large_offsets)} cases")
    print(f"  Reached <= 1.0 pp within 600s: {(large_offsets['t_reach_1pp_s'] <= 600.0).sum()}/{len(large_offsets)} cases")
    print(f"  Median time to <= 2.0 pp: {large_offsets['t_reach_2pp_s'].median():.1f} s")
    print(f"  Median time to <= 1.0 pp: {large_offsets['t_reach_1pp_s'].median():.1f} s")

    # -------------------------------------------------------------
    # 5. Local Plateau Slope & Voltage-Implied Error Floors
    # -------------------------------------------------------------
    print("\n--- 5. Local Plateau Slope vs Mean Slope ---")
    d9_csv = repo_root / "reports" / "diagnostics" / "d9_plateau_summary.csv"
    df_d9 = pd.read_csv(d9_csv)

    slope_records = []
    for t in [20, 25, 30, 40, 50]:
        d = prepare_scenario_data(t, profile="DST", cell_id="A1-007")
        # Compute mean slope across W-mid (10% to 90% SOC)
        soc_pts = np.linspace(0.10, 0.90, 81)
        from scripts.gauntlet_scenarios import SOC_GRID
        v_pts = np.interp(soc_pts, SOC_GRID, d.ocv_mono)
        mean_slope_mv_pp = float((v_pts[-1] - v_pts[0]) * 1000.0 / 80.0) # mV/pp

        d9_row = df_d9[df_d9["Temp (C)"] == t]
        min_slope_mv_pp = float(d9_row["Min Slope (mV/pp)"].iloc[0])

        # Get W-mid bias from Stage 1 Rung 2
        r2_row = df_r2[df_r2["temp_nominal"] == t]
        wmid_bias_mv = float(r2_row["mid_bias_mv"].iloc[0])

        # Implied SOC error for W-mid bias
        err_mean_slope_pp = abs(wmid_bias_mv) / mean_slope_mv_pp
        err_min_slope_pp = abs(wmid_bias_mv) / min_slope_mv_pp

        # Implied SOC error for 1.0 mV and 5.0 mV voltage errors
        implied_1mv_mean = 1.0 / mean_slope_mv_pp
        implied_1mv_min = 1.0 / min_slope_mv_pp
        implied_5mv_mean = 5.0 / mean_slope_mv_pp
        implied_5mv_min = 5.0 / min_slope_mv_pp

        slope_records.append({
            "temp_c": t,
            "mean_slope_mv_pp": mean_slope_mv_pp,
            "min_slope_mv_pp": min_slope_mv_pp,
            "wmid_bias_mv": wmid_bias_mv,
            "soc_err_at_mean_slope_pp": err_mean_slope_pp,
            "soc_err_at_min_slope_pp": err_min_slope_pp,
            "implied_1mv_floor_mean_pp": implied_1mv_mean,
            "implied_1mv_floor_min_pp": implied_1mv_min,
            "implied_5mv_floor_mean_pp": implied_5mv_mean,
            "implied_5mv_floor_min_pp": implied_5mv_min,
        })
        print(f"T={t:2d}C | Mean Slope={mean_slope_mv_pp:.3f} mV/pp | Min Slope={min_slope_mv_pp:.3f} mV/pp | W-mid Bias={wmid_bias_mv:+.2f} mV | Implied Err @ Mean={err_mean_slope_pp:.2f} pp | Implied Err @ Min={err_min_slope_pp:.2f} pp")

    df_slopes = pd.DataFrame(slope_records)

    # Save summary data to CSVs
    df_gamma.to_csv(repo_root / "reports" / "gauntlet_v2" / "errata_gamma_sensitivity.csv", index=False)
    df_conv.to_csv(repo_root / "reports" / "gauntlet_v2" / "errata_convergence_sb.csv", index=False)
    df_slopes.to_csv(repo_root / "reports" / "gauntlet_v2" / "errata_plateau_slopes.csv", index=False)
    print("\nSaved intermediate errata CSVs to reports/gauntlet_v2/")

if __name__ == "__main__":
    run_v0()
