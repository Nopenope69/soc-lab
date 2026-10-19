"""Compute comprehensive performance metrics for Gauntlet FINAL.md report."""
import pickle
from pathlib import Path
import sys
import numpy as np
import pandas as pd

repo_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo_root))

from soc.estimators.e2_ekf_hysteresis import E2EKFHysteresis
from soc.estimators.base import Measurement, ParamSet
from scripts.gauntlet_scenarios import (
    prepare_scenario_data,
    init_estimator_state,
    invert_ocv_table,
    run_stream_slice,
)

# Load frozen winner E7 (E2 tune_2)
with open(repo_root / "reports" / "gauntlet" / ".stage2_checkpoint.pkl", "rb") as f:
    cp = pickle.load(f)
p_e7 = cp["best_by_estimator"]["E2"]["params"]

def compute_metrics(err_array: np.ndarray):
    bias = float(np.mean(err_array))
    rmse = float(np.sqrt(np.mean(err_array ** 2)))
    max_err = float(np.max(np.abs(err_array)))
    p95 = float(np.percentile(np.abs(err_array), 95))
    return bias, rmse, max_err, p95

def evaluate_cell_profile(cell_id: str, profile: str = "DST"):
    records = []
    temps = [20, 25, 30, 40, 50]
    for t in temps:
        d = prepare_scenario_data(t, profile=profile, cell_id=cell_id)
        n = len(d.truth_soc)
        
        # --- S-A ---
        est_sa = E2EKFHysteresis(p_e7)
        init_estimator_state(est_sa, d.truth_soc[0], 0.0, 0.0, 0.0)
        soc_sa = run_stream_slice(est_sa, d, 0, n)
        err_sa = (soc_sa - d.truth_soc) * 100.0
        b_sa, r_sa, m_sa, p_sa = compute_metrics(err_sa)
        records.append({"cell": cell_id, "temp_c": t, "scenario": "S-A", "bias_pp": b_sa, "rmse_pp": r_sa, "max_err_pp": m_sa, "p95_pp": p_sa})
        
        # --- S-B ---
        sb_errs = []
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
                est_sb = E2EKFHysteresis(p_e7)
                init_estimator_state(est_sb, soc0=z_init, i1=d.i1_truth[k0], i2=d.i2_truth[k0], h=d.h_truth[k0])
                soc_sb = run_stream_slice(est_sb, d, k0, n)
                err_sb = (soc_sb - d.truth_soc[k0:]) * 100.0
                sb_errs.append(err_sb)
        all_sb_err = np.concatenate(sb_errs)
        b_sb, r_sb, m_sb, p_sb = compute_metrics(all_sb_err)
        records.append({"cell": cell_id, "temp_c": t, "scenario": "S-B", "bias_pp": b_sb, "rmse_pp": r_sb, "max_err_pp": m_sb, "p95_pp": p_sb})
        
        # --- S-C ---
        sc_errs = []
        sc_windows = [(0.80, 0.30), (0.90, 0.40)]
        for z_start, z_end in sc_windows:
            idx_start = np.where(d.truth_soc <= z_start)[0]
            idx_end = np.where(d.truth_soc <= z_end)[0]
            if len(idx_start) == 0 or len(idx_end) == 0:
                continue
            k_s = int(idx_start[0])
            k_e = int(idx_end[0])
            if k_e <= k_s:
                continue
            est_sc = E2EKFHysteresis(p_e7)
            init_estimator_state(est_sc, soc0=d.truth_soc[k_s], i1=d.i1_truth[k_s], i2=d.i2_truth[k_s], h=d.h_truth[k_s])
            soc_sc = run_stream_slice(est_sc, d, k_s, k_e)
            err_sc = (soc_sc - d.truth_soc[k_s:k_e]) * 100.0
            sc_errs.append(err_sc)
        all_sc_err = np.concatenate(sc_errs)
        b_sc, r_sc, m_sc, p_sc = compute_metrics(all_sc_err)
        records.append({"cell": cell_id, "temp_c": t, "scenario": "S-C", "bias_pp": b_sc, "rmse_pp": r_sc, "max_err_pp": m_sc, "p95_pp": p_sc})
        
        # --- S-D ---
        v_rest = float(d.voltage_v[0])
        z_inv = invert_ocv_table(v_rest, d.ocv_mono)
        est_sd = E2EKFHysteresis(p_e7)
        init_estimator_state(est_sd, z_inv, 0.0, 0.0, 0.0)
        soc_sd = run_stream_slice(est_sd, d, 0, n)
        err_sd = (soc_sd - d.truth_soc) * 100.0
        b_sd, r_sd, m_sd, p_sd = compute_metrics(err_sd)
        records.append({"cell": cell_id, "temp_c": t, "scenario": "S-D", "bias_pp": b_sd, "rmse_pp": r_sd, "max_err_pp": m_sd, "p95_pp": p_sd})
        
        # --- S-F ---
        sf_errs = []
        for i_b in [-0.050, -0.010, +0.010, +0.050]:
            est_sf = E2EKFHysteresis(p_e7)
            init_estimator_state(est_sf, d.truth_soc[0], 0.0, 0.0, 0.0)
            soc_sf = run_stream_slice(est_sf, d, 0, n, i_bias=i_b)
            sf_errs.append((soc_sf - d.truth_soc) * 100.0)
        for v_off in [-0.010, -0.005, +0.005, +0.010]:
            est_sf = E2EKFHysteresis(p_e7)
            init_estimator_state(est_sf, d.truth_soc[0], 0.0, 0.0, 0.0)
            soc_sf = run_stream_slice(est_sf, d, 0, n, v_offset=v_off)
            sf_errs.append((soc_sf - d.truth_soc) * 100.0)
        from dataclasses import replace
        for cap_err_ratio in [-0.03, +0.03]:
            p_cap = replace(p_e7, nominal_capacity_ah=p_e7.nominal_capacity_ah * (1.0 + cap_err_ratio))
            est_sf = E2EKFHysteresis(p_cap)
            init_estimator_state(est_sf, d.truth_soc[0], 0.0, 0.0, 0.0)
            soc_sf = run_stream_slice(est_sf, d, 0, n)
            sf_errs.append((soc_sf - d.truth_soc) * 100.0)
        all_sf_err = np.concatenate(sf_errs)
        b_sf, r_sf, m_sf, p_sf = compute_metrics(all_sf_err)
        records.append({"cell": cell_id, "temp_c": t, "scenario": "S-F", "bias_pp": b_sf, "rmse_pp": r_sf, "max_err_pp": m_sf, "p95_pp": p_sf})

    return pd.DataFrame(records)

if __name__ == "__main__":
    df_a007 = evaluate_cell_profile("A1-007")
    df_a008 = evaluate_cell_profile("A1-008")
    df_all = pd.concat([df_a007, df_a008], ignore_index=True)
    df_all.to_csv(repo_root / "reports" / "gauntlet" / "final_perf_table.csv", index=False)
    print("Computed final perf table successfully:")
    print(df_all.to_string())
