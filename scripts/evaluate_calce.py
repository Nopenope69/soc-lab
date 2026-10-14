"""Evaluation pipeline for CALCE A123 dataset.

Evaluates E0, E2, E5 v1, E5 v2, and E6 across gating (20, 25, 30, 40, 50 C)
and informational (-10, 0, 10 C) temperatures on US06 and FUDS.
Executes the fault injection matrix (SOC offset, current bias, OCV mismatch),
evaluates cross-cell transfer on Cell A1-008, checks the 4 fixed pass rules,
and generates reports/calce_a123_verdict.md.
"""

from dataclasses import replace
import json
import math
from pathlib import Path
from typing import Any, Dict, List, Tuple
import numpy as np
import pandas as pd

from soc.assumptions.loader import load_assumptions
from soc.data.calce_loader import load_dynamic_cycle, load_ocv_file, get_raw_dir, CalceCycleData
from soc.estimators.base import ParamSet
from soc.estimators.registry import get_estimator
from soc.models.plant import Measurement

GATING_TEMPS = [20, 25, 30, 40, 50]
INFORMATIONAL_TEMPS = [-10, 0, 10]
ALL_TEMPS = [-10, 0, 10, 20, 25, 30, 40, 50]
EVAL_PROFILES = ["US06", "FUDS"]


def get_file_paths(raw_dir: Path, temp: int, cell: str) -> Tuple[Path, Path]:
    """Resolve file paths for OCV and dynamic workbooks."""
    if temp == -10:
        ocv_pattern = "*OCV-10*"
    elif temp == 25:
        ocv_pattern = "*OCV25*"
    else:
        ocv_pattern = f"*OCV{temp}-*"

    ocv_dirs = [p for p in raw_dir.glob(ocv_pattern) if p.is_dir()]
    if not ocv_dirs:
        raise FileNotFoundError(f"No OCV folder for {temp}C")
    ocv_cands = [p for p in ocv_dirs[0].rglob(f"*{cell}*.xlsx") if not p.name.startswith("~$")]
    if not ocv_cands:
        raise FileNotFoundError(f"Cannot find OCV file for {temp}C {cell}")
    ocv_path = ocv_cands[0]

    if temp == -10:
        dyn_pattern = "*DST-US06-FUDS-N10*"
    elif temp == 20:
        dyn_pattern = "*DST-US06-FUDS-20*"
    else:
        dyn_pattern = f"*DST-US06-FUDS-{temp}*"

    dyn_dirs = [p for p in raw_dir.glob(dyn_pattern) if p.is_dir()]
    if not dyn_dirs:
        raise FileNotFoundError(f"No dynamic folder for {temp}C")

    if temp == 20:
        dyn_cands = [p for p in dyn_dirs[0].rglob(f"*{cell}*20120817.xlsx") if not p.name.startswith("~$") and "newprofile" not in p.name]
    else:
        dyn_cands = [p for p in dyn_dirs[0].rglob(f"*{cell}*.xlsx") if not p.name.startswith("~$")]

    if not dyn_cands:
        dyn_cands = [p for p in dyn_dirs[0].rglob(f"*{cell}*") if not p.name.startswith("~$") and ("xlsx" in p.name or "xls" in p.name)]
    if not dyn_cands:
        raise FileNotFoundError(f"Cannot find dynamic file for {temp}C {cell}")
    dyn_path = dyn_cands[0]

    return ocv_path, dyn_path


def build_param_sets(profile_name: str, ocv_offset_v: float = 0.0) -> Dict[str, ParamSet]:
    """Construct frozen ParamSet instances for E0, E2, E5 v1, E5 v2, and E6."""
    assumptions, _, _ = load_assumptions(profile=profile_name)
    base_params = ParamSet.from_assumptions(assumptions, matched=True)

    if ocv_offset_v != 0.0:
        shifted_ocv = {}
        for k, v in base_params.ocv_table.items():
            if isinstance(v, list):
                shifted_ocv[k] = [float(x) + ocv_offset_v for x in v]
            elif isinstance(v, (int, float)):
                shifted_ocv[k] = float(v) + ocv_offset_v
            else:
                shifted_ocv[k] = v
        base_params = replace(base_params, ocv_table=shifted_ocv)

    p_e0 = base_params
    p_e2 = base_params
    p_e5_v1 = replace(
        base_params,
        e5_enable_r_inflation=True,
        e5_enable_slope_gating=True,
        e5_enable_step_cap=True,
        e5_sigma_ocv_model_v=0.005,
        e5_slope_ref=0.1,
        e5_max_soc_step=0.0002,
        e5_use_observability_cap=False,
    )
    p_e5_v2 = replace(
        base_params,
        e5_enable_r_inflation=True,
        e5_enable_slope_gating=True,
        e5_enable_step_cap=True,
        e5_sigma_ocv_model_v=0.02,
        e5_slope_ref=0.2,
        e5_use_observability_cap=True,
        e5_cap_plateau=1e-5,
        e5_cap_knee=0.01,
    )
    p_e6 = replace(
        base_params,
        rbc_use_hysteresis_state=True,
        rbc_q_theta=1e-9,
        rbc_r_theta=1e-4,
        rbc_initial_theta_std=0.002,
    )

    return {
        "E0": p_e0,
        "E2": p_e2,
        "E5 v1": p_e5_v1,
        "E5 v2": p_e5_v2,
        "E6": p_e6,
    }


