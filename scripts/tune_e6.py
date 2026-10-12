"""E6 Tuning Script and Verdict Generator.

Grid:
- filter.rbc_q_theta in [1e-12, 1e-10, 1e-9, 1e-8, 1e-6]
- filter.rbc_r_theta in [2.5e-5, 1e-4]
- filter.rbc_initial_theta_std in [0.002, 0.02]
- filter.rbc_use_hysteresis_state in [True, False]

Scenarios:
- t3_bess_24h (profile: bess)
- t4_plateau_stress (profile: automotive)
- t12_hysteresis_mismatch (profile: automotive)

Variants:
- matched
- mismatched with estimator_model.mismatch.ocv_offset_mv = -5.0
- mismatched with estimator_model.mismatch.ocv_offset_mv = +5.0

Pass Rules (for E6 with rbc_use_hysteresis_state=True):
- Rule 1 (do no harm): matched RMSE within 0.3 pp of E2 on all 3 scenarios.
- Rule 2 (help under mismatch): for both offset signs, E6 RMSE < E2 on all 3 scenarios,
  with average reduction >= 20%.
- Rule 3 (sanity): in +5 mV and -5 mV runs, theta settles toward the offset with correct sign.
"""

import argparse
import csv
import itertools
from pathlib import Path
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

import matplotlib.pyplot as plt
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
) -> Tuple[List[float], List[float]]:
    """Execute estimator on measurement stream, returning (held_soc_estimates, theta_series)."""
    est = get_estimator(est_name, params)
    est.reset(init_soc)

    held_socs: List[float] = []
    thetas: List[float] = []
    curr_soc = init_soc

    for m in measurements:
        out = est.step(m)
        if not m.dropout:
            curr_soc = out.soc
        held_socs.append(curr_soc)
        thetas.append(getattr(est, "theta", float("nan")))

    return held_socs, thetas


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
    parser = argparse.ArgumentParser(description="Tune estimator E6 across parameter grid.")
    parser.add_argument("--csv", default="reports/e6_tuning.csv", help="Path to output CSV.")
    parser.add_argument("--report", default="reports/e6_tuning.md", help="Path to output report markdown.")
    parser.add_argument("--plot", default="reports/e6_theta_t3_bess_24h.png", help="Path to output plot PNG.")
    parser.add_argument("--seeds", type=int, default=2, help="Number of random seeds (default 2).")
    args = parser.parse_args()

    csv_path = Path(args.csv)
    report_path = Path(args.report)
    plot_path = Path(args.plot)

    csv_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    plot_path.parent.mkdir(parents=True, exist_ok=True)

    # 1. Grid definition
    q_theta_vals = [1e-12, 1e-10, 1e-9, 1e-8, 1e-6]
    r_theta_vals = [2.5e-5, 1e-4]
    std_theta_vals = [0.002, 0.02]
    use_hyst_vals = [True, False]

    configs = []
    cfg_idx = 1
    for q, r, std, hyst in itertools.product(q_theta_vals, r_theta_vals, std_theta_vals, use_hyst_vals):
        configs.append({
            "config_id": f"CFG_{cfg_idx:03d}",
            "q_theta": q,
            "r_theta": r,
            "initial_theta_std": std,
            "use_hysteresis": hyst,
        })
        cfg_idx += 1

    scenarios = [
        ("t3_bess_24h", "bess"),
        ("t4_plateau_stress", "automotive"),
        ("t12_hysteresis_mismatch", "automotive"),
    ]

    variants = [
        ("matched", 0.0),
        ("mismatched_neg5", -5.0),
        ("mismatched_pos5", 5.0),
    ]

    seeds = list(range(args.seeds))

    runner = ScenarioRunner()

    print(f"================================================================")
    print(f"E6 Grid Tuning: {len(configs)} configs, {len(scenarios)} scenarios, {len(variants)} variants, {len(seeds)} seeds")
    print(f"Total E6 evaluations: {len(configs) * len(scenarios) * len(variants) * len(seeds)}")
    print(f"Output CSV: {csv_path}")
    print(f"================================================================")

    # 2. Pre-generate and cache measurement streams and baseline estimators (E1, E2)
    # Cache key: (sc_name, var_name, seed_idx)
    cached_streams: Dict[Tuple[str, str, int], Any] = {}
    cached_baselines: Dict[Tuple[str, str, int], Dict[str, Any]] = {}

    print("Phase 1/3: Generating measurement streams and evaluating E1, E2 baselines...")
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

                # Run E2 baseline
                init_soc = float(assumptions.duty.initial_soc.value) + float(assumptions.filter.initial_soc_offset.value)
                p_e2 = ParamSet.from_assumptions(assumptions, matched=is_matched)
                e2_socs, _ = step_estimator("E2", p_e2, meas, init_soc)
                e2_rmse, e2_max, e2_plat = compute_metrics(e2_socs, truths, meas)

                # Run E1 baseline
                p_e1 = ParamSet.from_assumptions(assumptions, matched=is_matched)
                e1_socs, _ = step_estimator("E1", p_e1, meas, init_soc)
                e1_rmse, e1_max, e1_plat = compute_metrics(e1_socs, truths, meas)

                cached_baselines[key] = {
                    "e2_rmse": e2_rmse * PERCENT_FACTOR,
                    "e2_max": e2_max * PERCENT_FACTOR,
                    "e2_plat": e2_plat * PERCENT_FACTOR,
                    "e1_rmse": e1_rmse * PERCENT_FACTOR,
                    "e1_max": e1_max * PERCENT_FACTOR,
                    "e1_plat": e1_plat * PERCENT_FACTOR,
                }
    t1_base = time.perf_counter()
    print(f"Phase 1 complete in {t1_base - t0_base:.2f} s. Baseline results cached.")

    # 3. Read existing CSV for resume support
    existing_keys = set()
    csv_fields = [
        "config_id",
        "q_theta",
        "r_theta",
        "initial_theta_std",
        "use_hysteresis",
        "scenario",
        "variant",
        "seed_index",
        "e6_rmse_pp",
        "e6_max_err_pp",
        "e6_plat_rmse_pp",
        "final_theta_v",
        "e2_rmse_pp",
        "e1_rmse_pp",
    ]

    if csv_path.exists():
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                existing_keys.add((
                    row["config_id"],
                    row["scenario"],
                    row["variant"],
                    int(row["seed_index"]),
                ))
        print(f"Resuming: found {len(existing_keys)} completed rows in {csv_path}")

    # Open CSV for appending
    write_header = not csv_path.exists() or csv_path.stat().st_size == 0
    csv_file = open(csv_path, "a", newline="", encoding="utf-8")
    writer = csv.DictWriter(csv_file, fieldnames=csv_fields)
    if write_header:
        writer.writeheader()
        csv_file.flush()

    # 4. Evaluate E6 across grid
    print("Phase 2/3: Evaluating E6 configurations...")
    t0_e6 = time.perf_counter()
    eval_count = 0

    # Also store detailed runs for plotting the best config
    # Dict: (config_id, sc, var, seed) -> thetas
    theta_traces: Dict[Tuple[str, str, str, int], Tuple[List[float], List[float]]] = {}

    for cfg in configs:
        cid = cfg["config_id"]
        q_th = cfg["q_theta"]
        r_th = cfg["r_theta"]
        std_th = cfg["initial_theta_std"]
        use_hyst = cfg["use_hysteresis"]

        for sc_name, _ in scenarios:
            for var_name, offset_mv in variants:
                is_matched = var_name == "matched"
                for seed_idx in seeds:
                    eval_key = (cid, sc_name, var_name, seed_idx)
                    if eval_key in existing_keys:
                        continue

                    stream_key = (sc_name, var_name, seed_idx)
                    assumptions, meas, truths, times = cached_streams[stream_key]
                    base_info = cached_baselines[stream_key]

                    # Construct ParamSet with specific E6 grid tunings
                    p_orig = ParamSet.from_assumptions(assumptions, matched=is_matched)
                    p_e6 = ParamSet(
                        nominal_capacity_ah=p_orig.nominal_capacity_ah,
                        coulombic_efficiency=p_orig.coulombic_efficiency,
                        soc_grid=p_orig.soc_grid,
                        temperatures_c=p_orig.temperatures_c,
                        ocv_table=p_orig.ocv_table,
                        r0_table=p_orig.r0_table,
                        r1_table=p_orig.r1_table,
                        tau1_table=p_orig.tau1_table,
                        r2_table=p_orig.r2_table,
                        tau2_table=p_orig.tau2_table,
                        hysteresis_amplitude_v=p_orig.hysteresis_amplitude_v,
                        hysteresis_gamma=p_orig.hysteresis_gamma,
                        initial_soc_std=p_orig.initial_soc_std,
                        initial_rc_current_std_a=p_orig.initial_rc_current_std_a,
                        initial_hysteresis_std=p_orig.initial_hysteresis_std,
                        process_noise_q_soc=p_orig.process_noise_q_soc,
                        process_noise_q_rc=p_orig.process_noise_q_rc,
                        process_noise_q_hysteresis=p_orig.process_noise_q_hysteresis,
                        measurement_noise_r_v=p_orig.measurement_noise_r_v,
                        anchor_enabled=p_orig.anchor_enabled,
                        rest_anchor_enabled=p_orig.rest_anchor_enabled,
                        rest_current_threshold_a=p_orig.rest_current_threshold_a,
                        rest_duration_threshold_s=p_orig.rest_duration_threshold_s,
                        full_charge_voltage_threshold_v=p_orig.full_charge_voltage_threshold_v,
                        full_charge_current_threshold_a=p_orig.full_charge_current_threshold_a,
                        full_charge_anchor_soc=p_orig.full_charge_anchor_soc,
                        full_charge_anchor_enabled=p_orig.full_charge_anchor_enabled,
                        full_charge_hold_s=p_orig.full_charge_hold_s,
                        rbc_use_hysteresis_state=use_hyst,
                        rbc_q_theta=q_th,
                        rbc_r_theta=r_th,
                        rbc_initial_theta_std=std_th,
                    )

                    init_soc = float(assumptions.duty.initial_soc.value) + float(assumptions.filter.initial_soc_offset.value)
                    e6_socs, thetas = step_estimator("E6", p_e6, meas, init_soc)
                    e6_rmse, e6_max, e6_plat = compute_metrics(e6_socs, truths, meas)

                    final_th = thetas[-1] if thetas else float("nan")

                    # Record trace for potential plotting
                    if sc_name == "t3_bess_24h" and var_name == "mismatched_pos5" and seed_idx == 0:
                        theta_traces[eval_key] = (times, thetas)

                    row_dict = {
                        "config_id": cid,
                        "q_theta": f"{q_th:.1e}",
                        "r_theta": f"{r_th:.1e}",
                        "initial_theta_std": f"{std_th:.4f}",
                        "use_hysteresis": str(use_hyst),
                        "scenario": sc_name,
                        "variant": var_name,
                        "seed_index": seed_idx,
                        "e6_rmse_pp": f"{e6_rmse * PERCENT_FACTOR:.4f}",
                        "e6_max_err_pp": f"{e6_max * PERCENT_FACTOR:.4f}",
                        "e6_plat_rmse_pp": f"{e6_plat * PERCENT_FACTOR:.4f}",
                        "final_theta_v": f"{final_th:.6f}",
                        "e2_rmse_pp": f"{base_info['e2_rmse']:.4f}",
                        "e1_rmse_pp": f"{base_info['e1_rmse']:.4f}",
                    }
                    writer.writerow(row_dict)
                    csv_file.flush()
                    eval_count += 1

                    if eval_count % 50 == 0:
                        print(f"  Processed {eval_count} runs (elapsed: {time.perf_counter() - t0_e6:.1f} s)...")

    csv_file.close()
    t1_e6 = time.perf_counter()
    print(f"Phase 2 complete. Evaluated {eval_count} runs in {t1_e6 - t0_e6:.2f} s.")

    # 5. Analysis and Rule Verification
    print("Phase 3/3: Evaluating rules, ranking configs, and generating report...")

    # Load complete CSV to guarantee consistent aggregated evaluation
    all_rows = []
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            all_rows.append(r)

    # Group by (config_id, scenario, variant) -> average across seeds
    grouped = {}
    cfg_meta = {}
    for r in all_rows:
        cid = r["config_id"]
        sc = r["scenario"]
        var = r["variant"]
        key = (cid, sc, var)
        if key not in grouped:
            grouped[key] = {
                "e6_rmse": [],
                "e2_rmse": [],
                "e1_rmse": [],
                "final_theta": [],
            }
        grouped[key]["e6_rmse"].append(float(r["e6_rmse_pp"]))
        grouped[key]["e2_rmse"].append(float(r["e2_rmse_pp"]))
        grouped[key]["e1_rmse"].append(float(r["e1_rmse_pp"]))
        grouped[key]["final_theta"].append(float(r["final_theta_v"]))

        if cid not in cfg_meta:
            cfg_meta[cid] = {
                "config_id": cid,
                "q_theta": float(r["q_theta"]),
                "r_theta": float(r["r_theta"]),
                "initial_theta_std": float(r["initial_theta_std"]),
                "use_hysteresis": r["use_hysteresis"].lower() == "true",
            }

    # Aggregate means
    agg = {}
    for key, vals in grouped.items():
        agg[key] = {
            "e6_rmse": float(np.mean(vals["e6_rmse"])),
            "e2_rmse": float(np.mean(vals["e2_rmse"])),
            "e1_rmse": float(np.mean(vals["e1_rmse"])),
            "final_theta": float(np.mean(vals["final_theta"])),
        }

    # Evaluate Pass Rules for all configs where use_hysteresis == True
    config_scores = []
    sc_list = [s[0] for s in scenarios]

    for cid, meta in cfg_meta.items():
        if not meta["use_hysteresis"]:
            continue

        # Rule 1 (do no harm): matched RMSE is within 0.3 pp of E2 on all three scenarios
        rule_1_pass = True
        rule_1_max_dev = 0.0  # max(0, e6_rmse - e2_rmse - 0.30)
        matched_diffs = {}
        for sc in sc_list:
            e6_m = agg[(cid, sc, "matched")]["e6_rmse"]
            e2_m = agg[(cid, sc, "matched")]["e2_rmse"]
            diff = e6_m - e2_m
            matched_diffs[sc] = diff
            dev = max(0.0, diff - 0.30)
            if dev > 0.0:
                rule_1_pass = False
            rule_1_max_dev = max(rule_1_max_dev, dev)

        # Rule 2 (help under mismatch):
        # for both offset signs, E6 RMSE is below E2 on all three scenarios,
        # with an average reduction of at least 20%.
        rule_2_all_below = True
        reductions = []
        mism_dev = 0.0

        for sc in sc_list:
            for var in ["mismatched_neg5", "mismatched_pos5"]:
                e6_v = agg[(cid, sc, var)]["e6_rmse"]
                e2_v = agg[(cid, sc, var)]["e2_rmse"]
                if e6_v >= e2_v:
                    rule_2_all_below = False
                    mism_dev += (e6_v - e2_v)
                red = (e2_v - e6_v) / e2_v
                reductions.append(red)

        avg_reduction = float(np.mean(reductions))
        rule_2_red_pass = avg_reduction >= 0.20
        rule_2_pass = rule_2_all_below and rule_2_red_pass

        rule_2_avg_dev = max(0.0, 0.20 - avg_reduction)

        # Rule 3 (sanity): in the +5 mV and -5 mV runs, theta settles toward the injected offset with correct sign
        # For +5 mV (model too high), theta settles negative (compensating positive model offset)
        # For -5 mV (model too low), theta settles positive (compensating negative model offset)
        rule_3_pass = True
        theta_signs = {}
        for sc in sc_list:
            th_pos5 = agg[(cid, sc, "mismatched_pos5")]["final_theta"]
            th_neg5 = agg[(cid, sc, "mismatched_neg5")]["final_theta"]
            theta_signs[f"{sc}_pos5"] = th_pos5
            theta_signs[f"{sc}_neg5"] = th_neg5
            if th_pos5 >= 0.0 or th_neg5 <= 0.0:
                rule_3_pass = False

        overall_pass = rule_1_pass and rule_2_pass and rule_3_pass

        # Total penalty for ranking (lower is better; 0 means perfectly satisfies all constraints)
        penalty = rule_1_max_dev * 10.0 + mism_dev + rule_2_avg_dev * 10.0
        if not rule_3_pass:
            penalty += 50.0

        config_scores.append({
            "cid": cid,
            "meta": meta,
            "rule_1_pass": rule_1_pass,
            "rule_1_max_dev": rule_1_max_dev,
            "rule_2_pass": rule_2_pass,
            "rule_2_all_below": rule_2_all_below,
            "avg_reduction_pct": avg_reduction * PERCENT_FACTOR,
            "rule_3_pass": rule_3_pass,
            "overall_pass": overall_pass,
            "penalty": penalty,
            "matched_diffs": matched_diffs,
            "theta_signs": theta_signs,
        })

    # Sort configs: passing first, then by penalty ascending, then by avg_reduction descending
    config_scores.sort(key=lambda x: (not x["overall_pass"], x["penalty"], -x["avg_reduction_pct"]))

    top5 = config_scores[:5]
    best = top5[0]

    # Find the matching E6(false) config for the best config
    best_cid_false = None
    for cid, meta in cfg_meta.items():
        if not meta["use_hysteresis"]:
            if (
                meta["q_theta"] == best["meta"]["q_theta"]
                and meta["r_theta"] == best["meta"]["r_theta"]
                and meta["initial_theta_std"] == best["meta"]["initial_theta_std"]
            ):
                best_cid_false = cid
                break

    # 6. Generate Theta-vs-Time Plot for best config on t3_bess_24h at +5 mV
    print(f"Generating plot for best config {best['cid']} on t3_bess_24h (+5 mV)...")
    # If trace was captured in memory, use it; else re-run this single condition
    plot_trace_key = (best["cid"], "t3_bess_24h", "mismatched_pos5", 0)
    if plot_trace_key in theta_traces:
        p_times, p_thetas = theta_traces[plot_trace_key]
    else:
        # Re-run single step for plot
        stream_key = ("t3_bess_24h", "mismatched_pos5", 0)
        assumptions, meas, truths, times = cached_streams[stream_key]
        p_orig = ParamSet.from_assumptions(assumptions, matched=False)
        p_plot = ParamSet(
            nominal_capacity_ah=p_orig.nominal_capacity_ah,
            coulombic_efficiency=p_orig.coulombic_efficiency,
            soc_grid=p_orig.soc_grid,
            temperatures_c=p_orig.temperatures_c,
            ocv_table=p_orig.ocv_table,
            r0_table=p_orig.r0_table,
            r1_table=p_orig.r1_table,
            tau1_table=p_orig.tau1_table,
            r2_table=p_orig.r2_table,
            tau2_table=p_orig.tau2_table,
            hysteresis_amplitude_v=p_orig.hysteresis_amplitude_v,
            hysteresis_gamma=p_orig.hysteresis_gamma,
            initial_soc_std=p_orig.initial_soc_std,
            initial_rc_current_std_a=p_orig.initial_rc_current_std_a,
            initial_hysteresis_std=p_orig.initial_hysteresis_std,
            process_noise_q_soc=p_orig.process_noise_q_soc,
            process_noise_q_rc=p_orig.process_noise_q_rc,
            process_noise_q_hysteresis=p_orig.process_noise_q_hysteresis,
            measurement_noise_r_v=p_orig.measurement_noise_r_v,
            anchor_enabled=p_orig.anchor_enabled,
            rest_anchor_enabled=p_orig.rest_anchor_enabled,
            rest_current_threshold_a=p_orig.rest_current_threshold_a,
            rest_duration_threshold_s=p_orig.rest_duration_threshold_s,
            full_charge_voltage_threshold_v=p_orig.full_charge_voltage_threshold_v,
            full_charge_current_threshold_a=p_orig.full_charge_current_threshold_a,
            full_charge_anchor_soc=p_orig.full_charge_anchor_soc,
            full_charge_anchor_enabled=p_orig.full_charge_anchor_enabled,
            full_charge_hold_s=p_orig.full_charge_hold_s,
            rbc_use_hysteresis_state=True,
            rbc_q_theta=best["meta"]["q_theta"],
            rbc_r_theta=best["meta"]["r_theta"],
            rbc_initial_theta_std=best["meta"]["initial_theta_std"],
        )
        init_soc = float(assumptions.duty.initial_soc.value) + float(assumptions.filter.initial_soc_offset.value)
        _, p_thetas = step_estimator("E6", p_plot, meas, init_soc)
        p_times = times

    # Convert times to hours and thetas to mV
    times_hr = [t / 3600.0 for t in p_times]
    thetas_mv = [th * 1000.0 for th in p_thetas]

    plt.figure(figsize=(10, 4.5), dpi=150)
    plt.plot(times_hr, thetas_mv, label=r"Estimated Residual Bias $\hat{\theta}(t)$", color="#1f77b4", linewidth=1.5)
    plt.axhline(-5.0, color="#d62728", linestyle="--", label="Target Injected Offset (-5.0 mV)")
    plt.axhline(0.0, color="#7f7f7f", linestyle=":", alpha=0.7)
    plt.xlabel("Time (hours)")
    plt.ylabel(r"Residual Bias $\theta$ (mV)")
    plt.title(f"E6 Residual Bias Convergence on t3_bess_24h (+5 mV OCV Mismatch)\nConfig {best['cid']} (Q_theta={best['meta']['q_theta']:.1e}, R_theta={best['meta']['r_theta']:.1e}, std0={best['meta']['initial_theta_std']})")
    plt.grid(True, linestyle="--", alpha=0.5)
    plt.legend(loc="best")
    plt.tight_layout()
    plt.savefig(plot_path)
    plt.close()
    print(f"Plot saved to {plot_path}")

    # 7. Generate markdown report
    print(f"Writing tuning report to {report_path}...")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("# E6 Tuning & Pass/Fail Verdict Report\n\n")

        # Overall Verdict Section
        f.write("## Executive Verdict\n\n")
        f.write(f"- **Overall Verdict**: **{'PASS' if best['overall_pass'] else 'FAIL'}**\n")
        f.write(f"- **Rule 1 (Do No Harm)**: **{'PASS' if best['rule_1_pass'] else 'FAIL'}** (matched RMSE within 0.3 pp of E2)\n")
        f.write(f"- **Rule 2 (Help Under Mismatch)**: **{'PASS' if best['rule_2_pass'] else 'FAIL'}** (RMSE below E2 on all scenarios, avg reduction >= 20%)\n")
        f.write(f"- **Rule 3 (Sanity)**: **{'PASS' if best['rule_3_pass'] else 'FAIL'}** (theta settles with correct sign to counteract injected offset)\n\n")

        if not best["overall_pass"]:
            f.write("> [!CAUTION]\n")
            f.write("> **No configuration passed all three rules.** Per instructions, no further fixes or rule modifications are attempted.\n\n")

        # Top 5 Configs Table
        f.write("## 1. Top 5 Configurations Ranked by Worst-Case Deviation\n\n")
        f.write("| Rank | Config ID | $Q_\\theta$ | $R_\\theta$ | $\\sigma_0(\\theta)$ | Rule 1 | Rule 2 | Avg Red. (%) | Rule 3 | Overall | Penalty |\n")
        f.write("| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |\n")
        for rank, c in enumerate(top5, 1):
            f.write(
                f"| {rank} | `{c['cid']}` | {c['meta']['q_theta']:.1e} | {c['meta']['r_theta']:.1e} | {c['meta']['initial_theta_std']} | "
                f"{'PASS' if c['rule_1_pass'] else 'FAIL'} | {'PASS' if c['rule_2_pass'] else 'FAIL'} | {c['avg_reduction_pct']:.1f}% | "
                f"{'PASS' if c['rule_3_pass'] else 'FAIL'} | **{'PASS' if c['overall_pass'] else 'FAIL'}** | {c['penalty']:.2f} |\n"
            )
        f.write("\n")

        # Best Config Details
        f.write("## 2. Side-by-Side Comparison for Best Configuration\n\n")
        f.write(f"**Best Configuration (`{best['cid']}`) Tunings**:\n")
        f.write(f"- `filter.rbc_q_theta`: `{best['meta']['q_theta']:.1e}`\n")
        f.write(f"- `filter.rbc_r_theta`: `{best['meta']['r_theta']:.1e}`\n")
        f.write(f"- `filter.rbc_initial_theta_std`: `{best['meta']['initial_theta_std']}`\n\n")

        f.write("| Scenario | Variant | Metric | E2 (Baseline) | E6 (`flag=true`) | E6 (`flag=false`) | E1 (Reference) |\n")
        f.write("| :--- | :--- | :--- | :---: | :---: | :---: | :---: |\n")

        for sc_name, _ in scenarios:
            for var_name, _ in variants:
                var_label = {
                    "matched": "matched",
                    "mismatched_neg5": "mismatch (-5 mV)",
                    "mismatched_pos5": "mismatch (+5 mV)",
                }[var_name]

                e2_r = agg[(best["cid"], sc_name, var_name)]["e2_rmse"]
                e6_true_r = agg[(best["cid"], sc_name, var_name)]["e6_rmse"]
                e6_false_r = agg[(best_cid_false, sc_name, var_name)]["e6_rmse"] if best_cid_false else float("nan")
                e1_r = agg[(best["cid"], sc_name, var_name)]["e1_rmse"]

                f.write(f"| **{sc_name}** | {var_label} | RMSE (pp) | {e2_r:.2f} | {e6_true_r:.2f} | {e6_false_r:.2f} | {e1_r:.2f} |\n")

        f.write("\n")

        # Plot Section
        f.write("## 3. Theta vs Time Convergence Plot\n\n")
        f.write(f"Convergence of residual bias $\\hat{{\\theta}}(t)$ on `t3_bess_24h` under +5 mV OCV mismatch:\n\n")
        f.write(f"![Residual Bias Convergence]({plot_path.name})\n\n")

        # Rule Audit Details
        f.write("## 4. Detailed Audit of Pass Rules for Best Configuration\n\n")
        f.write("### Rule 1: Do No Harm (Matched RMSE <= E2 + 0.30 pp)\n")
        for sc in sc_list:
            diff = best["matched_diffs"][sc]
            status = "PASS" if diff <= 0.30 else "FAIL"
            f.write(f"- **{sc}**: E6 RMSE minus E2 RMSE = `{diff:+.2f}` pp (threshold: +0.30 pp) -> **{status}**\n")
        f.write("\n")

        f.write("### Rule 2: Help Under Mismatch (RMSE < E2 on all scenarios, Avg Reduction >= 20%)\n")
        f.write(f"- **Average Error Reduction**: `{best['avg_reduction_pct']:.1f}%` (threshold: >= 20.0%) -> **{'PASS' if best['rule_2_pass'] else 'FAIL'}**\n")
        for sc in sc_list:
            for var in ["mismatched_neg5", "mismatched_pos5"]:
                e6_v = agg[(best["cid"], sc, var)]["e6_rmse"]
                e2_v = agg[(best["cid"], sc, var)]["e2_rmse"]
                st = "PASS" if e6_v < e2_v else "FAIL"
                f.write(f"- **{sc} ({var})**: E6 `{e6_v:.2f}` pp vs E2 `{e2_v:.2f}` pp -> **{st}**\n")
        f.write("\n")

        f.write("### Rule 3: Sanity (Theta Settling Sign)\n")
        for sc in sc_list:
            th_pos = best["theta_signs"][f"{sc}_pos5"] * 1000.0
            th_neg = best["theta_signs"][f"{sc}_neg5"] * 1000.0
            st_pos = "PASS" if th_pos < 0.0 else "FAIL"
            st_neg = "PASS" if th_neg > 0.0 else "FAIL"
            f.write(f"- **{sc} (+5 mV)**: final $\\theta$ = `{th_pos:+.2f}` mV (expected negative) -> **{st_pos}**\n")
            f.write(f"- **{sc} (-5 mV)**: final $\\theta$ = `{th_neg:+.2f}` mV (expected positive) -> **{st_neg}**\n")
        f.write("\n")

    print(f"Report generated successfully at {report_path}.")
    print(f"Overall verdict: {'PASS' if best['overall_pass'] else 'FAIL'}")


if __name__ == "__main__":
    main()
