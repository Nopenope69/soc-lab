"""Stage V0 Audit Script for Gauntlet V3.

Performs:
1. Audit (a): RLS direction on Set X (A1-008) and A1-007 across all temperatures.
   Logs theta over time, computes median, 10th and 90th percentile, compares to R0 ratio.
2. Audit (b): Variant test of e4v2: RLS adapting R0 only (adapt_r1=False) vs R0 and R1 jointly (adapt_r1=True).
   Evaluates against the V2 Keep Rule criteria.
3. Audit (c): Inspects bms_soc_ref.py and E7v2 for Q(T) and M(T) usage (scalar vs table),
   verifies imports of bms_soc_ref.py to confirm zero imports from soc.* or harness.
4. Audit (d): Tau2 bound impact test: fixes tau2 at 20, 25, 50 C to interior ~210 s,
   measures W-mid voltage bias/RMSE and S-A SOC RMSE.
"""

from dataclasses import replace
import json
from pathlib import Path
import sys
import numpy as np
import pandas as pd

repo_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo_root))

from soc.assumptions.loader import load_assumptions
from soc.estimators.base import ParamSet
from soc.estimators.e4v2_rls import E4V2RLSEKF
from soc.estimators.e7v2 import E7V2CompositeFilter
from soc.models.plant import Measurement
from soc.models.tables import InterpolatedTable2D
from soc.models.cell_2rc import Cell2RCModel
from scripts.gauntlet_v2_scenarios import (
    prepare_scenario_data_v2,
    evaluate_estimator_v2,
    init_estimator_state,
    run_stream_slice,
    R3_GUARANTEE_LINE,
    M_AUDIT,
)

TEMPS = [20, 25, 30, 40, 50]
DECISION_TEMPS = [20, 30, 40, 50]
HELDOUT_TEMPS = [40, 50]

# Independent R0 from Stage V1 model report (calce_a123_v4.yaml vs A1-008 own-fit)
R0_A1007 = {20: 0.15951, 25: 0.15851, 30: 0.15500, 40: 0.15359, 50: 0.15371}
R0_A1008 = {20: 0.17561, 25: 0.19680, 30: 0.17633, 40: 0.17777, 50: 0.22449}
R0_RATIO = {t: R0_A1008[t] / R0_A1007[t] for t in TEMPS}

# Frozen tuned parameters from Stage V3 (cand_sl_0.3)
TUNED_PARAMS = {
    "process_noise_q_soc": 2.9031433196504225e-08,
    "process_noise_q_rc": 1.1198164932559382e-05,
    "process_noise_q_hysteresis": 0.00017150882346504795,
    "measurement_noise_r_v": 0.0008610323423725228,
    "e4_rls_forgetting_factor": 0.999,
    "e5_slope_ref": 0.3,
    "e5_cap_plateau": 1.0e-05,
    "e5_cap_knee": 0.01,
    "e5_sigma_ocv_model_v": 0.02,
}


