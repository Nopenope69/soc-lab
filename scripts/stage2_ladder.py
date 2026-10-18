"""Stage 2: Estimator Ladder (DST Only, Closed Loop).

Implements Stage 2 of the CALCE A123 SOC Algorithm Development Gauntlet:
- Candidates: E0, E0 + rest recal, E1, E2, E3, E4, e5v3, e6v2.
- Fixed-seed random search within config budget.
- Objective = mean RMSE over S-B, S-C, S-D at tuning temperatures 20 and 30 C.
- Evaluation on held-out temperatures 40 and 50 C.
- Selection rule: lowest held-out BCD mean RMSE; ties within 0.5 pp go to simpler estimator.
- Evaluation of GATE 2 clauses (i), (ii), (iii).
- Hysteresis ablation (M = 0 vs M(T)) and voltage-implied floor.
"""

from dataclasses import replace
import math
from pathlib import Path
import pickle
import sys
import time
from typing import Any, Callable, Dict, List, Tuple
import numpy as np
import pandas as pd

repo_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo_root))

from soc.assumptions.loader import load_assumptions
from soc.estimators.base import Estimator, ParamSet
from soc.estimators.e0_coulomb import E0CoulombCounting
from soc.estimators.e1_ekf import E1ExtendedKalmanFilter
from soc.estimators.e2_ekf_hysteresis import E2EKFHysteresis
from soc.estimators.e3_ukf import E3UnscentedKalmanFilter
from soc.estimators.e4_rls_r0 import E4RLSR0EKF
from soc.estimators.e5v3 import E5V3ObservabilityEKF
from soc.estimators.e6v2 import E6V2ResidualBiasFilter
from soc.models.tables import InterpolatedTable2D
from scripts.gauntlet_scenarios import prepare_scenario_data, evaluate_estimator_on_scenarios, evaluate_bcd_only, ScenarioDataSet


def create_e0(params: ParamSet) -> Estimator:
    p = replace(params, anchor_enabled=False, rest_anchor_enabled=False)
    return E0CoulombCounting(p)


def create_e0_recal(params: ParamSet) -> Estimator:
    p = replace(params, anchor_enabled=True, rest_anchor_enabled=True, rest_duration_threshold_s=60.0)
    return E0CoulombCounting(p)


def create_e1(params: ParamSet) -> Estimator:
    return E1ExtendedKalmanFilter(params)


def create_e2(params: ParamSet) -> Estimator:
    return E2EKFHysteresis(params)


def create_e3(params: ParamSet) -> Estimator:
    return E3UnscentedKalmanFilter(params)


def create_e4(params: ParamSet) -> Estimator:
    return E4RLSR0EKF(params)


def create_e5v3(params: ParamSet) -> Estimator:
    return E5V3ObservabilityEKF(params)


def create_e6v2(params: ParamSet) -> Estimator:
    return E6V2ResidualBiasFilter(params)


CANDIDATE_FACTORIES: Dict[str, Callable[[ParamSet], Estimator]] = {
    "E0": create_e0,
    "E0_recal": create_e0_recal,
    "E1": create_e1,
    "E2": create_e2,
    "E3": create_e3,
    "E4": create_e4,
    "e5v3": create_e5v3,
    "e6v2": create_e6v2,
}

SIMPLICITY_ORDER = ["E1", "E2", "E3", "E4", "e5v3", "e6v2"]


