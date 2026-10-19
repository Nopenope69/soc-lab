"""Evaluate a candidate component in Gauntlet V2 against the Keep Rule.

Usage:
  python scripts/evaluate_v2_component.py --component D1
  python scripts/evaluate_v2_component.py --component D2
  python scripts/evaluate_v2_component.py --component D3
"""

import argparse
from dataclasses import replace
import json
from pathlib import Path
import sys
import numpy as np

repo_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo_root))

from soc.assumptions.loader import load_assumptions
from soc.estimators.base import ParamSet
from soc.estimators.e5v4 import E5V4ObservabilityEKF
from soc.estimators.e4v2_rls import E4V2RLSEKF
from soc.estimators.innovation_gating import D3InnovationGatedEKF
from scripts.gauntlet_v2_scenarios import (
    prepare_scenario_data_v2,
    evaluate_estimator_v2,
    R3_GUARANTEE_LINE,
)

ALL_TEMPS = [20, 25, 30, 40, 50]
HELDOUT_TEMPS = [40, 50]

# Frozen core filter tunings (E2 tune_2)
E2_TUNED_PARAMS = {
    "process_noise_q_soc": 2.9031433196504225e-08,
    "process_noise_q_rc": 1.1198164932559382e-05,
    "process_noise_q_hysteresis": 0.00017150882346504795,
    "measurement_noise_r_v": 0.0008610323423725228,
}


def load_baseline():
    baseline_path = repo_root / "reports" / "gauntlet_v2" / "baseline_reference.json"
    with open(baseline_path, "r") as f:
        return json.load(f)["summary_keep_rule_reference"]


