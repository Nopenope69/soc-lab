"""E5 v2 Observability-Gated EKF Tuning, Held-Out Evaluation, and Verdict Script.

Change to E5:
    cap_eff = cap_plateau + (cap_knee - cap_plateau) * g
    where g = min(1.0, |dOCV/dSOC| / slope_ref) is the slope gate.

Tuning Grid:
- sigma_ocv_model_v in [0.005, 0.010, 0.020]
- slope_ref in [0.1, 0.2, 0.5]
- cap_plateau in [0.00001, 0.00003, 0.00005, 0.0001]
- cap_knee in [0.01, 0.02, 0.05]

Evaluation Scenarios (5 tuning):
- t3_bess_24h (bess)
- t4_plateau_stress (automotive)
- t12_hysteresis_mismatch (automotive)
- t5_knee_crossing (automotive)
- t6_current_bias (automotive)

Variants: matched, mismatched_neg5 (-5 mV), mismatched_pos5 (+5 mV)
Seeds: 0, 1

Pass Rules for Best E5 v2 Config:
- Rule 1: matched RMSE within 0.3 pp of E2 on t3, t4, t12, t5_knee_crossing, and t6_current_bias.
- Rule 2: for both offset signs, RMSE at least 50% below E2 on t3 and t4.
- Rule 3: on t5_knee_crossing, RMSE within 2 pp of E2. On t6 mismatched, RMSE no more than 0.5 pp above E0.
- Rule 4 (held-out): freeze config, run on mismatch grid (ocv in -8, -3, +3, +8; capacity at +-3%; R0 at +-5%),
  3 new seeds (2, 3, 4), plus t3_t10_minor_loops and t11_anchor_toggle.
  E5 RMSE <= E2 + 0.3 pp in >= 90% of held-out runs, and avg reduction >= 30% below E2 across held-out mismatched runs.
"""

import argparse
import csv
import itertools
from pathlib import Path
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from soc.assumptions.loader import load_assumptions
from soc.estimators.base import ParamSet, SocEstimate
from soc.estimators.registry import get_estimator
from soc.eval.metrics import max_abs_error, plateau_rmse_20_80, rmse
from soc.harness.runner import ScenarioRunner
from soc.models.plant import Measurement, PlantTruthState

PERCENT_FACTOR = 100.0


def step_estimator(
    est_name: str,
    params: ParamSet,
    measurements: List[Measurement],
    init_soc: float,
) -> List[float]:
    """Execute estimator on measurement stream, returning held SOC estimates."""
    est = get_estimator(est_name, params)
    est.reset(init_soc)

    held_socs: List[float] = []
    curr_soc = init_soc

    for m in measurements:
        out = est.step(m)
        if not m.dropout:
            curr_soc = out.soc
        held_socs.append(curr_soc)

    return held_socs


def compute_metrics(
    held_socs: List[float],
    truths: List[PlantTruthState],
    measurements: List[Measurement],
) -> Tuple[float, float, float]:
    """Compute (rmse, max_abs_error, plateau_rmse) in fractional units on non-dropped samples."""
    kept_idx = [i for i, m in enumerate(measurements) if not m.dropout]
    if len(kept_idx) == 0:
        kept_idx = list(range(len(measurements)))

    t_arr = np.array([truths[i].soc for i in kept_idx], dtype=float)
    e_arr = np.array([held_socs[i] for i in kept_idx], dtype=float)

    r_rmse = rmse(t_arr, e_arr)
    r_max = max_abs_error(t_arr, e_arr)
    r_plat = plateau_rmse_20_80(t_arr, e_arr, soc_min=0.20, soc_max=0.80)
    return r_rmse, r_max, r_plat


