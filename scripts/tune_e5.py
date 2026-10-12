"""E5 Observability-Gated EKF Tuning & Verdict Evaluation Script.

Grid:
- Variant (a): e5_enable_r_inflation=True, e5_enable_slope_gating=False, e5_enable_step_cap=False
  sigma_ocv_model_v in [0.002, 0.005, 0.010, 0.020]
- Variant (a)+(b): e5_enable_r_inflation=True, e5_enable_slope_gating=True, e5_enable_step_cap=False
  sigma_ocv_model_v in [0.002, 0.005, 0.010, 0.020]
  slope_ref in [0.05, 0.1, 0.2, 0.5]
- Variant (a)+(b)+(c): e5_enable_r_inflation=True, e5_enable_slope_gating=True, e5_enable_step_cap=True
  sigma_ocv_model_v in [0.002, 0.005, 0.010, 0.020]
  slope_ref in [0.05, 0.1, 0.2, 0.5]
  max_soc_step in [0.0002, 0.0005, 0.001, 0.002]

Baselines:
- E0: Coulomb counting
- E2: 2RC EKF with hysteresis
- E6: RBC-DEKF with CFG_021 (q_theta=1e-9, r_theta=1e-4, initial_theta_std=0.002, flag=True)

Scenarios (5 total):
- t3_bess_24h (profile: bess)
- t4_plateau_stress (profile: automotive)
- t12_hysteresis_mismatch (profile: automotive)
- t5_initial_soc_offset (profile: automotive)
- t6_current_bias (profile: automotive)

Variants (3 total):
- matched (0 mV)
- mismatched_neg5 (-5 mV)
- mismatched_pos5 (+5 mV)

Pass Rules (applied to the best E5 variant across 2 seeds):
- Rule 1 (do no harm): matched RMSE within 0.3 pp of E2 on t3, t4, t12.
- Rule 2 (help under mismatch): for both offset signs, RMSE at least 50% below E2 on t3 and t4.
- Rule 3 (sanity against E0): on initial-SOC-offset and current-bias scenarios, RMSE is below E0.
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
    parser = argparse.ArgumentParser(description="Tune and evaluate E5 Observability EKF.")
    parser.add_argument("--csv", default="reports/e5_tuning.csv", help="Path to output CSV.")
    parser.add_argument("--report", default="reports/e5_verdict.md", help="Path to output markdown report.")
    parser.add_argument("--seeds", type=int, default=2, help="Number of random seeds (default 2).")
    args = parser.parse_args()

    csv_path = Path(args.csv)
    report_path = Path(args.report)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)

    # 1. Grid Definition
    # Parameters
    sigmas = [0.002, 0.005, 0.010, 0.020]
    slopes = [0.05, 0.1, 0.2, 0.5]
    caps = [0.0002, 0.0005, 0.001, 0.002]

    configs: List[Dict[str, Any]] = []
    cfg_id = 1

    # Variant (a): r_inflation only
    for s in sigmas:
        configs.append({
            "config_id": f"CFG_A_{cfg_id:03d}",
            "variant_type": "(a)",
            "enable_r_inf": True,
            "enable_sl_gate": False,
            "enable_st_cap": False,
            "sigma_ocv": s,
            "slope_ref": 0.2,
            "max_soc_step": 0.001,
        })
        cfg_id += 1

    # Variant (a)+(b): r_inflation + slope_gating
    cfg_id = 1
    for s, sl in itertools.product(sigmas, slopes):
        configs.append({
            "config_id": f"CFG_AB_{cfg_id:03d}",
            "variant_type": "(a)+(b)",
            "enable_r_inf": True,
            "enable_sl_gate": True,
            "enable_st_cap": False,
            "sigma_ocv": s,
            "slope_ref": sl,
            "max_soc_step": 0.001,
        })
        cfg_id += 1

    # Variant (a)+(b)+(c): r_inflation + slope_gating + step_cap
    cfg_id = 1
    for s, sl, c in itertools.product(sigmas, slopes, caps):
        configs.append({
            "config_id": f"CFG_ABC_{cfg_id:03d}",
            "variant_type": "(a)+(b)+(c)",
            "enable_r_inf": True,
            "enable_sl_gate": True,
            "enable_st_cap": True,
            "sigma_ocv": s,
            "slope_ref": sl,
            "max_soc_step": c,
        })
        cfg_id += 1

    scenarios = [
        ("t3_bess_24h", "bess"),
        ("t4_plateau_stress", "automotive"),
        ("t12_hysteresis_mismatch", "automotive"),
        ("t5_initial_soc_offset", "automotive"),
        ("t6_current_bias", "automotive"),
    ]

    variants = [
        ("matched", 0.0),
        ("mismatched_neg5", -5.0),
        ("mismatched_pos5", 5.0),
    ]

    seeds = list(range(args.seeds))

    runner = ScenarioRunner()

    print(f"================================================================")
    print(f"E5 Tuning & Verdict Evaluation")
    print(f"Configs: {len(configs)} ({len(sigmas)} (a), {len(sigmas)*len(slopes)} (a+b), {len(sigmas)*len(slopes)*len(caps)} (a+b+c))")
    print(f"Scenarios: {len(scenarios)}, Variants: {len(variants)}, Seeds: {len(seeds)}")
    print(f"Total Stream Conditions: {len(scenarios) * len(variants) * len(seeds)}")
    print(f"Total E5 Evaluations: {len(configs) * len(scenarios) * len(variants) * len(seeds)}")
    print(f"CSV output: {csv_path}")
    print(f"Report output: {report_path}")
    print(f"================================================================")

    # 2. Pre-generate and cache streams & baselines (E0, E2, E6 CFG_021)
    cached_streams: Dict[Tuple[str, str, int], Any] = {}
    cached_baselines: Dict[Tuple[str, str, int], Dict[str, float]] = {}

    print("Phase 1/3: Generating measurement streams and evaluating baselines (E0, E2, E6)...")
    t0_base = time.perf_counter()

    for sc_name, prof in scenarios:
        sc_file = f"configs/assumptions/scenarios/{sc_name}.yaml"
        for var_name, offset_mv in variants:
            is_matched = var_name == "matched"
            overrides = []
            if not is_matched:
                overrides.append(f"estimator_model.mismatch.ocv_offset_mv={offset_mv}")

            assumptions, _, _ = load_assumptions(
                profile=prof,
                scenario_file=sc_file,
                cli_overrides=overrides,
            )

            for seed_idx in seeds:
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

                # E6 (CFG_021: q=1e-9, r=1e-4, std=0.002, flag=True)
                p_e6 = ParamSet(
                    **{
                        **p_e2.__dict__,
                        "rbc_q_theta": 1e-9,
                        "rbc_r_theta": 1e-4,
                        "rbc_initial_theta_std": 0.002,
                        "rbc_use_hysteresis_state": True,
                    }
                )
                e6_socs = step_estimator("E6", p_e6, meas, init_soc)
                e6_rmse, e6_max, e6_plat = compute_metrics(e6_socs, truths, meas)

                cached_baselines[key] = {
                    "e0_rmse": e0_rmse * PERCENT_FACTOR,
                    "e0_max": e0_max * PERCENT_FACTOR,
                    "e0_plat": e0_plat * PERCENT_FACTOR,
                    "e2_rmse": e2_rmse * PERCENT_FACTOR,
                    "e2_max": e2_max * PERCENT_FACTOR,
                    "e2_plat": e2_plat * PERCENT_FACTOR,
                    "e6_rmse": e6_rmse * PERCENT_FACTOR,
                    "e6_max": e6_max * PERCENT_FACTOR,
                    "e6_plat": e6_plat * PERCENT_FACTOR,
                }

    t1_base = time.perf_counter()
    print(f"Phase 1 complete in {t1_base - t0_base:.2f} s. Baselines cached.")

    # 3. Read existing CSV for resume support
    existing_keys = set()
    csv_fields = [
        "config_id",
        "variant_type",
        "enable_r_inf",
        "enable_sl_gate",
        "enable_st_cap",
        "sigma_ocv",
        "slope_ref",
        "max_soc_step",
        "scenario",
        "variant",
        "seed",
        "e5_rmse",
        "e5_max_err",
        "e5_plat_rmse",
        "e2_rmse",
        "e2_max_err",
        "e2_plat_rmse",
        "e0_rmse",
        "e6_rmse",
    ]

    file_exists = csv_path.exists() and csv_path.stat().st_size > 0
    if file_exists:
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                existing_keys.add((row["config_id"], row["scenario"], row["variant"], int(row["seed"])))
        print(f"Resuming run: found {len(existing_keys)} completed rows in {csv_path}")

    csv_file = open(csv_path, "a", newline="", encoding="utf-8")
    writer = csv.DictWriter(csv_file, fieldnames=csv_fields)
    if not file_exists:
        writer.writeheader()
        csv_file.flush()

    # 4. Phase 2: Run E5 Grid
    print("Phase 2/3: Evaluating E5 configurations across grid...")
    t0_eval = time.perf_counter()
    eval_count = 0

    all_results: Dict[Tuple[str, str, str, int], Dict[str, float]] = {}

    # If resuming, load existing results into memory
    if file_exists:
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                all_results[(row["config_id"], row["scenario"], row["variant"], int(row["seed"]))] = {
                    "e5_rmse": float(row["e5_rmse"]),
                    "e5_max_err": float(row["e5_max_err"]),
                    "e5_plat_rmse": float(row["e5_plat_rmse"]),
                    "e2_rmse": float(row["e2_rmse"]),
                    "e0_rmse": float(row["e0_rmse"]),
                    "e6_rmse": float(row["e6_rmse"]),
                }

    for cfg in configs:
        cid = cfg["config_id"]
        vtype = cfg["variant_type"]
        r_inf = cfg["enable_r_inf"]
        sl_gate = cfg["enable_sl_gate"]
        st_cap = cfg["enable_st_cap"]
        sig_ocv = cfg["sigma_ocv"]
        sl_ref = cfg["slope_ref"]
        mx_step = cfg["max_soc_step"]

        for sc_name, _ in scenarios:
            for var_name, _ in variants:
                for seed_idx in seeds:
                    run_key = (cid, sc_name, var_name, seed_idx)
                    if run_key in existing_keys:
                        continue

                    stream_key = (sc_name, var_name, seed_idx)
                    assumptions, meas, truths, _ = cached_streams[stream_key]
                    is_matched = var_name == "matched"
                    base_params = ParamSet.from_assumptions(assumptions, matched=is_matched)

                    p_e5 = ParamSet(
                        **{
                            **base_params.__dict__,
                            "e5_enable_r_inflation": r_inf,
                            "e5_enable_slope_gating": sl_gate,
                            "e5_enable_step_cap": st_cap,
                            "e5_sigma_ocv_model_v": sig_ocv,
                            "e5_slope_ref": sl_ref,
                            "e5_max_soc_step": mx_step,
                        }
                    )

                    init_soc = float(assumptions.duty.initial_soc.value) + float(assumptions.filter.initial_soc_offset.value)
                    e5_socs = step_estimator("E5", p_e5, meas, init_soc)
                    e5_r, e5_m, e5_p = compute_metrics(e5_socs, truths, meas)

                    e5_rmse_pp = e5_r * PERCENT_FACTOR
                    e5_max_pp = e5_m * PERCENT_FACTOR
                    e5_plat_pp = e5_p * PERCENT_FACTOR

                    base_metrics = cached_baselines[stream_key]

                    row_data = {
                        "config_id": cid,
                        "variant_type": vtype,
                        "enable_r_inf": r_inf,
                        "enable_sl_gate": sl_gate,
                        "enable_st_cap": st_cap,
                        "sigma_ocv": sig_ocv,
                        "slope_ref": sl_ref,
                        "max_soc_step": mx_step,
                        "scenario": sc_name,
                        "variant": var_name,
                        "seed": seed_idx,
                        "e5_rmse": f"{e5_rmse_pp:.4f}",
                        "e5_max_err": f"{e5_max_pp:.4f}",
                        "e5_plat_rmse": f"{e5_plat_pp:.4f}",
                        "e2_rmse": f"{base_metrics['e2_rmse']:.4f}",
                        "e2_max_err": f"{base_metrics['e2_max']:.4f}",
                        "e2_plat_rmse": f"{base_metrics['e2_plat']:.4f}",
                        "e0_rmse": f"{base_metrics['e0_rmse']:.4f}",
                        "e6_rmse": f"{base_metrics['e6_rmse']:.4f}",
                    }

                    writer.writerow(row_data)
                    csv_file.flush()

                    all_results[run_key] = {
                        "e5_rmse": e5_rmse_pp,
                        "e5_max_err": e5_max_pp,
                        "e5_plat_rmse": e5_plat_pp,
                        "e2_rmse": base_metrics["e2_rmse"],
                        "e0_rmse": base_metrics["e0_rmse"],
                        "e6_rmse": base_metrics["e6_rmse"],
                    }

                    eval_count += 1
                    if eval_count % 200 == 0:
                        elapsed = time.perf_counter() - t0_eval
                        print(f"  Completed {eval_count} E5 evals in {elapsed:.1f} s ({eval_count/elapsed:.1f} evals/s)...")

    csv_file.close()
    t1_eval = time.perf_counter()
    print(f"Phase 2 complete in {t1_eval - t0_eval:.2f} s.")

    # 5. Phase 3: Evaluate Pass Rules and Generate Report
    print("Phase 3/3: Evaluating Pass Rules and generating verdict report...")

    # Evaluate each config
    scored_configs = []

    for cfg in configs:
        cid = cfg["config_id"]

        # Aggregate across seeds: mean RMSE per (scenario, variant)
        means: Dict[Tuple[str, str], Dict[str, float]] = {}
        for sc_name, _ in scenarios:
            for var_name, _ in variants:
                e5_vals = [all_results[(cid, sc_name, var_name, s)]["e5_rmse"] for s in seeds]
                e2_vals = [all_results[(cid, sc_name, var_name, s)]["e2_rmse"] for s in seeds]
                e0_vals = [all_results[(cid, sc_name, var_name, s)]["e0_rmse"] for s in seeds]
                e6_vals = [all_results[(cid, sc_name, var_name, s)]["e6_rmse"] for s in seeds]
                means[(sc_name, var_name)] = {
                    "e5": float(np.mean(e5_vals)),
                    "e2": float(np.mean(e2_vals)),
                    "e0": float(np.mean(e0_vals)),
                    "e6": float(np.mean(e6_vals)),
                }

        # Rule 1: matched RMSE within 0.3 pp of E2 on t3, t4, t12
        r1_t3_diff = means[("t3_bess_24h", "matched")]["e5"] - means[("t3_bess_24h", "matched")]["e2"]
        r1_t4_diff = means[("t4_plateau_stress", "matched")]["e5"] - means[("t4_plateau_stress", "matched")]["e2"]
        r1_t12_diff = means[("t12_hysteresis_mismatch", "matched")]["e5"] - means[("t12_hysteresis_mismatch", "matched")]["e2"]

        rule1_t3 = r1_t3_diff <= 0.30
        rule1_t4 = r1_t4_diff <= 0.30
        rule1_t12 = r1_t12_diff <= 0.30
        rule1_pass = rule1_t3 and rule1_t4 and rule1_t12

        # Rule 2: for both offset signs, RMSE at least 50% below E2 on t3 and t4
        # (RMSE_E5 <= 0.50 * RMSE_E2)
        r2_t3_neg_ratio = means[("t3_bess_24h", "mismatched_neg5")]["e5"] / means[("t3_bess_24h", "mismatched_neg5")]["e2"]
        r2_t3_pos_ratio = means[("t3_bess_24h", "mismatched_pos5")]["e5"] / means[("t3_bess_24h", "mismatched_pos5")]["e2"]
        r2_t4_neg_ratio = means[("t4_plateau_stress", "mismatched_neg5")]["e5"] / means[("t4_plateau_stress", "mismatched_neg5")]["e2"]
        r2_t4_pos_ratio = means[("t4_plateau_stress", "mismatched_pos5")]["e5"] / means[("t4_plateau_stress", "mismatched_pos5")]["e2"]

        rule2_t3_neg = r2_t3_neg_ratio <= 0.50
        rule2_t3_pos = r2_t3_pos_ratio <= 0.50
        rule2_t4_neg = r2_t4_neg_ratio <= 0.50
        rule2_t4_pos = r2_t4_pos_ratio <= 0.50
        rule2_pass = rule2_t3_neg and rule2_t3_pos and rule2_t4_neg and rule2_t4_pos

        # Rule 3: on initial-SOC-offset and current-bias scenarios, RMSE is below E0
        # (check across matched and both mismatch variants)
        r3_t5_matched = means[("t5_initial_soc_offset", "matched")]["e5"] < means[("t5_initial_soc_offset", "matched")]["e0"]
        r3_t5_neg = means[("t5_initial_soc_offset", "mismatched_neg5")]["e5"] < means[("t5_initial_soc_offset", "mismatched_neg5")]["e0"]
        r3_t5_pos = means[("t5_initial_soc_offset", "mismatched_pos5")]["e5"] < means[("t5_initial_soc_offset", "mismatched_pos5")]["e0"]

        r3_t6_matched = means[("t6_current_bias", "matched")]["e5"] < means[("t6_current_bias", "matched")]["e0"]
        r3_t6_neg = means[("t6_current_bias", "mismatched_neg5")]["e5"] < means[("t6_current_bias", "mismatched_neg5")]["e0"]
        r3_t6_pos = means[("t6_current_bias", "mismatched_pos5")]["e5"] < means[("t6_current_bias", "mismatched_pos5")]["e0"]

        rule3_t5 = r3_t5_matched and r3_t5_neg and r3_t5_pos
        rule3_t6 = r3_t6_matched and r3_t6_neg and r3_t6_pos
        rule3_pass = rule3_t5 and rule3_t6

        overall_pass = rule1_pass and rule2_pass and rule3_pass

        # Ranking score: penalty formulation
        # 1. Rule 1 penalty: sum of max(0, diff - 0.30)
        p1 = max(0.0, r1_t3_diff - 0.30) + max(0.0, r1_t4_diff - 0.30) + max(0.0, r1_t12_diff - 0.30)
        # 2. Rule 2 penalty: sum of max(0, ratio - 0.50) * 10
        p2 = (
            max(0.0, r2_t3_neg_ratio - 0.50)
            + max(0.0, r2_t3_pos_ratio - 0.50)
            + max(0.0, r2_t4_neg_ratio - 0.50)
            + max(0.0, r2_t4_pos_ratio - 0.50)
        ) * 10.0
        # 3. Rule 3 penalty: sum of max(0, e5 - e0)
        p3 = sum(
            max(0.0, means[(sc, v)]["e5"] - means[(sc, v)]["e0"])
            for sc in ["t5_initial_soc_offset", "t6_current_bias"]
            for v in ["matched", "mismatched_neg5", "mismatched_pos5"]
        )

        total_penalty = p1 * 100.0 + p2 * 10.0 + p3 * 10.0
        # Average reduction on t3 and t4 mismatch
        avg_red_r2 = (
            (1.0 - r2_t3_neg_ratio)
            + (1.0 - r2_t3_pos_ratio)
            + (1.0 - r2_t4_neg_ratio)
            + (1.0 - r2_t4_pos_ratio)
        ) / 4.0 * 100.0

        scored_configs.append({
            "cfg": cfg,
            "means": means,
            "rule1_pass": rule1_pass,
            "rule1_t3": rule1_t3,
            "rule1_t4": rule1_t4,
            "rule1_t12": rule1_t12,
            "r1_t3_diff": r1_t3_diff,
            "r1_t4_diff": r1_t4_diff,
            "r1_t12_diff": r1_t12_diff,
            "rule2_pass": rule2_pass,
            "r2_t3_neg_ratio": r2_t3_neg_ratio,
            "r2_t3_pos_ratio": r2_t3_pos_ratio,
            "r2_t4_neg_ratio": r2_t4_neg_ratio,
            "r2_t4_pos_ratio": r2_t4_pos_ratio,
            "avg_red_r2": avg_red_r2,
            "rule3_pass": rule3_pass,
            "rule3_t5": rule3_t5,
            "rule3_t6": rule3_t6,
            "overall_pass": overall_pass,
            "penalty": total_penalty,
        })

    # Sort configs: overall_pass True first, then lowest penalty
    scored_configs.sort(key=lambda x: (not x["overall_pass"], x["penalty"]))

    best_config = scored_configs[0]
    print("\nBest Configuration Found:")
    print(f"ID: {best_config['cfg']['config_id']}, Variant: {best_config['cfg']['variant_type']}")
    print(f"Parameters: sigma={best_config['cfg']['sigma_ocv']}, slope_ref={best_config['cfg']['slope_ref']}, max_step={best_config['cfg']['max_soc_step']}")
    print(f"Rule 1: {'PASS' if best_config['rule1_pass'] else 'FAIL'}")
    print(f"Rule 2: {'PASS' if best_config['rule2_pass'] else 'FAIL'} (avg reduction: {best_config['avg_red_r2']:.1f}%)")
    print(f"Rule 3: {'PASS' if best_config['rule3_pass'] else 'FAIL'}")
    print(f"Overall Verdict: {'PASS' if best_config['overall_pass'] else 'FAIL'}")

    # Best representative per variant type:
    best_per_variant: Dict[str, Any] = {}
    for vtype in ["(a)", "(a)+(b)", "(a)+(b)+(c)"]:
        v_cfgs = [c for c in scored_configs if c["cfg"]["variant_type"] == vtype]
        if v_cfgs:
            best_per_variant[vtype] = v_cfgs[0]

    # 6. Generate reports/e5_verdict.md
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("# E5 Observability-Gated EKF Verdict Report\n\n")

        overall_str = "**PASS**" if best_config["overall_pass"] else "**FAIL**"
        r1_str = "**PASS**" if best_config["rule1_pass"] else "**FAIL**"
        r2_str = "**PASS**" if best_config["rule2_pass"] else "**FAIL**"
        r3_str = "**PASS**" if best_config["rule3_pass"] else "**FAIL**"

        f.write("## Executive Verdict\n\n")
        f.write(f"- **Overall Verdict**: {overall_str}\n")
        f.write(f"- **Best E5 Variant**: `{best_config['cfg']['config_id']}` ({best_config['cfg']['variant_type']})\n")
        f.write(f"- **Rule 1 (Do No Harm on Matched)**: {r1_str} (matched RMSE within 0.3 pp of E2 on t3, t4, t12)\n")
        f.write(f"- **Rule 2 (Help Under Mismatch)**: {r2_str} (RMSE at least 50% below E2 on t3 and t4 for +5 mV and -5 mV)\n")
        f.write(f"- **Rule 3 (Beat Coulomb Counting on Offsets)**: {r3_str} (RMSE below E0 on initial-SOC-offset and current-bias)\n\n")

        if not best_config["overall_pass"]:
            f.write("> [!CAUTION]\n")
            f.write("> **No E5 configuration passed all three rules.** Per instructions, no rules are modified and no ad-hoc fixes are attempted.\n\n")
        else:
            f.write("> [!NOTE]\n")
            f.write("> **E5 successfully passed all three pass rules across all evaluation scenarios.**\n\n")

        f.write("## 1. Top Configurations Ranked across the Parameter Grid\n\n")
        f.write("| Rank | Config ID | Variant Type | $\\sigma_{\\text{ocv}}$ (V) | $\\text{slope}_{\\text{ref}}$ (V) | $\\Delta soc_{\\text{max}}$ | Rule 1 | Rule 2 | Avg Red. (%) | Rule 3 | Overall Verdict |\n")
        f.write("| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |\n")

        for idx, sc in enumerate(scored_configs[:10], start=1):
            c = sc["cfg"]
            o_str = "**PASS**" if sc["overall_pass"] else "**FAIL**"
            r1 = "PASS" if sc["rule1_pass"] else "FAIL"
            r2 = "PASS" if sc["rule2_pass"] else "FAIL"
            r3 = "PASS" if sc["rule3_pass"] else "FAIL"
            f.write(
                f"| {idx} | `{c['config_id']}` | {c['variant_type']} | {c['sigma_ocv']} | {c['slope_ref']} | {c['max_soc_step']} | "
                f"{r1} | {r2} | {sc['avg_red_r2']:.1f}% | {r3} | {o_str} |\n"
            )

        f.write("\n## 2. Comprehensive Comparison Table: E0, E2, E6, and E5 Variants\n\n")
        f.write("Comparison across all 5 evaluation scenarios and 3 variants (averaged across 2 seeds).\n")
        f.write("Estimators compared:\n")
        f.write("- **E0**: Coulomb counting\n")
        f.write("- **E2**: Baseline 2RC EKF with hysteresis\n")
        f.write("- **E6**: RBC-DEKF (`CFG_021`: $Q_\\theta=10^{-9}, R_\\theta=10^{-4}, \\sigma_0=0.002$)\n")
        f.write(f"- **E5 (a)**: Variance inflation only (`{best_per_variant['(a)']['cfg']['config_id']}`)\n")
        f.write(f"- **E5 (a+b)**: Variance inflation + slope gating (`{best_per_variant['(a)+(b)']['cfg']['config_id']}`)\n")
        f.write(f"- **E5 (a+b+c)**: Full observability gating (`{best_per_variant['(a)+(b)+(c)']['cfg']['config_id']}`)\n\n")

        f.write("| Scenario | Variant | E0 (pp) | E2 Baseline (pp) | E6 RBC-DEKF (pp) | E5 (a) (pp) | E5 (a+b) (pp) | E5 (a+b+c) (pp) |\n")
        f.write("| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: |\n")

        for sc_name, _ in scenarios:
            for var_name, _ in variants:
                var_label = "matched" if var_name == "matched" else ("mismatch (-5 mV)" if "neg5" in var_name else "mismatch (+5 mV)")
                e0_v = best_config["means"][(sc_name, var_name)]["e0"]
                e2_v = best_config["means"][(sc_name, var_name)]["e2"]
                e6_v = best_config["means"][(sc_name, var_name)]["e6"]
                e5_a_v = best_per_variant["(a)"]["means"][(sc_name, var_name)]["e5"]
                e5_ab_v = best_per_variant["(a)+(b)"]["means"][(sc_name, var_name)]["e5"]
                e5_abc_v = best_per_variant["(a)+(b)+(c)"]["means"][(sc_name, var_name)]["e5"]

                f.write(
                    f"| **{sc_name}** | {var_label} | {e0_v:.2f} | {e2_v:.2f} | {e6_v:.2f} | "
                    f"{e5_a_v:.2f} | {e5_ab_v:.2f} | {e5_abc_v:.2f} |\n"
                )

        f.write("\n## 3. Detailed Audit of Pass Rules for Best E5 Variant (`" + best_config['cfg']['config_id'] + "`)\n\n")

        f.write("### Rule 1: Do No Harm on Matched (Threshold: within 0.30 pp of E2)\n")
        for sc_name in ["t3_bess_24h", "t4_plateau_stress", "t12_hysteresis_mismatch"]:
            e5_val = best_config["means"][(sc_name, "matched")]["e5"]
            e2_val = best_config["means"][(sc_name, "matched")]["e2"]
            diff = e5_val - e2_val
            v_stat = "PASS" if diff <= 0.30 else "FAIL"
            f.write(f"- **{sc_name}**: E5 = `{e5_val:.2f}` pp, E2 = `{e2_val:.2f}` pp, Diff = `{diff:+.2f}` pp -> **{v_stat}**\n")

        f.write("\n### Rule 2: Help Under Mismatch (Threshold: at least 50% below E2 on t3 and t4)\n")
        for sc_name in ["t3_bess_24h", "t4_plateau_stress"]:
            for var_name in ["mismatched_neg5", "mismatched_pos5"]:
                sign_str = "-5 mV" if "neg" in var_name else "+5 mV"
                e5_val = best_config["means"][(sc_name, var_name)]["e5"]
                e2_val = best_config["means"][(sc_name, var_name)]["e2"]
                target = 0.50 * e2_val
                ratio = e5_val / e2_val
                reduction = (1.0 - ratio) * 100.0
                v_stat = "PASS" if e5_val <= target else "FAIL"
                f.write(
                    f"- **{sc_name} ({sign_str})**: E5 = `{e5_val:.2f}` pp, E2 = `{e2_val:.2f}` pp, "
                    f"Reduction = `{reduction:.1f}%` (target >= 50.0%) -> **{v_stat}**\n"
                )

        f.write("\n### Rule 3: Beat Coulomb Counting on Offset Scenarios (Threshold: RMSE < E0)\n")
        for sc_name in ["t5_initial_soc_offset", "t6_current_bias"]:
            for var_name in ["matched", "mismatched_neg5", "mismatched_pos5"]:
                var_label = "matched" if var_name == "matched" else ("-5 mV" if "neg5" in var_name else "+5 mV")
                e5_val = best_config["means"][(sc_name, var_name)]["e5"]
                e0_val = best_config["means"][(sc_name, var_name)]["e0"]
                v_stat = "PASS" if e5_val < e0_val else "FAIL"
                f.write(
                    f"- **{sc_name} ({var_label})**: E5 = `{e5_val:.2f}` pp vs E0 = `{e0_val:.2f}` pp -> **{v_stat}**\n"
                )

        f.write("\n## 4. Architectural Assumptions & Differences from Shi et al. (2026)\n\n")
        f.write(
            "1. **Discrete-Time EKF Framework**: Shi et al. (2026) formulate Fisher-information weighting in a continuous-time "
            "observer framework. E5 adapts this concept into a discrete-time EKF combined with a 2RC equivalent circuit model "
            "and 1-state hysteresis.\n"
            "2. **State-Selective Observability Gating**: The gating $g = \\min(1, |\\partial\\text{OCV}/\\partial\\text{SOC}| / \\text{slope}_{\\text{ref}})$ "
            "and per-step cap $\\Delta soc_{\\text{max}}$ are applied strictly to the SOC state correction. Polarization current states "
            "($i_1, i_2$) and hysteresis ($h$) retain unattenuated Kalman gain corrections to maintain accurate dynamic voltage modeling.\n"
            "3. **Joseph Covariance Consistency**: To prevent overconfidence and covariance matrix singularity when updates are gated "
            "on the plateau, an effective Kalman gain $K_{\\text{eff}}$ is constructed and propagated via the Joseph stabilized formulation "
            "$P^+ = (I - K_{\\text{eff}} H) P (I - K_{\\text{eff}} H)^T + K_{\\text{eff}} R_{\\text{eff}} K_{\\text{eff}}^T$.\n"
            "4. **Additive Model Uncertainty Inflation**: Measurement variance is inflated by an additive model uncertainty term "
            "$R_{\\text{eff}} = R_v + \\sigma_{\\text{ocv\\_model}}^2$.\n"
            "5. **Dropout Handling**: In the presence of dropouts (NaN inputs), E5 executes time propagation only without measurement update.\n"
        )

    print(f"Report written to: {report_path}")
    print(f"Overall verdict: {'PASS' if best_config['overall_pass'] else 'FAIL'}")


if __name__ == "__main__":
    main()