def get_factory(component: str, base_params: ParamSet, extra_kwargs=None):
    if extra_kwargs is None:
        extra_kwargs = {}
    p = replace(
        base_params,
        process_noise_q_soc=E2_TUNED_PARAMS["process_noise_q_soc"],
        process_noise_q_rc=E2_TUNED_PARAMS["process_noise_q_rc"],
        process_noise_q_hysteresis=E2_TUNED_PARAMS["process_noise_q_hysteresis"],
        measurement_noise_r_v=E2_TUNED_PARAMS["measurement_noise_r_v"],
    )
    if component == "D1":
        # e5v4
        c_plat = extra_kwargs.get("c_plat", p.e5_cap_plateau if p.e5_cap_plateau > 0 else 1e-5)
        c_knee = extra_kwargs.get("c_knee", p.e5_cap_knee if p.e5_cap_knee > 0 else 0.01)
        sl_ref = extra_kwargs.get("sl_ref", p.e5_slope_ref if p.e5_slope_ref > 0 else 0.2)
        p_d1 = replace(p, e5_cap_plateau=c_plat, e5_cap_knee=c_knee, e5_slope_ref=sl_ref)
        return lambda params: E5V4ObservabilityEKF(p_d1)
    elif component == "D2":
        # e4v2
        ff = extra_kwargs.get("ff", p.e4_rls_forgetting_factor)
        p_d2 = replace(p, e4_rls_forgetting_factor=ff)
        return lambda params: E4V2RLSEKF(p_d2)
    elif component == "D3":
        # innovation gating
        k_gate = extra_kwargs.get("k_gate", 2.5)
        sl_th = extra_kwargs.get("sl_th", 0.1)
        p_th = extra_kwargs.get("p_th", 0.0004)
        def factory(params):
            est = D3InnovationGatedEKF(params)
            est.k_gate = k_gate
            est.slope_threshold = sl_th
            est.p_soc_threshold = p_th
            return est
        return factory
    else:
        raise ValueError(f"Unknown component {component}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--component", type=str, required=True, choices=["D1", "D2", "D3"])
    parser.add_argument("--extra-json", type=str, default="{}")
    args = parser.parse_args()

    extra_kwargs = json.loads(args.extra_json)
    base_ref = load_baseline()

    print("=" * 80)
    print(f"EVALUATING COMPONENT {args.component} AGAINST KEEP RULE")
    print(f"R3 Guarantee: {R3_GUARANTEE_LINE}")
    print(f"Extra config: {extra_kwargs}")
    print("=" * 80)

    assumptions, _, _ = load_assumptions(profile="calce_a123_v4")
    base_params = ParamSet.from_assumptions(assumptions, matched=True)
    factory = get_factory(args.component, base_params, extra_kwargs)

    res_a1_007 = {}
    res_set_x = {}

    # Evaluate A1-007
    print("\n--- Evaluating on A1-007 ---")
    for t in ALL_TEMPS:
        suspect_tag = " (SUSPECT - REPORT ONLY)" if t == 25 else ""
        ds = prepare_scenario_data_v2(t, profile="DST", cell_id="A1-007", profile_name="calce_a123_v4")
        eval_res = evaluate_estimator_v2(factory, base_params, ds)
        res_a1_007[str(t)] = eval_res
        print(
            f"  [A1-007 {t}C{suspect_tag}] S-A: {eval_res['sa_rmse_pp']:.3f} pp | "
            f"S-B: {eval_res['sb_mean_rmse_pp']:.3f} pp | S-C: {eval_res['sc_mean_rmse_pp']:.3f} pp | "
            f"SBC: {eval_res['sbc_mean_rmse_pp']:.3f} pp | S-F worst: {eval_res['sf_worst_err_pp']:.3f} pp"
        )

    # Evaluate Set X
    print("\n--- Evaluating on Set X (A1-008 with A1-007 params) ---")
    for t in ALL_TEMPS:
        suspect_tag = " (SUSPECT - REPORT ONLY)" if t == 25 else ""
        ds_x = prepare_scenario_data_v2(t, profile="DST", cell_id="A1-008", profile_name="calce_a123_v4")
        eval_res_x = evaluate_estimator_v2(factory, base_params, ds_x)
        res_set_x[str(t)] = eval_res_x
        print(
            f"  [Set X {t}C{suspect_tag}] S-A: {eval_res_x['sa_rmse_pp']:.3f} pp | "
            f"S-B: {eval_res_x['sb_mean_rmse_pp']:.3f} pp | S-C: {eval_res_x['sc_mean_rmse_pp']:.3f} pp | "
            f"SBC: {eval_res_x['sbc_mean_rmse_pp']:.3f} pp | S-F worst: {eval_res_x['sf_worst_err_pp']:.3f} pp"
        )

    # Compute held-out aggregates
    a1_007_sbc = float(np.mean([res_a1_007[str(t)]["sbc_mean_rmse_pp"] for t in HELDOUT_TEMPS]))
    a1_007_sa = float(np.mean([res_a1_007[str(t)]["sa_rmse_pp"] for t in HELDOUT_TEMPS]))
    a1_007_sf_worst = float(np.max([res_a1_007[str(t)]["sf_worst_err_pp"] for t in HELDOUT_TEMPS]))

    set_x_sbc = float(np.mean([res_set_x[str(t)]["sbc_mean_rmse_pp"] for t in HELDOUT_TEMPS]))
    set_x_sa = float(np.mean([res_set_x[str(t)]["sa_rmse_pp"] for t in HELDOUT_TEMPS]))
    set_x_sf_worst = float(np.max([res_set_x[str(t)]["sf_worst_err_pp"] for t in HELDOUT_TEMPS]))

    # Relative improvements/worsening
    ref_007_sbc = base_ref["A1_007_heldout_sbc_mean_rmse_pp"]
    ref_007_sa = base_ref["A1_007_heldout_sa_mean_rmse_pp"]
    ref_007_sf_worst = base_ref["A1_007_heldout_sf_worst_pp"]

    ref_x_sbc = base_ref["Set_X_heldout_sbc_mean_rmse_pp"]
    ref_x_sa = base_ref["Set_X_heldout_sa_mean_rmse_pp"]
    ref_x_sf_worst = base_ref["Set_X_heldout_sf_worst_pp"]

    rel_diff_007_sbc = (a1_007_sbc - ref_007_sbc) / ref_007_sbc  # negative is improvement
    rel_diff_x_sbc = (set_x_sbc - ref_x_sbc) / ref_x_sbc

    diff_007_sa = a1_007_sa - ref_007_sa
    diff_007_sf_worst = a1_007_sf_worst - ref_007_sf_worst

    # Check Keep Rule clauses:
    # (1) mean RMSE over S-B and S-C improves by >= 10% RELATIVE on A1-007 held-out (40, 50 C) OR on cross-cell set X (40, 50 C)
    c1_007_pass = (rel_diff_007_sbc <= -0.10)
    c1_x_pass = (rel_diff_x_sbc <= -0.10)
    c1_pass = c1_007_pass or c1_x_pass

    # (2) does not worsen the other set by more than 5% relative
    if c1_007_pass and not c1_x_pass:
        c2_pass = (rel_diff_x_sbc <= 0.05)
    elif c1_x_pass and not c1_007_pass:
        c2_pass = (rel_diff_007_sbc <= 0.05)
    else:  # both pass c1 or neither
        c2_pass = (rel_diff_007_sbc <= 0.05) and (rel_diff_x_sbc <= 0.05)

    # (3) S-A on A1-007 does not worsen by more than 0.3 pp
    c3_pass = (diff_007_sa <= 0.30)

    # (4) S-F worst-case error does not increase by more than 2 pp
    c4_pass = (diff_007_sf_worst <= 2.0)

    keep_verdict = c1_pass and c2_pass and c3_pass and c4_pass
    status_str = "KEEP" if keep_verdict else "DROP"

    print("\n" + "=" * 80)
    print(f"KEEP RULE VERDICT FOR {args.component}: {status_str}")
    print("=" * 80)
    print(f"  Reference A1-007 Held-out SBC: {ref_007_sbc:.4f} pp | Candidate: {a1_007_sbc:.4f} pp (change: {rel_diff_007_sbc*100:+.2f}%)")
    print(f"  Reference Set X  Held-out SBC: {ref_x_sbc:.4f} pp | Candidate: {set_x_sbc:.4f} pp (change: {rel_diff_x_sbc*100:+.2f}%)")
    print(f"  Reference A1-007 S-A         : {ref_007_sa:.4f} pp | Candidate: {a1_007_sa:.4f} pp (diff: {diff_007_sa:+.4f} pp, limit: <= +0.30 pp)")
    print(f"  Reference A1-007 S-F Worst   : {ref_007_sf_worst:.4f} pp | Candidate: {a1_007_sf_worst:.4f} pp (diff: {diff_007_sf_worst:+.4f} pp, limit: <= +2.00 pp)")
    print(f"  Clause (1) >= 10% on 007 or X: {c1_pass} (007: {c1_007_pass}, X: {c1_x_pass})")
    print(f"  Clause (2) <= +5% on other   : {c2_pass}")
    print(f"  Clause (3) S-A diff <= 0.3 pp: {c3_pass}")
    print(f"  Clause (4) S-F worst <= 2 pp : {c4_pass}")
    print("=" * 80)

    summary_result = {
        "component": args.component,
        "extra_kwargs": extra_kwargs,
        "verdict": status_str,
        "clauses": {
            "clause1_improve_10pct": bool(c1_pass),
            "clause1_007_pass": bool(c1_007_pass),
            "clause1_x_pass": bool(c1_x_pass),
            "clause2_other_le_5pct": bool(c2_pass),
            "clause3_sa_le_03pp": bool(c3_pass),
            "clause4_sf_worst_le_2pp": bool(c4_pass),
        },
        "metrics": {
            "a1_007_sbc_rmse_pp": a1_007_sbc,
            "a1_007_sbc_rel_change_pct": rel_diff_007_sbc * 100.0,
            "set_x_sbc_rmse_pp": set_x_sbc,
            "set_x_sbc_rel_change_pct": rel_diff_x_sbc * 100.0,
            "a1_007_sa_rmse_pp": a1_007_sa,
            "a1_007_sa_diff_pp": diff_007_sa,
            "a1_007_sf_worst_pp": a1_007_sf_worst,
            "a1_007_sf_worst_diff_pp": diff_007_sf_worst,
            "set_x_sa_rmse_pp": set_x_sa,
            "set_x_sf_worst_pp": set_x_sf_worst,
        },
        "per_temp_a1_007": res_a1_007,
        "per_temp_set_x": res_set_x,
    }

    out_file = repo_root / "reports" / "gauntlet_v2" / f"component_{args.component}_eval.json"
    with open(out_file, "w") as f:
        json.dump(summary_result, f, indent=2)
    print(f"Saved evaluation result to {out_file}")


if __name__ == "__main__":
    main()