def evaluate_stream(
    estimator_name: str,
    params: ParamSet,
    cycle_data: CalceCycleData,
    soc_offset: float = 0.0,
    current_bias_a: float = 0.0,
) -> Dict[str, float]:
    """Execute estimator over drive cycle stream with optional fault injection."""
    real_est_name = "E5" if estimator_name.startswith("E5") else estimator_name
    est = get_estimator(real_est_name, params)
    est.reset(1.0 + soc_offset)

    time_s = cycle_data.time_s
    n_samples = len(time_s)
    dt_arr = np.diff(time_s, prepend=time_s[0])
    v_arr = cycle_data.voltage_v
    i_arr = cycle_data.current_a + current_bias_a
    temp_arr = cycle_data.temperature_measured_c

    soc_preds = np.empty(n_samples, dtype=float)

    for k in range(n_samples):
        dt = float(dt_arr[k]) if k > 0 else (float(time_s[1] - time_s[0]) if n_samples > 1 else 1.0)
        meas = Measurement(
            v=float(v_arr[k]),
            i=float(i_arr[k]),
            temp_c=float(temp_arr[k]),
            dt=dt,
            dropout=False,
        )
        out = est.step(meas)
        soc_preds[k] = out.soc

    err_pp = (soc_preds - cycle_data.truth_soc) * 100.0
    rmse = float(np.sqrt(np.mean(err_pp ** 2)))
    mae = float(np.mean(np.abs(err_pp)))
    max_err = float(np.max(np.abs(err_pp)))
    final_err = float(err_pp[-1])

    return {
        "rmse": rmse,
        "mae": mae,
        "max_err": max_err,
        "final_err": final_err,
    }