def run_audit_a():
    """Audit (a): Log multiplier theta over time on Set X and A1-007."""
    print("\n" + "=" * 80)
    print("AUDIT (A): RLS MULTIPLIER THETA TRAJECTORY AUDIT")
    print("=" * 80)

    assumptions, _, _ = load_assumptions(profile="calce_a123_v4")
    base_params = ParamSet.from_assumptions(assumptions, matched=True)
    p = replace(base_params, **TUNED_PARAMS)

    results_a = {}

    for cell_id in ["A1-007", "A1-008"]:
        results_a[cell_id] = {}
        for t in TEMPS:
            data = prepare_scenario_data_v2(temp_c=t, profile="DST", cell_id=cell_id)
            est = E7V2CompositeFilter(p)
            init_estimator_state(est, data.truth_soc[0], 0.0, 0.0, 0.0)

            thetas = []
            residuals = []
            for k in range(len(data.time_s)):
                dt = float(data.dt_arr[k]) if k > 0 else 1.0
                meas = Measurement(
                    v=float(data.voltage_v[k]),
                    i=float(data.current_a[k]),
                    temp_c=float(data.temp_measured_c[k]),
                    dt=dt,
                    dropout=False,
                )
                out = est.step(meas)
                thetas.append(out.theta)
                if out.voltage_residual is not None:
                    residuals.append(out.voltage_residual)

            thetas_arr = np.array(thetas)
            med = float(np.median(thetas_arr))
            p10 = float(np.percentile(thetas_arr, 10))
            p90 = float(np.percentile(thetas_arr, 90))
            t_min = float(np.min(thetas_arr))
            t_max = float(np.max(thetas_arr))

            results_a[cell_id][t] = {
                "median": med,
                "p10": p10,
                "p90": p90,
                "min": t_min,
                "max": t_max,
                "mean_res_mv": float(np.mean(residuals)) * 1000.0 if residuals else 0.0,
            }

    print(f"{'Cell':<8} {'Temp':<6} {'R0 Ratio':<10} {'Median Theta':<14} {'10th %ile':<12} {'90th %ile':<12} {'Min':<8} {'Max':<8} {'Mean Res (mV)'}")
    print("-" * 90)
    for t in TEMPS:
        res7 = results_a["A1-007"][t]
        print(f"A1-007   {t:<6} {'1.000':<10} {res7['median']:<14.4f} {res7['p10']:<12.4f} {res7['p90']:<12.4f} {res7['min']:<8.4f} {res7['max']:<8.4f} {res7['mean_res_mv']:+.2f}")
    print("-" * 90)
    for t in TEMPS:
        res8 = results_a["A1-008"][t]
        ratio_str = f"{R0_RATIO[t]:.4f} (+{(R0_RATIO[t]-1)*100:.1f}%)"
        print(f"A1-008   {t:<6} {ratio_str:<10} {res8['median']:<14.4f} {res8['p10']:<12.4f} {res8['p90']:<12.4f} {res8['min']:<8.4f} {res8['max']:<8.4f} {res8['mean_res_mv']:+.2f}")

    return results_a


