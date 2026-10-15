"""Comprehensive script for Task A3: Open-Loop Gate and Estimator Evaluation.

Runs open-loop model simulation and estimator evaluations across DST, US06, FUDS
at gating temperatures (20, 25, 30, 40, 50 C) under:
  (i) v2 parameters (calce_a123_v2)
  (ii) M=0 variant (calce_a123_v2_m0)

Evaluates:
  - 3 SOC Windows: W-mid (10-90%), W-low (<10%), W-high (>90%), plus full range.
  - Voltage RMSE, Bias, Max error, sample count.
  - Cutoff times (measured vs predicted).
  - Implied SOC error at SOC = 0.3, 0.5, 0.7.
  - Proposed Gate evaluation on DST in W-mid: |bias| <= 5 mV, RMSE <= 15 mV.
  - Estimator SOC RMSE (pp) for E1, E2, E5 v1, E5 v2, E6 across all windows.
"""

from dataclasses import replace
from pathlib import Path
import sys
import numpy as np
import pandas as pd

repo_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(repo_root))

from soc.assumptions.loader import load_assumptions
from soc.data.calce_loader import load_ocv_file, load_dynamic_cycle, get_raw_dir
from soc.estimators.base import ParamSet
from soc.models.tables import InterpolatedTable2D
from soc.models.cell_2rc import Cell2RCModel
from soc.estimators.registry import get_estimator
from soc.models.plant import Measurement
from scripts.evaluate_calce import get_file_paths

GATING_TEMPS = [20, 25, 30, 40, 50]
PROFILES = ["DST", "US06", "FUDS"]

def build_param_sets_for_profile(profile_name: str):
    assumptions, _, _ = load_assumptions(profile=profile_name)
    base_params = ParamSet.from_assumptions(assumptions, matched=True)
    p_e0 = base_params
    p_e1 = base_params  # E1 ignores hysteresis internally
    p_e2 = base_params
    p_e5_v1 = replace(
        base_params,
        e5_enable_r_inflation=True,
        e5_enable_slope_gating=True,
        e5_enable_step_cap=True,
        e5_sigma_ocv_model_v=0.005,
        e5_slope_ref=0.1,
        e5_max_soc_step=0.0002,
        e5_use_observability_cap=False,
    )
    p_e5_v2 = replace(
        base_params,
        e5_enable_r_inflation=True,
        e5_enable_slope_gating=True,
        e5_enable_step_cap=True,
        e5_sigma_ocv_model_v=0.02,
        e5_slope_ref=0.2,
        e5_use_observability_cap=True,
        e5_cap_plateau=1e-5,
        e5_cap_knee=0.01,
    )
    p_e6 = replace(
        base_params,
        rbc_use_hysteresis_state=True if base_params.hysteresis_amplitude_v > 0 else False,
        rbc_q_theta=1e-9,
        rbc_r_theta=1e-4,
        rbc_initial_theta_std=0.002,
    )
    return {
        "E0": p_e0,
        "E1": p_e1,
        "E2": p_e2,
        "E5 v1": p_e5_v1,
        "E5 v2": p_e5_v2,
        "E6": p_e6,
    }

