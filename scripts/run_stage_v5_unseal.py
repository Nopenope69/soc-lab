"""Stage V5: Single Unseal Evaluation on US06 and FUDS (Gauntlet V3).

Protocol Rules:
- Evaluates frozen candidate (E7v3 with cand_cplat_2.0e-05 parameters) and references:
  E0 (fair), E0 (oracle on Set X), E1, E2, E7v2.
- Profiles: US06 and FUDS.
- Cells: A1-007 and Set X (A1-008).
- Temperatures: 20, 30, 40, 50 C (25 C reported separately as suspect).
- Single unseal: strictly executed once. No retuning, rerunning, or reselection.
- GATE A evaluated on A1-007 across all 4 decision temperatures.
- GATE B evaluated on Set X across all 4 decision temperatures against fair E0.
- End state decision: GO if both pass on US06 and FUDS, otherwise NO-GO(unseal).
"""

from dataclasses import replace
import json
import math
from pathlib import Path
import sys
import time
from typing import Any, Callable, Dict, List
import numpy as np

repo_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo_root))

from soc.assumptions.loader import load_assumptions
from soc.estimators.base import ParamSet
from soc.estimators.e0_coulomb import E0CoulombCounting
from soc.estimators.e1_ekf import E1ExtendedKalmanFilter
from soc.estimators.e2_ekf_hysteresis import E2EKFHysteresis
from soc.estimators.e7v2 import E7V2CompositeFilter
from soc.estimators.e7v3 import E7V3CompositeFilter
from scripts.gauntlet_v3_scenarios import (
    prepare_scenario_data_v3,
    evaluate_estimator_v3,
    R3_GUARANTEE_LINE,
)

ALL_TEMPS = [20, 25, 30, 40, 50]
DECISION_TEMPS = [20, 30, 40, 50]
UNSEAL_PROFILES = ["US06", "FUDS"]

FROZEN_PARAMS = {
    "process_noise_q_soc": 2.0e-09,
    "process_noise_q_rc": 1.1198164932559382e-05,
    "process_noise_q_hysteresis": 0.00017150882346504795,
    "measurement_noise_r_v": 0.0008610323423725228,
    "e4_rls_forgetting_factor": 0.9990,
    "e5_slope_ref": 0.20,
    "e5_cap_plateau": 2.0e-05,
    "e5_cap_knee": 0.01,
    "e5_sigma_ocv_model_v": 0.02,
}

E2_TUNED_PARAMS = {
    "process_noise_q_soc": 2.9031433196504225e-08,
    "process_noise_q_rc": 1.1198164932559382e-05,
    "process_noise_q_hysteresis": 0.00017150882346504795,
    "measurement_noise_r_v": 0.0008610323423725228,
}


def build_estimator_factory(name: str, base_params: ParamSet) -> Callable[[ParamSet], Any]:
    if name == "E0_fair":
        return lambda p: E0CoulombCounting(p)
    elif name == "E0_oracle":
        return lambda p: E0CoulombCounting(p)
    elif name == "E1":
        return lambda p: E1ExtendedKalmanFilter(p)
    elif name == "E2":
        p_e2 = replace(
            base_params,
            process_noise_q_soc=E2_TUNED_PARAMS["process_noise_q_soc"],
            process_noise_q_rc=E2_TUNED_PARAMS["process_noise_q_rc"],
            process_noise_q_hysteresis=E2_TUNED_PARAMS["process_noise_q_hysteresis"],
            measurement_noise_r_v=E2_TUNED_PARAMS["measurement_noise_r_v"],
        )
        return lambda p: E2EKFHysteresis(replace(p, **E2_TUNED_PARAMS))
    elif name == "E7v2":
        p_v2 = replace(
            base_params,
            **E2_TUNED_PARAMS,
            e4_rls_forgetting_factor=0.999,
            e5_slope_ref=0.2,
            e5_cap_plateau=1e-5,
            e5_cap_knee=0.01,
            e5_sigma_ocv_model_v=0.02,
        )
        return lambda p: E7V2CompositeFilter(replace(p, **E2_TUNED_PARAMS, e4_rls_forgetting_factor=0.999, e5_slope_ref=0.2, e5_cap_plateau=1e-5, e5_cap_knee=0.01, e5_sigma_ocv_model_v=0.02))
    elif name == "E7v3":
        def factory(p_in: ParamSet) -> E7V3CompositeFilter:
            p = replace(p_in, **FROZEN_PARAMS)
            return E7V3CompositeFilter(p)
        return factory
    else:
        raise ValueError(f"Unknown estimator {name}")