def main():
    print("=== Starting CALCE A123 Real-Data Evaluation Pipeline ===")
    root_dir = Path(__file__).resolve().parent.parent
    raw_dir = get_raw_dir(root_dir)

    # 1. Load and cache all drive cycles in memory
    print("\n--- Ingesting and caching drive cycles ---")
    data_cache: Dict[Tuple[str, int, str], CalceCycleData] = {}
    c20_capacities: Dict[Tuple[str, int], float] = {}

    for cell in ["A1-007", "A1-008"]:
        for temp in ALL_TEMPS:
            ocv_p, dyn_p = get_file_paths(raw_dir, temp, cell)
            print(f"Loading {cell} at {temp}C...")
            ocv = load_ocv_file(ocv_p, float(temp), cell)
            c20_capacities[(cell, temp)] = ocv.c20_capacity_ah

            for prof in ["DST", "US06", "FUDS"]:
                cyc = load_dynamic_cycle(dyn_p, float(temp), cell, prof, ocv.c20_capacity_ah)
                data_cache[(cell, temp, prof)] = cyc

    print(f"Loaded {len(data_cache)} drive cycles successfully.")

    # 2. Build baseline param sets
    param_sets_a1007 = build_param_sets("calce_a123")
    param_sets_a1008 = build_param_sets("calce_a123_a1008")

    # 3. Baseline Evaluation on A1-007
    print("\n--- Running Baseline Evaluation on Cell A1-007 ---")
    baseline_results = []
    for temp in ALL_TEMPS:
        is_gating = temp in GATING_TEMPS
        for prof in EVAL_PROFILES:
            cyc = data_cache[("A1-007", temp, prof)]
            for est_name in ["E0", "E2", "E5 v1", "E5 v2", "E6"]:
                res = evaluate_stream(est_name, param_sets_a1007[est_name], cyc)
                baseline_results.append({
                    "cell": "A1-007",
                    "temp_c": temp,
                    "is_gating": is_gating,
                    "profile": prof,
                    "estimator": est_name,
                    "rmse": res["rmse"],
                    "mae": res["mae"],
                    "max_err": res["max_err"],
                    "final_err": res["final_err"],
                })

    df_base = pd.DataFrame(baseline_results)

    # 4. Fault Injection Matrix on Cell A1-007
    print("\n--- Running Fault Injection Matrix on Cell A1-007 ---")
    fault_results = []

    fault_configs = [
        # Injected Initial SOC Offset (+-10 pp)
        {"type": "soc_offset", "name": "soc_offset_+10pp", "soc_offset": 0.10, "i_bias": 0.0, "ocv_offset": 0.0, "is_stress": False},
        {"type": "soc_offset", "name": "soc_offset_-10pp", "soc_offset": -0.10, "i_bias": 0.0, "ocv_offset": 0.0, "is_stress": False},
        # Current Bias Main (+-10 mA)
        {"type": "current_bias", "name": "current_bias_+10mA", "soc_offset": 0.0, "i_bias": 0.010, "ocv_offset": 0.0, "is_stress": False},
        {"type": "current_bias", "name": "current_bias_-10mA", "soc_offset": 0.0, "i_bias": -0.010, "ocv_offset": 0.0, "is_stress": False},
        # Current Bias Stress (+-50 mA)
        {"type": "current_bias", "name": "current_bias_+50mA", "soc_offset": 0.0, "i_bias": 0.050, "ocv_offset": 0.0, "is_stress": True},
        {"type": "current_bias", "name": "current_bias_-50mA", "soc_offset": 0.0, "i_bias": -0.050, "ocv_offset": 0.0, "is_stress": True},
        # OCV Model Mismatch Main (+-5 mV)
        {"type": "ocv_offset", "name": "ocv_offset_+5mV", "soc_offset": 0.0, "i_bias": 0.0, "ocv_offset": 0.005, "is_stress": False},
        {"type": "ocv_offset", "name": "ocv_offset_-5mV", "soc_offset": 0.0, "i_bias": 0.0, "ocv_offset": -0.005, "is_stress": False},
        # OCV Model Mismatch Stress (+-10 mV)
        {"type": "ocv_offset", "name": "ocv_offset_+10mV", "soc_offset": 0.0, "i_bias": 0.0, "ocv_offset": 0.010, "is_stress": True},
        {"type": "ocv_offset", "name": "ocv_offset_-10mV", "soc_offset": 0.0, "i_bias": 0.0, "ocv_offset": -0.010, "is_stress": True},
    ]

    for fcfg in fault_configs:
        print(f"Evaluating fault: {fcfg['name']}...")
        if fcfg["ocv_offset"] != 0.0:
            p_sets = build_param_sets("calce_a123", ocv_offset_v=fcfg["ocv_offset"])
        else:
            p_sets = param_sets_a1007

        for temp in ALL_TEMPS:
            is_gating = temp in GATING_TEMPS
            for prof in EVAL_PROFILES:
                cyc = data_cache[("A1-007", temp, prof)]
                for est_name in ["E0", "E2", "E5 v1", "E5 v2", "E6"]:
                    res = evaluate_stream(
                        est_name,
                        p_sets[est_name],
                        cyc,
                        soc_offset=fcfg["soc_offset"],
                        current_bias_a=fcfg["i_bias"],
                    )
                    fault_results.append({
                        "cell": "A1-007",
                        "temp_c": temp,
                        "is_gating": is_gating,
                        "profile": prof,
                        "fault_type": fcfg["type"],
                        "fault_name": fcfg["name"],
                        "is_stress": fcfg["is_stress"],
                        "estimator": est_name,
                        "rmse": res["rmse"],
                        "mae": res["mae"],
                        "max_err": res["max_err"],
                        "final_err": res["final_err"],
                    })

    df_faults = pd.DataFrame(fault_results)

    # 5. Cell Transfer Evaluation on Cell A1-008
    print("\n--- Running Cell Transfer Evaluation on Cell A1-008 ---")
    transfer_results = []
    for temp in ALL_TEMPS:
        is_gating = temp in GATING_TEMPS
        for prof in EVAL_PROFILES:
            cyc = data_cache[("A1-008", temp, prof)]
            for est_name in ["E0", "E2", "E5 v1", "E5 v2", "E6"]:
                # Run with A1-007 parameters (zero refit transfer)
                res_trans = evaluate_stream(est_name, param_sets_a1007[est_name], cyc)
                # Run with A1-008's own fit
                res_own = evaluate_stream(est_name, param_sets_a1008[est_name], cyc)
                transfer_results.append({
                    "cell": "A1-008",
                    "temp_c": temp,
                    "is_gating": is_gating,
                    "profile": prof,
                    "estimator": est_name,
                    "rmse_a1007_params": res_trans["rmse"],
                    "rmse_own_fit": res_own["rmse"],
                    "ratio": res_trans["rmse"] / max(res_own["rmse"], 1e-6),
                })

    df_trans = pd.DataFrame(transfer_results)

    # 6. Evaluate Fixed Pass Rules
    print("\n--- Evaluating Pass Rules ---")

    # Rule 1 (Accuracy): best of E2, E5 v1, E5 v2, E6 has median RMSE <= 2.0 pp across gating cases
    df_gate_base = df_base[df_base["is_gating"]]
    r1_medians = {}
    for est in ["E2", "E5 v1", "E5 v2", "E6"]:
        sub = df_gate_base[df_gate_base["estimator"] == est]
        r1_medians[est] = float(sub["rmse"].median())

    best_r1_est = min(r1_medians, key=r1_medians.get)
    best_r1_median = r1_medians[best_r1_est]
    r1_pass = best_r1_median <= 2.0

    print(f"Rule 1 - Accuracy: Best estimator {best_r1_est} has median RMSE = {best_r1_median:.3f} pp (Threshold: <= 2.0 pp) -> {'PASS' if r1_pass else 'FAIL'}")
    for est, med in r1_medians.items():
        print(f"   {est}: median RMSE = {med:.3f} pp")

    # Determine better E5 variant on gating baseline
    e5v1_med = r1_medians["E5 v1"]
    e5v2_med = r1_medians["E5 v2"]
    better_e5 = "E5 v1" if e5v1_med < e5v2_med else "E5 v2"
    print(f"\nBetter E5 variant on baseline: {better_e5} ({min(e5v1_med, e5v2_med):.3f} pp vs {max(e5v1_med, e5v2_med):.3f} pp)")

    # Rule 2 (No Harm):
    # (a) Better E5 within 0.3 pp of E2 RMSE in >= 80% of gating cases without faults
    # (b) Averages >= 30% lower RMSE than E2 in the +-5 mV OCV runs
    gate_cases = df_gate_base[["temp_c", "profile"]].drop_duplicates().to_dict("records")
    within_03_count = 0
    total_base_cases = len(gate_cases)
    for c in gate_cases:
        sub_e2 = df_gate_base[(df_gate_base["temp_c"] == c["temp_c"]) & (df_gate_base["profile"] == c["profile"]) & (df_gate_base["estimator"] == "E2")]
        sub_e5 = df_gate_base[(df_gate_base["temp_c"] == c["temp_c"]) & (df_gate_base["profile"] == c["profile"]) & (df_gate_base["estimator"] == better_e5)]
        e2_val = sub_e2["rmse"].iloc[0]
        e5_val = sub_e5["rmse"].iloc[0]
        if abs(e5_val - e2_val) <= 0.3 or (e5_val <= e2_val + 0.3):
            within_03_count += 1

    r2_no_harm_pct = (within_03_count / total_base_cases) * 100.0
    r2_no_harm_pass = r2_no_harm_pct >= 80.0

    # +-5 mV OCV runs
    df_ocv_5mv = df_faults[df_faults["is_gating"] & df_faults["fault_name"].isin(["ocv_offset_+5mV", "ocv_offset_-5mV"])]
    e2_ocv_mean = float(df_ocv_5mv[df_ocv_5mv["estimator"] == "E2"]["rmse"].mean())
    e5_ocv_mean = float(df_ocv_5mv[df_ocv_5mv["estimator"] == better_e5]["rmse"].mean())
    r2_reduction_pct = ((e2_ocv_mean - e5_ocv_mean) / e2_ocv_mean) * 100.0 if e2_ocv_mean > 0 else 0.0
    r2_reduction_pass = r2_reduction_pct >= 30.0
    r2_pass = r2_no_harm_pass and r2_reduction_pass

    print(f"Rule 2 - No Harm & Benefit:")
    print(f"   Part A (No harm): {better_e5} within 0.3 pp of E2 in {within_03_count}/{total_base_cases} cases ({r2_no_harm_pct:.1f}%, Threshold: >= 80%) -> {'PASS' if r2_no_harm_pass else 'FAIL'}")
    print(f"   Part B (Benefit): In +-5 mV OCV, E2 mean RMSE = {e2_ocv_mean:.3f} pp, {better_e5} mean RMSE = {e5_ocv_mean:.3f} pp (Reduction: {r2_reduction_pct:.1f}%, Threshold: >= 30%) -> {'PASS' if r2_reduction_pass else 'FAIL'}")
    print(f"   Rule 2 Overall: {'PASS' if r2_pass else 'FAIL'}")

    # Rule 3 (Recovery): under +-10 pp initial offset, better E5 within 2 pp of E2 RMSE on average
    df_soc_off = df_faults[df_faults["is_gating"] & df_faults["fault_name"].isin(["soc_offset_+10pp", "soc_offset_-10pp"])]
    e2_soc_mean = float(df_soc_off[df_soc_off["estimator"] == "E2"]["rmse"].mean())
    e5_soc_mean = float(df_soc_off[df_soc_off["estimator"] == better_e5]["rmse"].mean())
    r3_diff = abs(e5_soc_mean - e2_soc_mean)
    r3_pass = r3_diff <= 2.0 or (e5_soc_mean <= e2_soc_mean + 2.0)

    print(f"\nRule 3 - Recovery under +-10 pp offset:")
    print(f"   E2 mean RMSE = {e2_soc_mean:.3f} pp, {better_e5} mean RMSE = {e5_soc_mean:.3f} pp (Diff = {r3_diff:.3f} pp, Threshold: <= 2.0 pp) -> {'PASS' if r3_pass else 'FAIL'}")

    # Rule 4 (Cell Transfer): best estimator on A1-008 with A1-007 parameters has RMSE <= 1.5x own fit
    # Best estimator from Rule 1
    df_trans_gate = df_trans[df_trans["is_gating"] & (df_trans["estimator"] == best_r1_est)]
    mean_rmse_trans = float(df_trans_gate["rmse_a1007_params"].mean())
    mean_rmse_own = float(df_trans_gate["rmse_own_fit"].mean())
    r4_ratio = mean_rmse_trans / max(mean_rmse_own, 1e-6)
    r4_pass = r4_ratio <= 1.5

    print(f"\nRule 4 - Cell Transfer on Cell A1-008 ({best_r1_est}):")
    print(f"   Mean RMSE (A1-007 params) = {mean_rmse_trans:.3f} pp, Mean RMSE (own fit) = {mean_rmse_own:.3f} pp (Ratio = {r4_ratio:.2f}x, Threshold: <= 1.5x) -> {'PASS' if r4_pass else 'FAIL'}")

    overall_pass = r1_pass and r2_pass and r3_pass and r4_pass
    print(f"\n=== OVERALL VERDICT: {'PASS' if overall_pass else 'FAIL'} ===")

    # -10 C Capacity statistics
    print("\n--- Delivered Capacity at -10 C ---")
    c20_n10_a1007 = c20_capacities[("A1-007", -10)]
    c20_n10_a1008 = c20_capacities[("A1-008", -10)]
    dst_n10_a1007 = data_cache[("A1-007", -10, "DST")]
    dst_n10_a1008 = data_cache[("A1-008", -10, "DST")]

    delivered_pct_a1007 = (dst_n10_a1007.integrated_capacity_ah / c20_n10_a1007) * 100.0
    delivered_pct_a1008 = (dst_n10_a1008.integrated_capacity_ah / c20_n10_a1008) * 100.0
    print(f"Cell A1-007 at -10 C: C/20 capacity = {c20_n10_a1007:.4f} Ah, DST delivered {dst_n10_a1007.integrated_capacity_ah:.4f} Ah ({delivered_pct_a1007:.1f}%), final cutoff SOC = {dst_n10_a1007.final_soc:.4f}")
    print(f"Cell A1-008 at -10 C: C/20 capacity = {c20_n10_a1008:.4f} Ah, DST delivered {dst_n10_a1008.integrated_capacity_ah:.4f} Ah ({delivered_pct_a1008:.1f}%), final cutoff SOC = {dst_n10_a1008.final_soc:.4f}")

    # Generate Markdown Report: reports/calce_a123_verdict.md
    print("\n--- Generating reports/calce_a123_verdict.md ---")
    generate_markdown_report(
        root_dir=root_dir,
        r1_pass=r1_pass,
        r1_medians=r1_medians,
        best_r1_est=best_r1_est,
        best_r1_median=best_r1_median,
        r2_pass=r2_pass,
        r2_no_harm_pass=r2_no_harm_pass,
        r2_reduction_pass=r2_reduction_pass,
        better_e5=better_e5,
        within_03_count=within_03_count,
        total_base_cases=total_base_cases,
        r2_no_harm_pct=r2_no_harm_pct,
        e2_ocv_mean=e2_ocv_mean,
        e5_ocv_mean=e5_ocv_mean,
        r2_reduction_pct=r2_reduction_pct,
        r3_pass=r3_pass,
        e2_soc_mean=e2_soc_mean,
        e5_soc_mean=e5_soc_mean,
        r3_diff=r3_diff,
        r4_pass=r4_pass,
        mean_rmse_trans=mean_rmse_trans,
        mean_rmse_own=mean_rmse_own,
        r4_ratio=r4_ratio,
        overall_pass=overall_pass,
        df_base=df_base,
        df_faults=df_faults,
        df_trans=df_trans,
        c20_capacities=c20_capacities,
        delivered_stats={
            "A1-007": (c20_n10_a1007, dst_n10_a1007.integrated_capacity_ah, delivered_pct_a1007, dst_n10_a1007.final_soc),
            "A1-008": (c20_n10_a1008, dst_n10_a1008.integrated_capacity_ah, delivered_pct_a1008, dst_n10_a1008.final_soc),
        }
    )
    print("Report written successfully.")


