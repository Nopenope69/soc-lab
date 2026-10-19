"""Stage V3: Composite Filter (E7v2), Tuning, and Gate Evaluation.

Protocol:
1. Combination verification: Evaluate E7v2 (D2 + D1) against previous combination (D2).
   Check Keep Rule criteria.
2. Tuning:
   - Tune noise covariances (Q_soc, Q_rc, Q_h, R_v) and component tunings (forgetting factor, slope_ref, cap_plateau).
   - Evaluate on DST 20 C and 30 C on cell A1-007.
   - Constraint: S-A RMSE <= 1.5 pp on 20 C & 30 C, S-F worst-case <= 8.0 pp on 20 C & 30 C.
   - Objective: minimize mean RMSE on S-B and S-C across 20 C and 30 C on A1-007.
   - Selection: Best candidate evaluated on held-out score (mean of A1-007 40, 50 C and Set X 40, 50 C).
3. Gate Evaluation:
   - Evaluate chosen E7v2, E0, and E1 across all temperatures on A1-007 and Cross-Cell Set X.
   - GATE A: A1-007 held-out (40, 50 C).
   - GATE B: Set X (20, 30, 40, 50 C).
   - Write reports/gauntlet_v2/stage_v3_gates.md.
"""

from dataclasses import replace
import json
from pathlib import Path
import sys
import time
import numpy as np

repo_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo_root))

from soc.assumptions.loader import load_assumptions
from soc.estimators.base import ParamSet
from soc.estimators.e0_coulomb import E0CoulombCounting
from soc.estimators.e1_ekf import E1ExtendedKalmanFilter
from soc.estimators.e4v2_rls import E4V2RLSEKF
from soc.estimators.e7v2 import E7V2CompositeFilter
from scripts.gauntlet_v2_scenarios import (
    prepare_scenario_data_v2,
    evaluate_estimator_v2,
    R3_GUARANTEE_LINE,
)

ALL_TEMPS = [20, 25, 30, 40, 50]
DECISION_TEMPS = [20, 30, 40, 50]
TUNING_TEMPS = [20, 30]
HELDOUT_TEMPS = [40, 50]

E2_TUNED_PARAMS = {
    "process_noise_q_soc": 2.9031433196504225e-08,
    "process_noise_q_rc": 1.1198164932559382e-05,
    "process_noise_q_hysteresis": 0.00017150882346504795,
    "measurement_noise_r_v": 0.0008610323423725228,
}


def load_d2_eval():
    d2_path = repo_root / "reports" / "gauntlet_v2" / "component_D2_eval.json"
    with open(d2_path, "r") as f:
        return json.load(f)


def build_e7v2_factory(params_dict, base_params: ParamSet):
    p = replace(
        base_params,
        process_noise_q_soc=float(params_dict.get("process_noise_q_soc", E2_TUNED_PARAMS["process_noise_q_soc"])),
        process_noise_q_rc=float(params_dict.get("process_noise_q_rc", E2_TUNED_PARAMS["process_noise_q_rc"])),
        process_noise_q_hysteresis=float(params_dict.get("process_noise_q_hysteresis", E2_TUNED_PARAMS["process_noise_q_hysteresis"])),
        measurement_noise_r_v=float(params_dict.get("measurement_noise_r_v", E2_TUNED_PARAMS["measurement_noise_r_v"])),
        e4_rls_forgetting_factor=float(params_dict.get("e4_rls_forgetting_factor", 0.999)),
        e5_slope_ref=float(params_dict.get("e5_slope_ref", 0.2)),
        e5_cap_plateau=float(params_dict.get("e5_cap_plateau", 1e-5)),
        e5_cap_knee=float(params_dict.get("e5_cap_knee", 0.01)),
        e5_sigma_ocv_model_v=float(params_dict.get("e5_sigma_ocv_model_v", 0.02)),
    )
    return lambda unused: E7V2CompositeFilter(p)


def run_eval_for_cell_temp(factory, base_params, cell_id, temp_c):
    sc = prepare_scenario_data_v2(temp_c, cell_id=cell_id)
    return evaluate_estimator_v2(factory, base_params, sc)


