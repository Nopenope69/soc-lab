"""Compute Reference Baseline for Gauntlet V2 Keep Rule.

Evaluates E0 and tuned E2 (tune_2 from Stage 1/V1:
  q_soc=2.9031e-08, q_rc=1.1198e-05, q_hyst=1.7151e-04, r_v=8.6103e-04)
on the Stage V1 model (calce_a123_v4.yaml) across:
1. A1-007 (DST): 20, 25, 30, 40, 50 C
2. Cross-cell Set X (A1-008 DST with A1-007 parameters): 20, 25, 30, 40, 50 C

Outputs:
- reports/gauntlet_v2/baseline_reference.json
- Printed summary tables with exact metrics.
"""

from dataclasses import replace
import json
from pathlib import Path
import sys
import numpy as np

repo_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo_root))

from soc.assumptions.loader import load_assumptions
from soc.estimators.base import ParamSet
from soc.estimators.e0_coulomb import E0CoulombCounting
from soc.estimators.e2_ekf_hysteresis import E2EKFHysteresis
from scripts.gauntlet_v2_scenarios import (
    prepare_scenario_data_v2,
    evaluate_estimator_v2,
    R3_GUARANTEE_LINE,
)

ALL_TEMPS = [20, 25, 30, 40, 50]
DECISION_TEMPS = [20, 30, 40, 50]
HELDOUT_TEMPS = [40, 50]

# Tuned E2 parameters from V1 Stage 2
E2_TUNED_PARAMS = {
    "process_noise_q_soc": 2.9031433196504225e-08,
    "process_noise_q_rc": 1.1198164932559382e-05,
    "process_noise_q_hysteresis": 0.00017150882346504795,
    "measurement_noise_r_v": 0.0008610323423725228,
}


def build_e2_params(base_params: ParamSet) -> ParamSet:
    return replace(
        base_params,
        process_noise_q_soc=E2_TUNED_PARAMS["process_noise_q_soc"],
        process_noise_q_rc=E2_TUNED_PARAMS["process_noise_q_rc"],
        process_noise_q_hysteresis=E2_TUNED_PARAMS["process_noise_q_hysteresis"],
        measurement_noise_r_v=E2_TUNED_PARAMS["measurement_noise_r_v"],
    )