def run_open_loop_simulation(profile_name: str, mode_label: str):
    raw_dir = get_raw_dir(repo_root)
    params_dict = build_param_sets_for_profile(profile_name)
    base_params = params_dict["E2"]

    temps = list(base_params.temperatures_c)
    socs = list(base_params.soc_grid)
    ocv_table = InterpolatedTable2D(temps, socs, base_params.ocv_table)
    r0_table = InterpolatedTable2D(temps, socs, base_params.r0_table)
    r1_table = InterpolatedTable2D(temps, socs, base_params.r1_table)
    tau1_table = InterpolatedTable2D(temps, socs, base_params.tau1_table)
    r2_table = InterpolatedTable2D(temps, socs, base_params.r2_table)
    tau2_table = InterpolatedTable2D(temps, socs, base_params.tau2_table)

    m_eff = base_params.hysteresis_amplitude_v
    gamma = base_params.hysteresis_gamma
    cap_ah = base_params.nominal_capacity_ah
    eta = base_params.coulombic_efficiency

    rows = []

    for temp in GATING_TEMPS:
        ocv_p, dyn_p = get_file_paths(raw_dir, temp, "A1-007")
        ocv_data = load_ocv_file(ocv_p, float(temp), "A1-007")

        for prof in PROFILES:
            cyc = load_dynamic_cycle(dyn_p, float(temp), "A1-007", prof, ocv_data.c20_capacity_ah)
            time_s = cyc.time_s
            n = len(time_s)
            dt_arr = np.diff(time_s, prepend=time_s[0])
            i_arr = cyc.current_a
            v_meas = cyc.voltage_v
            z_truth = cyc.truth_soc
            t_meas = cyc.temperature_measured_c

            v_model = np.empty(n, dtype=float)
            v_res = np.empty(n, dtype=float)
            docv_dz_arr = np.empty(n, dtype=float)

            i1 = 0.0
            i2 = 0.0
            h = 0.0

            for k in range(n):
                dt = float(dt_arr[k]) if k > 0 else 1.0
                cur_t = float(t_meas[k])
                cur_i = float(i_arr[k])
                cur_z = float(z_truth[k])

                r0 = r0_table.lookup(cur_z, cur_t)
                r1 = r1_table.lookup(cur_z, cur_t)
                r2 = r2_table.lookup(cur_z, cur_t)
                tau1 = tau1_table.lookup(cur_z, cur_t)
                tau2 = tau2_table.lookup(cur_z, cur_t)
                ocv = ocv_table.lookup(cur_z, cur_t)
                docv = ocv_table.derivative_soc(cur_z, cur_t)

                v_mod = ocv + m_eff * h - r1 * i1 - r2 * i2 - r0 * cur_i
                v_model[k] = v_mod
                v_res[k] = float(v_meas[k]) - v_mod
                docv_dz_arr[k] = docv

                i1 = Cell2RCModel.step_rc_current(i1, cur_i, dt, tau1)
                i2 = Cell2RCModel.step_rc_current(i2, cur_i, dt, tau2)
                h = Cell2RCModel.step_hysteresis(h, cur_i, dt, cap_ah, gamma, eta)

            # Cutoff detection
            t_meas_cutoff = float(time_s[-1])
            cutoff_pred_idx = np.where(v_model <= 2.0)[0]
            t_pred_cutoff = float(time_s[cutoff_pred_idx[0]]) if len(cutoff_pred_idx) > 0 else float("nan")

            # Windows
            mask_mid = (z_truth >= 0.10) & (z_truth <= 0.90)
            mask_low = z_truth < 0.10
            mask_high = z_truth > 0.90
            mask_full = np.ones(n, dtype=bool)

            def get_win_stats(mask):
                if not np.any(mask):
                    return {"rmse_mv": float("nan"), "bias_mv": float("nan"), "max_err_mv": float("nan"), "n_samples": 0}
                res_w = v_res[mask]
                rmse = float(np.sqrt(np.mean(res_w ** 2)) * 1000.0)
                bias = float(np.mean(res_w) * 1000.0)
                max_err = float(np.max(np.abs(res_w)) * 1000.0)
                return {"rmse_mv": rmse, "bias_mv": bias, "max_err_mv": max_err, "n_samples": int(np.sum(mask))}

            stats_full = get_win_stats(mask_full)
            stats_mid = get_win_stats(mask_mid)
            stats_low = get_win_stats(mask_low)
            stats_high = get_win_stats(mask_high)

            # Implied SOC error at SOC 0.3, 0.5, 0.7
            # Implied SOC error (pp) = residual / (dOCV/dSOC) * 100
            implied_soc_errs = {}
            for target_soc in [0.3, 0.5, 0.7]:
                idx_closest = int(np.argmin(np.abs(z_truth - target_soc)))
                res_pt = v_res[idx_closest]
                docv_pt = docv_dz_arr[idx_closest]
                denom = max(abs(docv_pt), 1e-4) * np.sign(docv_pt if docv_pt != 0 else 1.0)
                soc_err_pp = (res_pt / denom) * 100.0
                implied_soc_errs[f"implied_soc_err_{int(target_soc*100)}"] = float(soc_err_pp)

            row = {
                "variant": mode_label,
                "profile_yaml": profile_name,
                "temp_c": temp,
                "profile": prof,
                "m_eff_v": m_eff,
                "meas_cutoff_s": t_meas_cutoff,
                "pred_cutoff_s": t_pred_cutoff,
                "cutoff_delta_s": t_pred_cutoff - t_meas_cutoff if not np.isnan(t_pred_cutoff) else float("nan"),
                # Full
                "full_rmse_mv": stats_full["rmse_mv"],
                "full_bias_mv": stats_full["bias_mv"],
                "full_max_err_mv": stats_full["max_err_mv"],
                "full_n_samples": stats_full["n_samples"],
                # W-mid (10-90%)
                "mid_rmse_mv": stats_mid["rmse_mv"],
                "mid_bias_mv": stats_mid["bias_mv"],
                "mid_max_err_mv": stats_mid["max_err_mv"],
                "mid_n_samples": stats_mid["n_samples"],
                # W-low (<10%)
                "low_rmse_mv": stats_low["rmse_mv"],
                "low_bias_mv": stats_low["bias_mv"],
                "low_max_err_mv": stats_low["max_err_mv"],
                "low_n_samples": stats_low["n_samples"],
                # W-high (>90%)
                "high_rmse_mv": stats_high["rmse_mv"],
                "high_bias_mv": stats_high["bias_mv"],
                "high_max_err_mv": stats_high["max_err_mv"],
                "high_n_samples": stats_high["n_samples"],
                # Implied SOC error
                "implied_soc_err_30_pp": implied_soc_errs["implied_soc_err_30"],
                "implied_soc_err_50_pp": implied_soc_errs["implied_soc_err_50"],
                "implied_soc_err_70_pp": implied_soc_errs["implied_soc_err_70"],
            }
            rows.append(row)

    return pd.DataFrame(rows)