def run_audit_b():
    """Audit (b): Variant test of R0 only vs R0+R1 adaptation."""
    print("\n" + "=" * 80)
    print("AUDIT (B): VARIANT TEST (RLS ADAPTING R0 ONLY VS R0+R1 JOINTLY)")
    print("=" * 80)

    # Reference baseline from baseline_reference.json (Tuned E2)
    baseline_path = repo_root / "reports" / "gauntlet_v2" / "baseline_reference.json"
    with open(baseline_path, "r") as f:
        base_ref = json.load(f)["summary_keep_rule_reference"]

    assumptions, _, _ = load_assumptions(profile="calce_a123_v4")
    base_params = ParamSet.from_assumptions(assumptions, matched=True)
    p_tuned = replace(
        base_params,
        process_noise_q_soc=TUNED_PARAMS["process_noise_q_soc"],
        process_noise_q_rc=TUNED_PARAMS["process_noise_q_rc"],
        process_noise_q_hysteresis=TUNED_PARAMS["process_noise_q_hysteresis"],
        measurement_noise_r_v=TUNED_PARAMS["measurement_noise_r_v"],
        e4_rls_forgetting_factor=TUNED_PARAMS["e4_rls_forgetting_factor"],
    )

    def eval_variant(adapt_r1_flag: bool):
        def factory(params):
            est = E4V2RLSEKF(params)
            est.adapt_r1 = adapt_r1_flag
            return est

        metrics_007 = {}
        for t in TEMPS:
            data = prepare_scenario_data_v2(temp_c=t, profile="DST", cell_id="A1-007")
            res = evaluate_estimator_v2(factory, p_tuned, data)
            metrics_007[t] = res

        metrics_008 = {}
        for t in TEMPS:
            data = prepare_scenario_data_v2(temp_c=t, profile="DST", cell_id="A1-008")
            res = evaluate_estimator_v2(factory, p_tuned, data)
            metrics_008[t] = res

        sbc_007_held = np.mean([metrics_007[t]["sbc_mean_rmse_pp"] for t in HELDOUT_TEMPS])
        sbc_008_held = np.mean([metrics_008[t]["sbc_mean_rmse_pp"] for t in HELDOUT_TEMPS])
        sa_007_held = np.mean([metrics_007[t]["sa_rmse_pp"] for t in HELDOUT_TEMPS])
        sf_007_worst = np.max([metrics_007[t]["sf_worst_err_pp"] for t in HELDOUT_TEMPS])
        sa_008_held = np.mean([metrics_008[t]["sa_rmse_pp"] for t in HELDOUT_TEMPS])
        sf_008_worst = np.max([metrics_008[t]["sf_worst_err_pp"] for t in HELDOUT_TEMPS])

        return {
            "sbc_007_held": float(sbc_007_held),
            "sbc_008_held": float(sbc_008_held),
            "sa_007_held": float(sa_007_held),
            "sf_007_worst": float(sf_007_worst),
            "sa_008_held": float(sa_008_held),
            "sf_008_worst": float(sf_008_worst),
            "metrics_007": metrics_007,
            "metrics_008": metrics_008,
        }

    print("Evaluating RLS with R0 only (adapt_r1=False)...")
    res_r0_only = eval_variant(False)
    print("Evaluating RLS with R0 and R1 jointly (adapt_r1=True)...")
    res_r0_r1 = eval_variant(True)

    k_007_sbc = "A1_007_heldout_sbc_mean_rmse_pp"
    k_007_sa = "A1_007_heldout_sa_mean_rmse_pp"
    k_007_sf = "A1_007_heldout_sf_worst_pp"
    k_x_sbc = "Set_X_heldout_sbc_mean_rmse_pp"
    k_x_sa = "Set_X_heldout_sa_mean_rmse_pp"
    k_x_sf = "Set_X_heldout_sf_worst_pp"

    print("\n--- Keep Rule Comparison Table ---")
    print(f"{'Metric':<35} {'Baseline (E2)':<15} {'R0 Only (adapt_r1=F)':<22} {'R0+R1 (adapt_r1=T)':<22}")
    print("-" * 95)
    print(f"{'A1-007 Held-Out SBC (pp)':<35} {base_ref[k_007_sbc]:<15.4f} {res_r0_only['sbc_007_held']:<22.4f} {res_r0_r1['sbc_007_held']:<22.4f}")
    print(f"{'Set X (A1-008) Held-Out SBC (pp)':<35} {base_ref[k_x_sbc]:<15.4f} {res_r0_only['sbc_008_held']:<22.4f} {res_r0_r1['sbc_008_held']:<22.4f}")
    print(f"{'A1-007 Held-Out S-A (pp)':<35} {base_ref[k_007_sa]:<15.4f} {res_r0_only['sa_007_held']:<22.4f} {res_r0_r1['sa_007_held']:<22.4f}")
    print(f"{'A1-007 Held-Out S-F Worst (pp)':<35} {base_ref[k_007_sf]:<15.4f} {res_r0_only['sf_007_worst']:<22.4f} {res_r0_r1['sf_007_worst']:<22.4f}")
    print(f"{'Set X Held-Out S-A (pp)':<35} {base_ref[k_x_sa]:<15.4f} {res_r0_only['sa_008_held']:<22.4f} {res_r0_r1['sa_008_held']:<22.4f}")
    print(f"{'Set X Held-Out S-F Worst (pp)':<35} {base_ref[k_x_sf]:<15.4f} {res_r0_only['sf_008_worst']:<22.4f} {res_r0_r1['sf_008_worst']:<22.4f}")

    # Relative improvements vs Baseline
    r0_diff_x = (res_r0_only["sbc_008_held"] - base_ref[k_x_sbc]) / base_ref[k_x_sbc] * 100.0
    r0_diff_007 = (res_r0_only["sbc_007_held"] - base_ref[k_007_sbc]) / base_ref[k_007_sbc] * 100.0

    r0r1_diff_x = (res_r0_r1["sbc_008_held"] - base_ref[k_x_sbc]) / base_ref[k_x_sbc] * 100.0
    r0r1_diff_007 = (res_r0_r1["sbc_007_held"] - base_ref[k_007_sbc]) / base_ref[k_007_sbc] * 100.0

    print("-" * 95)
    print(f"Set X SBC Relative Diff vs E2:  R0 Only = {r0_diff_x:+.2f}%,  R0+R1 = {r0r1_diff_x:+.2f}%")
    print(f"A1-007 SBC Relative Diff vs E2: R0 Only = {r0_diff_007:+.2f}%,  R0+R1 = {r0r1_diff_007:+.2f}%")

    return {"r0_only": res_r0_only, "r0_r1": res_r0_r1, "baseline": base_ref}