def main():
    print("=" * 80)
    print("GAUNTLET V2: COMPUTING REFERENCE BASELINE (TUNED E2 & E0)")
    print(f"R3 Guarantee: {R3_GUARANTEE_LINE}")
    print("=" * 80)

    # Load frozen plant profile calce_a123_v4.yaml
    assumptions, _, _ = load_assumptions(profile="calce_a123_v4")
    base_params_raw = ParamSet.from_assumptions(assumptions, matched=True)
    base_params_e2 = build_e2_params(base_params_raw)

    results = {
        "A1-007": {"E0": {}, "E2_tuned": {}},
        "Set_X": {"E0": {}, "E2_tuned": {}},
    }

    # 1. Evaluate on A1-007
    print("\n--- Evaluating A1-007 (Primary Cell) ---")
    for t in ALL_TEMPS:
        suspect_tag = " (SUSPECT - REPORT ONLY)" if t == 25 else ""
        print(f"\nLoading A1-007 DST at {t}C{suspect_tag}...")
        ds = prepare_scenario_data_v2(t, profile="DST", cell_id="A1-007", profile_name="calce_a123_v4")

        # E0
        res_e0 = evaluate_estimator_v2(lambda p: E0CoulombCounting(p), base_params_raw, ds)
        results["A1-007"]["E0"][str(t)] = res_e0
        print(
            f"  [A1-007 {t}C E0] S-A: {res_e0['sa_rmse_pp']:.3f} pp | S-B: {res_e0['sb_mean_rmse_pp']:.3f} pp | "
            f"S-C: {res_e0['sc_mean_rmse_pp']:.3f} pp | SBC: {res_e0['sbc_mean_rmse_pp']:.3f} pp | "
            f"S-F worst: {res_e0['sf_worst_err_pp']:.3f} pp"
        )

        # Tuned E2
        res_e2 = evaluate_estimator_v2(lambda p: E2EKFHysteresis(p), base_params_e2, ds)
        results["A1-007"]["E2_tuned"][str(t)] = res_e2
        print(
            f"  [A1-007 {t}C E2] S-A: {res_e2['sa_rmse_pp']:.3f} pp | S-B: {res_e2['sb_mean_rmse_pp']:.3f} pp | "
            f"S-C: {res_e2['sc_mean_rmse_pp']:.3f} pp | SBC: {res_e2['sbc_mean_rmse_pp']:.3f} pp | "
            f"S-F worst: {res_e2['sf_worst_err_pp']:.3f} pp"
        )

    # 2. Evaluate on Cross-cell Set X (A1-008 with A1-007 parameters)
    print("\n--- Evaluating Cross-cell Set X (A1-008 DST with A1-007 parameters) ---")
    for t in ALL_TEMPS:
        suspect_tag = " (SUSPECT - REPORT ONLY)" if t == 25 else ""
        print(f"\nLoading A1-008 DST at {t}C{suspect_tag}...")
        ds_x = prepare_scenario_data_v2(t, profile="DST", cell_id="A1-008", profile_name="calce_a123_v4")

        # E0 (uses A1-008 Q(T))
        res_e0_x = evaluate_estimator_v2(lambda p: E0CoulombCounting(p), base_params_raw, ds_x)
        results["Set_X"]["E0"][str(t)] = res_e0_x
        print(
            f"  [Set X {t}C E0] S-A: {res_e0_x['sa_rmse_pp']:.3f} pp | S-B: {res_e0_x['sb_mean_rmse_pp']:.3f} pp | "
            f"S-C: {res_e0_x['sc_mean_rmse_pp']:.3f} pp | SBC: {res_e0_x['sbc_mean_rmse_pp']:.3f} pp | "
            f"S-F worst: {res_e0_x['sf_worst_err_pp']:.3f} pp"
        )

        # Tuned E2 (A1-007 parameters on A1-008 data)
        res_e2_x = evaluate_estimator_v2(lambda p: E2EKFHysteresis(p), base_params_e2, ds_x)
        results["Set_X"]["E2_tuned"][str(t)] = res_e2_x
        print(
            f"  [Set X {t}C E2] S-A: {res_e2_x['sa_rmse_pp']:.3f} pp | S-B: {res_e2_x['sb_mean_rmse_pp']:.3f} pp | "
            f"S-C: {res_e2_x['sc_mean_rmse_pp']:.3f} pp | SBC: {res_e2_x['sbc_mean_rmse_pp']:.3f} pp | "
            f"S-F worst: {res_e2_x['sf_worst_err_pp']:.3f} pp"
        )

    # Compute summary aggregates for Keep Rule reference
    # A1-007 held-out (40, 50 C)
    a1_007_heldout_sbc = float(np.mean([
        results["A1-007"]["E2_tuned"][str(t)]["sbc_mean_rmse_pp"] for t in HELDOUT_TEMPS
    ]))
    a1_007_heldout_sa = float(np.mean([
        results["A1-007"]["E2_tuned"][str(t)]["sa_rmse_pp"] for t in HELDOUT_TEMPS
    ]))
    a1_007_heldout_sf_worst = float(np.max([
        results["A1-007"]["E2_tuned"][str(t)]["sf_worst_err_pp"] for t in HELDOUT_TEMPS
    ]))

    # Set X held-out (40, 50 C)
    set_x_heldout_sbc = float(np.mean([
        results["Set_X"]["E2_tuned"][str(t)]["sbc_mean_rmse_pp"] for t in HELDOUT_TEMPS
    ]))
    set_x_heldout_sa = float(np.mean([
        results["Set_X"]["E2_tuned"][str(t)]["sa_rmse_pp"] for t in HELDOUT_TEMPS
    ]))
    set_x_heldout_sf_worst = float(np.max([
        results["Set_X"]["E2_tuned"][str(t)]["sf_worst_err_pp"] for t in HELDOUT_TEMPS
    ]))

    summary = {
        "A1_007_heldout_sbc_mean_rmse_pp": a1_007_heldout_sbc,
        "A1_007_heldout_sa_mean_rmse_pp": a1_007_heldout_sa,
        "A1_007_heldout_sf_worst_pp": a1_007_heldout_sf_worst,
        "Set_X_heldout_sbc_mean_rmse_pp": set_x_heldout_sbc,
        "Set_X_heldout_sa_mean_rmse_pp": set_x_heldout_sa,
        "Set_X_heldout_sf_worst_pp": set_x_heldout_sf_worst,
    }
    results["summary_keep_rule_reference"] = summary

    out_file = repo_root / "reports" / "gauntlet_v2" / "baseline_reference.json"
    with open(out_file, "w") as f:
        json.dump(results, f, indent=2)

    print("\n" + "=" * 80)
    print("SUMMARY KEEP RULE REFERENCE (TUNED E2 ON V1 MODEL):")
    print(f"  A1-007 Held-out (40, 50C) Mean SBC RMSE : {a1_007_heldout_sbc:.4f} pp")
    print(f"  A1-007 Held-out (40, 50C) Mean S-A RMSE : {a1_007_heldout_sa:.4f} pp")
    print(f"  A1-007 Held-out (40, 50C) S-F Worst Err : {a1_007_heldout_sf_worst:.4f} pp")
    print(f"  Set X  Held-out (40, 50C) Mean SBC RMSE : {set_x_heldout_sbc:.4f} pp")
    print(f"  Set X  Held-out (40, 50C) Mean S-A RMSE : {set_x_heldout_sa:.4f} pp")
    print(f"  Set X  Held-out (40, 50C) S-F Worst Err : {set_x_heldout_sf_worst:.4f} pp")
    print(f"Saved baseline reference to {out_file}")
    print("=" * 80)


if __name__ == "__main__":
    main()
