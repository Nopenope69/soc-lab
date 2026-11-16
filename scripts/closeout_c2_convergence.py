"""Closeout C2: Convergence and Region Decomposition Analysis.

Evaluates frozen E7v3 and fair E0 on S-B and S-G across DST, US06, FUDS at 20, 30, 40, 50 C
on Cell A1-007 and Cell A1-008.

Metrics computed:
1. Time (s) until |error| first stays below 2 pp for 60 s.
2. Fraction of cases that never converge before window ends.
3. Error at window end (|e_end| in pp).
4. Median and 90th percentile convergence time by offset size and by start SOC.
5. Variance / RMSE reduction decomposition: plateau (10-90%) vs knees (<10%, >90%).
"""

from dataclasses import replace
import json
from pathlib import Path
import sys
import time
from typing import Any, Dict, List
import numpy as np

repo_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo_root))

from soc.assumptions.loader import load_assumptions
from soc.estimators.base import ParamSet
from soc.estimators.e0_coulomb import E0CoulombCounting
from soc.estimators.e7v3 import E7V3CompositeFilter
from scripts.gauntlet_v3_scenarios import (
    prepare_scenario_data_v3,
    init_estimator_state,
    run_stream_slice,
    ScenarioDataSet,
)

PROFILES = ["DST", "US06", "FUDS"]
CELLS = ["A1-007", "A1-008"]
DECISION_TEMPS = [20, 30, 40, 50]

CONVERGE_THRESH_PP = 2.0
HOLD_DURATION_S = 60.0


def compute_convergence_time(err_pp: np.ndarray, dt_arr: np.ndarray) -> float:
    """Find the first time t (s) where |err_pp| remains <= CONVERGE_THRESH_PP for >= HOLD_DURATION_S."""
    n = len(err_pp)
    abs_err = np.abs(err_pp)
    time_elapsed = np.cumsum(dt_arr)

    # Window duration check
    for i in range(n):
        if abs_err[i] <= CONVERGE_THRESH_PP:
            # Check if it holds for HOLD_DURATION_S
            hold_time = 0.0
            held = True
            for j in range(i, n):
                if abs_err[j] > CONVERGE_THRESH_PP:
                    held = False
                    break
                hold_time += dt_arr[j]
                if hold_time >= HOLD_DURATION_S:
                    return float(time_elapsed[i])
            if held and hold_time >= HOLD_DURATION_S:
                return float(time_elapsed[i])

    return float("inf")