def generate_markdown_report(
    root_dir: Path,
    r1_pass: bool,
    r1_medians: Dict[str, float],
    best_r1_est: str,
    best_r1_median: float,
    r2_pass: bool,
    r2_no_harm_pass: bool,
    r2_reduction_pass: bool,
    better_e5: str,
    within_03_count: int,
    total_base_cases: int,
    r2_no_harm_pct: float,
    e2_ocv_mean: float,
    e5_ocv_mean: float,
    r2_reduction_pct: float,
    r3_pass: bool,
    e2_soc_mean: float,
    e5_soc_mean: float,
    r3_diff: float,
    r4_pass: bool,
    mean_rmse_trans: float,
    mean_rmse_own: float,
    r4_ratio: float,
    overall_pass: bool,
    df_base: pd.DataFrame,
    df_faults: pd.DataFrame,
    df_trans: pd.DataFrame,
    c20_capacities: Dict[Tuple[str, int], float],
    delivered_stats: Dict[str, Tuple[float, float, float, float]],
):
    """Write comprehensive markdown report with pass/fail verdicts and results tables."""
    reports_dir = root_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    report_path = reports_dir / "calce_a123_verdict.md"

    def status_badge(p: bool) -> str:
        return "PASS" if p else "FAIL"

    lines = []
    lines.append("# CALCE A123 26650 LFP Real-Data Benchmark Verdict")
    lines.append("")
    lines.append(f"**Overall Verdict: {status_badge(overall_pass)}**")
    lines.append("")
    lines.append("## 1. Executive Summary & Fixed Pass Rules Evaluation")
    lines.append("")
    lines.append("| Rule | Description | Target Threshold | Measured Performance | Verdict |")
    lines.append("| :--- | :--- | :--- | :--- | :---: |")
    lines.append(f"| **Rule 1 (Accuracy)** | Best of E2, E5 v1, E5 v2, E6 median RMSE on baseline gating cases | $\\le 2.0$ pp | Best: `{best_r1_est}` with {best_r1_median:.2f} pp | **{status_badge(r1_pass)}** |")
    lines.append(f"| **Rule 2 (No Harm & Benefit)** | Better E5 ({better_e5}) within 0.3 pp of E2 in $\\ge 80\\%$ baseline cases AND $\\ge 30\\%$ RMSE reduction in $\\pm 5$ mV OCV | No harm $\\ge 80\\%$, Benefit $\\ge 30\\%$ | No harm: {r2_no_harm_pct:.1f}% ({within_03_count}/{total_base_cases}), Benefit: {r2_reduction_pct:.1f}% | **{status_badge(r2_pass)}** |")
    lines.append(f"| **Rule 3 (Recovery)** | Under $\\pm 10$ pp initial offset, better E5 within 2 pp of E2 average RMSE | Average diff $\\le 2.0$ pp | E2: {e2_soc_mean:.2f} pp, {better_e5}: {e5_soc_mean:.2f} pp (diff: {r3_diff:.2f} pp) | **{status_badge(r3_pass)}** |")
    lines.append(f"| **Rule 4 (Cell Transfer)** | Best estimator ({best_r1_est}) on Cell A1-008 with A1-007 parameters vs own fit | Transfer ratio $\\le 1.5\\times$ | A1-007 fit: {mean_rmse_trans:.2f} pp, Own fit: {mean_rmse_own:.2f} pp (ratio: {r4_ratio:.2f}x) | **{status_badge(r4_pass)}** |")
    lines.append("")

    lines.append("### Detailed Rule Analysis")
    lines.append(f"- **Rule 1 (Accuracy):** Evaluated across 10 gating cases (20, 25, 30, 40, 50 C on US06 and FUDS for Cell A1-007 without faults).")
    for est, med in r1_medians.items():
        lines.append(f"  - `{est}` median RMSE: **{med:.2f} pp**")
    lines.append(f"  - Verdict: **{status_badge(r1_pass)}**. Best estimator `{best_r1_est}` achieved median RMSE of {best_r1_median:.2f} pp (requirement: $\\le 2.0$ pp).")
    lines.append(f"- **Rule 2 (No Harm & Benefit):** Better variant selected was `{better_e5}`.")
    lines.append(f"  - Baseline parity: `{better_e5}` stayed within 0.3 pp of E2 in {within_03_count} of {total_base_cases} cases ({r2_no_harm_pct:.1f}%). Requirement was $\\ge 80\\%$. (**{status_badge(r2_no_harm_pass)}**)")
    lines.append(f"  - Benefit under $\\pm 5$ mV OCV mismatch: E2 average RMSE = {e2_ocv_mean:.2f} pp, `{better_e5}` average RMSE = {e5_ocv_mean:.2f} pp ({r2_reduction_pct:.1f}% reduction). Requirement was $\\ge 30\\%$. (**{status_badge(r2_reduction_pass)}**)")
    lines.append(f"- **Rule 3 (Recovery):** Under $\\pm 10$ pp initial offset injection, `{better_e5}` maintained an average RMSE difference of {r3_diff:.2f} pp relative to E2 (requirement: $\\le 2.0$ pp). (**{status_badge(r3_pass)}**)")
    lines.append(f"- **Rule 4 (Cell Transfer):** Evaluated cross-specimen transfer on Cell A1-008 across gating temperatures. `{best_r1_est}` achieved {mean_rmse_trans:.2f} pp with zero-refit A1-007 parameters versus {mean_rmse_own:.2f} pp with its own fit (ratio: {r4_ratio:.2f}x, requirement: $\\le 1.5\\times$). (**{status_badge(r4_pass)}**)")
    lines.append("")

    lines.append("## 2. Experimental Scope & Ground Truth Accounting")
    lines.append("- **Specimens:** A123 ANR26650M1-A LiFePO4 cells (`A1-007` and `A1-008`).")
    lines.append("- **Gating Temperatures (enforced by pass rules):** 20, 25, 30, 40, and 50 C.")
    lines.append("- **Informational Temperatures (reported only, excluded from pass rules):** -10, 0, and 10 C.")
    lines.append("- **Profiles:** DST (Step 8, used for fitting and tuning), US06 (Step 16, sealed test), FUDS (Step 24, sealed test).")
    lines.append("- **Ground Truth SOC Protocol:** Evaluated via continuous Coulomb integration from full-charge CV-end anchor (Step 5/13/21 cutoff at C/20 current = 0.055 A, SOC = 1.0000), normalized to measured C/20 discharge capacity at that temperature. In accordance with physical reality, no empty anchor and no forced closure to 0 were applied.")
    lines.append("")

    lines.append("## 3. Informational Temperatures & Sub-Zero Delivered Capacity")
    lines.append("### Sub-Zero (-10 C) Delivered Capacity Under Dynamic Load")
    lines.append("At -10 C, severe electrolyte freezing and solid-state diffusion kinetics cause the terminal voltage to reach the 2.0 V cutoff long before the thermodynamic C/20 capacity is exhausted:")
    for cell_id, (q_c20, q_int, pct, final_z) in delivered_stats.items():
        lines.append(f"- **Cell {cell_id} at -10 C:**")
        lines.append(f"  - Measured C/20 Capacity: **{q_c20:.4f} Ah**")
        lines.append(f"  - Dynamic DST Delivered Capacity: **{q_int:.4f} Ah** (**{pct:.1f}%** of C/20 capacity)")
        lines.append(f"  - Cutoff Final SOC: **{final_z:.4f}** ({final_z*100:.1f}% unextracted capacity remaining)")
    lines.append("")

    lines.append("## 4. Hardware Artifact Note: 10 C OCV Discontinuity")
    lines.append("> [!NOTE]")
    lines.append("> **10 C OCV Interruption Handling:** In row 5449 of both 10 C OCV spreadsheets, a 6-hour hardware interruption during the discharge branch created a non-monotonic time jump (-94 s) and +24 mV voltage relaxation. Per plan specifications, this artifact was **not repaired** or smoothed; rather, the affected SOC range `[0.75, 0.78]` was explicitly **excluded from OCV and hysteresis identification**, marked in the configuration YAML note, and documented here. Dynamic drive cycles (DST, US06, FUDS) were unaffected by this interruption.")
    lines.append("")

    lines.append("## 5. Fault Injection Accounting: Real Model Error vs Injected Perturbations")
    lines.append("> [!IMPORTANT]")
    lines.append("> **Injected Faults Sit on Top of Real Model Error:** In synthetic benchmarks, estimator models are compared against perfect simulation plants with zero unmodeled dynamics. In this real laboratory dataset, equivalent circuit models (2RC + hysteresis) already suffer from real electrochemical model discrepancy (solid-state diffusion limitations, temperature gradients, concentration polarization). All injected sensor and model perturbations (initial SOC offset, current sensor bias, OCV shift) sit strictly on top of this real physical model error.")
    lines.append("")

    lines.append("## 6. Limitations of the Benchmark Dataset")
    lines.append("> [!WARNING]")
    lines.append("> **Full-Discharge Profile Limitation:** All dynamic cycles in the CALCE A123 dataset are full discharges from 100% full charge down to the 2.0 V cutoff after a complete CC-CV recharge. Consequently, the battery current is predominantly unidirectional discharging ($I > 0$). **Minor-loop hysteresis behavior is barely exercised**, and the minor-loop decay parameter $\\gamma$ remains unobserved and unexcited in these tests.")
    lines.append("")

    lines.append("## 7. Complete Experimental Results Tables")
    lines.append("")
    lines.append("### Table 1: Baseline Evaluation on Cell A1-007 (No Injected Faults)")
    lines.append("")
    lines.append("| Temp (C) | Scope | Profile | E0 RMSE (pp) | E2 RMSE (pp) | E5 v1 RMSE (pp) | E5 v2 RMSE (pp) | E6 RMSE (pp) |")
    lines.append("| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |")

    # Pivot baseline
    for temp in ALL_TEMPS:
        scope_str = "Gating" if temp in GATING_TEMPS else "Informational"
        for prof in EVAL_PROFILES:
            sub = df_base[(df_base["temp_c"] == temp) & (df_base["profile"] == prof)]
            e0_v = sub[sub["estimator"] == "E0"]["rmse"].values[0]
            e2_v = sub[sub["estimator"] == "E2"]["rmse"].values[0]
            e5v1_v = sub[sub["estimator"] == "E5 v1"]["rmse"].values[0]
            e5v2_v = sub[sub["estimator"] == "E5 v2"]["rmse"].values[0]
            e6_v = sub[sub["estimator"] == "E6"]["rmse"].values[0]
            lines.append(f"| {temp} | {scope_str} | {prof} | {e0_v:.2f} | {e2_v:.2f} | {e5v1_v:.2f} | {e5v2_v:.2f} | {e6_v:.2f} |")
    lines.append("")

    lines.append("### Table 2: Fault Injection Performance on Cell A1-007 (Gating Temperatures Average RMSE)")
    lines.append("")
    lines.append("| Fault Category | Injected Fault Condition | Stress? | E0 (pp) | E2 (pp) | E5 v1 (pp) | E5 v2 (pp) | E6 (pp) |")
    lines.append("| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: |")

    # Baseline row
    sub_base_gate = df_base[df_base["is_gating"]]
    lines.append(f"| **Baseline** | None (No Injected Fault) | No | {sub_base_gate[sub_base_gate['estimator']=='E0']['rmse'].mean():.2f} | {sub_base_gate[sub_base_gate['estimator']=='E2']['rmse'].mean():.2f} | {sub_base_gate[sub_base_gate['estimator']=='E5 v1']['rmse'].mean():.2f} | {sub_base_gate[sub_base_gate['estimator']=='E5 v2']['rmse'].mean():.2f} | {sub_base_gate[sub_base_gate['estimator']=='E6']['rmse'].mean():.2f} |")

    fault_order = [
        "soc_offset_+10pp", "soc_offset_-10pp",
        "current_bias_+10mA", "current_bias_-10mA",
        "current_bias_+50mA", "current_bias_-50mA",
        "ocv_offset_+5mV", "ocv_offset_-5mV",
        "ocv_offset_+10mV", "ocv_offset_-10mV"
    ]

    for fname in fault_order:
        sub_f = df_faults[df_faults["is_gating"] & (df_faults["fault_name"] == fname)]
        cat = sub_f["fault_type"].iloc[0].replace("_", " ").title()
        is_stress = "Yes" if sub_f["is_stress"].iloc[0] else "No"
        e0_v = sub_f[sub_f["estimator"] == "E0"]["rmse"].mean()
        e2_v = sub_f[sub_f["estimator"] == "E2"]["rmse"].mean()
        e5v1_v = sub_f[sub_f["estimator"] == "E5 v1"]["rmse"].mean()
        e5v2_v = sub_f[sub_f["estimator"] == "E5 v2"]["rmse"].mean()
        e6_v = sub_f[sub_f["estimator"] == "E6"]["rmse"].mean()
        lines.append(f"| {cat} | `{fname}` | {is_stress} | {e0_v:.2f} | {e2_v:.2f} | {e5v1_v:.2f} | {e5v2_v:.2f} | {e6_v:.2f} |")
    lines.append("")

    lines.append("### Table 3: Cell Transfer Evaluation on Cell A1-008")
    lines.append("")
    lines.append("| Temp (C) | Scope | Profile | Estimator | A1-007 Params RMSE (pp) | Own Fit RMSE (pp) | Transfer Ratio |")
    lines.append("| :---: | :---: | :---: | :---: | :---: | :---: | :---: |")

    for temp in ALL_TEMPS:
        scope_str = "Gating" if temp in GATING_TEMPS else "Informational"
        for prof in EVAL_PROFILES:
            sub = df_trans[(df_trans["temp_c"] == temp) & (df_trans["profile"] == prof)]
            for est in ["E2", "E5 v1", "E5 v2", "E6"]:
                row = sub[sub["estimator"] == est].iloc[0]
                lines.append(f"| {temp} | {scope_str} | {prof} | {est} | {row['rmse_a1007_params']:.2f} | {row['rmse_own_fit']:.2f} | {row['ratio']:.2f}x |")
    lines.append("")

    report_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Verdict report saved to {report_path}")


if __name__ == "__main__":
    main()
