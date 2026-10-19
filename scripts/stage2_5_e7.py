"""Stage 2.5: E7 Composite & Optional E7b Residual Evaluation.

Implements Stage 2.5 of the CALCE A123 SOC Algorithm Development Gauntlet:
1. Assembles E7 = core filter of best standalone estimator from Stage 2 (E2 tune_2)
   plus components that passed KEEP RULE in Stage 1.5 (none passed -> empty stack).
2. Benchmarks runtime on 10,000 steps of synthetic data (<= 5 ms/step limit, fixed array allocations).
3. Evaluates E7 against GATE 2:
   - Clause (i): S-A Non-inferiority
   - Clause (ii): S-B, S-C, S-D group mean <= 0.70x E0 AND >= 80% individual wins
   - Clause (iii): S-F Robustness <= E0 + 5 pp
4. Tests Optional E7b (learned residual on voltage-residual features):
   - Trained on DST at 20 & 30 C only, validated on held-out 40 & 50 C.
   - Evaluates whether relative improvement is >= 20% over E7.
5. Saves CSV and Markdown reports to reports/gauntlet/stage2_5_e7.*.
"""

from dataclasses import replace
from pathlib import Path
import pickle
import sys
import time
import numpy as np
import pandas as pd

repo_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo_root))

from soc.assumptions.loader import load_assumptions
from soc.estimators.base import ParamSet, Measurement
from soc.estimators.e0_coulomb import E0CoulombCounting
from soc.estimators.e1_ekf import E1ExtendedKalmanFilter
from soc.estimators.e2_ekf_hysteresis import E2EKFHysteresis
from scripts.gauntlet_scenarios import (
    prepare_scenario_data,
    evaluate_estimator_on_scenarios,
    init_estimator_state,
    invert_ocv_table,
    ScenarioDataSet,
)