def evaluate_estimator_stream(est, cycle_data):
    time_s = cycle_data.time_s
    n = len(time_s)
    dt_arr = np.diff(time_s, prepend=time_s[0])
    i_arr = cycle_data.current_a
    v_arr = cycle_data.voltage_v
    t_arr = cycle_data.temperature_measured_c
    z_truth = cycle_data.truth_soc

    est_soc = np.empty(n, dtype=float)
    est.reset(1.0)

    for k in range(n):
        dt = float(dt_arr[k]) if k > 0 else 1.0
        m = Measurement(
            v=float(v_arr[k]),
            i=float(i_arr[k]),
            temp_c=float(t_arr[k]),
            dt=dt,
            dropout=False,
        )
        res = est.step(m)
        est_soc[k] = res.soc

    return est_soc

def run_estimator_evaluation(profile_name: str, mode_label: str):
    raw_dir = get_raw_dir(repo_root)
    params_dict = build_param_sets_for_profile(profile_name)

    rows = []
    for temp in GATING_TEMPS:
        ocv_p, dyn_p = get_file_paths(raw_dir, temp, "A1-007")
        ocv_data = load_ocv_file(ocv_p, float(temp), "A1-007")

        for prof in PROFILES:
            cyc = load_dynamic_cycle(dyn_p, float(temp), "A1-007", prof, ocv_data.c20_capacity_ah)
            z_truth = cyc.truth_soc

            mask_mid = (z_truth >= 0.10) & (z_truth <= 0.90)
            mask_low = z_truth < 0.10
            mask_high = z_truth > 0.90
            mask_full = np.ones(len(z_truth), dtype=bool)

            for est_name in ["E1", "E2", "E5 v1", "E5 v2", "E6"]:
                p = params_dict[est_name]
                real_name = "E5" if est_name.startswith("E5") else est_name
                est = get_estimator(real_name, p)
                est_soc = evaluate_estimator_stream(est, cyc)

                err_pp = (est_soc - z_truth) * 100.0

                def calc_rmse(mask):
                    if not np.any(mask):
                        return float("nan")
                    return float(np.sqrt(np.mean(err_pp[mask] ** 2)))

                rows.append({
                    "variant": mode_label,
                    "temp_c": temp,
                    "profile": prof,
                    "estimator": est_name,
                    "rmse_full_pp": calc_rmse(mask_full),
                    "rmse_mid_pp": calc_rmse(mask_mid),
                    "rmse_low_pp": calc_rmse(mask_low),
                    "rmse_high_pp": calc_rmse(mask_high),
                })
    return pd.DataFrame(rows)