def run_c2_analysis():
    print("=" * 80)
    print("GAUNTLET V3 CLOSE-OUT: C2 CONVERGENCE ANALYSIS")
    print("=" * 80)

    t0_start = time.time()

    # Load frozen parameters
    assumptions, _, _ = load_assumptions(profile="calce_a123_v4")
    base_params = ParamSet.from_assumptions(assumptions, matched=True)
    frozen_params = replace(
        base_params,
        process_noise_q_soc=2.0e-09,
        process_noise_q_rc=1.1198164932559382e-05,
        process_noise_q_hysteresis=0.00017150882346504795,
        measurement_noise_r_v=0.0008610323423725228,
        e4_rls_forgetting_factor=0.9990,
        e5_slope_ref=0.20,
        e5_cap_plateau=2.0e-05,
        e5_cap_knee=0.01,
        e5_sigma_ocv_model_v=0.02,
    )

    sb_target_socs = [0.80, 0.60, 0.40, 0.20]
    sb_offsets_pp = [-10.0, -5.0, +5.0, +10.0]

    sg_target_socs = [0.80, 0.60, 0.40]
    sg_offsets_pp = [-5.0, -3.0, +3.0, +5.0]

    all_case_records = []

    for prof in PROFILES:
        for cell in CELLS:
            for temp in DECISION_TEMPS:
                print(f"Running {prof} {cell} @ {temp} C...")
                data = prepare_scenario_data_v3(temp, profile=prof, cell_id=cell)
                n = len(data.time_s)

                # Fair E0 capacity
                e0_params = replace(base_params, nominal_capacity_ah=data.cap_c20_007)

                # 1. S-B Cases (16 cases, unknown start soc_std = 0.10)
                for z_tgt in sb_target_socs:
                    cross_idx = np.where(data.truth_soc <= z_tgt)[0]
                    if len(cross_idx) == 0:
                        continue
                    k0 = int(cross_idx[0])

                    for off_pp in sb_offsets_pp:
                        off_frac = off_pp / 100.0
                        z_init = min(max(float(data.truth_soc[k0] + off_frac), 0.0), 1.0)

                        # E7v3
                        est_v3 = E7V3CompositeFilter(frozen_params)
                        init_estimator_state(
                            est_v3,
                            soc0=z_init,
                            soc_std=0.10,
                            i1=data.i1_truth[k0],
                            i2=data.i2_truth[k0],
                            h=data.h_truth[k0],
                        )
                        soc_v3 = run_stream_slice(est_v3, data, k0, n)

                        # E0
                        est_e0 = E0CoulombCounting(e0_params)
                        init_estimator_state(
                            est_e0,
                            soc0=z_init,
                            soc_std=0.10,
                            i1=0.0,
                            i2=0.0,
                            h=0.0,
                        )
                        soc_e0 = run_stream_slice(est_e0, data, k0, n)

                        truth_w = data.truth_soc[k0:]
                        dt_w = data.dt_arr[k0:]
                        err_v3 = (soc_v3 - truth_w) * 100.0
                        err_e0 = (soc_e0 - truth_w) * 100.0

                        conv_time_s = compute_convergence_time(err_v3, dt_w)
                        never_conv = math.isinf(conv_time_s)
                        end_err_pp = float(abs(err_v3[-1]))

                        # Region decomposition
                        # Plateau: 10% <= truth <= 90%
                        # Knees: truth < 10% or truth > 90%
                        m_plat = (truth_w >= 0.10) & (truth_w <= 0.90)
                        m_knee = ~m_plat

                        sum_sq_e0_plat = float(np.sum(err_e0[m_plat] ** 2)) if np.any(m_plat) else 0.0
                        sum_sq_e0_knee = float(np.sum(err_e0[m_knee] ** 2)) if np.any(m_knee) else 0.0
                        sum_sq_v3_plat = float(np.sum(err_v3[m_plat] ** 2)) if np.any(m_plat) else 0.0
                        sum_sq_v3_knee = float(np.sum(err_v3[m_knee] ** 2)) if np.any(m_knee) else 0.0

                        delta_ss_total = float(np.sum(err_e0 ** 2) - np.sum(err_v3 ** 2))
                        delta_ss_plat = sum_sq_e0_plat - sum_sq_v3_plat
                        delta_ss_knee = sum_sq_e0_knee - sum_sq_v3_knee

                        rmse_v3 = float(np.sqrt(np.mean(err_v3 ** 2)))
                        rmse_e0 = float(np.sqrt(np.mean(err_e0 ** 2)))

                        all_case_records.append({
                            "scenario": "S-B",
                            "profile": prof,
                            "cell": cell,
                            "temp": temp,
                            "target_soc": z_tgt,
                            "offset_pp": off_pp,
                            "abs_offset_pp": abs(off_pp),
                            "window_len_s": float(np.sum(dt_w)),
                            "conv_time_s": conv_time_s,
                            "never_converged": never_conv,
                            "end_err_pp": end_err_pp,
                            "rmse_v3": rmse_v3,
                            "rmse_e0": rmse_e0,
                            "delta_ss_total": delta_ss_total,
                            "delta_ss_plat": delta_ss_plat,
                            "delta_ss_knee": delta_ss_knee,
                        })

                # 2. S-G Cases (12 cases, wrongly confident start soc_std = 0.005)
                for z_tgt in sg_target_socs:
                    cross_idx = np.where(data.truth_soc <= z_tgt)[0]
                    if len(cross_idx) == 0:
                        continue
                    k0 = int(cross_idx[0])

                    for off_pp in sg_offsets_pp:
                        off_frac = off_pp / 100.0
                        z_init = min(max(float(data.truth_soc[k0] + off_frac), 0.0), 1.0)

                        # E7v3
                        est_v3 = E7V3CompositeFilter(frozen_params)
                        init_estimator_state(
                            est_v3,
                            soc0=z_init,
                            soc_std=0.005,
                            i1=data.i1_truth[k0],
                            i2=data.i2_truth[k0],
                            h=data.h_truth[k0],
                        )
                        soc_v3 = run_stream_slice(est_v3, data, k0, n)

                        # E0
                        est_e0 = E0CoulombCounting(e0_params)
                        init_estimator_state(
                            est_e0,
                            soc0=z_init,
                            soc_std=0.005,
                            i1=0.0,
                            i2=0.0,
                            h=0.0,
                        )
                        soc_e0 = run_stream_slice(est_e0, data, k0, n)

                        truth_w = data.truth_soc[k0:]
                        dt_w = data.dt_arr[k0:]
                        err_v3 = (soc_v3 - truth_w) * 100.0
                        err_e0 = (soc_e0 - truth_w) * 100.0

                        conv_time_s = compute_convergence_time(err_v3, dt_w)
                        never_conv = math.isinf(conv_time_s)
                        end_err_pp = float(abs(err_v3[-1]))

                        m_plat = (truth_w >= 0.10) & (truth_w <= 0.90)
                        m_knee = ~m_plat

                        sum_sq_e0_plat = float(np.sum(err_e0[m_plat] ** 2)) if np.any(m_plat) else 0.0
                        sum_sq_e0_knee = float(np.sum(err_e0[m_knee] ** 2)) if np.any(m_knee) else 0.0
                        sum_sq_v3_plat = float(np.sum(err_v3[m_plat] ** 2)) if np.any(m_plat) else 0.0
                        sum_sq_v3_knee = float(np.sum(err_v3[m_knee] ** 2)) if np.any(m_knee) else 0.0

                        delta_ss_total = float(np.sum(err_e0 ** 2) - np.sum(err_v3 ** 2))
                        delta_ss_plat = sum_sq_e0_plat - sum_sq_v3_plat
                        delta_ss_knee = sum_sq_e0_knee - sum_sq_v3_knee

                        rmse_v3 = float(np.sqrt(np.mean(err_v3 ** 2)))
                        rmse_e0 = float(np.sqrt(np.mean(err_e0 ** 2)))

                        all_case_records.append({
                            "scenario": "S-G",
                            "profile": prof,
                            "cell": cell,
                            "temp": temp,
                            "target_soc": z_tgt,
                            "offset_pp": off_pp,
                            "abs_offset_pp": abs(off_pp),
                            "window_len_s": float(np.sum(dt_w)),
                            "conv_time_s": conv_time_s,
                            "never_converged": never_conv,
                            "end_err_pp": end_err_pp,
                            "rmse_v3": rmse_v3,
                            "rmse_e0": rmse_e0,
                            "delta_ss_total": delta_ss_total,
                            "delta_ss_plat": delta_ss_plat,
                            "delta_ss_knee": delta_ss_knee,
                        })

    out_dir = repo_root / "reports" / "gauntlet_v3" / "closeout"
    out_dir.mkdir(parents=True, exist_ok=True)

    # Save detailed per-case JSON
    json_path = out_dir / "convergence_records.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(all_case_records, f, indent=2)

    print(f"\nSaved raw convergence records ({len(all_case_records)} total cases) to {json_path}")

    # Generate Aggregate Summary Statistics
    summary = aggregate_convergence_summary(all_case_records)
    summary_path = out_dir / "convergence_summary.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print(f"Saved aggregated convergence summary to {summary_path}")
    print(f"C2 Analysis completed in {time.time() - t0_start:.1f} s.")