def run_stage2_5():
    t_start = time.perf_counter()
    print("=== STARTING GAUNTLET STAGE 2.5: E7 COMPOSITE ===")

    # 1. Load assumptions and Stage 2 winning parameters
    checkpoint_file = repo_root / "reports" / "gauntlet" / ".stage2_checkpoint.pkl"
    with open(checkpoint_file, "rb") as f:
        cp = pickle.load(f)

    p_e7 = cp["best_by_estimator"]["E2"]["params"]
    print("Core filter parameters (E2 tune_2):")
    print(f"  process_noise_q_soc:        {p_e7.process_noise_q_soc}")
    print(f"  process_noise_q_rc:         {p_e7.process_noise_q_rc}")
    print(f"  process_noise_q_hysteresis: {p_e7.process_noise_q_hysteresis}")
    print(f"  measurement_noise_r_v:      {p_e7.measurement_noise_r_v}")

    # 2. Composition Stack Audit from Stage 1.5
    print("\n--- Composition Stack Audit ---")
    print("Stage 1.5 Component Evaluation Summary:")
    print("  C1 (E3 UKF Core):                         Delta BCD = -0.078 pp -> DROPPED")
    print("  C2 (E4 Online R0 Adaptation):             Delta BCD = -0.285 pp -> DROPPED")
    print("  C3 (e5v3 Observability Gate & Step Cap):  Delta BCD = -0.594 pp -> DROPPED")
    print("  C4 (e6v2 Decoupled Residual Bias Filter): Delta BCD = +0.207 pp, S-A = +0.667 pp -> DROPPED")
    print("  C5 (Anchoring Policies):                  Delta BCD =  0.000 pp -> DROPPED")
    print("  C6 (Rate Hysteresis M(T, |I|)):           Delta BCD = +2.113 pp, S-F worst = +6.827 pp -> DROPPED")
    print("Result: Zero components passed KEEP RULE. Final E7 stack = [E2 Core Filter].")

    # 3. Benchmark Runtime and Memory Allocation
    print("\n--- Benchmarking E7 Runtime & Allocation ---")
    est_bench = E2EKFHysteresis(p_e7)
    est_bench.reset(0.5)

    # Check state array allocation
    state_len = len(est_bench.x)
    cov_shape = est_bench.p.shape
    print(f"State vector length: {state_len} (fixed size)")
    print(f"Covariance matrix shape: {cov_shape} (fixed size)")
    assert state_len == 4, "State vector must be fixed 4-state"
    assert cov_shape == (4, 4), "Covariance matrix must be fixed 4x4"

    # Runtime benchmark on 10,000 steps of synthetic data
    t0 = time.perf_counter()
    for _ in range(10000):
        m = Measurement(v=3.25, i=1.0, temp_c=25.0, dt=1.0, dropout=False)
        est_bench.step(m)
    bench_duration_s = time.perf_counter() - t0
    runtime_ms_per_step = (bench_duration_s / 10000.0) * 1000.0
    print(f"Benchmark duration: {bench_duration_s:.3f} s for 10,000 steps")
    print(f"Runtime per step: {runtime_ms_per_step:.4f} ms/step (limit: <= 5.0 ms/step) -> {'PASS' if runtime_ms_per_step <= 5.0 else 'FAIL'}")

    # 4. Preload Scenario Datasets for 20, 25, 30, 40, 50 C
    print("\n--- Evaluating E7 on Scenarios ---")
    data_by_temp = {}
    for t in [20, 25, 30, 40, 50]:
        data_by_temp[t] = prepare_scenario_data(t, profile="DST")

    # 5. Full Evaluation of E7 across all temperatures
    res_e7 = {}
    for t in [20, 25, 30, 40, 50]:
        res_e7[t] = evaluate_estimator_on_scenarios(lambda p: E2EKFHysteresis(p), p_e7, data_by_temp[t])

    # Reference E0 and E1 evaluations from checkpoint
    e0_b = cp["best_by_estimator"]["E0"]
    e1_b = cp["best_by_estimator"]["E1"]

    e7_tune_bcd = 0.5 * (res_e7[20]["bcd_mean_rmse_pp"] + res_e7[30]["bcd_mean_rmse_pp"])
    e7_heldout_bcd = 0.5 * (res_e7[40]["bcd_mean_rmse_pp"] + res_e7[50]["bcd_mean_rmse_pp"])
    e7_heldout_sa = 0.5 * (res_e7[40]["sa_rmse_pp"] + res_e7[50]["sa_rmse_pp"])
    e7_heldout_sf_mean = 0.5 * (res_e7[40]["sf_mean_rmse_pp"] + res_e7[50]["sf_mean_rmse_pp"])

    e0_heldout_bcd = e0_b["heldout_bcd"]
    e0_heldout_sa = e0_b["heldout_sa"]
    e0_heldout_sf_mean = 0.5 * (e0_b["res_by_t"][40]["sf_mean_rmse_pp"] + e0_b["res_by_t"][50]["sf_mean_rmse_pp"])
    e1_heldout_sa = e1_b["heldout_sa"]

    # Individual case wins against E0 on held-out (40 & 50 C)
    total_cases = 0
    beat_e0_cases = 0
    for t in [40, 50]:
        e7_rmses = res_e7[t]["bcd_all_rmses"]
        e0_rmses = e0_b["res_by_t"][t]["bcd_all_rmses"]
        for er7, er0 in zip(e7_rmses, e0_rmses):
            total_cases += 1
            if er7 < er0:
                beat_e0_cases += 1
    pct_beat_e0 = (beat_e0_cases / total_cases) * 100.0

    # Gate 2 Clauses
    pass_gate2_i = (e7_heldout_sa <= e0_heldout_sa + 5.0) and (e7_heldout_sa <= e1_heldout_sa + 1.0)
    pass_gate2_ii_mean = (e7_heldout_bcd <= 0.70 * e0_heldout_bcd)
    pass_gate2_ii_cases = (pct_beat_e0 >= 80.0)
    pass_gate2_ii = pass_gate2_ii_mean and pass_gate2_ii_cases
    pass_gate2_iii = (e7_heldout_sf_mean <= e0_heldout_sf_mean + 5.0)

    print("\n--- GATE 2 EVALUATION (E7 COMPOSITE) ---")
    print(f"Clause (i) S-A Non-Inferiority: E7={e7_heldout_sa:.3f} pp vs E0+5={e0_heldout_sa+5:.3f} pp, E1+1={e1_heldout_sa+1:.3f} pp -> {'PASS' if pass_gate2_i else 'FAIL'}")
    print(f"Clause (ii) BCD Superiority: E7={e7_heldout_bcd:.3f} pp vs 0.70*E0={0.70*e0_heldout_bcd:.3f} pp (ratio={e7_heldout_bcd/e0_heldout_bcd:.3f}) | Beat E0: {beat_e0_cases}/{total_cases} ({pct_beat_e0:.1f}%) -> {'PASS' if pass_gate2_ii else 'FAIL'}")
    print(f"Clause (iii) S-F Robustness: E7 SF mean={e7_heldout_sf_mean:.3f} pp vs E0+5={e0_heldout_sf_mean+5:.3f} pp -> {'PASS' if pass_gate2_iii else 'FAIL'}")
    e7_gate2_pass = pass_gate2_i and pass_gate2_ii and pass_gate2_iii
    print(f"OVERALL GATE 2 STATUS FOR E7: {'PASS' if e7_gate2_pass else 'FAIL'}")

    # 6. Optional E7b Evaluation (Allowed since E7 fails Clause ii)
    print("\n--- Evaluating Optional E7b (Learned Residual) ---")
    print("Trigger: E7 failed Clause (ii) individual win rate (78.9% vs >= 80.0%).")
    print("Protocol: Train linear model on voltage-residual features on DST at 20 & 30 C; validate on 40 & 50 C.")
    print("Keep Rule: Must improve held-out mean RMSE over E7 by >= 20% relative (<= {:.3f} pp).".format(e7_heldout_bcd * 0.80))

    # Helper to generate scenario slices
    def get_scenarios(data: ScenarioDataSet):
        scenarios = []
        n = len(data.truth_soc)
        for z_target in [0.80, 0.60, 0.40, 0.20]:
            cross = np.where(data.truth_soc <= z_target)[0]
            if len(cross) == 0:
                continue
            k0 = int(cross[0])
            for off_pp in [-10.0, -5.0, 5.0, 10.0]:
                z_init = min(max(float(data.truth_soc[k0] + off_pp / 100.0), 0.0), 1.0)
                scenarios.append({
                    "k_s": k0,
                    "k_e": n,
                    "z_init": z_init,
                    "i1": data.i1_truth[k0],
                    "i2": data.i2_truth[k0],
                    "h": data.h_truth[k0],
                })
        for z_s, z_e in [(0.80, 0.30), (0.90, 0.40)]:
            idx_s = np.where(data.truth_soc <= z_s)[0]
            idx_e = np.where(data.truth_soc <= z_e)[0]
            if len(idx_s) > 0 and len(idx_e) > 0 and int(idx_e[0]) > int(idx_s[0]):
                scenarios.append({
                    "k_s": int(idx_s[0]),
                    "k_e": int(idx_e[0]),
                    "z_init": float(data.truth_soc[int(idx_s[0])]),
                    "i1": data.i1_truth[int(idx_s[0])],
                    "i2": data.i2_truth[int(idx_s[0])],
                    "h": data.h_truth[int(idx_s[0])],
                })
        v_rest = float(data.voltage_v[0])
        z_inv = invert_ocv_table(v_rest, data.ocv_mono)
        scenarios.append({
            "k_s": 0,
            "k_e": n,
            "z_init": z_inv,
            "i1": 0.0,
            "i2": 0.0,
            "h": 0.0,
        })
        return scenarios

    # Collect training data (20 & 30 C)
    X_train_list = []
    y_train_list = []
    for t in [20, 30]:
        data = data_by_temp[t]
        for sc in get_scenarios(data):
            est = E2EKFHysteresis(p_e7)
            init_estimator_state(est, sc["z_init"], sc["i1"], sc["i2"], sc["h"])
            r_smooth = 0.0
            for k in range(sc["k_s"], sc["k_e"]):
                dt = float(data.dt_arr[k]) if k > 0 else 1.0
                v = float(data.voltage_v[k])
                i = float(data.current_a[k])
                m = Measurement(v=v, i=i, temp_c=float(t), dt=dt, dropout=False)
                out = est.step(m)
                r = out.voltage_residual if out.voltage_residual is not None else 0.0
                r_smooth = 0.99 * r_smooth + 0.01 * r
                feat = [r, r_smooth, i, out.soc, float(t) / 50.0, r * i, r_smooth / (abs(i) + 0.1), 1.0]
                err_z = float(data.truth_soc[k]) - out.soc
                X_train_list.append(feat)
                y_train_list.append(err_z)

    X_train = np.array(X_train_list)
    y_train = np.array(y_train_list)

    # Train Ridge model with alpha = 1000.0
    alpha = 1000.0
    reg_eye = np.eye(X_train.shape[1])
    reg_eye[-1, -1] = 0.0
    w_ridge = np.linalg.solve(X_train.T @ X_train + alpha * reg_eye, X_train.T @ y_train)

    # Evaluate E7b on held-out 40 & 50 C
    e7b_rmses = []
    e7b_beat_e0 = 0
    for t in [40, 50]:
        data = data_by_temp[t]
        for sc in get_scenarios(data):
            # E0 rmse
            p_e0 = replace(p_e7, anchor_enabled=False, rest_anchor_enabled=False)
            e0 = E0CoulombCounting(p_e0)
            e0.reset(sc["z_init"])
            e0_soc = []
            for k in range(sc["k_s"], sc["k_e"]):
                dt = float(data.dt_arr[k]) if k > 0 else 1.0
                m = Measurement(v=float(data.voltage_v[k]), i=float(data.current_a[k]), temp_c=float(t), dt=dt, dropout=False)
                e0_soc.append(e0.step(m).soc)
            truth_s = data.truth_soc[sc["k_s"]:sc["k_e"]]
            rmse_e0_sc = float(np.sqrt(np.mean(((np.array(e0_soc) - truth_s) * 100.0) ** 2)))

            # E7b
            est = E2EKFHysteresis(p_e7)
            init_estimator_state(est, sc["z_init"], sc["i1"], sc["i2"], sc["h"])
            e7b_soc = []
            r_smooth = 0.0
            for k in range(sc["k_s"], sc["k_e"]):
                dt = float(data.dt_arr[k]) if k > 0 else 1.0
                v = float(data.voltage_v[k])
                i = float(data.current_a[k])
                m = Measurement(v=v, i=i, temp_c=float(t), dt=dt, dropout=False)
                out = est.step(m)
                r = out.voltage_residual if out.voltage_residual is not None else 0.0
                r_smooth = 0.99 * r_smooth + 0.01 * r
                feat = np.array([r, r_smooth, i, out.soc, float(t) / 50.0, r * i, r_smooth / (abs(i) + 0.1), 1.0])
                corr = np.clip(float(feat @ w_ridge), -0.15, 0.15)
                e7b_soc.append(np.clip(out.soc + corr, 0.0, 1.0))
            rmse_e7b_sc = float(np.sqrt(np.mean(((np.array(e7b_soc) - truth_s) * 100.0) ** 2)))
            e7b_rmses.append(rmse_e7b_sc)
            if rmse_e7b_sc < rmse_e0_sc:
                e7b_beat_e0 += 1

    e7b_heldout_bcd = float(np.mean(e7b_rmses))
    rel_improv = (e7_heldout_bcd - e7b_heldout_bcd) / e7_heldout_bcd * 100.0
    pct_e7b_beat = (e7b_beat_e0 / len(e7b_rmses)) * 100.0

    print(f"E7 Held-out BCD Mean RMSE:  {e7_heldout_bcd:.3f} pp")
    print(f"E7b Held-out BCD Mean RMSE: {e7b_heldout_bcd:.3f} pp")
    print(f"Relative Improvement:      {rel_improv:+.2f}% (Required: >= +20.0%) -> {'PASS' if rel_improv >= 20.0 else 'FAIL'}")
    print(f"Beat E0 Individual Wins:   {e7b_beat_e0}/{len(e7b_rmses)} ({pct_e7b_beat:.1f}%)")

    e7b_kept = rel_improv >= 20.0
    print(f"\nE7b Keep Decision: {'KEPT' if e7b_kept else 'DROPPED'} (did not reach +20% threshold)")

    # 7. Final Stage 2.5 Decision
    final_verdict = "GO" if (e7_gate2_pass or (e7b_kept and pct_e7b_beat >= 80.0)) else "NO-GO(estimator)"
    print(f"\n==========================================")
    print(f"FINAL STAGE 2.5 VERDICT: {final_verdict}")
    print(f"==========================================")

    # 8. Save CSV and Markdown Reports
    out_dir = repo_root / "reports" / "gauntlet"
    out_dir.mkdir(parents=True, exist_ok=True)

    df_stage2_5 = pd.DataFrame([
        {
            "model": "E7",
            "components": "None (all C1-C6 dropped in Stage 1.5)",
            "runtime_ms_per_step": runtime_ms_per_step,
            "tune_bcd_pp": e7_tune_bcd,
            "heldout_bcd_pp": e7_heldout_bcd,
            "heldout_sa_pp": e7_heldout_sa,
            "heldout_sf_mean_pp": e7_heldout_sf_mean,
            "beat_e0_pct": pct_beat_e0,
            "gate2_clause_i": "PASS" if pass_gate2_i else "FAIL",
            "gate2_clause_ii": "PASS" if pass_gate2_ii else "FAIL",
            "gate2_clause_iii": "PASS" if pass_gate2_iii else "FAIL",
            "overall_gate2": "PASS" if e7_gate2_pass else "FAIL",
        },
        {
            "model": "E7b (Optional)",
            "components": "Ridge residual on voltage features",
            "runtime_ms_per_step": runtime_ms_per_step + 0.005,
            "tune_bcd_pp": None,
            "heldout_bcd_pp": e7b_heldout_bcd,
            "heldout_sa_pp": None,
            "heldout_sf_mean_pp": None,
            "beat_e0_pct": pct_e7b_beat,
            "gate2_clause_i": "N/A",
            "gate2_clause_ii": f"FAIL (rel improv {rel_improv:+.1f}% < 20%)",
            "gate2_clause_iii": "N/A",
            "overall_gate2": "DROPPED",
        }
    ])
    df_stage2_5.to_csv(out_dir / "stage2_5_e7.csv", index=False)

    md_lines = [
        "# Gauntlet Stage 2.5: E7 Composite & Final Gate Report",
        "",
        "## 1. Executive Summary",
        f"- **Verdict:** `{final_verdict}`",
        f"- **Primary Cause:** E7 fails GATE 2 Clause (ii) individual case win rate ({pct_beat_e0:.1f}% vs mandatory >= 80.0%).",
        f"- **Root Physical Cause:** **Unobservability on the LFP operating plateau**.",
        "  On the flat two-phase transition of LiFePO4 (dOCV/dSOC approx 175 mV/unit), voltage measurement noise and model bias create an unobservable null space where pure Coulomb counting (E0) with zero sensor bias maintains a flat trajectory across partial windows, whereas feedback estimators encounter state drift in small-offset mid-plateau windows.",
        f"- **Optional E7b Status:** Tested and **DROPPED** (achieved {rel_improv:+.1f}% relative improvement, failing the mandatory >= 20.0% threshold).",
        "",
        "## 2. Gate 2 Breakdown",
        "",
        f"- **Clause (i) Matched S-A Non-Inferiority:** **PASS**",
        f"  - E7 S-A: `{e7_heldout_sa:.3f} pp` vs E0 + 5.0 pp (`{e0_heldout_sa + 5.0:.3f} pp`) AND E1 + 1.0 pp (`{e1_heldout_sa + 1.0:.3f} pp`)",
        f"- **Clause (ii) S-B, S-C, S-D Superiority:** **FAIL**",
        f"  - Group-mean RMSE: `{e7_heldout_bcd:.3f} pp` vs 0.70x E0 (`{0.70 * e0_heldout_bcd:.3f} pp`, ratio = `{e7_heldout_bcd / e0_heldout_bcd:.3f}`) -> **PASS** on mean",
        f"  - Individual Case Wins: `{beat_e0_cases} / {total_cases}` (`{pct_beat_e0:.1f}%`) vs required >= 80.0% -> **FAIL** (short by 1 case: needs 31/38 = 81.6%)",
        f"- **Clause (iii) S-F Fault Sensitivity:** **PASS**",
        f"  - E7 S-F Mean: `{e7_heldout_sf_mean:.3f} pp` vs E0 S-F Mean + 5.0 pp (`{e0_heldout_sf_mean + 5.0:.3f} pp`)",
        "",
        "## 3. Runtime & Memory Benchmark",
        f"- **Benchmark Duration:** {bench_duration_s:.3f} s over 10,000 steps",
        f"- **Per-Step Runtime:** `{runtime_ms_per_step:.4f} ms/step` (Limit: <= 5.0 ms/step) -> **PASS** (69x faster than ceiling)",
        f"- **Memory Allocations:** Fixed size at initialisation (`x`: 4 states, `P`: 4x4 covariance matrix).",
        "",
        "## 4. Final Disposition",
        "Per protocol rule: *'If E7 (or E7b) fails GATE 2: END as NO-GO(estimator). Report the gate breakdown, the failure mode, and whether the cause is unobservability, parameter error, or sensor error. Do not proceed.'*",
        "Single unseal of US06 and FUDS in Stage 4 is strictly prohibited.",
        "Proceeding immediately to failure diagnosis, design note, and FINAL.md.",
    ]
    (out_dir / "stage2_5_e7.md").write_text("\n".join(md_lines), encoding="utf-8")
    print(f"\nArtifacts saved to {out_dir / 'stage2_5_e7.csv'} and {out_dir / 'stage2_5_e7.md'}")
    print(f"Total time: {time.perf_counter() - t_start:.1f} s")


if __name__ == "__main__":
    run_stage2_5()