def evaluate_gate_a(eval_cand: Dict[str, Any], eval_e0: Dict[str, Any], eval_e1: Dict[str, Any]) -> Dict[str, Any]:
    """Evaluate GATE A on Cell A1-007 across all 4 decision temperatures (20, 30, 40, 50 C)."""
    # Clause (i): S-A RMSE <= E0 + 2.0 pp AND <= E1 + 1.0 pp (mean across 4 decision temps)
    sa_cand_mean = float(np.mean([eval_cand[str(t)]["sa_rmse_pp"] for t in DECISION_TEMPS]))
    sa_e0_mean = float(np.mean([eval_e0[str(t)]["sa_rmse_pp"] for t in DECISION_TEMPS]))
    sa_e1_mean = float(np.mean([eval_e1[str(t)]["sa_rmse_pp"] for t in DECISION_TEMPS]))
    bar_sa_e0 = sa_e0_mean + 2.0
    bar_sa_e1 = sa_e1_mean + 1.0
    pass_i = (sa_cand_mean <= bar_sa_e0) and (sa_cand_mean <= bar_sa_e1)

    # Clause (ii-a): S-B group-mean RMSE <= 0.70 x E0 group-mean AND beats E0 in >= 80% of S-B cases
    sb_cand_all = []
    sb_e0_all = []
    for t in DECISION_TEMPS:
        sb_cand_all.extend(eval_cand[str(t)]["sb_rmses"])
        sb_e0_all.extend(eval_e0[str(t)]["sb_rmses"])
    sb_cand_mean = float(np.mean(sb_cand_all))
    sb_e0_mean = float(np.mean(sb_e0_all))
    bar_sb = 0.70 * sb_e0_mean
    sb_wins = sum(1 for c, e in zip(sb_cand_all, sb_e0_all) if c < e)
    win_rate = sb_wins / len(sb_cand_all)
    pass_iia = (sb_cand_mean <= bar_sb) and (win_rate >= 0.80)

    # Clause (ii-b): S-C mean RMSE per temperature <= E0 + 1.5 pp at each decision temperature
    pass_iib = True
    sc_details = {}
    for t in DECISION_TEMPS:
        sc_c = eval_cand[str(t)]["sc_mean_rmse_pp"]
        sc_e = eval_e0[str(t)]["sc_mean_rmse_pp"]
        bar = sc_e + 1.5
        p = sc_c <= bar
        sc_details[str(t)] = {"cand": sc_c, "bar": bar, "pass": p}
        if not p:
            pass_iib = False

    # Clause (ii-c): S-G mean RMSE per temperature <= E0 + 1.0 pp at each decision temperature
    pass_iic = True
    sg_details = {}
    for t in DECISION_TEMPS:
        sg_c = eval_cand[str(t)]["sg_mean_rmse_pp"]
        sg_e = eval_e0[str(t)]["sg_mean_rmse_pp"]
        bar = sg_e + 1.0
        p = sg_c <= bar
        sg_details[str(t)] = {"cand": sg_c, "bar": bar, "pass": p}
        if not p:
            pass_iic = False

    # Clause (iii): S-F mean RMSE <= E0 + 5.0 pp
    sf_cand_mean = float(np.mean([eval_cand[str(t)]["sf_mean_rmse_pp"] for t in DECISION_TEMPS]))
    sf_e0_mean = float(np.mean([eval_e0[str(t)]["sf_mean_rmse_pp"] for t in DECISION_TEMPS]))
    bar_sf = sf_e0_mean + 5.0
    pass_iii = (sf_cand_mean <= bar_sf)

    gate_a_pass = pass_i and pass_iia and pass_iib and pass_iic and pass_iii

    return {
        "pass": gate_a_pass,
        "clause_i": {"pass": pass_i, "sa_cand_mean": sa_cand_mean, "bar_e0": bar_sa_e0, "bar_e1": bar_sa_e1},
        "clause_iia": {"pass": pass_iia, "sb_cand_mean": sb_cand_mean, "bar_sb": bar_sb, "wins": sb_wins, "total": len(sb_cand_all), "win_rate": win_rate},
        "clause_iib": {"pass": pass_iib, "details": sc_details},
        "clause_iic": {"pass": pass_iic, "details": sg_details},
        "clause_iii": {"pass": pass_iii, "sf_cand_mean": sf_cand_mean, "bar_sf": bar_sf},
    }