def run_audit_c():
    """Audit (c): Inspect Q(T) and M(T) usage in bms_soc_ref.py and E7v2, check imports."""
    print("\n" + "=" * 80)
    print("AUDIT (C): Q(T) AND M(T) CODE & IMPORT AUDIT")
    print("=" * 80)

    # 1. Check imports of deliverable/bms_soc_ref.py
    ref_file = repo_root / "deliverable" / "bms_soc_ref.py"
    with open(ref_file, "r") as f:
        code_ref = f.read()

    soc_imports = [line.strip() for line in code_ref.splitlines() if "import soc" in line or "from soc" in line]
    harness_imports = [line.strip() for line in code_ref.splitlines() if "import harness" in line or "from harness" in line or "scripts" in line]

    print(f"bms_soc_ref.py Top-Level / Run-Time Imports from soc.*:")
    # Check lines outside run_self_test
    lines = code_ref.splitlines()
    outside_self_test = []
    in_self_test = False
    for line in lines:
        if "def run_self_test" in line:
            in_self_test = True
        if not in_self_test and ("import" in line):
            outside_self_test.append(line.strip())

    print("Non-test module imports:")
    for imp in outside_self_test:
        print(f"  {imp}")

    # Check whether bms_soc_ref.py has any soc.* import outside self_test
    has_forbidden_import = any("soc." in imp or "from soc" in imp for imp in outside_self_test)
    print(f"Zero soc.* or harness imports in operational code: {not has_forbidden_import}")

    # 2. Check Q(T) and M(T) usage in bms_soc_ref.py and E7v2
    # In bms_soc_ref.py:
    ref_has_q_table = "Q_TABLE" in code_ref or "capacity_table" in code_ref
    ref_has_m_table = "M_TABLE" in code_ref or "hysteresis_table" in code_ref
    print(f"bms_soc_ref.py uses Q table: {ref_has_q_table} (Uses scalar NOMINAL_CAPACITY_AH: {not ref_has_q_table})")
    print(f"bms_soc_ref.py uses M table: {ref_has_m_table} (Uses scalar HYSTERESIS_AMPLITUDE_V: {not ref_has_m_table})")

    # In E7v2 (src/soc/estimators/e7v2.py):
    e7v2_file = repo_root / "src" / "soc" / "estimators" / "e7v2.py"
    with open(e7v2_file, "r") as f:
        code_e7v2 = f.read()

    e7v2_has_q_table = "capacity_table" in code_e7v2 or "q_table" in code_e7v2
    e7v2_has_m_table = "hysteresis_table" in code_e7v2 or "m_table" in code_e7v2
    print(f"E7v2 uses Q table: {e7v2_has_q_table} (Uses self.params.nominal_capacity_ah: {not e7v2_has_q_table})")
    print(f"E7v2 uses M table: {e7v2_has_m_table} (Uses self.params.hysteresis_amplitude_v: {not e7v2_has_m_table})")

    return {
        "outside_self_test_imports": outside_self_test,
        "has_forbidden_import": has_forbidden_import,
        "ref_has_q_table": ref_has_q_table,
        "ref_has_m_table": ref_has_m_table,
        "e7v2_has_q_table": e7v2_has_q_table,
        "e7v2_has_m_table": e7v2_has_m_table,
    }