def main():
    parser = argparse.ArgumentParser(description="Tune and evaluate E5 v2 Observability EKF.")
    parser.add_argument("--csv", default="reports/e5v2_tuning.csv", help="Path to output CSV.")
    parser.add_argument("--report", default="reports/e5v2_verdict.md", help="Path to output markdown report.")
    args = parser.parse_args()

    csv_path = Path(args.csv)
    report_path = Path(args.report)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)

    # 1. Tuning Grid Definition
    sigmas = [0.005, 0.010, 0.020]
    slopes = [0.1, 0.2, 0.5]
    cap_plats = [0.00001, 0.00003, 0.00005, 0.0001]
    cap_knees = [0.01, 0.02, 0.05]

    configs: List[Dict[str, Any]] = []
    cfg_id = 1
    for s, sl, cp, ck in itertools.product(sigmas, slopes, cap_plats, cap_knees):
        configs.append({
            "config_id": f"CFG_V2_{cfg_id:03d}",
            "sigma_ocv": s,
            "slope_ref": sl,
            "cap_plateau": cp,
            "cap_knee": ck,
        })
        cfg_id += 1

    tuning_scenarios = [
        ("t3_bess_24h", "bess"),
        ("t4_plateau_stress", "automotive"),
        ("t12_hysteresis_mismatch", "automotive"),
        ("t5_knee_crossing", "automotive"),
        ("t6_current_bias", "automotive"),
    ]

    tuning_variants = [
        ("matched", 0.0),
        ("mismatched_neg5", -5.0),
        ("mismatched_pos5", 5.0),
    ]

    tuning_seeds = [0, 1]

    runner = ScenarioRunner()

    print("================================================================")
    print(f"E5 v2 Tuning & Evaluation")
    print(f"Grid: {len(configs)} configs, {len(tuning_scenarios)} scenarios, {len(tuning_variants)} variants, {len(tuning_seeds)} seeds")
    print(f"Total Tuning Evaluations: {len(configs) * len(tuning_scenarios) * len(tuning_variants) * len(tuning_seeds)}")
    print(f"CSV Output: {csv_path}")
    print(f"Report Output: {report_path}")
    print("================================================================")

    # 2. Phase 1: Pre-generate and cache tuning streams & baselines
    print("Phase 1/4: Generating tuning streams and evaluating baselines (E0, E2, E5 v1 best)...")
    cached_streams: Dict[Tuple[str, str, int], Any] = {}
    cached_baselines: Dict[Tuple[str, str, int], Dict[str, float]] = {}

    t0_base = time.perf_counter()

    for sc_name, prof in tuning_scenarios:
        sc_file = f"configs/assumptions/scenarios/{sc_name}.yaml"
        for var_name, offset_mv in tuning_variants:
            is_matched = var_name == "matched"
            overrides = []
            if not is_matched:
                overrides.append(f"estimator_model.mismatch.ocv_offset_mv={offset_mv}")

            assumptions, _, _ = load_assumptions(
                profile=prof,
                scenario_file=sc_file,
                cli_overrides=overrides,
            )

            for seed_idx in tuning_seeds:
                key = (sc_name, var_name, seed_idx)
                meas, truths, times, _, _ = runner.generate_scenario_stream(
                    assumptions, sc_name, seed_index=seed_idx
                )
                cached_streams[key] = (assumptions, meas, truths, times)

                init_soc = float(assumptions.duty.initial_soc.value) + float(assumptions.filter.initial_soc_offset.value)

                # E0
                p_e0 = ParamSet.from_assumptions(assumptions, matched=is_matched)
                e0_socs = step_estimator("E0", p_e0, meas, init_soc)
                e0_rmse, e0_max, e0_plat = compute_metrics(e0_socs, truths, meas)

                # E2
                p_e2 = ParamSet.from_assumptions(assumptions, matched=is_matched)
                e2_socs = step_estimator("E2", p_e2, meas, init_soc)
                e2_rmse, e2_max, e2_plat = compute_metrics(e2_socs, truths, meas)

                # E5 v1 Best (CFG_ABC_021: sigma=0.005, slope=0.1, cap=0.0002, fixed cap)
                p_e5v1 = ParamSet(
                    **{
                        **p_e2.__dict__,
                        "e5_enable_r_inflation": True,
                        "e5_enable_slope_gating": True,
                        "e5_enable_step_cap": True,
                        "e5_use_observability_cap": False,
                        "e5_sigma_ocv_model_v": 0.005,
                        "e5_slope_ref": 0.1,
                        "e5_max_soc_step": 0.0002,
                    }
                )
                e5v1_socs = step_estimator("E5", p_e5v1, meas, init_soc)
                e5v1_rmse, e5v1_max, e5v1_plat = compute_metrics(e5v1_socs, truths, meas)

                cached_baselines[key] = {
                    "e0_rmse": e0_rmse * PERCENT_FACTOR,
                    "e0_max": e0_max * PERCENT_FACTOR,
                    "e2_rmse": e2_rmse * PERCENT_FACTOR,
                    "e2_max": e2_max * PERCENT_FACTOR,
                    "e5v1_rmse": e5v1_rmse * PERCENT_FACTOR,
                    "e5v1_max": e5v1_max * PERCENT_FACTOR,
                }

    t1_base = time.perf_counter()
    print(f"Phase 1 complete in {t1_base - t0_base:.2f} s. Baselines cached.")

    # 3. Phase 2: Run E5 v2 Tuning Grid
    print("Phase 2/4: Evaluating E5 v2 configurations across grid...")
    t0_eval = time.perf_counter()

    all_tuning_results: Dict[Tuple[str, str, str, int], Dict[str, float]] = {}

    csv_fields = [
        "config_id",
        "sigma_ocv",
        "slope_ref",
        "cap_plateau",
        "cap_knee",
        "scenario",
        "variant",
        "seed",
        "e5v2_rmse",
        "e5v2_max_err",
        "e2_rmse",
        "e0_rmse",
        "e5v1_rmse",
    ]

    with open(csv_path, "w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=csv_fields)
        writer.writeheader()

        eval_count = 0
        for cfg in configs:
            cid = cfg["config_id"]
            s_val = cfg["sigma_ocv"]
            sl_val = cfg["slope_ref"]
            cp_val = cfg["cap_plateau"]
            ck_val = cfg["cap_knee"]

            for sc_name, _ in tuning_scenarios:
                for var_name, _ in tuning_variants:
                    for seed_idx in tuning_seeds:
                        run_key = (cid, sc_name, var_name, seed_idx)
                        stream_key = (sc_name, var_name, seed_idx)

                        assumptions, meas, truths, _ = cached_streams[stream_key]
                        is_matched = var_name == "matched"
                        base_params = ParamSet.from_assumptions(assumptions, matched=is_matched)

                        p_e5v2 = ParamSet(
                            **{
                                **base_params.__dict__,
                                "e5_enable_r_inflation": True,
                                "e5_enable_slope_gating": True,
                                "e5_enable_step_cap": True,
                                "e5_use_observability_cap": True,
                                "e5_sigma_ocv_model_v": s_val,
                                "e5_slope_ref": sl_val,
                                "e5_cap_plateau": cp_val,
                                "e5_cap_knee": ck_val,
                            }
                        )

                        init_soc = float(assumptions.duty.initial_soc.value) + float(assumptions.filter.initial_soc_offset.value)
                        e5v2_socs = step_estimator("E5", p_e5v2, meas, init_soc)
                        e5v2_r, e5v2_m, _ = compute_metrics(e5v2_socs, truths, meas)

                        e5v2_rmse_pp = e5v2_r * PERCENT_FACTOR
                        e5v2_max_pp = e5v2_m * PERCENT_FACTOR

                        base_metrics = cached_baselines[stream_key]

                        row_data = {
                            "config_id": cid,
                            "sigma_ocv": s_val,
                            "slope_ref": sl_val,
                            "cap_plateau": cp_val,
                            "cap_knee": ck_val,
                            "scenario": sc_name,
                            "variant": var_name,
                            "seed": seed_idx,
                            "e5v2_rmse": f"{e5v2_rmse_pp:.4f}",
                            "e5v2_max_err": f"{e5v2_max_pp:.4f}",
                            "e2_rmse": f"{base_metrics['e2_rmse']:.4f}",
                            "e0_rmse": f"{base_metrics['e0_rmse']:.4f}",
                            "e5v1_rmse": f"{base_metrics['e5v1_rmse']:.4f}",
                        }
                        writer.writerow(row_data)

                        all_tuning_results[run_key] = {
                            "e5v2_rmse": e5v2_rmse_pp,
                            "e5v2_max_err": e5v2_max_pp,
                            "e2_rmse": base_metrics["e2_rmse"],
                            "e0_rmse": base_metrics["e0_rmse"],
                            "e5v1_rmse": base_metrics["e5v1_rmse"],
                        }

                        eval_count += 1
                        if eval_count % 500 == 0:
                            elapsed = time.perf_counter() - t0_eval
                            print(f"  Completed {eval_count} evals in {elapsed:.1f} s ({eval_count/elapsed:.1f} evals/s)...")

    t1_eval = time.perf_counter()
    print(f"Phase 2 complete in {t1_eval - t0_eval:.2f} s. Tuning results written to {csv_path}.")

    # 4. Phase 3: Evaluate Rules 1, 2, 3 and Pick Best E5 v2 Config
    print("Phase 3/4: Auditing Rules 1, 2, 3 on tuning set...")
    scored_configs = []

    for cfg in configs:
        cid = cfg["config_id"]

        # Means across seeds
        means: Dict[Tuple[str, str], Dict[str, float]] = {}
        for sc_name, _ in tuning_scenarios:
            for var_name, _ in tuning_variants:
                e5_vals = [all_tuning_results[(cid, sc_name, var_name, s)]["e5v2_rmse"] for s in tuning_seeds]
                e2_vals = [all_tuning_results[(cid, sc_name, var_name, s)]["e2_rmse"] for s in tuning_seeds]
                e0_vals = [all_tuning_results[(cid, sc_name, var_name, s)]["e0_rmse"] for s in tuning_seeds]
                e5v1_vals = [all_tuning_results[(cid, sc_name, var_name, s)]["e5v1_rmse"] for s in tuning_seeds]
                means[(sc_name, var_name)] = {
                    "e5v2": float(np.mean(e5_vals)),
                    "e2": float(np.mean(e2_vals)),
                    "e0": float(np.mean(e0_vals)),
                    "e5v1": float(np.mean(e5v1_vals)),
                }

        # Rule 1: matched RMSE within 0.3 pp of E2 on t3, t4, t12, t5_knee_crossing, t6_current_bias
        r1_diffs = {
            sc: means[(sc, "matched")]["e5v2"] - means[(sc, "matched")]["e2"]
            for sc in ["t3_bess_24h", "t4_plateau_stress", "t12_hysteresis_mismatch", "t5_knee_crossing", "t6_current_bias"]
        }
        rule1_pass = all(diff <= 0.30 for diff in r1_diffs.values())

        # Rule 2: for both offset signs, RMSE at least 50% below E2 on t3 and t4
        r2_ratios = {
            (sc, var): means[(sc, var)]["e5v2"] / means[(sc, var)]["e2"]
            for sc in ["t3_bess_24h", "t4_plateau_stress"]
            for var in ["mismatched_neg5", "mismatched_pos5"]
        }
        rule2_pass = all(ratio <= 0.50 for ratio in r2_ratios.values())
        avg_red_r2 = float(np.mean([1.0 - ratio for ratio in r2_ratios.values()])) * 100.0

        # Rule 3: on t5_knee_crossing, RMSE within 2 pp of E2; on t6 mismatched, RMSE no more than 0.5 pp above E0
        # t5: check across matched and both mismatch variants
        r3_t5_matched = abs(means[("t5_knee_crossing", "matched")]["e5v2"] - means[("t5_knee_crossing", "matched")]["e2"]) <= 2.0
        r3_t5_neg = abs(means[("t5_knee_crossing", "mismatched_neg5")]["e5v2"] - means[("t5_knee_crossing", "mismatched_neg5")]["e2"]) <= 2.0
        r3_t5_pos = abs(means[("t5_knee_crossing", "mismatched_pos5")]["e5v2"] - means[("t5_knee_crossing", "mismatched_pos5")]["e2"]) <= 2.0
        r3_t5 = r3_t5_matched and r3_t5_neg and r3_t5_pos

        # t6 mismatched: neg5 and pos5
        r3_t6_neg = means[("t6_current_bias", "mismatched_neg5")]["e5v2"] <= means[("t6_current_bias", "mismatched_neg5")]["e0"] + 0.50
        r3_t6_pos = means[("t6_current_bias", "mismatched_pos5")]["e5v2"] <= means[("t6_current_bias", "mismatched_pos5")]["e0"] + 0.50
        r3_t6 = r3_t6_neg and r3_t6_pos

        rule3_pass = r3_t5 and r3_t6

        # Penalties for ranking
        p1 = sum(max(0.0, diff - 0.30) for diff in r1_diffs.values())
        p2 = sum(max(0.0, ratio - 0.50) for ratio in r2_ratios.values()) * 10.0
        p3_t5 = max(0.0, abs(means[("t5_knee_crossing", "matched")]["e5v2"] - means[("t5_knee_crossing", "matched")]["e2"]) - 2.0)
        p3_t6 = (
            max(0.0, means[("t6_current_bias", "mismatched_neg5")]["e5v2"] - (means[("t6_current_bias", "mismatched_neg5")]["e0"] + 0.50))
            + max(0.0, means[("t6_current_bias", "mismatched_pos5")]["e5v2"] - (means[("t6_current_bias", "mismatched_pos5")]["e0"] + 0.50))
        )
        total_penalty = p1 * 100.0 + p2 * 10.0 + (p3_t5 + p3_t6) * 10.0

        rules_123_pass = rule1_pass and rule2_pass and rule3_pass

        scored_configs.append({
            "cfg": cfg,
            "means": means,
            "rule1_pass": rule1_pass,
            "r1_diffs": r1_diffs,
            "rule2_pass": rule2_pass,
            "r2_ratios": r2_ratios,
            "avg_red_r2": avg_red_r2,
            "rule3_pass": rule3_pass,
            "r3_t5": r3_t5,
            "r3_t6": r3_t6,
            "rules_123_pass": rules_123_pass,
            "penalty": total_penalty,
        })

    scored_configs.sort(key=lambda x: (not x["rules_123_pass"], x["penalty"]))
    best_config = scored_configs[0]

    print("\nBest E5 v2 Tuning Configuration:")
    print(f"ID: {best_config['cfg']['config_id']}")
    print(f"Parameters: sigma={best_config['cfg']['sigma_ocv']}, slope_ref={best_config['cfg']['slope_ref']}, cap_plat={best_config['cfg']['cap_plateau']}, cap_knee={best_config['cfg']['cap_knee']}")
    print(f"Rule 1: {'PASS' if best_config['rule1_pass'] else 'FAIL'}")
    print(f"Rule 2: {'PASS' if best_config['rule2_pass'] else 'FAIL'} (avg reduction: {best_config['avg_red_r2']:.1f}%)")
    print(f"Rule 3: {'PASS' if best_config['rule3_pass'] else 'FAIL'}")

    # 5. Phase 4: Held-Out Evaluation (Rule 4)
    print("\nPhase 4/4: Running Held-Out Evaluation on Frozen Config (Rule 4)...")
    held_scenarios = [
        ("t3_bess_24h", "bess"),
        ("t4_plateau_stress", "automotive"),
        ("t12_hysteresis_mismatch", "automotive"),
        ("t5_knee_crossing", "automotive"),
        ("t6_current_bias", "automotive"),
        ("t3_t10_minor_loops", "automotive"),
        ("t11_anchor_toggle", "automotive"),
    ]

    held_seeds = [2, 3, 4]

    # Mismatch grid: ocv in [-8, -3, 3, 8], capacity in [-3, 3], R0 in [-5, 5]
    ocv_vals = [-8.0, -3.0, 3.0, 8.0]
    cap_vals = [-3.0, 3.0]
    r0_vals = [-5.0, 5.0]

    held_mismatches = list(itertools.product(ocv_vals, cap_vals, r0_vals))
    print(f"Held-out conditions: {len(held_scenarios)} scenarios x ({len(held_mismatches)} mismatch + 1 matched) x {len(held_seeds)} seeds = {len(held_scenarios) * (len(held_mismatches) + 1) * len(held_seeds)} runs")

    best_cfg_params = best_config["cfg"]
    held_runs_total = 0
    held_runs_within_03 = 0

    held_mismatched_e2: List[float] = []
    held_mismatched_e5: List[float] = []

    t0_held = time.perf_counter()

    for sc_name, prof in held_scenarios:
        sc_file = f"configs/assumptions/scenarios/{sc_name}.yaml"

        # 1. Matched run for this scenario on held-out seeds
        assumptions_m, _, _ = load_assumptions(profile=prof, scenario_file=sc_file)
        for s_idx in held_seeds:
            meas_m, truths_m, _, _, _ = runner.generate_scenario_stream(assumptions_m, sc_name, seed_index=s_idx)
            init_soc_m = float(assumptions_m.duty.initial_soc.value) + float(assumptions_m.filter.initial_soc_offset.value)

            p_e2_m = ParamSet.from_assumptions(assumptions_m, matched=True)
            e2_socs = step_estimator("E2", p_e2_m, meas_m, init_soc_m)
            e2_r, _, _ = compute_metrics(e2_socs, truths_m, meas_m)
            e2_pp = e2_r * PERCENT_FACTOR

            p_e5_m = ParamSet(
                **{
                    **p_e2_m.__dict__,
                    "e5_enable_r_inflation": True,
                    "e5_enable_slope_gating": True,
                    "e5_enable_step_cap": True,
                    "e5_use_observability_cap": True,
                    "e5_sigma_ocv_model_v": best_cfg_params["sigma_ocv"],
                    "e5_slope_ref": best_cfg_params["slope_ref"],
                    "e5_cap_plateau": best_cfg_params["cap_plateau"],
                    "e5_cap_knee": best_cfg_params["cap_knee"],
                }
            )
            e5_socs = step_estimator("E5", p_e5_m, meas_m, init_soc_m)
            e5_r, _, _ = compute_metrics(e5_socs, truths_m, meas_m)
            e5_pp = e5_r * PERCENT_FACTOR

            held_runs_total += 1
            if e5_pp <= e2_pp + 0.30:
                held_runs_within_03 += 1

        # 2. Mismatched runs across grid
        for ocv_mv, cap_pct, r0_pct in held_mismatches:
            overrides = [
                f"estimator_model.mismatch.ocv_offset_mv={ocv_mv}",
                f"estimator_model.mismatch.capacity_pct={cap_pct}",
                f"estimator_model.mismatch.r0_pct={r0_pct}",
            ]
            assumptions_mis, _, _ = load_assumptions(profile=prof, scenario_file=sc_file, cli_overrides=overrides)

            for s_idx in held_seeds:
                meas_mis, truths_mis, _, _, _ = runner.generate_scenario_stream(assumptions_mis, sc_name, seed_index=s_idx)
                init_soc_mis = float(assumptions_mis.duty.initial_soc.value) + float(assumptions_mis.filter.initial_soc_offset.value)

                p_e2_mis = ParamSet.from_assumptions(assumptions_mis, matched=False)
                e2_socs = step_estimator("E2", p_e2_mis, meas_mis, init_soc_mis)
                e2_r, _, _ = compute_metrics(e2_socs, truths_mis, meas_mis)
                e2_pp = e2_r * PERCENT_FACTOR

                p_e5_mis = ParamSet(
                    **{
                        **p_e2_mis.__dict__,
                        "e5_enable_r_inflation": True,
                        "e5_enable_slope_gating": True,
                        "e5_enable_step_cap": True,
                        "e5_use_observability_cap": True,
                        "e5_sigma_ocv_model_v": best_cfg_params["sigma_ocv"],
                        "e5_slope_ref": best_cfg_params["slope_ref"],
                        "e5_cap_plateau": best_cfg_params["cap_plateau"],
                        "e5_cap_knee": best_cfg_params["cap_knee"],
                    }
                )
                e5_socs = step_estimator("E5", p_e5_mis, meas_mis, init_soc_mis)
                e5_r, _, _ = compute_metrics(e5_socs, truths_mis, meas_mis)
                e5_pp = e5_r * PERCENT_FACTOR

                held_runs_total += 1
                if e5_pp <= e2_pp + 0.30:
                    held_runs_within_03 += 1

                held_mismatched_e2.append(e2_pp)
                held_mismatched_e5.append(e5_pp)

    t1_held = time.perf_counter()
    pct_within_03 = (held_runs_within_03 / held_runs_total) * 100.0
    avg_reduction_held = float(np.mean([
        (e2 - e5) / e2 for e2, e5 in zip(held_mismatched_e2, held_mismatched_e5) if e2 > 0
    ])) * 100.0

    rule4_pass = (pct_within_03 >= 90.0) and (avg_reduction_held >= 30.0)

    print(f"Held-out complete in {t1_held - t0_held:.2f} s.")
    print(f"Runs <= E2 + 0.30 pp: {held_runs_within_03}/{held_runs_total} ({pct_within_03:.1f}%, target >= 90.0%)")
    print(f"Average reduction on mismatched held-out runs: {avg_reduction_held:.1f}% (target >= 30.0%)")
    print(f"Rule 4: {'PASS' if rule4_pass else 'FAIL'}")

    overall_pass = best_config["rules_123_pass"] and rule4_pass
    print(f"\nOVERALL VERDICT: {'PASS' if overall_pass else 'FAIL'}")

    # 6. Generate reports/e5v2_verdict.md
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("# E5 v2 Observability-Gated EKF Verdict Report\n\n")

        overall_str = "**PASS**" if overall_pass else "**FAIL**"
        r1_str = "**PASS**" if best_config["rule1_pass"] else "**FAIL**"
        r2_str = "**PASS**" if best_config["rule2_pass"] else "**FAIL**"
        r3_str = "**PASS**" if best_config["rule3_pass"] else "**FAIL**"
        r4_str = "**PASS**" if rule4_pass else "**FAIL**"

        f.write("## Executive Verdict\n\n")
        f.write(f"- **Overall Verdict**: {overall_str}\n")
        f.write(f"- **Best E5 v2 Configuration**: `{best_config['cfg']['config_id']}`\n")
        f.write(f"  - $\\sigma_{{\\text{{ocv}}}}$: `{best_config['cfg']['sigma_ocv']} V`\n")
        f.write(f"  - $\\text{{slope}}_{{\\text{{ref}}}}$: `{best_config['cfg']['slope_ref']} V`\n")
        f.write(f"  - $\\text{{cap}}_{{\\text{{plateau}}}}$: `{best_config['cfg']['cap_plateau']}`\n")
        f.write(f"  - $\\text{{cap}}_{{\\text{{knee}}}}$: `{best_config['cfg']['cap_knee']}`\n\n")

        f.write("### Per-Rule Verdicts:\n")
        f.write(f"- **Rule 1 (Parity on Matched Scenarios)**: {r1_str} (matched RMSE within 0.3 pp of E2 on t3, t4, t12, t5_knee_crossing, t6)\n")
        f.write(f"- **Rule 2 (Help Under Mismatch on Plateau)**: {r2_str} (RMSE at least 50% below E2 on t3 and t4 for +5 mV and -5 mV)\n")
        f.write(f"- **Rule 3 (Knee Crossing & Current Bias Boundaries)**: {r3_str} (t5 within 2 pp of E2; t6 mismatched within 0.5 pp of E0)\n")
        f.write(f"- **Rule 4 (Held-Out Generalization)**: {r4_str} (<= E2 + 0.3 pp in >= 90% runs; avg reduction >= 30% across mismatched runs)\n\n")

        if not overall_pass:
            f.write("> [!CAUTION]\n")
            f.write("> **E5 v2 did not achieve a full PASS across all four rules.** Per strict instructions, rules were not modified and no ad-hoc workarounds were applied.\n\n")
        else:
            f.write("> [!NOTE]\n")
            f.write("> **E5 v2 successfully passed all four pass rules.**\n\n")

        f.write("## 1. Comparison Table: E0, E2, E5 v1 Best, and E5 v2 Best\n\n")
        f.write("Performance across the evaluation scenarios (mean RMSE in pp across tuning seeds 0 and 1):\n")
        f.write("- **E0**: Coulomb counting\n")
        f.write("- **E2**: Baseline 2RC EKF with hysteresis\n")
        f.write("- **E5 v1 Best**: `CFG_ABC_021` (fixed cap = 0.0002)\n")
        f.write(f"- **E5 v2 Best**: `{best_config['cfg']['config_id']}` (observability cap: plateau={best_config['cfg']['cap_plateau']}, knee={best_config['cfg']['cap_knee']})\n\n")

        f.write("| Scenario | Variant | E0 (pp) | E2 Baseline (pp) | E5 v1 Best (pp) | E5 v2 Best (pp) |\n")
        f.write("| :--- | :--- | :---: | :---: | :---: | :---: |\n")

        for sc_name, _ in tuning_scenarios:
            for var_name, _ in tuning_variants:
                var_label = "matched" if var_name == "matched" else ("mismatch (-5 mV)" if "neg5" in var_name else "mismatch (+5 mV)")
                e0_v = best_config["means"][(sc_name, var_name)]["e0"]
                e2_v = best_config["means"][(sc_name, var_name)]["e2"]
                e5v1_v = best_config["means"][(sc_name, var_name)]["e5v1"]
                e5v2_v = best_config["means"][(sc_name, var_name)]["e5v2"]
                f.write(f"| **{sc_name}** | {var_label} | {e0_v:.2f} | {e2_v:.2f} | {e5v1_v:.2f} | {e5v2_v:.2f} |\n")

        f.write("\n## 2. Detailed Audit of Pass Rules for Best E5 v2 Config\n\n")

        f.write("### Rule 1: Matched Parity (Threshold: within 0.30 pp of E2)\n")
        for sc in ["t3_bess_24h", "t4_plateau_stress", "t12_hysteresis_mismatch", "t5_knee_crossing", "t6_current_bias"]:
            e5_val = best_config["means"][(sc, "matched")]["e5v2"]
            e2_val = best_config["means"][(sc, "matched")]["e2"]
            diff = e5_val - e2_val
            v_stat = "PASS" if diff <= 0.30 else "FAIL"
            f.write(f"- **{sc}**: E5 v2 = `{e5_val:.2f}` pp, E2 = `{e2_val:.2f}` pp, Diff = `{diff:+.2f}` pp -> **{v_stat}**\n")

        f.write("\n### Rule 2: Mismatch Reduction on Plateau (Threshold: >= 50% below E2 on t3 and t4)\n")
        for sc in ["t3_bess_24h", "t4_plateau_stress"]:
            for var in ["mismatched_neg5", "mismatched_pos5"]:
                sign_str = "-5 mV" if "neg" in var else "+5 mV"
                e5_val = best_config["means"][(sc, var)]["e5v2"]
                e2_val = best_config["means"][(sc, var)]["e2"]
                target = 0.50 * e2_val
                ratio = e5_val / e2_val
                red = (1.0 - ratio) * 100.0
                v_stat = "PASS" if e5_val <= target else "FAIL"
                f.write(f"- **{sc} ({sign_str})**: E5 v2 = `{e5_val:.2f}` pp, E2 = `{e2_val:.2f}` pp, Reduction = `{red:.1f}%` -> **{v_stat}**\n")

        f.write("\n### Rule 3: Knee Crossing & Current Bias Boundaries\n")
        for var in ["matched", "mismatched_neg5", "mismatched_pos5"]:
            v_lbl = "matched" if var == "matched" else ("-5 mV" if "neg" in var else "+5 mV")
            e5_val = best_config["means"][("t5_knee_crossing", var)]["e5v2"]
            e2_val = best_config["means"][("t5_knee_crossing", var)]["e2"]
            diff = abs(e5_val - e2_val)
            v_stat = "PASS" if diff <= 2.0 else "FAIL"
            f.write(f"- **t5_knee_crossing ({v_lbl})**: E5 v2 = `{e5_val:.2f}` pp, E2 = `{e2_val:.2f}` pp, |Diff| = `{diff:.2f}` pp (target <= 2.0 pp) -> **{v_stat}**\n")

        for var in ["mismatched_neg5", "mismatched_pos5"]:
            v_lbl = "-5 mV" if "neg" in var else "+5 mV"
            e5_val = best_config["means"][("t6_current_bias", var)]["e5v2"]
            e0_val = best_config["means"][("t6_current_bias", var)]["e0"]
            diff = e5_val - e0_val
            v_stat = "PASS" if diff <= 0.50 else "FAIL"
            f.write(f"- **t6_current_bias ({v_lbl})**: E5 v2 = `{e5_val:.2f}` pp vs E0 = `{e0_val:.2f}` pp, Diff = `{diff:+.2f}` pp (target <= +0.50 pp) -> **{v_stat}**\n")

        f.write("\n### Rule 4: Held-Out Generalization Audit\n")
        f.write(f"- **Total Held-Out Evaluated Runs**: `{held_runs_total}`\n")
        f.write(f"- **Runs with RMSE(E5) <= RMSE(E2) + 0.30 pp**: `{held_runs_within_03}` / `{held_runs_total}` (`{pct_within_03:.1f}%`, target >= 90.0%) -> **{'PASS' if pct_within_03 >= 90.0 else 'FAIL'}**\n")
        f.write(f"- **Average Error Reduction Across Held-Out Mismatches**: `{avg_reduction_held:.1f}%` (target >= 30.0%) -> **{'PASS' if avg_reduction_held >= 30.0 else 'FAIL'}**\n")
        f.write(f"- **Rule 4 Verdict**: **{r4_str}**\n")

        f.write("\n## 3. Top 10 Configurations from Tuning Grid\n\n")
        f.write("| Rank | Config ID | $\\sigma_{\\text{ocv}}$ (V) | $\\text{slope}_{\\text{ref}}$ (V) | $\\text{cap}_{\\text{plat}}$ | $\\text{cap}_{\\text{knee}}$ | Rule 1 | Rule 2 | Avg Red (%) | Rule 3 | Penalty |\n")
        f.write("| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |\n")

        for idx, sc in enumerate(scored_configs[:10], start=1):
            c = sc["cfg"]
            r1 = "PASS" if sc["rule1_pass"] else "FAIL"
            r2 = "PASS" if sc["rule2_pass"] else "FAIL"
            r3 = "PASS" if sc["rule3_pass"] else "FAIL"
            f.write(f"| {idx} | `{c['config_id']}` | {c['sigma_ocv']} | {c['slope_ref']} | {c['cap_plateau']} | {c['cap_knee']} | {r1} | {r2} | {sc['avg_red_r2']:.1f}% | {r3} | {sc['penalty']:.2f} |\n")

    print(f"Report generated: {report_path}")


if __name__ == "__main__":
    main()