def main():
    print("=== Task A3: Running Open-Loop Gate and Estimator Evaluation ===")
    out_dir = repo_root / "reports" / "b2"
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1. Open-loop simulations
    print("\n[1/4] Running open-loop simulation: (i) v2 parameters...")
    df_ol_v2 = run_open_loop_simulation("calce_a123_v2", "v2")

    print("\n[2/4] Running open-loop simulation: (ii) M=0 variant...")
    df_ol_m0 = run_open_loop_simulation("calce_a123_v2_m0", "M=0")

    df_ol = pd.concat([df_ol_v2, df_ol_m0], ignore_index=True)
    ol_csv = out_dir / "a3_open_loop_voltage_summary.csv"
    df_ol.to_csv(ol_csv, index=False)
    print(f"Saved open loop summary to: {ol_csv}")

    # 2. Estimator evaluations
    print("\n[3/4] Running estimators: (i) v2 parameters...")
    df_est_v2 = run_estimator_evaluation("calce_a123_v2", "v2")

    print("\n[4/4] Running estimators: (ii) M=0 variant...")
    df_est_m0 = run_estimator_evaluation("calce_a123_v2_m0", "M=0")

    df_est = pd.concat([df_est_v2, df_est_m0], ignore_index=True)
def run_cutoff_diagnosis():
    raw_dir = get_raw_dir(repo_root)
    print("\n========================================================")
    print("CUTOFF DIAGNOSIS FOR A1-007 ON DST (20, 25, 30 C)")
    print("Comparing OLD baseline (calce_a123) vs NEW v2 (calce_a123_v2)")
    print("========================================================")

    diag_rows = []
    for param_label, prof_yaml in [("OLD (calce_a123)", "calce_a123"), ("v2 (calce_a123_v2)", "calce_a123_v2")]:
        assumptions, _, _ = load_assumptions(profile=prof_yaml)
        p = ParamSet.from_assumptions(assumptions, matched=True)
        temps = list(p.temperatures_c)
        socs = list(p.soc_grid)
        ocv_tab = InterpolatedTable2D(temps, socs, p.ocv_table)
        r0_tab = InterpolatedTable2D(temps, socs, p.r0_table)
        r1_tab = InterpolatedTable2D(temps, socs, p.r1_table)
        tau1_tab = InterpolatedTable2D(temps, socs, p.tau1_table)
        r2_tab = InterpolatedTable2D(temps, socs, p.r2_table)
        tau2_tab = InterpolatedTable2D(temps, socs, p.tau2_table)
        m_eff = p.hysteresis_amplitude_v
        gamma = p.hysteresis_gamma
        cap_ah = p.nominal_capacity_ah
        eta = p.coulombic_efficiency

        for temp in [20, 25, 30]:
            ocv_p, dyn_p = get_file_paths(raw_dir, temp, "A1-007")
            ocv_data = load_ocv_file(ocv_p, float(temp), "A1-007")
            cyc = load_dynamic_cycle(dyn_p, float(temp), "A1-007", "DST", ocv_data.c20_capacity_ah)

            time_s = cyc.time_s
            n = len(time_s)
            dt_arr = np.diff(time_s, prepend=time_s[0])
            i_arr = cyc.current_a
            v_meas = cyc.voltage_v
            z_truth = cyc.truth_soc
            t_meas = cyc.temperature_measured_c

            v_model = np.empty(n, dtype=float)
            i1 = i2 = h = 0.0

            for k in range(n):
                dt = float(dt_arr[k]) if k > 0 else 1.0
                cur_t = float(t_meas[k])
                cur_i = float(i_arr[k])
                cur_z = float(z_truth[k])

                r0 = r0_tab.lookup(cur_z, cur_t)
                r1 = r1_tab.lookup(cur_z, cur_t)
                r2 = r2_tab.lookup(cur_z, cur_t)
                tau1 = tau1_tab.lookup(cur_z, cur_t)
                tau2 = tau2_tab.lookup(cur_z, cur_t)
                ocv = ocv_tab.lookup(cur_z, cur_t)

                v_mod = ocv + m_eff * h - r1 * i1 - r2 * i2 - r0 * cur_i
                v_model[k] = v_mod

                i1 = Cell2RCModel.step_rc_current(i1, cur_i, dt, tau1)
                i2 = Cell2RCModel.step_rc_current(i2, cur_i, dt, tau2)
                h = Cell2RCModel.step_hysteresis(h, cur_i, dt, cap_ah, gamma, eta)

            min_v = float(np.min(v_model))
            min_soc = float(z_truth[np.argmin(v_model)])
            crosses_2v = bool(np.any(v_model <= 2.0))
            ocv_at_0 = float(ocv_tab.lookup(0.0, float(temp)))
            v_mod_at_cutoff = float(v_model[-1])
            v_meas_at_cutoff = float(v_meas[-1])
            v_err_at_cutoff = (v_meas_at_cutoff - v_mod_at_cutoff) * 1000.0  # mV
            final_soc = float(z_truth[-1])
            cutoff_t = float(time_s[-1])

            diag_rows.append({
                "params": param_label,
                "temp_c": temp,
                "cutoff_time_s": cutoff_t,
                "final_truth_soc_pct": final_soc * 100.0,
                "min_v_model_v": min_v,
                "soc_at_min_v_pct": min_soc * 100.0,
                "crosses_2v": crosses_2v,
                "ocv_at_soc_0_v": ocv_at_0,
                "v_model_at_cutoff_v": v_mod_at_cutoff,
                "v_meas_at_cutoff_v": v_meas_at_cutoff,
                "v_err_at_cutoff_mv": v_err_at_cutoff,
            })

    df_diag = pd.DataFrame(diag_rows)
    print(df_diag.to_string(index=False))
    return df_diag