def evaluate_gate_b(eval_cand: Dict[str, Any], eval_e0: Dict[str, Any]) -> Dict[str, Any]:
    """Evaluate GATE B on Set X / A1-008 across all 4 decision temperatures against Fair E0."""
    # Clause (i): S-A <= E0 + 3.0 pp at each temperature
    pass_i = True
    sa_details = {}
    for t in DECISION_TEMPS:
        c = eval_cand[str(t)]["sa_rmse_pp"]
        e = eval_e0[str(t)]["sa_rmse_pp"]
        bar = e + 3.0
        p = c <= bar
        sa_details[str(t)] = {"cand": c, "bar": bar, "pass": p}
        if not p:
            pass_i = False

    # Clause (ii): S-B group-mean <= E0 group-mean at every temperature
    pass_ii = True
    sb_details = {}
    for t in DECISION_TEMPS:
        c = eval_cand[str(t)]["sb_mean_rmse_pp"]
        e = eval_e0[str(t)]["sb_mean_rmse_pp"]
        p = c <= e
        sb_details[str(t)] = {"cand": c, "bar": e, "pass": p}
        if not p:
            pass_ii = False

    # Clause (iii): S-C mean <= E0 + 3.0 pp at each temperature
    pass_iii = True
    sc_details = {}
    for t in DECISION_TEMPS:
        c = eval_cand[str(t)]["sc_mean_rmse_pp"]
        e = eval_e0[str(t)]["sc_mean_rmse_pp"]
        bar = e + 3.0
        p = c <= bar
        sc_details[str(t)] = {"cand": c, "bar": bar, "pass": p}
        if not p:
            pass_iii = False

    # Clause (iv): S-G mean <= E0 + 1.5 pp at each temperature
    pass_iv = True
    sg_details = {}
    for t in DECISION_TEMPS:
        c = eval_cand[str(t)]["sg_mean_rmse_pp"]
        e = eval_e0[str(t)]["sg_mean_rmse_pp"]
        bar = e + 1.5
        p = c <= bar
        sg_details[str(t)] = {"cand": c, "bar": bar, "pass": p}
        if not p:
            pass_iv = False

    gate_b_pass = pass_i and pass_ii and pass_iii and pass_iv

    return {
        "pass": gate_b_pass,
        "clause_i": {"pass": pass_i, "details": sa_details},
        "clause_ii": {"pass": pass_ii, "details": sb_details},
        "clause_iii": {"pass": pass_iii, "details": sc_details},
        "clause_iv": {"pass": pass_iv, "details": sg_details},
    }