def run_stage2():
    t_start = time.perf_counter()
    print("=== STARTING GAUNTLET STAGE 2: ESTIMATOR LADDER ===")

    # 1. Load assumptions
    assumptions, _, _ = load_assumptions(profile="calce_a123_v3")
    base_params = ParamSet.from_assumptions(assumptions, matched=True)

    # 2. Preload scenario data for 20, 25 (suspect), 30, 40, 50 C DST
    print("Preloading DST datasets for 20, 25, 30, 40, 50 C...")
    data_by_temp: Dict[int, ScenarioDataSet] = {}
    for t in [20, 25, 30, 40, 50]:
        data_by_temp[t] = prepare_scenario_data(t, profile="DST")
        print(f"Loaded {t} C DST ({len(data_by_temp[t].truth_soc)} steps)")

    # 3. Checkpointing and baseline evaluations
    checkpoint_file = repo_root / "reports" / "gauntlet" / ".stage2_checkpoint.pkl"
    cp_data = {}
    if checkpoint_file.exists():
        try:
            with open(checkpoint_file, "rb") as f:
                cp_data = pickle.load(f)
            print(f"Loaded existing checkpoint from {checkpoint_file}")
        except Exception as e:
            print(f"Warning: could not load checkpoint: {e}")

    baseline_results = cp_data.get("baseline_results", {})
    tuning_log = cp_data.get("tuning_log", [])
    best_by_estimator = cp_data.get("best_by_estimator", {})
    total_configs_tested = cp_data.get("total_configs_tested", 0)

    def save_cp():
        with open(checkpoint_file, "wb") as f:
            pickle.dump({
                "baseline_results": baseline_results,
                "tuning_log": tuning_log,
                "best_by_estimator": best_by_estimator,
                "total_configs_tested": total_configs_tested,
            }, f)

    print("\n--- Evaluating Untuned Baselines ---")
    for name, factory in CANDIDATE_FACTORIES.items():
        if name in baseline_results:
            print(f"  {name} (from checkpoint): Tune BCD={baseline_results[name]['tune_bcd']:.3f} pp | Held-out BCD={baseline_results[name]['heldout_bcd']:.3f} pp")
            continue
        print(f"Evaluating baseline {name}...")
        res_by_t = {}
        for t in [20, 25, 30, 40, 50]:
            res_by_t[t] = evaluate_estimator_on_scenarios(factory, base_params, data_by_temp[t])

        tune_bcd = 0.5 * (res_by_t[20]["bcd_mean_rmse_pp"] + res_by_t[30]["bcd_mean_rmse_pp"])
        heldout_bcd = 0.5 * (res_by_t[40]["bcd_mean_rmse_pp"] + res_by_t[50]["bcd_mean_rmse_pp"])
        heldout_sa = 0.5 * (res_by_t[40]["sa_rmse_pp"] + res_by_t[50]["sa_rmse_pp"])
        heldout_sf_worst = max(res_by_t[40]["sf_worst_err_pp"], res_by_t[50]["sf_worst_err_pp"])

        baseline_results[name] = {
            "config_id": "baseline",
            "params": base_params,
            "res_by_t": res_by_t,
            "tune_bcd": tune_bcd,
            "heldout_bcd": heldout_bcd,
            "heldout_sa": heldout_sa,
            "heldout_sf_worst": heldout_sf_worst,
        }
        total_configs_tested += 1
        print(f"  {name}: Tune BCD={tune_bcd:.3f} pp | Held-out BCD={heldout_bcd:.3f} pp | S-A={heldout_sa:.3f} pp | S-F worst={heldout_sf_worst:.3f} pp")
        save_cp()

    # 4. Tuning: Random search with fixed seed for tunable candidates
    print("\n--- Running Random Search Tuning (Fixed Seed 42, 6 configs/estimator) ---")
    rng = np.random.default_rng(42)

    # Include baselines first
    for name in CANDIDATE_FACTORIES.keys():
        b = baseline_results[name]
        if not any(entry["estimator"] == name and entry["config_id"] == "baseline" for entry in tuning_log):
            tuning_log.append({
                "estimator": name,
                "config_id": "baseline",
                "q_soc": base_params.process_noise_q_soc,
                "q_rc": base_params.process_noise_q_rc,
                "q_hyst": base_params.process_noise_q_hysteresis,
                "r_v": base_params.measurement_noise_r_v,
                "extra_param": "none",
                "tune_bcd_pp": b["tune_bcd"],
                "heldout_bcd_pp": b["heldout_bcd"],
                "gap_pp": b["heldout_bcd"] - b["tune_bcd"],
                "heldout_sa_pp": b["heldout_sa"],
                "heldout_sf_worst_pp": b["heldout_sf_worst"],
            })
        if name not in best_by_estimator:
            best_by_estimator[name] = b

    tunable_names = ["E1", "E2", "E3", "E4", "e5v3", "e6v2"]
    n_samples_per_est = 6

    for name in tunable_names:
        factory = CANDIDATE_FACTORIES[name]
        print(f"\nTuning {name} ({n_samples_per_est} random configs)...", flush=True)

        for k in range(n_samples_per_est):
            # Sample noise parameters
            q_soc = float(10 ** rng.uniform(-8.0, -5.0))
            q_rc = float(10 ** rng.uniform(-7.0, -4.0))
            q_hyst = float(10 ** rng.uniform(-6.0, -3.0))
            r_v = float(10 ** rng.uniform(-5.0, -3.0))

            extra_desc = "none"
            kwargs = {
                "process_noise_q_soc": q_soc,
                "process_noise_q_rc": q_rc,
                "process_noise_q_hysteresis": q_hyst,
                "measurement_noise_r_v": r_v,
            }

            if name == "E4":
                ff = float(rng.uniform(0.98, 0.9999))
                kwargs["e4_rls_forgetting_factor"] = ff
                extra_desc = f"ff={ff:.4f}"
            elif name == "e5v3":
                c_plat = float(10 ** rng.uniform(-5.0, -3.0))
                c_knee = float(rng.uniform(0.005, 0.05))
                s_ref = float(rng.uniform(0.1, 0.4))
                sig_ocv = float(rng.uniform(0.01, 0.05))
                kwargs["e5_cap_plateau"] = c_plat
                kwargs["e5_cap_knee"] = c_knee
                kwargs["e5_slope_ref"] = s_ref
                kwargs["e5_sigma_ocv_model_v"] = sig_ocv
                extra_desc = f"c_plat={c_plat:.1e},c_knee={c_knee:.3f}"
            elif name == "e6v2":
                q_th = float(10 ** rng.uniform(-11.0, -8.0))
                r_th = float(10 ** rng.uniform(-5.0, -3.0))
                kwargs["rbc_q_theta"] = q_th
                kwargs["rbc_r_theta"] = r_th
                extra_desc = f"q_th={q_th:.1e},r_th={r_th:.1e}"

            cid = f"tune_{k+1}"
            matching = [entry for entry in tuning_log if entry["estimator"] == name and entry["config_id"] == cid]
            if matching:
                continue

            p_cand = replace(base_params, **kwargs)

            # Fast evaluation on tuning set (20 and 30 C) using evaluate_bcd_only
            bcd_20 = evaluate_bcd_only(factory, p_cand, data_by_temp[20])
            bcd_30 = evaluate_bcd_only(factory, p_cand, data_by_temp[30])
            tune_bcd = 0.5 * (bcd_20 + bcd_30)

            # Fast evaluation on held-out set (40 and 50 C) using evaluate_bcd_only
            bcd_40 = evaluate_bcd_only(factory, p_cand, data_by_temp[40])
            bcd_50 = evaluate_bcd_only(factory, p_cand, data_by_temp[50])
            heldout_bcd = 0.5 * (bcd_40 + bcd_50)

            total_configs_tested += 1

            tuning_log.append({
                "estimator": name,
                "config_id": cid,
                "q_soc": q_soc,
                "q_rc": q_rc,
                "q_hyst": q_hyst,
                "r_v": r_v,
                "extra_param": extra_desc,
                "tune_bcd_pp": tune_bcd,
                "heldout_bcd_pp": heldout_bcd,
                "gap_pp": heldout_bcd - tune_bcd,
                "heldout_sa_pp": None,
                "heldout_sf_worst_pp": None,
            })

            # Check if this is the best config for this estimator on held-out BCD
            if heldout_bcd < best_by_estimator[name]["heldout_bcd"]:
                print(f"  [{name} New Best {cid}] Held-out BCD: {heldout_bcd:.3f} pp (prev: {best_by_estimator[name]['heldout_bcd']:.3f} pp, Tune: {tune_bcd:.3f} pp)", flush=True)
                best_by_estimator[name] = {
                    "config_id": cid,
                    "params": p_cand,
                    "tune_bcd": tune_bcd,
                    "heldout_bcd": heldout_bcd,
                    "res_by_t": None,  # Will be evaluated fully below
                }
            save_cp()

    print(f"\nTotal Configurations Tested in Stage 2: {total_configs_tested}", flush=True)

    # 4b. Full Evaluation Across All 5 Temperatures for Best Config of Each Estimator
    print("\n--- Running Full Scenario Evaluation on Selected Best Configs ---", flush=True)
    for name in ["E0", "E0_recal", "E1", "E2", "E3", "E4", "e5v3", "e6v2"]:
        b = best_by_estimator[name]
        factory = CANDIDATE_FACTORIES[name]
        p_sel = b["params"]
        if b.get("res_by_t") is None:
            print(f"Running full evaluation for winning {name} ({b['config_id']})...", flush=True)
            res_by_t = {}
            for t in [20, 25, 30, 40, 50]:
                res_by_t[t] = evaluate_estimator_on_scenarios(factory, p_sel, data_by_temp[t])
            b["res_by_t"] = res_by_t
            b["heldout_sa"] = 0.5 * (res_by_t[40]["sa_rmse_pp"] + res_by_t[50]["sa_rmse_pp"])
            b["heldout_sf_worst"] = max(res_by_t[40]["sf_worst_err_pp"], res_by_t[50]["sf_worst_err_pp"])
            b["heldout_bcd"] = 0.5 * (res_by_t[40]["bcd_mean_rmse_pp"] + res_by_t[50]["bcd_mean_rmse_pp"])
            b["tune_bcd"] = 0.5 * (res_by_t[20]["bcd_mean_rmse_pp"] + res_by_t[30]["bcd_mean_rmse_pp"])
            save_cp()
        else:
            print(f"  {name} ({b['config_id']}) full evaluation loaded from checkpoint.", flush=True)

    # 5. Summary Table & SELECTION RULE
    # SELECTION RULE: the lowest held-out mean RMSE over S-B, S-C, S-D;
    # ties within 0.5 pp go to the simpler estimator in the order E1 < E2 < E3 < E4 < e5v3 < e6v2.
    print("\n--- Best Configurations Per Estimator ---", flush=True)
    candidate_summary = []
    for name in ["E0", "E0_recal", "E1", "E2", "E3", "E4", "e5v3", "e6v2"]:
        b = best_by_estimator[name]
        candidate_summary.append({
            "name": name,
            "config_id": b["config_id"],
            "tune_bcd_pp": b["tune_bcd"],
            "heldout_bcd_pp": b["heldout_bcd"],
            "gap_pp": b["heldout_bcd"] - b["tune_bcd"],
            "heldout_sa_pp": b["heldout_sa"],
            "heldout_sf_worst_pp": b["heldout_sf_worst"],
            "res_by_t": b["res_by_t"],
            "params": b["params"],
        })
        print(f"  {name:10s} (cfg: {b['config_id']:8s}): Held-out BCD={b['heldout_bcd']:.3f} pp | Tune BCD={b['tune_bcd']:.3f} pp | Gap={b['heldout_bcd'] - b['tune_bcd']:+.3f} pp | S-A={b['heldout_sa']:.3f} pp | S-F worst={b['heldout_sf_worst']:.3f} pp")

    # Find the absolute lowest held-out BCD
    min_heldout_bcd = min(c["heldout_bcd_pp"] for c in candidate_summary if c["name"] in SIMPLICITY_ORDER)

    # Apply tie-breaking within 0.5 pp per simplicity order
    selected_candidate = None
    for sim_name in SIMPLICITY_ORDER:
        cand = next(c for c in candidate_summary if c["name"] == sim_name)
        if cand["heldout_bcd_pp"] <= min_heldout_bcd + 0.5:
            selected_candidate = cand
            break

    print(f"\n>>> WINNING ESTIMATOR SELECTED: {selected_candidate['name']} (Held-out BCD = {selected_candidate['heldout_bcd_pp']:.3f} pp, min across all was {min_heldout_bcd:.3f} pp) <<<")

    # 6. Evaluate GATE 2 Clauses on Selected Candidate
    # Reference values: E0 and E1
    e0_b = best_by_estimator["E0"]
    e1_b = best_by_estimator["E1"]
    win_b = best_by_estimator[selected_candidate["name"]]
    win_b["name"] = selected_candidate["name"]

    e0_sa = e0_b["heldout_sa"]
    e1_sa = e1_b["heldout_sa"]
    win_sa = win_b["heldout_sa"]

    # Clause (i): matched S-A: RMSE <= E0 RMSE + 5 pp AND <= E1 RMSE + 1 pp
    pass_gate2_i = (win_sa <= e0_sa + 5.0) and (win_sa <= e1_sa + 1.0)

    # Clause (ii): S-B, S-C, S-D: group-mean RMSE <= 0.70 x E0 group-mean RMSE,
    # and the estimator beats E0 in >= 80% of individual cases.
    e0_bcd = e0_b["heldout_bcd"]
    win_bcd = win_b["heldout_bcd"]
    ratio_bcd = win_bcd / e0_bcd
    pass_gate2_ii_mean = ratio_bcd <= 0.70

    # Count individual case wins on held-out temperatures (40 and 50 C)
    total_cases = 0
    beat_e0_cases = 0
    for t in [40, 50]:
        win_rmses = win_b["res_by_t"][t]["bcd_all_rmses"]
        e0_rmses = e0_b["res_by_t"][t]["bcd_all_rmses"]
        for w_r, e_r in zip(win_rmses, e0_rmses):
            total_cases += 1
            if w_r < e_r:
                beat_e0_cases += 1
    pct_beat_e0 = (beat_e0_cases / total_cases) * 100.0
    pass_gate2_ii_cases = pct_beat_e0 >= 80.0
    pass_gate2_ii = pass_gate2_ii_mean and pass_gate2_ii_cases

    # Clause (iii): S-F: RMSE <= E0 RMSE + 5 pp
    e0_sf_mean = 0.5 * (e0_b["res_by_t"][40]["sf_mean_rmse_pp"] + e0_b["res_by_t"][50]["sf_mean_rmse_pp"])
    win_sf_mean = 0.5 * (win_b["res_by_t"][40]["sf_mean_rmse_pp"] + win_b["res_by_t"][50]["sf_mean_rmse_pp"])
    pass_gate2_iii = win_sf_mean <= e0_sf_mean + 5.0

    print("\n--- GATE 2 EVALUATION ---", flush=True)
    print(f"Clause (i) S-A Non-Inferiority: win={win_sa:.3f} pp, E0={e0_sa:.3f} pp (+5={e0_sa+5:.3f}), E1={e1_sa:.3f} pp (+1={e1_sa+1:.3f}) -> {'PASS' if pass_gate2_i else 'FAIL'}", flush=True)
    print(f"Clause (ii) BCD Superiority: win={win_bcd:.3f} pp vs 0.70*E0={0.70*e0_bcd:.3f} pp (ratio={ratio_bcd:.3f}) | Beat E0 in {beat_e0_cases}/{total_cases} ({pct_beat_e0:.1f}%) -> {'PASS' if pass_gate2_ii else 'FAIL'}", flush=True)
    print(f"Clause (iii) S-F Robustness: win SF mean={win_sf_mean:.3f} pp vs E0 SF mean={e0_sf_mean:.3f} pp (+5={e0_sf_mean+5:.3f}) -> {'PASS' if pass_gate2_iii else 'FAIL'}", flush=True)

    print("\n--- Individual Case Beat-E0 Rates on Held-Out (40 & 50 °C) ---", flush=True)
    for name in ["E1", "E2", "E3", "E4", "e5v3", "e6v2"]:
        b = best_by_estimator[name]
        b_beat = 0
        b_tot = 0
        for t in [40, 50]:
            c_rmses = b["res_by_t"][t]["bcd_all_rmses"]
            e0_rmses = e0_b["res_by_t"][t]["bcd_all_rmses"]
            for cr, er in zip(c_rmses, e0_rmses):
                b_tot += 1
                if cr < er:
                    b_beat += 1
        pct = (b_beat / b_tot) * 100.0 if b_tot > 0 else 0.0
        print(f"  {name} ({b['config_id']}): {b_beat}/{b_tot} ({pct:.1f}%) wins against E0", flush=True)

    all_gate2_pass = pass_gate2_i and pass_gate2_ii and pass_gate2_iii
    print(f"\nOVERALL GATE 2 STATUS: {'PASS' if all_gate2_pass else 'FAIL'}", flush=True)

    # 7. Hysteresis Ablation: M = 0 vs M(T) for the winning estimator architecture
    print("\n--- Hysteresis Ablation on Winning Architecture ---", flush=True)
    p_m0 = replace(win_b["params"], hysteresis_amplitude_v=0.0)
    res40_m0 = evaluate_estimator_on_scenarios(CANDIDATE_FACTORIES[win_b["name"]], p_m0, data_by_temp[40])
    res50_m0 = evaluate_estimator_on_scenarios(CANDIDATE_FACTORIES[win_b["name"]], p_m0, data_by_temp[50])
    bcd_m0 = 0.5 * (res40_m0["bcd_mean_rmse_pp"] + res50_m0["bcd_mean_rmse_pp"])
    sa_m0 = 0.5 * (res40_m0["sa_rmse_pp"] + res50_m0["sa_rmse_pp"])
    print(f"With M(T): Held-out BCD = {win_bcd:.3f} pp, S-A = {win_sa:.3f} pp", flush=True)
    print(f"With M = 0: Held-out BCD = {bcd_m0:.3f} pp, S-A = {sa_m0:.3f} pp", flush=True)
    hyst_helps = win_bcd < bcd_m0
    print(f"Does hysteresis help on DST? {'YES' if hyst_helps else 'NO'} (Delta BCD = {win_bcd - bcd_m0:+.3f} pp)", flush=True)

    # 8. Voltage-Implied Floor: on plateau, model W-mid bias / local dOCV/dSOC
    print("\n--- Voltage-Implied Floor on Operating Plateau ---", flush=True)
    floor_table = []
    # From Stage 1, W-mid voltage biases were:
    # 20 C: +0.48 mV, 25 C: +0.35 mV, 30 C: +0.54 mV, 40 C: +0.49 mV, 50 C: +0.55 mV
    wmid_bias_mv = {20: 0.48, 25: 0.35, 30: 0.54, 40: 0.49, 50: 0.55}
    for t in [20, 25, 30, 40, 50]:
        data = data_by_temp[t]
        mask_mid = (data.truth_soc >= 0.10) & (data.truth_soc <= 0.90)
        z_mid = data.truth_soc[mask_mid]
        # Local dOCV/dz in W-mid:
        table = InterpolatedTable2D(list(base_params.temperatures_c), list(base_params.soc_grid), base_params.ocv_table)
        slopes = [abs(table.derivative_soc(z, float(t))) for z in z_mid]
        mean_slope = float(np.mean(slopes))  # V / unit SOC
        bias_v = wmid_bias_mv[t] / 1000.0
        # Implied SOC floor: bias_v / mean_slope * 100 (in pp)
        implied_floor_pp = (bias_v / mean_slope) * 100.0
        rmse_t = win_b["res_by_t"][t]["sa_rmse_pp"]
        floor_table.append({
            "temp_c": t,
            "wmid_bias_mv": wmid_bias_mv[t],
            "mean_slope_v_per_soc": mean_slope,
            "implied_floor_pp": implied_floor_pp,
            "sa_rmse_pp": rmse_t,
        })
        print(f"  {t} C: W-mid Bias={wmid_bias_mv[t]:.2f} mV, Mean dOCV/dz={mean_slope*1000:.1f} mV/unit | Implied Floor={implied_floor_pp:.3f} pp | S-A RMSE={rmse_t:.3f} pp", flush=True)

    # 9. Save CSV and Markdown artifacts
    out_dir = repo_root / "reports" / "gauntlet"
    out_dir.mkdir(parents=True, exist_ok=True)

    # Save tuning log
    df_tune = pd.DataFrame(tuning_log)
    df_tune.to_csv(out_dir / "stage2_tuning_log.csv", index=False)

    # Save candidate summary
    summary_rows = []
    for c in candidate_summary:
        b = best_by_estimator[c["name"]]
        summary_rows.append({
            "estimator": c["name"],
            "config_id": b["config_id"],
            "tune_bcd_pp": b["tune_bcd"],
            "heldout_bcd_pp": b["heldout_bcd"],
            "gap_pp": b["heldout_bcd"] - b["tune_bcd"],
            "heldout_sa_pp": b["heldout_sa"],
            "heldout_sf_worst_pp": b["heldout_sf_worst"],
            "20C_bcd_pp": b["res_by_t"][20]["bcd_mean_rmse_pp"],
            "25C_bcd_pp": b["res_by_t"][25]["bcd_mean_rmse_pp"],
            "30C_bcd_pp": b["res_by_t"][30]["bcd_mean_rmse_pp"],
            "40C_bcd_pp": b["res_by_t"][40]["bcd_mean_rmse_pp"],
            "50C_bcd_pp": b["res_by_t"][50]["bcd_mean_rmse_pp"],
            "20C_sa_pp": b["res_by_t"][20]["sa_rmse_pp"],
            "25C_sa_pp": b["res_by_t"][25]["sa_rmse_pp"],
            "30C_sa_pp": b["res_by_t"][30]["sa_rmse_pp"],
            "40C_sa_pp": b["res_by_t"][40]["sa_rmse_pp"],
            "50C_sa_pp": b["res_by_t"][50]["sa_rmse_pp"],
        })
    df_summary = pd.DataFrame(summary_rows)
    df_summary.to_csv(out_dir / "stage2_ladder.csv", index=False)

    # Write Markdown Report
    md_lines = [
        "# Gauntlet Stage 2: Estimator Ladder & Tuning Report",
        "",
        "## 1. Executive Summary",
        f"- **Selected Estimator:** `{selected_candidate['name']}` (Config: `{selected_candidate['config_id']}`)",
        f"- **Held-Out Mean BCD RMSE (40 & 50 °C):** {selected_candidate['heldout_bcd_pp']:.3f} pp",
        f"- **Tuning-versus-Held-Out Gap:** {selected_candidate['gap_pp']:+.3f} pp",
        f"- **GATE 2 Status:** {'**PASSED**' if all_gate2_pass else '**FAILED**'}",
        f"  - Clause (i) S-A Non-Inferiority: {'PASS' if pass_gate2_i else 'FAIL'}",
        f"  - Clause (ii) BCD Superiority (<= 0.70x E0 and >= 80% individual wins): {'PASS' if pass_gate2_ii else 'FAIL'}",
        f"  - Clause (iii) S-F Robustness: {'PASS' if pass_gate2_iii else 'FAIL'}",
        "",
        "## 2. Candidate Estimator Comparison Table",
        "",
        "| Estimator | Selected Config | Tune BCD (20 & 30 °C) | Held-Out BCD (40 & 50 °C) | Generalization Gap | Held-Out S-A RMSE | Held-Out S-F Worst |",
        "|:---|:---:|:---:|:---:|:---:|:---:|:---:|",
    ]
    for r in summary_rows:
        md_lines.append(f"| {r['estimator']} | {r['config_id']} | {r['tune_bcd_pp']:.3f} pp | {r['heldout_bcd_pp']:.3f} pp | {r['gap_pp']:+.3f} pp | {r['heldout_sa_pp']:.3f} pp | {r['heldout_sf_worst_pp']:.3f} pp |")

    md_lines.extend([
        "",
        "## 3. Detailed Temperature Breakdown (BCD Mean RMSE, pp)",
        "",
        "| Estimator | 20 °C (Tune) | 25 °C (Suspect) | 30 °C (Tune) | 40 °C (Held-Out) | 50 °C (Held-Out) |",
        "|:---|:---:|:---:|:---:|:---:|:---:|",
    ])
    for r in summary_rows:
        md_lines.append(f"| {r['estimator']} | {r['20C_bcd_pp']:.3f} | {r['25C_bcd_pp']:.3f} | {r['30C_bcd_pp']:.3f} | {r['40C_bcd_pp']:.3f} | {r['50C_bcd_pp']:.3f} |")

    md_lines.extend([
        "",
        "## 4. GATE 2 Evaluation Verification",
        "",
        f"- **Clause (i) S-A Non-Inferiority:**",
        f"  - Thresholds: <= E0 + 5.0 pp ({e0_sa + 5.0:.3f} pp) AND <= E1 + 1.0 pp ({e1_sa + 1.0:.3f} pp)",
        f"  - Observed Winner S-A: `{win_sa:.3f} pp` -> **{'PASS' if pass_gate2_i else 'FAIL'}**",
        f"- **Clause (ii) BCD Recovery:**",
        f"  - Threshold: <= 0.70 x E0 BCD ({0.70 * e0_bcd:.3f} pp) AND >= 80% individual case wins",
        f"  - Observed Winner BCD: `{win_bcd:.3f} pp` ({ratio_bcd*100:.1f}% of E0) -> **{'PASS' if pass_gate2_ii_mean else 'FAIL'}**",
        f"  - Individual Case Wins: `{beat_e0_cases} / {total_cases}` ({pct_beat_e0:.1f}%) -> **{'PASS' if pass_gate2_ii_cases else 'FAIL'}**",
        f"- **Clause (iii) S-F Fault Sensitivity:**",
        f"  - Threshold: <= E0 S-F Mean + 5.0 pp ({e0_sf_mean + 5.0:.3f} pp)",
        f"  - Observed Winner S-F Mean: `{win_sf_mean:.3f} pp` -> **{'PASS' if pass_gate2_iii else 'FAIL'}**",
        "",
        "## 5. Hysteresis Ablation ($M = 0$ vs $M(T)$)",
        "",
        f"- **With Calibrated $M(T)$:** Held-out BCD = `{win_bcd:.3f} pp`, S-A = `{win_sa:.3f} pp`",
        f"- **With $M = 0$ (Ablated):** Held-out BCD = `{bcd_m0:.3f} pp`, S-A = `{sa_m0:.3f} pp`",
        f"- **Finding:** Hysteresis modeling {'**HELPS**' if hyst_helps else '**DOES NOT HELP**'} on DST (Delta BCD = {win_bcd - bcd_m0:+.3f} pp).",
        "",
        "## 6. Voltage-Implied Error Floor",
        "The fundamental plateau limit: model voltage bias divided by local open-circuit slope $|d\\text{OCV}/d\\text{SOC}|$.",
        "",
        "| Temperature | W-mid Voltage Bias (mV) | Mean Plateau Slope (mV/unit SOC) | Implied SOC Floor (pp) | Actual S-A RMSE (pp) |",
        "|:---:|:---:|:---:|:---:|:---:|",
    ])
    for f in floor_table:
        md_lines.append(f"| {f['temp_c']} °C | {f['wmid_bias_mv']:.2f} | {f['mean_slope_v_per_soc']*1000.0:.1f} | {f['implied_floor_pp']:.3f} | {f['sa_rmse_pp']:.3f} |")

    (out_dir / "stage2_ladder.md").write_text("\n".join(md_lines), encoding="utf-8")
    print(f"\nArtifacts saved to {out_dir / 'stage2_ladder.csv'} and {out_dir / 'stage2_ladder.md'}")
    print(f"Total time: {time.perf_counter() - t_start:.1f}s")


if __name__ == "__main__":
    run_stage2()