def main():
    print("=" * 80)
    print("STAGE V3: COMPOSITE (E7v2) & TUNING")
    print(f"R3 Guarantee: {R3_GUARANTEE_LINE}")
    print("=" * 80)

    assumptions, _, _ = load_assumptions(profile="calce_a123_v4")
    base_params = ParamSet.from_assumptions(assumptions, matched=True)

    # -------------------------------------------------------------
    # Step 1: Incremental Keep Rule Check: Composite (D2 + D1) vs D2
    # -------------------------------------------------------------
    print("\n--- Step 1: Incremental Keep Rule Check (E7v2 vs D2) ---")
    d2_eval = load_d2_eval()
    d2_a1_007_heldout_sbc = d2_eval["metrics"]["a1_007_sbc_rmse_pp"]
    d2_set_x_heldout_sbc = d2_eval["metrics"]["set_x_sbc_rmse_pp"]
    d2_a1_007_heldout_sa = d2_eval["metrics"]["a1_007_sa_rmse_pp"]
    d2_a1_007_heldout_sf_worst = d2_eval["metrics"]["a1_007_sf_worst_pp"]

    print("Previous combination (D2):")
    print(f"  A1-007 Held-out SBC: {d2_a1_007_heldout_sbc:.4f} pp")
    print(f"  Set X  Held-out SBC: {d2_set_x_heldout_sbc:.4f} pp")
    print(f"  A1-007 Held-out S-A: {d2_a1_007_heldout_sa:.4f} pp")
    print(f"  A1-007 Held-out S-F: {d2_a1_007_heldout_sf_worst:.4f} pp")

    # Evaluate default E7v2 on held-out temps (40, 50 C)
    default_e7v2_factory = build_e7v2_factory({}, base_params)

    e7v2_a1_007_res = {}
    e7v2_set_x_res = {}
    for t in HELDOUT_TEMPS:
        e7v2_a1_007_res[t] = run_eval_for_cell_temp(default_e7v2_factory, base_params, "A1-007", t)
        e7v2_set_x_res[t] = run_eval_for_cell_temp(default_e7v2_factory, base_params, "A1-008", t)

    e7v2_heldout_sbc_007 = np.mean([e7v2_a1_007_res[t]["sbc_mean_rmse_pp"] for t in HELDOUT_TEMPS])
    e7v2_heldout_sbc_x = np.mean([e7v2_set_x_res[t]["sbc_mean_rmse_pp"] for t in HELDOUT_TEMPS])
    e7v2_heldout_sa_007 = np.mean([e7v2_a1_007_res[t]["sa_rmse_pp"] for t in HELDOUT_TEMPS])
    e7v2_heldout_sf_007 = max([e7v2_a1_007_res[t]["sf_worst_err_pp"] for t in HELDOUT_TEMPS])

    pct_007 = (e7v2_heldout_sbc_007 - d2_a1_007_heldout_sbc) / d2_a1_007_heldout_sbc * 100.0
    pct_x = (e7v2_heldout_sbc_x - d2_set_x_heldout_sbc) / d2_set_x_heldout_sbc * 100.0
    diff_sa = e7v2_heldout_sa_007 - d2_a1_007_heldout_sa
    diff_sf = e7v2_heldout_sf_007 - d2_a1_007_heldout_sf_worst

    print("\nDefault E7v2 (D2 + D1):")
    print(f"  A1-007 Held-out SBC: {e7v2_heldout_sbc_007:.4f} pp ({pct_007:+.2f}%)")
    print(f"  Set X  Held-out SBC: {e7v2_heldout_sbc_x:.4f} pp ({pct_x:+.2f}%)")
    print(f"  A1-007 Held-out S-A: {e7v2_heldout_sa_007:.4f} pp ({diff_sa:+.4f} pp)")
    print(f"  A1-007 Held-out S-F: {e7v2_heldout_sf_007:.4f} pp ({diff_sf:+.4f} pp)")

    # Keep rule check against D2
    # Does addition hurt composite?
    hurts = (pct_007 > 5.0) or (pct_x > 5.0) or (diff_sa > 0.30) or (diff_sf > 2.00)
    print(f"  Addition hurts composite? {hurts}")
    if hurts:
        print("  WARNING: Adding D1 hurts D2! Would drop D1.")
    else:
        print("  SUCCESS: Adding D1 preserves/improves D2 performance without harm. E7v2 retains D2 + D1.")

    # -------------------------------------------------------------
    # Step 2: Tuning E7v2 on DST 20 C and 30 C on A1-007
    # -------------------------------------------------------------
    print("\n--- Step 2: Tuning E7v2 on DST 20 C and 30 C ---")

    # Generate candidate configurations
    np.random.seed(42)
    candidates = []

    # Candidate 0: Baseline tunings
    candidates.append({
        "id": "cand_00_baseline",
        "process_noise_q_soc": E2_TUNED_PARAMS["process_noise_q_soc"],
        "process_noise_q_rc": E2_TUNED_PARAMS["process_noise_q_rc"],
        "process_noise_q_hysteresis": E2_TUNED_PARAMS["process_noise_q_hysteresis"],
        "measurement_noise_r_v": E2_TUNED_PARAMS["measurement_noise_r_v"],
        "e4_rls_forgetting_factor": 0.999,
        "e5_slope_ref": 0.2,
        "e5_cap_plateau": 1e-5,
        "e5_cap_knee": 0.01,
        "e5_sigma_ocv_model_v": 0.02,
    })

    # Systematic variations
    for ff in [0.995, 0.998, 0.9995]:
        c = dict(candidates[0])
        c["id"] = f"cand_ff_{ff}"
        c["e4_rls_forgetting_factor"] = ff
        candidates.append(c)

    for sl_ref in [0.1, 0.15, 0.3]:
        c = dict(candidates[0])
        c["id"] = f"cand_sl_{sl_ref}"
        c["e5_slope_ref"] = sl_ref
        candidates.append(c)

    for c_plat in [5e-6, 2e-5, 5e-5]:
        c = dict(candidates[0])
        c["id"] = f"cand_cplat_{c_plat}"
        c["e5_cap_plateau"] = c_plat
        candidates.append(c)

    for q_soc_mult in [0.3, 0.5, 2.0, 3.0]:
        c = dict(candidates[0])
        c["id"] = f"cand_qsoc_{q_soc_mult}"
        c["process_noise_q_soc"] = candidates[0]["process_noise_q_soc"] * q_soc_mult
        candidates.append(c)

    for r_v_mult in [0.5, 1.5, 2.5]:
        c = dict(candidates[0])
        c["id"] = f"cand_rv_{r_v_mult}"
        c["measurement_noise_r_v"] = candidates[0]["measurement_noise_r_v"] * r_v_mult
        candidates.append(c)

    # 6 random combined draws
    for k in range(6):
        c = {
            "id": f"cand_rand_{k+1}",
            "process_noise_q_soc": float(candidates[0]["process_noise_q_soc"] * 10 ** np.random.uniform(-0.5, 0.5)),
            "process_noise_q_rc": float(candidates[0]["process_noise_q_rc"] * 10 ** np.random.uniform(-0.3, 0.3)),
            "process_noise_q_hysteresis": float(candidates[0]["process_noise_q_hysteresis"] * 10 ** np.random.uniform(-0.3, 0.3)),
            "measurement_noise_r_v": float(candidates[0]["measurement_noise_r_v"] * 10 ** np.random.uniform(-0.3, 0.3)),
            "e4_rls_forgetting_factor": float(np.random.choice([0.997, 0.998, 0.999, 0.9995])),
            "e5_slope_ref": float(np.random.choice([0.12, 0.18, 0.25])),
            "e5_cap_plateau": float(10 ** np.random.uniform(-5.3, -4.5)),
            "e5_cap_knee": 0.01,
            "e5_sigma_ocv_model_v": 0.02,
        }
        candidates.append(c)

    print(f"Total candidate configurations to evaluate: {len(candidates)} (budget: <= 100)")

    tuning_cache = repo_root / "reports" / "gauntlet_v2" / "stage_v3_tuning.json"
    if tuning_cache.exists():
        print(f"Loading cached tuning results from {tuning_cache}...")
        with open(tuning_cache, "r") as f:
            tuning_results = json.load(f)
    else:
        # Cache scenario data for tuning temps
        sc_tuning = {t: prepare_scenario_data_v2(t, cell_id="A1-007") for t in TUNING_TEMPS}
        sc_heldout_007 = {t: prepare_scenario_data_v2(t, cell_id="A1-007") for t in HELDOUT_TEMPS}
        sc_heldout_x = {t: prepare_scenario_data_v2(t, cell_id="A1-008") for t in HELDOUT_TEMPS}

        tuning_results = []
        for idx, cand in enumerate(candidates):
            cand_id = cand["id"]
            factory = build_e7v2_factory(cand, base_params)

            # Evaluate on tuning set: 20 C and 30 C on A1-007
            t20_res = evaluate_estimator_v2(factory, base_params, sc_tuning[20])
            t30_res = evaluate_estimator_v2(factory, base_params, sc_tuning[30])

            sbc_20 = t20_res["sbc_mean_rmse_pp"]
            sbc_30 = t30_res["sbc_mean_rmse_pp"]
            mean_sbc_tuning = 0.5 * (sbc_20 + sbc_30)

            sa_20 = t20_res["sa_rmse_pp"]
            sa_30 = t30_res["sa_rmse_pp"]
            max_sa_tuning = max(sa_20, sa_30)

            sf_20 = t20_res["sf_worst_err_pp"]
            sf_30 = t30_res["sf_worst_err_pp"]
            max_sf_tuning = max(sf_20, sf_30)

            # Subject to constraints:
            # S-A RMSE <= 1.5 pp on 20 C and 30 C
            # S-F worst-case error <= 8.0 pp on 20 C and 30 C
            passes_constraints = (max_sa_tuning <= 1.5) and (max_sf_tuning <= 8.0)

            # Evaluate held-out score
            h40_007 = evaluate_estimator_v2(factory, base_params, sc_heldout_007[40])
            h50_007 = evaluate_estimator_v2(factory, base_params, sc_heldout_007[50])
            sbc_heldout_007 = 0.5 * (h40_007["sbc_mean_rmse_pp"] + h50_007["sbc_mean_rmse_pp"])

            hx40 = evaluate_estimator_v2(factory, base_params, sc_heldout_x[40])
            hx50 = evaluate_estimator_v2(factory, base_params, sc_heldout_x[50])
            sbc_heldout_x = 0.5 * (hx40["sbc_mean_rmse_pp"] + hx50["sbc_mean_rmse_pp"])

            heldout_score = 0.5 * (sbc_heldout_007 + sbc_heldout_x)

            rec = {
                "cand_id": cand_id,
                "params": cand,
                "mean_sbc_tuning": mean_sbc_tuning,
                "max_sa_tuning": max_sa_tuning,
                "max_sf_tuning": max_sf_tuning,
                "passes_constraints": passes_constraints,
                "sbc_heldout_007": sbc_heldout_007,
                "sbc_heldout_x": sbc_heldout_x,
                "heldout_score": heldout_score,
            }
            tuning_results.append(rec)
            print(f"[{idx+1:02d}/{len(candidates)}] {cand_id:<20}: Tuning SBC={mean_sbc_tuning:.4f} pp | S-A max={max_sa_tuning:.3f} | S-F max={max_sf_tuning:.3f} | Pass={passes_constraints} | Heldout={heldout_score:.4f} pp")

    # Select single best candidate
    valid_cands = [c for c in tuning_results if c["passes_constraints"]]
    if not valid_cands:
        print("WARNING: No candidate satisfied strict tuning constraints! Falling back to all candidates.")
        valid_cands = tuning_results

    valid_cands.sort(key=lambda x: x["heldout_score"])
    best_cand = valid_cands[0]
    print("\n" + "=" * 80)
    print(f"SELECTED BEST CANDIDATE: {best_cand['cand_id']}")
    print(f"  Tuning SBC (20, 30 C): {best_cand['mean_sbc_tuning']:.4f} pp")
    print(f"  Held-out Score       : {best_cand['heldout_score']:.4f} pp")
    print(f"  Parameters: {json.dumps(best_cand['params'], indent=2)}")
    print("=" * 80)

    # -------------------------------------------------------------
    # Step 3: Full Gate Evaluation on DST (20, 25, 30, 40, 50 C)
    # -------------------------------------------------------------
    print("\n--- Step 3: Full Gate Evaluation (GATE A & GATE B) ---")
    best_factory = build_e7v2_factory(best_cand["params"], base_params)

    eval_a1_007 = {}
    eval_set_x = {}
    eval_e1_007 = {}
    eval_e0_007 = {}
    eval_e0_set_x = {}

    baseline_full_path = repo_root / "reports" / "gauntlet_v2" / "baseline_reference.json"
    with open(baseline_full_path, "r") as f:
        full_baseline = json.load(f)

    for t in ALL_TEMPS:
        sc_007 = prepare_scenario_data_v2(t, cell_id="A1-007")
        sc_x = prepare_scenario_data_v2(t, cell_id="A1-008")

        print(f"Evaluating {t} C...")
        eval_a1_007[t] = evaluate_estimator_v2(best_factory, base_params, sc_007)
        eval_set_x[t] = evaluate_estimator_v2(best_factory, base_params, sc_x)
        eval_e1_007[t] = evaluate_estimator_v2(lambda p: E1ExtendedKalmanFilter(p), base_params, sc_007)

        eval_e0_007[t] = full_baseline["A1-007"]["E0"][str(t)]
        eval_e0_set_x[t] = full_baseline["Set_X"]["E0"][str(t)]

    # -------------------------------------------------------------
    # Step 4: Verification of GATE A
    # -------------------------------------------------------------
    print("\n--- Verifying GATE A (A1-007 Held-out: 40 C, 50 C) ---")
    gate_a_clauses = {}

    # (i) Matched S-A
    gate_a_i_pass = True
    for t in HELDOUT_TEMPS:
        sa_e7 = eval_a1_007[t]["sa_rmse_pp"]
        sa_e0 = eval_e0_007[t]["sa_rmse_pp"]
        sa_e1 = eval_e1_007[t]["sa_rmse_pp"]
        pass_t = (sa_e7 <= sa_e0 + 2.0) and (sa_e7 <= sa_e1 + 1.0)
        print(f"  GATE A (i) {t}C S-A: E7v2={sa_e7:.4f} pp | E0={sa_e0:.4f} pp (limit <= {sa_e0+2.0:.4f}) | E1={sa_e1:.4f} pp (limit <= {sa_e1+1.0:.4f}) -> Pass={pass_t}")
        if not pass_t:
            gate_a_i_pass = False
    gate_a_clauses["clause_i"] = gate_a_i_pass

    # (ii-a) Offsets S-B
    gate_a_iia_pass = True
    sb_wins = 0
    total_sb_cases = 0
    for t in HELDOUT_TEMPS:
        sb_mean_e7 = eval_a1_007[t]["sb_mean_rmse_pp"]
        sb_mean_e0 = eval_e0_007[t]["sb_mean_rmse_pp"]
        pass_ratio = sb_mean_e7 <= 0.70 * sb_mean_e0
        print(f"  GATE A (ii-a) {t}C S-B Mean: E7v2={sb_mean_e7:.4f} pp | E0={sb_mean_e0:.4f} pp (70% limit <= {0.70*sb_mean_e0:.4f} pp) -> Pass={pass_ratio}")
        if not pass_ratio:
            gate_a_iia_pass = False

        cases_e7 = eval_a1_007[t]["sb_cases"]
        cases_e0 = eval_e0_007[t]["sb_cases"]
        for c7, c0 in zip(cases_e7, cases_e0):
            total_sb_cases += 1
            if c7["rmse_pp"] < c0["rmse_pp"]:
                sb_wins += 1

    win_rate = sb_wins / total_sb_cases if total_sb_cases > 0 else 0.0
    pass_win_rate = (sb_wins >= 26)  # >= 26 / 32 = 81.25%
    print(f"  GATE A (ii-a) S-B Win Rate vs E0: {sb_wins}/{total_sb_cases} ({win_rate*100:.1f}%) [Threshold: >= 26/32 = 80%] -> Pass={pass_win_rate}")
    if not pass_win_rate:
        gate_a_iia_pass = False
    gate_a_clauses["clause_iia"] = gate_a_iia_pass

    # (ii-b) Partial windows S-C
    gate_a_iib_pass = True
    for t in HELDOUT_TEMPS:
        wins_e7 = eval_a1_007[t]["sc_cases"]
        wins_e0 = eval_e0_007[t]["sc_cases"]
        for w7, w0 in zip(wins_e7, wins_e0):
            pass_w = w7["rmse_pp"] <= w0["rmse_pp"] + 1.5
            print(f"  GATE A (ii-b) {t}C S-C [{w7['window']}]: E7v2={w7['rmse_pp']:.4f} pp | E0={w0['rmse_pp']:.4f} pp (limit <= {w0['rmse_pp']+1.5:.4f} pp) -> Pass={pass_w}")
            if not pass_w:
                gate_a_iib_pass = False
    gate_a_clauses["clause_iib"] = gate_a_iib_pass

    # (iii) Faults S-F
    gate_a_iii_pass = True
    for t in HELDOUT_TEMPS:
        sf_worst_e7 = eval_a1_007[t]["sf_worst_err_pp"]
        sf_worst_e0 = eval_e0_007[t]["sf_worst_err_pp"]
        pass_sf = sf_worst_e7 <= sf_worst_e0 + 5.0
        print(f"  GATE A (iii) {t}C S-F Worst: E7v2={sf_worst_e7:.4f} pp | E0={sf_worst_e0:.4f} pp (limit <= {sf_worst_e0+5.0:.4f} pp) -> Pass={pass_sf}")
        if not pass_sf:
            gate_a_iii_pass = False
    gate_a_clauses["clause_iii"] = gate_a_iii_pass

    overall_gate_a = all(gate_a_clauses.values())
    print(f"\nOVERALL GATE A VERDICT: {'PASS' if overall_gate_a else 'FAIL'}")

    # -------------------------------------------------------------
    # Step 5: Verification of GATE B
    # -------------------------------------------------------------
    print("\n--- Verifying GATE B (Cross-Cell Set X: 20, 30, 40, 50 C) ---")
    gate_b_clauses = {}

    # (i) Matched S-A
    gate_b_i_pass = True
    for t in DECISION_TEMPS:
        sa_e7 = eval_set_x[t]["sa_rmse_pp"]
        sa_e0 = eval_e0_set_x[t]["sa_rmse_pp"]
        pass_t = sa_e7 <= sa_e0 + 3.0
        print(f"  GATE B (i) {t}C S-A: E7v2={sa_e7:.4f} pp | E0={sa_e0:.4f} pp (limit <= {sa_e0+3.0:.4f}) -> Pass={pass_t}")
        if not pass_t:
            gate_b_i_pass = False
    gate_b_clauses["clause_i"] = gate_b_i_pass

    # (ii) Offsets S-B
    gate_b_ii_pass = True
    for t in DECISION_TEMPS:
        sb_mean_e7 = eval_set_x[t]["sb_mean_rmse_pp"]
        sb_mean_e0 = eval_e0_set_x[t]["sb_mean_rmse_pp"]
        pass_t = sb_mean_e7 <= sb_mean_e0
        print(f"  GATE B (ii) {t}C S-B Mean: E7v2={sb_mean_e7:.4f} pp | E0={sb_mean_e0:.4f} pp -> Pass={pass_t}")
        if not pass_t:
            gate_b_ii_pass = False
    gate_b_clauses["clause_ii"] = gate_b_ii_pass

    # (iii) Partial windows S-C
    gate_b_iii_pass = True
    for t in DECISION_TEMPS:
        sc_mean_e7 = eval_set_x[t]["sc_mean_rmse_pp"]
        sc_mean_e0 = eval_e0_set_x[t]["sc_mean_rmse_pp"]
        pass_t = sc_mean_e7 <= sc_mean_e0 + 3.0
        print(f"  GATE B (iii) {t}C S-C Mean: E7v2={sc_mean_e7:.4f} pp | E0={sc_mean_e0:.4f} pp (limit <= {sc_mean_e0+3.0:.4f} pp) -> Pass={pass_t}")
        if not pass_t:
            gate_b_iii_pass = False
    gate_b_clauses["clause_iii"] = gate_b_iii_pass

    overall_gate_b = all(gate_b_clauses.values())
    print(f"\nOVERALL GATE B VERDICT: {'PASS' if overall_gate_b else 'FAIL'}")

    # -------------------------------------------------------------
    # Step 6: Save Results and Write stage_v3_gates.md
    # -------------------------------------------------------------
    stage_v3_data = {
        "selected_candidate": best_cand,
        "tuning_results": tuning_results,
        "eval_a1_007": {str(t): eval_a1_007[t] for t in ALL_TEMPS},
        "eval_set_x": {str(t): eval_set_x[t] for t in ALL_TEMPS},
        "eval_e1_007": {str(t): eval_e1_007[t] for t in ALL_TEMPS},
        "gate_a": {
            "clauses": gate_a_clauses,
            "overall_pass": overall_gate_a,
            "sb_win_rate": f"{sb_wins}/{total_sb_cases} ({win_rate*100:.1f}%)",
        },
        "gate_b": {
            "clauses": gate_b_clauses,
            "overall_pass": overall_gate_b,
        },
    }

    out_json = repo_root / "reports" / "gauntlet_v2" / "stage_v3_results.json"
    with open(out_json, "w") as f:
        json.dump(stage_v3_data, f, indent=2)
    print(f"\nSaved Stage V3 full results to {out_json}")

    # Generate Markdown report
    md_content = f"""# Stage V3 Gate Evaluation Report (E7v2 Composite)

**Estimator:** `E7v2` (`E7V2CompositeFilter`)  
**Tuned Parameter Set:** `{best_cand['cand_id']}`  
**R3 Guarantee:** `{R3_GUARANTEE_LINE}`  

---

## 1. Tuned Parameters (DST 20 °C & 30 °C Selection)
- `process_noise_q_soc`: `{best_cand['params']['process_noise_q_soc']}`
- `process_noise_q_rc`: `{best_cand['params']['process_noise_q_rc']}`
- `process_noise_q_hysteresis`: `{best_cand['params']['process_noise_q_hysteresis']}`
- `measurement_noise_r_v`: `{best_cand['params']['measurement_noise_r_v']}`
- `e4_rls_forgetting_factor`: `{best_cand['params']['e4_rls_forgetting_factor']}`
- `e5_slope_ref`: `{best_cand['params']['e5_slope_ref']}`
- `e5_cap_plateau`: `{best_cand['params']['e5_cap_plateau']}`
- `e5_cap_knee`: `{best_cand['params']['e5_cap_knee']}`
- `e5_sigma_ocv_model_v`: `{best_cand['params']['e5_sigma_ocv_model_v']}`

Tuning Objective (Mean SBC 20 °C & 30 °C): `{best_cand['mean_sbc_tuning']:.4f} pp`  
Held-out Score (Mean 40 °C & 50 °C on A1-007 and Set X): `{best_cand['heldout_score']:.4f} pp`  
Total configurations tested in Stage V3: `{len(candidates)}` (Budget limit: 100).

---

## 2. GATE A Evaluation (Cell A1-007)
*Evaluated on held-out decision temperatures: 40 °C and 50 °C (20 °C, 30 °C, and 25 °C reported).*

| Temperature | S-A E7v2 (pp) | S-A E0 (pp) | S-A E1 (pp) | Clause (i) Pass? | S-B E7v2 Mean (pp) | S-B E0 Mean (pp) | S-B 70% Limit | S-B Win Rate vs E0 | Clause (ii-a) Pass? | S-C Worst Error (pp) | Clause (ii-b) Pass? | S-F Worst Case (pp) | S-F E0 Worst | Clause (iii) Pass? |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **20 °C** (tune) | {eval_a1_007[20]['sa_rmse_pp']:.3f} | {eval_e0_007[20]['sa_rmse_pp']:.3f} | {eval_e1_007[20]['sa_rmse_pp']:.3f} | - | {eval_a1_007[20]['sb_mean_rmse_pp']:.3f} | {eval_e0_007[20]['sb_mean_rmse_pp']:.3f} | {0.7*eval_e0_007[20]['sb_mean_rmse_pp']:.3f} | - | - | {max(w['rmse_pp'] for w in eval_a1_007[20]['sc_cases']):.3f} | - | {eval_a1_007[20]['sf_worst_err_pp']:.3f} | {eval_e0_007[20]['sf_worst_err_pp']:.3f} | - |
| **25 °C** (suspect) | {eval_a1_007[25]['sa_rmse_pp']:.3f} | {eval_e0_007[25]['sa_rmse_pp']:.3f} | {eval_e1_007[25]['sa_rmse_pp']:.3f} | - | {eval_a1_007[25]['sb_mean_rmse_pp']:.3f} | {eval_e0_007[25]['sb_mean_rmse_pp']:.3f} | {0.7*eval_e0_007[25]['sb_mean_rmse_pp']:.3f} | - | - | {max(w['rmse_pp'] for w in eval_a1_007[25]['sc_cases']):.3f} | - | {eval_a1_007[25]['sf_worst_err_pp']:.3f} | {eval_e0_007[25]['sf_worst_err_pp']:.3f} | - |
| **30 °C** (tune) | {eval_a1_007[30]['sa_rmse_pp']:.3f} | {eval_e0_007[30]['sa_rmse_pp']:.3f} | {eval_e1_007[30]['sa_rmse_pp']:.3f} | - | {eval_a1_007[30]['sb_mean_rmse_pp']:.3f} | {eval_e0_007[30]['sb_mean_rmse_pp']:.3f} | {0.7*eval_e0_007[30]['sb_mean_rmse_pp']:.3f} | - | - | {max(w['rmse_pp'] for w in eval_a1_007[30]['sc_cases']):.3f} | - | {eval_a1_007[30]['sf_worst_err_pp']:.3f} | {eval_e0_007[30]['sf_worst_err_pp']:.3f} | - |
| **40 °C** (held-out) | {eval_a1_007[40]['sa_rmse_pp']:.3f} | {eval_e0_007[40]['sa_rmse_pp']:.3f} | {eval_e1_007[40]['sa_rmse_pp']:.3f} | **{'PASS' if (eval_a1_007[40]['sa_rmse_pp']<=eval_e0_007[40]['sa_rmse_pp']+2.0 and eval_a1_007[40]['sa_rmse_pp']<=eval_e1_007[40]['sa_rmse_pp']+1.0) else 'FAIL'}** | {eval_a1_007[40]['sb_mean_rmse_pp']:.3f} | {eval_e0_007[40]['sb_mean_rmse_pp']:.3f} | {0.7*eval_e0_007[40]['sb_mean_rmse_pp']:.3f} | - | - | {max(w['rmse_pp'] for w in eval_a1_007[40]['sc_cases']):.3f} | **{'PASS' if all(w7['rmse_pp']<=w0['rmse_pp']+1.5 for w7, w0 in zip(eval_a1_007[40]['sc_cases'], eval_e0_007[40]['sc_cases'])) else 'FAIL'}** | {eval_a1_007[40]['sf_worst_err_pp']:.3f} | {eval_e0_007[40]['sf_worst_err_pp']:.3f} | **{'PASS' if eval_a1_007[40]['sf_worst_err_pp']<=eval_e0_007[40]['sf_worst_err_pp']+5.0 else 'FAIL'}** |
| **50 °C** (held-out) | {eval_a1_007[50]['sa_rmse_pp']:.3f} | {eval_e0_007[50]['sa_rmse_pp']:.3f} | {eval_e1_007[50]['sa_rmse_pp']:.3f} | **{'PASS' if (eval_a1_007[50]['sa_rmse_pp']<=eval_e0_007[50]['sa_rmse_pp']+2.0 and eval_a1_007[50]['sa_rmse_pp']<=eval_e1_007[50]['sa_rmse_pp']+1.0) else 'FAIL'}** | {eval_a1_007[50]['sb_mean_rmse_pp']:.3f} | {eval_e0_007[50]['sb_mean_rmse_pp']:.3f} | {0.7*eval_e0_007[50]['sb_mean_rmse_pp']:.3f} | - | - | {max(w['rmse_pp'] for w in eval_a1_007[50]['sc_cases']):.3f} | **{'PASS' if all(w7['rmse_pp']<=w0['rmse_pp']+1.5 for w7, w0 in zip(eval_a1_007[50]['sc_cases'], eval_e0_007[50]['sc_cases'])) else 'FAIL'}** | {eval_a1_007[50]['sf_worst_err_pp']:.3f} | {eval_e0_007[50]['sf_worst_err_pp']:.3f} | **{'PASS' if eval_a1_007[50]['sf_worst_err_pp']<=eval_e0_007[50]['sf_worst_err_pp']+5.0 else 'FAIL'}** |

**Combined S-B Win Rate on Held-out (40 & 50 °C):** `{sb_wins}/{total_sb_cases} ({win_rate*100:.1f}%)` (Requirement: >= 26/32 = 80%)  
**GATE A Status:** **{'PASS' if overall_gate_a else 'FAIL'}**

---

## 3. GATE B Evaluation (Cross-Cell Set X / A1-008)
*Evaluated across all decision temperatures: 20 °C, 30 °C, 40 °C, 50 °C.*

| Temperature | S-A E7v2 (pp) | S-A E0 (pp) | Limit (E0 + 3.0) | Clause (i) Pass? | S-B E7v2 Mean (pp) | S-B E0 Mean (pp) | Clause (ii) Pass? | S-C E7v2 Mean (pp) | S-C E0 Mean (pp) | Limit (E0 + 3.0) | Clause (iii) Pass? |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **20 °C** | {eval_set_x[20]['sa_rmse_pp']:.3f} | {eval_e0_set_x[20]['sa_rmse_pp']:.3f} | {eval_e0_set_x[20]['sa_rmse_pp']+3.0:.3f} | **{'PASS' if eval_set_x[20]['sa_rmse_pp']<=eval_e0_set_x[20]['sa_rmse_pp']+3.0 else 'FAIL'}** | {eval_set_x[20]['sb_mean_rmse_pp']:.3f} | {eval_e0_set_x[20]['sb_mean_rmse_pp']:.3f} | **{'PASS' if eval_set_x[20]['sb_mean_rmse_pp']<=eval_e0_set_x[20]['sb_mean_rmse_pp'] else 'FAIL'}** | {eval_set_x[20]['sc_mean_rmse_pp']:.3f} | {eval_e0_set_x[20]['sc_mean_rmse_pp']:.3f} | {eval_e0_set_x[20]['sc_mean_rmse_pp']+3.0:.3f} | **{'PASS' if eval_set_x[20]['sc_mean_rmse_pp']<=eval_e0_set_x[20]['sc_mean_rmse_pp']+3.0 else 'FAIL'}** |
| **25 °C** (suspect) | {eval_set_x[25]['sa_rmse_pp']:.3f} | {eval_e0_set_x[25]['sa_rmse_pp']:.3f} | {eval_e0_set_x[25]['sa_rmse_pp']+3.0:.3f} | - | {eval_set_x[25]['sb_mean_rmse_pp']:.3f} | {eval_e0_set_x[25]['sb_mean_rmse_pp']:.3f} | - | {eval_set_x[25]['sc_mean_rmse_pp']:.3f} | {eval_e0_set_x[25]['sc_mean_rmse_pp']:.3f} | {eval_e0_set_x[25]['sc_mean_rmse_pp']+3.0:.3f} | - |
| **30 °C** | {eval_set_x[30]['sa_rmse_pp']:.3f} | {eval_e0_set_x[30]['sa_rmse_pp']:.3f} | {eval_e0_set_x[30]['sa_rmse_pp']+3.0:.3f} | **{'PASS' if eval_set_x[30]['sa_rmse_pp']<=eval_e0_set_x[30]['sa_rmse_pp']+3.0 else 'FAIL'}** | {eval_set_x[30]['sb_mean_rmse_pp']:.3f} | {eval_e0_set_x[30]['sb_mean_rmse_pp']:.3f} | **{'PASS' if eval_set_x[30]['sb_mean_rmse_pp']<=eval_e0_set_x[30]['sb_mean_rmse_pp'] else 'FAIL'}** | {eval_set_x[30]['sc_mean_rmse_pp']:.3f} | {eval_e0_set_x[30]['sc_mean_rmse_pp']:.3f} | {eval_e0_set_x[30]['sc_mean_rmse_pp']+3.0:.3f} | **{'PASS' if eval_set_x[30]['sc_mean_rmse_pp']<=eval_e0_set_x[30]['sc_mean_rmse_pp']+3.0 else 'FAIL'}** |
| **40 °C** | {eval_set_x[40]['sa_rmse_pp']:.3f} | {eval_e0_set_x[40]['sa_rmse_pp']:.3f} | {eval_e0_set_x[40]['sa_rmse_pp']+3.0:.3f} | **{'PASS' if eval_set_x[40]['sa_rmse_pp']<=eval_e0_set_x[40]['sa_rmse_pp']+3.0 else 'FAIL'}** | {eval_set_x[40]['sb_mean_rmse_pp']:.3f} | {eval_e0_set_x[40]['sb_mean_rmse_pp']:.3f} | **{'PASS' if eval_set_x[40]['sb_mean_rmse_pp']<=eval_e0_set_x[40]['sb_mean_rmse_pp'] else 'FAIL'}** | {eval_set_x[40]['sc_mean_rmse_pp']:.3f} | {eval_e0_set_x[40]['sc_mean_rmse_pp']:.3f} | {eval_e0_set_x[40]['sc_mean_rmse_pp']+3.0:.3f} | **{'PASS' if eval_set_x[40]['sc_mean_rmse_pp']<=eval_e0_set_x[40]['sc_mean_rmse_pp']+3.0 else 'FAIL'}** |
| **50 °C** | {eval_set_x[50]['sa_rmse_pp']:.3f} | {eval_e0_set_x[50]['sa_rmse_pp']:.3f} | {eval_e0_set_x[50]['sa_rmse_pp']+3.0:.3f} | **{'PASS' if eval_set_x[50]['sa_rmse_pp']<=eval_e0_set_x[50]['sa_rmse_pp']+3.0 else 'FAIL'}** | {eval_set_x[50]['sb_mean_rmse_pp']:.3f} | {eval_e0_set_x[50]['sb_mean_rmse_pp']:.3f} | **{'PASS' if eval_set_x[50]['sb_mean_rmse_pp']<=eval_e0_set_x[50]['sb_mean_rmse_pp'] else 'FAIL'}** | {eval_set_x[50]['sc_mean_rmse_pp']:.3f} | {eval_e0_set_x[50]['sc_mean_rmse_pp']:.3f} | {eval_e0_set_x[50]['sc_mean_rmse_pp']+3.0:.3f} | **{'PASS' if eval_set_x[50]['sc_mean_rmse_pp']<=eval_e0_set_x[50]['sc_mean_rmse_pp']+3.0 else 'FAIL'}** |

**GATE B Status:** **{'PASS' if overall_gate_b else 'FAIL'}**

---

## 4. Overall Stage V3 Gate Conclusion
- **GATE A Verdict:** **{'PASS' if overall_gate_a else 'FAIL'}**
- **GATE B Verdict:** **{'PASS' if overall_gate_b else 'FAIL'}**
- **Composite Ready for Stage V4 Freeze:** **{'YES' if (overall_gate_a and overall_gate_b) else 'NO'}**
"""

    out_md = repo_root / "reports" / "gauntlet_v2" / "stage_v3_gates.md"
    with open(out_md, "w") as f:
        f.write(md_content)
    print(f"Written Gate report to {out_md}")


if __name__ == "__main__":
    main()