def aggregate_convergence_summary(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Compute aggregate median/p90 convergence times, un-converged rates, and plateau/knee splits."""
    summary = {}

    for scen in ["S-B", "S-G"]:
        scen_recs = [r for r in records if r["scenario"] == scen]
        n_tot = len(scen_recs)

        conv_times = [r["conv_time_s"] for r in scen_recs if not r["never_converged"]]
        never_conv_recs = [r for r in scen_recs if r["never_converged"]]
        never_conv_frac = len(never_conv_recs) / n_tot if n_tot > 0 else 0.0

        end_errs = [r["end_err_pp"] for r in scen_recs]

        # By offset size
        by_offset = {}
        for off in sorted(list(set(r["abs_offset_pp"] for r in scen_recs))):
            sub = [r for r in scen_recs if r["abs_offset_pp"] == off]
            sub_times = [r["conv_time_s"] for r in sub if not r["never_converged"]]
            sub_never = sum(1 for r in sub if r["never_converged"])
            by_offset[str(off)] = {
                "count": len(sub),
                "never_converged_count": sub_never,
                "never_converged_frac": sub_never / len(sub) if len(sub) > 0 else 0.0,
                "median_conv_time_s": float(np.median(sub_times)) if len(sub_times) > 0 else None,
                "p90_conv_time_s": float(np.percentile(sub_times, 90)) if len(sub_times) > 0 else None,
                "mean_end_err_pp": float(np.mean([r["end_err_pp"] for r in sub])),
            }

        # By start SOC
        by_start_soc = {}
        for z in sorted(list(set(r["target_soc"] for r in scen_recs)), reverse=True):
            sub = [r for r in scen_recs if r["target_soc"] == z]
            sub_times = [r["conv_time_s"] for r in sub if not r["never_converged"]]
            sub_never = sum(1 for r in sub if r["never_converged"])
            by_start_soc[f"{z:.2f}"] = {
                "count": len(sub),
                "never_converged_count": sub_never,
                "never_converged_frac": sub_never / len(sub) if len(sub) > 0 else 0.0,
                "median_conv_time_s": float(np.median(sub_times)) if len(sub_times) > 0 else None,
                "p90_conv_time_s": float(np.percentile(sub_times, 90)) if len(sub_times) > 0 else None,
                "mean_end_err_pp": float(np.mean([r["end_err_pp"] for r in sub])),
            }

        # Region decomposition across all cases
        tot_delta_ss = sum(r["delta_ss_total"] for r in scen_recs)
        plat_delta_ss = sum(r["delta_ss_plat"] for r in scen_recs)
        knee_delta_ss = sum(r["delta_ss_knee"] for r in scen_recs)

        summary[scen] = {
            "total_cases": n_tot,
            "converged_cases": len(conv_times),
            "never_converged_cases": len(never_conv_recs),
            "never_converged_frac": never_conv_frac,
            "overall_median_conv_time_s": float(np.median(conv_times)) if len(conv_times) > 0 else None,
            "overall_p90_conv_time_s": float(np.percentile(conv_times, 90)) if len(conv_times) > 0 else None,
            "mean_end_err_pp": float(np.mean(end_errs)),
            "p95_end_err_pp": float(np.percentile(end_errs, 95)),
            "by_offset_size": by_offset,
            "by_start_soc": by_start_soc,
            "variance_reduction_decomposition": {
                "total_delta_sum_squares": tot_delta_ss,
                "plateau_delta_sum_squares": plat_delta_ss,
                "knee_delta_sum_squares": knee_delta_ss,
                "plateau_share_pct": (plat_delta_ss / tot_delta_ss * 100.0) if tot_delta_ss != 0 else 0.0,
                "knee_share_pct": (knee_delta_ss / tot_delta_ss * 100.0) if tot_delta_ss != 0 else 0.0,
            }
        }

    return summary


if __name__ == "__main__":
    import math
    run_c2_analysis()