def run_stage_v5():
    print("=" * 80)
    print("STAGE V5: SINGLE UNSEAL (US06 and FUDS)")
    print(f"R3 Guarantee: {R3_GUARANTEE_LINE}")
    print("=" * 80)

    start_time = time.time()
    assumptions, _, _ = load_assumptions(profile="calce_a123_v4")
    base_params = ParamSet.from_assumptions(assumptions, matched=True)

    estimators = ["E0_fair", "E0_oracle", "E1", "E2", "E7v2", "E7v3"]
    cells = ["A1-007", "A1-008"]

    results: Dict[str, Any] = {
        "metadata": {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "profiles": UNSEAL_PROFILES,
            "frozen_commit": "394b337",
            "frozen_params": FROZEN_PARAMS,
        },
        "evaluations": {},
        "gates": {},
    }

    # Evaluate each profile
    for prof in UNSEAL_PROFILES:
        print(f"\n" + "#" * 80)
        print(f"UNSEALING PROFILE: {prof}")
        print("#" * 80)

        results["evaluations"][prof] = {}
        for cell in cells:
            results["evaluations"][prof][cell] = {}

        # Pre-load datasets for this profile
        print(f"Loading datasets for {prof}...")
        sc_data: Dict[str, Dict[int, Any]] = {c: {} for c in cells}
        for cell in cells:
            for t in ALL_TEMPS:
                sc_data[cell][t] = prepare_scenario_data_v3(t, profile=prof, cell_id=cell)
        print(f"Datasets loaded for {prof}.")

        # Evaluate estimators
        for est_name in estimators:
            factory = build_estimator_factory(est_name, base_params)
            for cell in cells:
                # E0_oracle only runs on Set X
                if est_name == "E0_oracle" and cell != "A1-008":
                    continue

                is_oracle = (est_name == "E0_oracle")
                results["evaluations"][prof][cell][est_name] = {}

                print(f"Evaluating {est_name} on {cell} [{prof}]...", flush=True)
                for t in ALL_TEMPS:
                    t0 = time.time()
                    sc = sc_data[cell][t]
                    r = evaluate_estimator_v3(factory, base_params, sc, is_oracle_e0=is_oracle)
                    results["evaluations"][prof][cell][est_name][str(t)] = r
                    print(
                        f"  {t} C ({time.time()-t0:.1f}s) | "
                        f"SA: {r['sa_rmse_pp']:.3f} pp | "
                        f"SB: {r['sb_mean_rmse_pp']:.3f} pp | "
                        f"SC: {r['sc_mean_rmse_pp']:.3f} pp | "
                        f"SG: {r['sg_mean_rmse_pp']:.3f} pp | "
                        f"SF: {r['sf_mean_rmse_pp']:.3f} pp",
                        flush=True,
                    )

        # Gate Evaluation for this profile
        print(f"\n--- GATE EVALUATION FOR {prof} ---")
        eval_007 = results["evaluations"][prof]["A1-007"]
        eval_008 = results["evaluations"][prof]["A1-008"]

        gate_a_res = evaluate_gate_a(eval_007["E7v3"], eval_007["E0_fair"], eval_007["E1"])
        gate_b_res = evaluate_gate_b(eval_008["E7v3"], eval_008["E0_fair"])

        results["gates"][prof] = {
            "gate_a": gate_a_res,
            "gate_b": gate_b_res,
            "both_pass": gate_a_res["pass"] and gate_b_res["pass"],
        }

        print(f"[{prof}] GATE A PASS: {gate_a_res['pass']}")
        print(f"[{prof}] GATE B PASS: {gate_b_res['pass']}")
        print(f"[{prof}] PROFILE PASS: {results['gates'][prof]['both_pass']}")

    # Overall Single Unseal Verdict
    us06_pass = results["gates"]["US06"]["both_pass"]
    fuds_pass = results["gates"]["FUDS"]["both_pass"]
    overall_unseal_go = us06_pass and fuds_pass

    results["verdict"] = {
        "us06_pass": us06_pass,
        "fuds_pass": fuds_pass,
        "overall_status": "GO" if overall_unseal_go else "NO-GO(unseal)",
    }

    print("\n" + "=" * 80)
    print(f"FINAL STAGE V5 UNSEAL VERDICT: {results['verdict']['overall_status']}")
    print(f"  US06 Gate A & Gate B: {'PASS' if us06_pass else 'FAIL'}")
    print(f"  FUDS Gate A & Gate B: {'PASS' if fuds_pass else 'FAIL'}")
    print("=" * 80)

    total_time = time.time() - start_time
    results["total_runtime_s"] = total_time

    # Save results json
    out_json = repo_root / "reports" / "gauntlet_v3" / "stage_v5_unseal.json"
    with open(out_json, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nSaved complete unseal results to {out_json}")

    return results


if __name__ == "__main__":
    run_stage_v5()