def main():
    print("=== Task A3: Running Open-Loop Gate and Estimator Evaluation ===")
    out_dir = repo_root / "reports" / "b2"
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1. Open-loop simulations
    print("\n[1/4] Running open-loop simulation: (i) v2 parameters...")
    df_ol_v2 = run_open_loop_simulation("calce_a123_v2", "v2")

    print("\n[2/4] Running open-loop simulation: (ii) M=0 variant...")
    df_ol_m0 = run_open_loop_simulation("calce_a123_v2_m0", "M=0")

    df_ol = pd.concat([df_ol_v2, df_ol_m0], ignore_index=True)
    ol_csv = out_dir / "a3_open_loop_voltage_summary.csv"
    df_ol.to_csv(ol_csv, index=False)
    print(f"Saved open loop summary to: {ol_csv}")

    # 2. Cutoff diagnosis
    run_cutoff_diagnosis()

    # 3. Estimator evaluations
    print("\n[3/4] Running estimators: (i) v2 parameters...")
    df_est_v2 = run_estimator_evaluation("calce_a123_v2", "v2")

    print("\n[4/4] Running estimators: (ii) M=0 variant...")
    df_est_m0 = run_estimator_evaluation("calce_a123_v2_m0", "M=0")

    df_est = pd.concat([df_est_v2, df_est_m0], ignore_index=True)
    est_csv = out_dir / "a3_estimator_soc_summary.csv"
    df_est.to_csv(est_csv, index=False)
    print(f"Saved estimator summary to: {est_csv}")

    # Print summary tables
    print("\n========================================================")
    print("OPEN-LOOP GATE EVALUATION ON DST (W-mid: SOC 10% to 90%)")
    print("Gate bar: |bias| <= 5.0 mV AND voltage RMSE <= 15.0 mV")
    print("========================================================")
    df_dst_mid = df_ol[df_ol["profile"] == "DST"][["variant", "temp_c", "mid_rmse_mv", "mid_bias_mv", "mid_max_err_mv", "mid_n_samples"]]
    df_dst_mid["gate_pass"] = (df_dst_mid["mid_rmse_mv"] <= 15.0) & (df_dst_mid["mid_bias_mv"].abs() <= 5.0)
    print(df_dst_mid.to_string(index=False))

    print("\n========================================================")
    print("OPEN-LOOP END-REGION WINDOWS ON DST (W-low <10%, W-high >90%)")
    print("========================================================")
    df_dst_ends = df_ol[df_ol["profile"] == "DST"][["variant", "temp_c", "low_rmse_mv", "low_bias_mv", "high_rmse_mv", "high_bias_mv"]]
    print(df_dst_ends.to_string(index=False))

    print("\n========================================================")
    print("IMPLIED SOC ERROR AT PLATEAU POINTS ON DST (pp)")
    print("========================================================")
    df_dst_implied = df_ol[df_ol["profile"] == "DST"][["variant", "temp_c", "implied_soc_err_30_pp", "implied_soc_err_50_pp", "implied_soc_err_70_pp"]]
    print(df_dst_implied.to_string(index=False))

    print("\n========================================================")
    print("ESTIMATOR SOC RMSE (pp) ON DST (W-mid, W-low, W-high)")
    print("========================================================")
    df_est_dst = df_est[df_est["profile"] == "DST"]
    print(df_est_dst.to_string(index=False))

if __name__ == "__main__":
    main()

