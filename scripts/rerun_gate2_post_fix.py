"""Rerun Stage 2 GATE 2 Evaluation Post-Fix.

Evaluates GATE 2 clauses (i), (ii), and (iii) for E7 using frozen tuned parameters
against the fixed E0 baseline and E1 baseline on held-out DST (40 & 50 °C),
reporting 20, 25, 30 °C as well.
"""

from pathlib import Path
import pickle
import sys
import numpy as np
import pandas as pd

repo_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo_root))

from soc.assumptions.loader import load_assumptions
from soc.estimators.base import ParamSet
from soc.estimators.e0_coulomb import E0CoulombCounting
from soc.estimators.e1_ekf import E1ExtendedKalmanFilter
from soc.estimators.e2_ekf_hysteresis import E2EKFHysteresis
from scripts.gauntlet_scenarios import prepare_scenario_data, evaluate_estimator_on_scenarios
from dataclasses import replace

def rerun_gate2():
    assumptions, _, _ = load_assumptions(profile="calce_a123_v3")
    base_params = ParamSet.from_assumptions(assumptions, matched=True)
    with open(repo_root / "reports" / "gauntlet" / ".stage2_checkpoint.pkl", "rb") as f:
        cp = pickle.load(f)
    p_e7 = cp["best_by_estimator"]["E2"]["params"]

    def e0_factory(p):
        return E0CoulombCounting(replace(p, anchor_enabled=False, rest_anchor_enabled=False))

    def e1_factory(p):
        return E1ExtendedKalmanFilter(p)

    def e7_factory(p):
        return E2EKFHysteresis(p_e7)

    temps = [20, 25, 30, 40, 50]
    res_e0 = {}
    res_e1 = {}
    res_e7 = {}

    for t in temps:
        d = prepare_scenario_data(t, profile="DST")
        res_e0[t] = evaluate_estimator_on_scenarios(e0_factory, base_params, d)
        res_e1[t] = evaluate_estimator_on_scenarios(e1_factory, base_params, d)
        res_e7[t] = evaluate_estimator_on_scenarios(e7_factory, p_e7, d)

    # Held-out averages (40 and 50 C)
    held_e0_sa = (res_e0[40]["sa_rmse_pp"] + res_e0[50]["sa_rmse_pp"]) / 2.0
    held_e1_sa = (res_e1[40]["sa_rmse_pp"] + res_e1[50]["sa_rmse_pp"]) / 2.0
    held_e7_sa = (res_e7[40]["sa_rmse_pp"] + res_e7[50]["sa_rmse_pp"]) / 2.0

    held_e0_bcd = (res_e0[40]["bcd_mean_rmse_pp"] + res_e0[50]["bcd_mean_rmse_pp"]) / 2.0
    held_e7_bcd = (res_e7[40]["bcd_mean_rmse_pp"] + res_e7[50]["bcd_mean_rmse_pp"]) / 2.0

    held_e0_sf = (res_e0[40]["sf_mean_rmse_pp"] + res_e0[50]["sf_mean_rmse_pp"]) / 2.0
    held_e7_sf = (res_e7[40]["sf_mean_rmse_pp"] + res_e7[50]["sf_mean_rmse_pp"]) / 2.0

    all_e0_bcd_rmses = res_e0[40]["bcd_all_rmses"] + res_e0[50]["bcd_all_rmses"]
    all_e7_bcd_rmses = res_e7[40]["bcd_all_rmses"] + res_e7[50]["bcd_all_rmses"]
    wins = sum(e7 < e0 for e7, e0 in zip(all_e7_bcd_rmses, all_e0_bcd_rmses))
    n_cases = len(all_e0_bcd_rmses)
    win_pct = (wins / n_cases) * 100.0

    # Gate 2 Evaluation
    thresh_clause_i_e0 = held_e0_sa + 5.0
    thresh_clause_i_e1 = held_e1_sa + 1.0
    pass_clause_i = (held_e7_sa <= thresh_clause_i_e0) and (held_e7_sa <= thresh_clause_i_e1)

    thresh_clause_ii_mean = 0.70 * held_e0_bcd
    pass_clause_ii_mean = held_e7_bcd <= thresh_clause_ii_mean
    pass_clause_ii_wins = win_pct >= 80.0
    pass_clause_ii = pass_clause_ii_mean and pass_clause_ii_wins

    thresh_clause_iii = held_e0_sf + 5.0
    pass_clause_iii = held_e7_sf <= thresh_clause_iii

    overall_pass = pass_clause_i and pass_clause_ii and pass_clause_iii

    print("=== GATE 2 RE-EVALUATION RESULTS (POST-E0 FIX) ===")
    print(f"Held-out S-A RMSE: E0 = {held_e0_sa:.4f} pp, E1 = {held_e1_sa:.4f} pp, E7 = {held_e7_sa:.4f} pp")
    print(f"  Clause (i): E7 <= E0+5 ({thresh_clause_i_e0:.4f}) AND <= E1+1 ({thresh_clause_i_e1:.4f}) -> {'PASS' if pass_clause_i else 'FAIL'}")
    print(f"Held-out BCD Mean RMSE: E0 = {held_e0_bcd:.4f} pp, E7 = {held_e7_bcd:.4f} pp")
    print(f"  Clause (ii) Mean: E7 <= 0.70*E0 ({thresh_clause_ii_mean:.4f}) -> {'PASS' if pass_clause_ii_mean else 'FAIL'}")
    print(f"  Clause (ii) Wins: {wins} / {n_cases} ({win_pct:.2f}%) vs >= 80.0% -> {'PASS' if pass_clause_ii_wins else 'FAIL'}")
    print(f"  Clause (ii) Overall: {'PASS' if pass_clause_ii else 'FAIL'}")
    print(f"Held-out S-F Mean RMSE: E0 = {held_e0_sf:.4f} pp, E7 = {held_e7_sf:.4f} pp")
    print(f"  Clause (iii): E7 <= E0+5 ({thresh_clause_iii:.4f}) -> {'PASS' if pass_clause_iii else 'FAIL'}")
    print(f"OVERALL GATE 2 STATUS: {'PASS' if overall_pass else 'FAIL (NO-GO)'}")

    # Save to CSV
    row = {
        "e0_heldout_sa_pp": held_e0_sa,
        "e1_heldout_sa_pp": held_e1_sa,
        "e7_heldout_sa_pp": held_e7_sa,
        "clause_i_pass": pass_clause_i,
        "e0_heldout_bcd_pp": held_e0_bcd,
        "e7_heldout_bcd_pp": held_e7_bcd,
        "clause_ii_mean_pass": pass_clause_ii_mean,
        "clause_ii_wins": wins,
        "clause_ii_total_cases": n_cases,
        "clause_ii_win_pct": win_pct,
        "clause_ii_pass": pass_clause_ii,
        "e0_heldout_sf_pp": held_e0_sf,
        "e7_heldout_sf_pp": held_e7_sf,
        "clause_iii_pass": pass_clause_iii,
        "overall_gate2_pass": overall_pass,
    }
    pd.DataFrame([row]).to_csv(repo_root / "reports" / "gauntlet" / "gate2_post_fix_results.csv", index=False)

if __name__ == "__main__":
    rerun_gate2()