def run_audit_d():
    """Audit (d): Tau2 bound impact test."""
    print("\n" + "=" * 80)
    print("AUDIT (D): TAU2 BOUND IMPACT TEST (600 s VS INTERIOR ~210 s)")
    print("=" * 80)

    # 1. List decision temperatures where tau2 equals 600 s bound
    assumptions, _, _ = load_assumptions(profile="calce_a123_v4")
    tau2_dict = assumptions.plant.tau2_table_s.value
    print("calce_a123_v4 tau2 values per temperature:")
    for t_str, val in tau2_dict.items():
        bound_flag = " == 600 s (BOUND)" if float(val) >= 599.9 else " (interior)"
        print(f"  {t_str:>5} C: {val:6.2f} s {bound_flag}")

    # Bounded decision temperatures: 20 °C, 50 °C (and suspect 25 °C)
    test_temps = [20, 25, 50]
    tau2_fixed_interior = 210.0

    # Test effect on W-mid bias/RMSE of plant model and S-A SOC estimation RMSE
    base_params = ParamSet.from_assumptions(assumptions, matched=True)
    p_baseline = replace(base_params, **TUNED_PARAMS)

    # Modified paramset with tau2 set to 210 s at 20, 25, 50 C
    tau2_mod = dict(base_params.tau2_table)
    # Format of tau2_table in ParamSet is dict
    for t in test_temps:
        for k in list(tau2_mod.keys()):
            if abs(float(k) - t) < 3.0:
                tau2_mod[k] = tau2_fixed_interior

    p_modified = replace(p_baseline, tau2_table=tau2_mod)

    print("\nEvaluating voltage fidelity (W-mid Bias/RMSE) and S-A SOC RMSE on A1-007:")
    print(f"{'Temp':<6} {'Base tau2':<12} {'Base Bias (mV)':<16} {'Base RMSE (mV)':<16} {'Base S-A (pp)':<14} {'Mod tau2':<10} {'Mod Bias (mV)':<16} {'Mod RMSE (mV)':<16} {'Mod S-A (pp)'}")
    print("-" * 115)

    results_d = {}
    for t in test_temps:
        data = prepare_scenario_data_v2(temp_c=t, profile="DST", cell_id="A1-007")

        # 1. Base plant model simulation error on W-mid (10% <= SOC <= 90%)
        # Extract W-mid mask
        mask_wmid = (data.truth_soc >= 0.10) & (data.truth_soc <= 0.90)
        v_meas = data.voltage_v[mask_wmid]

        v_base_model = data.v_model_truth[mask_wmid]
        base_bias = float(np.mean(v_meas - v_base_model)) * 1000.0
        base_rmse = float(np.sqrt(np.mean((v_meas - v_base_model) ** 2))) * 1000.0

        # Run E7v2 S-A with baseline
        est_base = E7V2CompositeFilter(p_baseline)
        init_estimator_state(est_base, data.truth_soc[0], 0.0, 0.0, 0.0)
        soc_base = run_stream_slice(est_base, data, 0, len(data.time_s))
        base_sa_soc_rmse = float(np.sqrt(np.mean(((soc_base - data.truth_soc) * 100.0) ** 2)))

        # 2. Modified simulation with tau2 = 210 s
        # Simulate 2RC with tau2_mod
        temps_p = list(base_params.temperatures_c)
        socs_p = list(base_params.soc_grid)
        r0_tab = InterpolatedTable2D(temps_p, socs_p, base_params.r0_table)
        r1_tab = InterpolatedTable2D(temps_p, socs_p, base_params.r1_table)
        tau1_tab = InterpolatedTable2D(temps_p, socs_p, base_params.tau1_table)
        r2_tab = InterpolatedTable2D(temps_p, socs_p, base_params.r2_table)
        tau2_tab_mod = InterpolatedTable2D(temps_p, socs_p, tau2_mod)
        ocv_tab = InterpolatedTable2D(temps_p, socs_p, base_params.ocv_table)
        m_val = M_AUDIT["A1-007"].get(t, base_params.hysteresis_amplitude_v)

        n = len(data.time_s)
        v_mod_model_full = np.zeros(n, dtype=float)
        i1, i2, h = 0.0, 0.0, 0.0
        for k in range(n):
            dt = float(data.dt_arr[k]) if k > 0 else 1.0
            cur_t = float(data.temp_measured_c[k])
            cur_i = float(data.current_a[k])
            cur_z = float(data.truth_soc[k])

            r0 = r0_tab.lookup(cur_z, cur_t)
            r1 = r1_tab.lookup(cur_z, cur_t)
            r2 = r2_tab.lookup(cur_z, cur_t)
            tau1 = tau1_tab.lookup(cur_z, cur_t)
            tau2 = tau2_tab_mod.lookup(cur_z, cur_t)
            ocv_v = ocv_tab.lookup(cur_z, cur_t)

            v_mod_model_full[k] = ocv_v + m_val * h - r1 * i1 - r2 * i2 - r0 * cur_i
            i1 = Cell2RCModel.step_rc_current(i1, cur_i, dt, tau1)
            i2 = Cell2RCModel.step_rc_current(i2, cur_i, dt, tau2)
            h = Cell2RCModel.step_hysteresis(h, cur_i, dt, data.cap_c20, base_params.hysteresis_gamma, base_params.coulombic_efficiency)

        v_mod_wmid = v_mod_model_full[mask_wmid]
        mod_bias = float(np.mean(v_meas - v_mod_wmid)) * 1000.0
        mod_rmse = float(np.sqrt(np.mean((v_meas - v_mod_wmid) ** 2))) * 1000.0

        # Run E7v2 S-A with modified tau2
        est_mod = E7V2CompositeFilter(p_modified)
        init_estimator_state(est_mod, data.truth_soc[0], 0.0, 0.0, 0.0)
        soc_mod = run_stream_slice(est_mod, data, 0, len(data.time_s))
        mod_sa_soc_rmse = float(np.sqrt(np.mean(((soc_mod - data.truth_soc) * 100.0) ** 2)))

        results_d[t] = {
            "base_bias_mv": base_bias,
            "base_rmse_mv": base_rmse,
            "base_sa_soc_rmse": base_sa_soc_rmse,
            "mod_bias_mv": mod_bias,
            "mod_rmse_mv": mod_rmse,
            "mod_sa_soc_rmse": mod_sa_soc_rmse,
        }

        print(f"{t:<6} {'600 s':<12} {base_bias:<+16.2f} {base_rmse:<16.2f} {base_sa_soc_rmse:<14.3f} {'210 s':<10} {mod_bias:<+16.2f} {mod_rmse:<16.2f} {mod_sa_soc_rmse:<.3f}")

    return results_d


if __name__ == "__main__":
    out_dir = repo_root / "reports" / "gauntlet_v3"
    out_dir.mkdir(parents=True, exist_ok=True)

    cp_a = out_dir / "checkpoint_a.json"
    if cp_a.exists():
        print("Loading cached Audit A results from checkpoint_a.json...")
        with open(cp_a, "r") as f:
            res_a = json.load(f)
    else:
        res_a = run_audit_a()

    res_b = run_audit_b()
    res_c = run_audit_c()
    res_d = run_audit_d()

    audit_data = {
        "audit_a": res_a,
        "audit_b": res_b,
        "audit_c": res_c,
        "audit_d": res_d,
    }

    with open(out_dir / "audit_results.json", "w") as f:
        json.dump(audit_data, f, indent=2)

    print("\nAudit successfully saved to reports/gauntlet_v3/audit_results.json")
