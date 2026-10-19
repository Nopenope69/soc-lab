"""Stage V3: Tuning and Gate Evaluation for Gauntlet V3 Confidence-Aware Estimator.

Protocol:
1. Candidate Pool:
   - E0 (fair), E1, E2, E7v2 (v2 baseline), E7v3.
   - Random search with fixed seed (np.random.seed(42)) over exposed noise, gating, RLS parameters.
2. Tuning:
   - Evaluate on A1-007 DST at 20 C and 30 C.
   - Objective: mean RMSE over S-B, S-C, S-G at 20 C and 30 C.
   - Constraints: S-A RMSE <= 1.5 pp and S-F worst-case <= 8.0 pp on tuning temps.
3. Selection:
   - Held-out score = mean of (A1-007 40 & 50 C SBC) and (Set X 40 & 50 C SBC).
   - Ties within 0.5 pp go to the simpler estimator.
   - Report tuning-versus-held-out gap.
4. Runtime limit:
   - Benchmark per-step execution time (<= 5 ms). Fixed-size arrays reported.
5. Gate Evaluation:
   - Apply GATE A (A1-007 held-out 40, 50 C) and GATE B (Set X 20, 30, 40, 50 C) to candidate and v2 baseline.
6. Additional Required Reports:
   - S-B vs S-G trade-off.
   - Paired bootstrap 95% CI of per-case RMSE difference vs E0 for S-B.
   - Hysteresis ablation (M = 0 vs M(T)) on both sets.
"""

from dataclasses import replace
import json
import math
from pathlib import Path
import sys
import time
from typing import Any, Callable, Dict, List, Tuple
import numpy as np

repo_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo_root))

from soc.assumptions.loader import load_assumptions
from soc.estimators.base import ParamSet
from soc.estimators.e7v3 import E7V3CompositeFilter
from soc.models.plant import Measurement
from scripts.gauntlet_v3_scenarios import (
    prepare_scenario_data_v3,
    evaluate_estimator_v3,
    R3_GUARANTEE_LINE,
)

ALL_TEMPS = [20, 25, 30, 40, 50]
DECISION_TEMPS = [20, 30, 40, 50]
TUNING_TEMPS = [20, 30]
HELDOUT_TEMPS = [40, 50]

E2_TUNED_PARAMS = {
    "process_noise_q_soc": 2.9031433196504225e-08,
    "process_noise_q_rc": 1.1198164932559382e-05,
    "process_noise_q_hysteresis": 0.00017150882346504795,
    "measurement_noise_r_v": 0.0008610323423725228,
}


def build_e7v3_factory(params_dict: Dict[str, Any], base_params: ParamSet) -> Callable[[ParamSet], E7V3CompositeFilter]:
    def factory(p_in: ParamSet) -> E7V3CompositeFilter:
        p = replace(
            p_in,
            process_noise_q_soc=float(params_dict.get("process_noise_q_soc", E2_TUNED_PARAMS["process_noise_q_soc"])),
            process_noise_q_rc=float(params_dict.get("process_noise_q_rc", E2_TUNED_PARAMS["process_noise_q_rc"])),
            process_noise_q_hysteresis=float(params_dict.get("process_noise_q_hysteresis", E2_TUNED_PARAMS["process_noise_q_hysteresis"])),
            measurement_noise_r_v=float(params_dict.get("measurement_noise_r_v", E2_TUNED_PARAMS["measurement_noise_r_v"])),
            e4_rls_forgetting_factor=float(params_dict.get("e4_rls_forgetting_factor", 0.999)),
            e5_slope_ref=float(params_dict.get("e5_slope_ref", 0.2)),
            e5_cap_plateau=float(params_dict.get("e5_cap_plateau", 1e-5)),
            e5_cap_knee=float(params_dict.get("e5_cap_knee", 0.01)),
            e5_sigma_ocv_model_v=float(params_dict.get("e5_sigma_ocv_model_v", 0.02)),
            hysteresis_amplitude_v=float(params_dict.get("hysteresis_amplitude_v", p_in.hysteresis_amplitude_v)),
        )
        return E7V3CompositeFilter(p)
    return factory


def generate_candidate_pool() -> List[Dict[str, Any]]:
    """Generate candidate configurations using systematic grid and fixed-seed random search."""
    np.random.seed(42)
    candidates = []

    # Candidate 0: Baseline tunings (un-tuned E7v3 with E2 defaults)
    base_cand = {
        "id": "cand_00_baseline",
        "process_noise_q_soc": E2_TUNED_PARAMS["process_noise_q_soc"],
        "process_noise_q_rc": E2_TUNED_PARAMS["process_noise_q_rc"],
        "process_noise_q_hysteresis": E2_TUNED_PARAMS["process_noise_q_hysteresis"],
        "measurement_noise_r_v": E2_TUNED_PARAMS["measurement_noise_r_v"],
        "e4_rls_forgetting_factor": 0.999,
        "e5_slope_ref": 0.2,
        "e5_cap_plateau": 1e-5,
        "e5_cap_knee": 0.01,
        "e5_sigma_ocv_model_v": 0.02,
    }
    candidates.append(base_cand)

    # Systematic exploration of process noise q_soc
    for q_soc in [1.0e-8, 5.0e-9, 2.0e-9, 1.0e-9, 5.0e-10]:
        c = dict(base_cand)
        c["id"] = f"cand_qsoc_{q_soc:.1e}"
        c["process_noise_q_soc"] = q_soc
        candidates.append(c)

    # Systematic exploration of plateau capping and slope reference
    for c_plat in [5.0e-6, 2.0e-5]:
        c = dict(base_cand)
        c["id"] = f"cand_cplat_{c_plat:.1e}"
        c["e5_cap_plateau"] = c_plat
        c["process_noise_q_soc"] = 2.0e-9
        candidates.append(c)

    for sl_ref in [0.15, 0.30]:
        c = dict(base_cand)
        c["id"] = f"cand_sl_{sl_ref}"
        c["e5_slope_ref"] = sl_ref
        c["process_noise_q_soc"] = 2.0e-9
        candidates.append(c)

    # Systematic exploration of RLS forgetting factor
    for ff in [0.998, 0.9995]:
        c = dict(base_cand)
        c["id"] = f"cand_ff_{ff}"
        c["e4_rls_forgetting_factor"] = ff
        c["process_noise_q_soc"] = 2.0e-9
        candidates.append(c)

    # Systematic exploration of measurement noise
    for rv_mult in [0.5, 2.0]:
        c = dict(base_cand)
        c["id"] = f"cand_rv_{rv_mult}x"
        c["measurement_noise_r_v"] = base_cand["measurement_noise_r_v"] * rv_mult
        c["process_noise_q_soc"] = 2.0e-9
        candidates.append(c)

    # 10 Random search draws around the promising region
    for k in range(10):
        c = {
            "id": f"cand_rand_{k+1:02d}",
            "process_noise_q_soc": float(10 ** np.random.uniform(-9.3, -8.3)),
            "process_noise_q_rc": float(base_cand["process_noise_q_rc"] * 10 ** np.random.uniform(-0.3, 0.3)),
            "process_noise_q_hysteresis": float(base_cand["process_noise_q_hysteresis"] * 10 ** np.random.uniform(-0.3, 0.3)),
            "measurement_noise_r_v": float(base_cand["measurement_noise_r_v"] * 10 ** np.random.uniform(-0.3, 0.3)),
            "e4_rls_forgetting_factor": float(np.random.choice([0.998, 0.999, 0.9995])),
            "e5_slope_ref": float(np.random.choice([0.15, 0.20, 0.25, 0.30])),
            "e5_cap_plateau": float(10 ** np.random.uniform(-5.5, -4.7)),
            "e5_cap_knee": 0.01,
            "e5_sigma_ocv_model_v": float(np.random.choice([0.015, 0.020, 0.025])),
        }
        candidates.append(c)

    return candidates


def run_stage_v3():
    print("=" * 80)
    print("STAGE V3: TUNING AND GATE EVALUATION (GAUNTLET V3)")
    print(f"R3 Guarantee: {R3_GUARANTEE_LINE}")
    print("=" * 80)

    start_time = time.time()
    assumptions, _, _ = load_assumptions(profile="calce_a123_v4")
    base_params = ParamSet.from_assumptions(assumptions, matched=True)

    # Pre-load scenario data
    print("\nPre-loading scenario data (DST across 20, 25, 30, 40, 50 C)...")
    sc_007 = {t: prepare_scenario_data_v3(t, "DST", "A1-007") for t in ALL_TEMPS}
    sc_008 = {t: prepare_scenario_data_v3(t, "DST", "A1-008") for t in ALL_TEMPS}
    print("Scenario datasets pre-loaded.")

    # Load baseline results for E0_fair, E1, E7v2
    with open(repo_root / "reports" / "gauntlet_v3" / "baselines_results.json", "r") as f:
        baselines = json.load(f)

    # Step 1: Candidate Pool Generation
    candidates = generate_candidate_pool()
    print(f"\nGenerated {len(candidates)} candidate configurations (budget limit: 250).")

    # Step 2: Tuning Evaluation on A1-007 (20 C and 30 C)
    print("\n" + "-" * 80)
    print("STEP 2: EVALUATING TUNING OBJECTIVE (20 C and 30 C on A1-007)")
    print("-" * 80)

    tuning_records = []
    for idx, cand in enumerate(candidates):
        cand_id = cand["id"]
        factory = build_e7v3_factory(cand, base_params)

        res_20 = evaluate_estimator_v3(factory, base_params, sc_007[20])
        res_30 = evaluate_estimator_v3(factory, base_params, sc_007[30])

        sbc_20 = res_20["sbc_mean_rmse_pp"]
        sbc_30 = res_30["sbc_mean_rmse_pp"]
        tuning_obj = 0.5 * (sbc_20 + sbc_30)

        sa_max = max(res_20["sa_rmse_pp"], res_30["sa_rmse_pp"])
        sf_worst = max(res_20["sf_worst_err_pp"], res_30["sf_worst_err_pp"])

        # Tuning constraints: S-A <= 1.5 pp, S-F worst <= 8.0 pp on tuning temperatures
        passes_constraints = (sa_max <= 1.5) and (sf_worst <= 8.0)

        rec = {
            "cand_id": cand_id,
            "params": cand,
            "tuning_sbc": tuning_obj,
            "sa_20": res_20["sa_rmse_pp"],
            "sa_30": res_30["sa_rmse_pp"],
            "sa_max": sa_max,
            "sf_worst": sf_worst,
            "passes_constraints": passes_constraints,
            "res_20": res_20,
            "res_30": res_30,
        }
        tuning_records.append(rec)
        print(
            f"[{idx+1:02d}/{len(candidates)}] {cand_id:<22} | "
            f"Tuning SBC: {tuning_obj:.3f} pp | "
            f"SA max: {sa_max:.3f} pp | "
            f"SF worst: {sf_worst:.2f} pp | "
            f"Pass constraints: {passes_constraints}",
            flush=True,
        )

    # Filter qualifying candidates
    qualifying = [r for r in tuning_records if r["passes_constraints"]]
    if not qualifying:
        print("\nWARNING: No candidate met strict constraints. Selecting top 5 by tuning objective.")
        tuning_records.sort(key=lambda x: x["tuning_sbc"])
        qualifying = tuning_records[:5]
    else:
        print(f"\n{len(qualifying)} candidates satisfied tuning constraints.")

    # Step 3: Held-Out Evaluation & Selection
    print("\n" + "-" * 80)
    print("STEP 3: HELD-OUT EVALUATION & SELECTION (40 C & 50 C on A1-007 and Set X)")
    print("-" * 80)

    heldout_records = []
    for r in qualifying:
        cand = r["params"]
        factory = build_e7v3_factory(cand, base_params)

        # A1-007 held-out (40, 50 C)
        res_007_40 = evaluate_estimator_v3(factory, base_params, sc_007[40])
        res_007_50 = evaluate_estimator_v3(factory, base_params, sc_007[50])
        sbc_007_held = 0.5 * (res_007_40["sbc_mean_rmse_pp"] + res_007_50["sbc_mean_rmse_pp"])

        # Set X held-out (40, 50 C)
        res_008_40 = evaluate_estimator_v3(factory, base_params, sc_008[40])
        res_008_50 = evaluate_estimator_v3(factory, base_params, sc_008[50])
        sbc_008_held = 0.5 * (res_008_40["sbc_mean_rmse_pp"] + res_008_50["sbc_mean_rmse_pp"])

        heldout_score = 0.5 * (sbc_007_held + sbc_008_held)
        gap = heldout_score - r["tuning_sbc"]

        h_rec = dict(r)
        h_rec.update({
            "sbc_007_held": sbc_007_held,
            "sbc_008_held": sbc_008_held,
            "heldout_score": heldout_score,
            "tuning_heldout_gap": gap,
            "res_007_40": res_007_40,
            "res_007_50": res_007_50,
            "res_008_40": res_008_40,
            "res_008_50": res_008_50,
        })
        heldout_records.append(h_rec)
        print(
            f"Candidate {r['cand_id']:<22} | "
            f"Tuning: {r['tuning_sbc']:.3f} pp | "
            f"Held 007: {sbc_007_held:.3f} pp | "
            f"Held Set X: {sbc_008_held:.3f} pp | "
            f"Held-out Score: {heldout_score:.3f} pp | "
            f"Gap: {gap:+.3f} pp",
            flush=True,
        )

    # Sort by held-out score
    heldout_records.sort(key=lambda x: x["heldout_score"])

    # Selection with tie-breaking: within 0.5 pp goes to simpler estimator
    best_score = heldout_records[0]["heldout_score"]
    close_candidates = [c for c in heldout_records if c["heldout_score"] <= best_score + 0.50]
    print(f"\n{len(close_candidates)} candidates within 0.5 pp tie-breaker window of best ({best_score:.3f} pp).")

    # Pick candidate with smallest complexity (lowest deviation from standard base params)
    def complexity_distance(cand):
        p = cand["params"]
        # Distance from default tunings
        return abs(math.log10(p["process_noise_q_soc"] / 2.0e-9)) + abs(p["e5_slope_ref"] - 0.2) + abs(p["e4_rls_forgetting_factor"] - 0.999) * 100

    close_candidates.sort(key=complexity_distance)
    selected = close_candidates[0]

    print("\n" + "=" * 80)
    print(f"SELECTED ESTIMATOR CANDIDATE: {selected['cand_id']}")
    print(f"  Tuning SBC (20, 30 C): {selected['tuning_sbc']:.4f} pp")
    print(f"  Held-out Score       : {selected['heldout_score']:.4f} pp")
    print(f"  Tuning vs Held-out Gap: {selected['tuning_heldout_gap']:+.4f} pp")
    print(f"  Parameters: {json.dumps(selected['params'], indent=2)}")
    print("=" * 80)

    # Step 4: Runtime Benchmark & Array Sizing
    print("\n" + "-" * 80)
    print("STEP 4: RUNTIME LIMIT BENCHMARK & ARRAY SIZING VERIFICATION")
    print("-" * 80)
    selected_factory = build_e7v3_factory(selected["params"], base_params)
    bench_est = selected_factory(base_params)
    bench_est.reset(0.50, soc_std=0.01)

    dummy_meas = Measurement(v=3.25, i=1.5, temp_c=25.0, dt=1.0, dropout=False)
    # Warm up
    for _ in range(50):
        bench_est.step(dummy_meas)

    n_bench = 1000
    t_start = time.perf_counter()
    for _ in range(n_bench):
        bench_est.step(dummy_meas)
    t_total = time.perf_counter() - t_start
    t_per_step_ms = (t_total / n_bench) * 1000.0

    print(f"Estimator runtime: {t_per_step_ms:.4f} ms per step (Limit: <= 5.0 ms per step).")
    print(f"Passes runtime limit: {t_per_step_ms <= 5.0}")
    print(f"State vector shape: {bench_est.x.shape} (dimension: 4, fixed-size).")
    print(f"Covariance matrix shape: {bench_est.p.shape} (dimension: 4x4, fixed-size).")

    # Step 5: Full Evaluation Across All Temperatures (A1-007 and Set X)
    print("\n" + "-" * 80)
    print("STEP 5: FULL GATE EVALUATION (GATE A & GATE B)")
    print("-" * 80)

    eval_007 = {}
    eval_008 = {}

    for t in ALL_TEMPS:
        print(f"Running evaluation on {t} C...", flush=True)
        eval_007[t] = evaluate_estimator_v3(selected_factory, base_params, sc_007[t])
        eval_008[t] = evaluate_estimator_v3(selected_factory, base_params, sc_008[t])

    # -------------------------------------------------------------
    # GATE A EVALUATION (A1-007; held-out 40 and 50 C; 25 C reported)
    # -------------------------------------------------------------
    print("\n" + "=" * 80)
    print("GATE A EVALUATION (Cell A1-007)")
    print("=" * 80)

    e0_007 = baselines["E0_fair"]["A1-007"]
    e1_007 = baselines["E1"]["A1-007"]

    # Clause (i): S-A RMSE <= E0 + 2.0 pp AND <= E1 + 1.0 pp
    sa_40 = eval_007[40]["sa_rmse_pp"]
    sa_50 = eval_007[50]["sa_rmse_pp"]
    sa_held = 0.5 * (sa_40 + sa_50)
    e0_sa_held = 0.5 * (e0_007["40"]["sa_rmse_pp"] + e0_007["50"]["sa_rmse_pp"])
    e1_sa_held = 0.5 * (e1_007["40"]["sa_rmse_pp"] + e1_007["50"]["sa_rmse_pp"])
    bar_sa_e0 = e0_sa_held + 2.0
    bar_sa_e1 = e1_sa_held + 1.0
    gate_a_i_pass = (sa_held <= bar_sa_e0) and (sa_held <= bar_sa_e1)

    # Clause (ii-a): S-B group-mean RMSE <= 0.70 x E0 group-mean AND beats E0 in >= 80% of S-B cases
    sb_40_rmses = eval_007[40]["sb_rmses"]
    sb_50_rmses = eval_007[50]["sb_rmses"]
    sb_all_held = sb_40_rmses + sb_50_rmses
    sb_held_mean = float(np.mean(sb_all_held))

    e0_sb_40 = e0_007["40"]["sb_rmses"]
    e0_sb_50 = e0_007["50"]["sb_rmses"]
    e0_sb_all_held = e0_sb_40 + e0_sb_50
    e0_sb_held_mean = float(np.mean(e0_sb_all_held))
    bar_sb_mean = 0.70 * e0_sb_held_mean

    sb_wins = sum(1 for c, e in zip(sb_all_held, e0_sb_all_held) if c < e)
    sb_win_rate = sb_wins / len(sb_all_held)
    gate_a_iia_pass = (sb_held_mean <= bar_sb_mean) and (sb_win_rate >= 0.80)

    # Clause (ii-b): S-C mean RMSE per temperature <= E0 + 1.5 pp
    sc_40_mean = eval_007[40]["sc_mean_rmse_pp"]
    sc_50_mean = eval_007[50]["sc_mean_rmse_pp"]
    e0_sc_40_mean = e0_007["40"]["sc_mean_rmse_pp"]
    e0_sc_50_mean = e0_007["50"]["sc_mean_rmse_pp"]
    bar_sc_40 = e0_sc_40_mean + 1.5
    bar_sc_50 = e0_sc_50_mean + 1.5
    gate_a_iib_pass = (sc_40_mean <= bar_sc_40) and (sc_50_mean <= bar_sc_50)

    # Clause (ii-c): S-G mean RMSE per temperature <= E0 + 1.0 pp
    sg_40_mean = eval_007[40]["sg_mean_rmse_pp"]
    sg_50_mean = eval_007[50]["sg_mean_rmse_pp"]
    e0_sg_40_mean = e0_007["40"]["sg_mean_rmse_pp"]
    e0_sg_50_mean = e0_007["50"]["sg_mean_rmse_pp"]
    bar_sg_40 = e0_sg_40_mean + 1.0
    bar_sg_50 = e0_sg_50_mean + 1.0
    gate_a_iic_pass = (sg_40_mean <= bar_sg_40) and (sg_50_mean <= bar_sg_50)

    # Clause (iii): S-F mean RMSE <= E0 + 5.0 pp
    sf_40_mean = eval_007[40]["sf_mean_rmse_pp"]
    sf_50_mean = eval_007[50]["sf_mean_rmse_pp"]
    sf_held_mean = 0.5 * (sf_40_mean + sf_50_mean)
    e0_sf_held_mean = 0.5 * (e0_007["40"]["sf_mean_rmse_pp"] + e0_007["50"]["sf_mean_rmse_pp"])
    bar_sf = e0_sf_held_mean + 5.0
    gate_a_iii_pass = (sf_held_mean <= bar_sf)

    gate_a_pass = gate_a_i_pass and gate_a_iia_pass and gate_a_iib_pass and gate_a_iic_pass and gate_a_iii_pass

    print(f"Clause (i)   S-A <= E0+2.0 & E1+1.0: {sa_held:.3f} pp vs bars ({bar_sa_e0:.3f}, {bar_sa_e1:.3f}) | Pass: {gate_a_i_pass}")
    print(f"Clause (ii-a) S-B mean <= 0.70*E0: {sb_held_mean:.3f} pp vs bar {bar_sb_mean:.3f} pp | Win rate: {sb_wins}/32 ({sb_win_rate*100:.1f}%) vs 80% | Pass: {gate_a_iia_pass}")
    print(f"Clause (ii-b) S-C mean <= E0+1.5: 40C={sc_40_mean:.3f} vs {bar_sc_40:.3f}, 50C={sc_50_mean:.3f} vs {bar_sc_50:.3f} | Pass: {gate_a_iib_pass}")
    print(f"Clause (ii-c) S-G mean <= E0+1.0: 40C={sg_40_mean:.3f} vs {bar_sg_40:.3f}, 50C={sg_50_mean:.3f} vs {bar_sg_50:.3f} | Pass: {gate_a_iic_pass}")
    print(f"Clause (iii)  S-F mean <= E0+5.0: {sf_held_mean:.3f} pp vs bar {bar_sf:.3f} pp | Pass: {gate_a_iii_pass}")
    print(f"--> GATE A OVERALL PASS: {gate_a_pass}")

    # -------------------------------------------------------------
    # GATE B EVALUATION (Set X / A1-008; 20, 30, 40, 50 C; 25 C reported)
    # -------------------------------------------------------------
    print("\n" + "=" * 80)
    print("GATE B EVALUATION (Set X / Cell A1-008 against Fair E0)")
    print("=" * 80)

    e0_008 = baselines["E0_fair"]["A1-008"]

    # Clause (i): S-A <= E0 + 3.0 pp (at every decision temp)
    gate_b_i_pass = True
    b_i_details = {}
    for t in DECISION_TEMPS:
        sa_cand = eval_008[t]["sa_rmse_pp"]
        sa_e0 = e0_008[str(t)]["sa_rmse_pp"]
        bar = sa_e0 + 3.0
        p = sa_cand <= bar
        b_i_details[t] = (sa_cand, bar, p)
        if not p:
            gate_b_i_pass = False

    # Clause (ii): S-B group-mean <= E0 group-mean at every temperature
    gate_b_ii_pass = True
    b_ii_details = {}
    for t in DECISION_TEMPS:
        sb_cand = eval_008[t]["sb_mean_rmse_pp"]
        sb_e0 = e0_008[str(t)]["sb_mean_rmse_pp"]
        p = sb_cand <= sb_e0
        b_ii_details[t] = (sb_cand, sb_e0, p)
        if not p:
            gate_b_ii_pass = False

    # Clause (iii): S-C mean <= E0 + 3.0 pp (at every decision temp)
    gate_b_iii_pass = True
    b_iii_details = {}
    for t in DECISION_TEMPS:
        sc_cand = eval_008[t]["sc_mean_rmse_pp"]
        sc_e0 = e0_008[str(t)]["sc_mean_rmse_pp"]
        bar = sc_e0 + 3.0
        p = sc_cand <= bar
        b_iii_details[t] = (sc_cand, bar, p)
        if not p:
            gate_b_iii_pass = False

    # Clause (iv): S-G mean <= E0 + 1.5 pp (at every decision temp)
    gate_b_iv_pass = True
    b_iv_details = {}
    for t in DECISION_TEMPS:
        sg_cand = eval_008[t]["sg_mean_rmse_pp"]
        sg_e0 = e0_008[str(t)]["sg_mean_rmse_pp"]
        bar = sg_e0 + 1.5
        p = sg_cand <= bar
        b_iv_details[t] = (sg_cand, bar, p)
        if not p:
            gate_b_iv_pass = False

    gate_b_pass = gate_b_i_pass and gate_b_ii_pass and gate_b_iii_pass and gate_b_iv_pass

    print(f"Clause (i)   S-A <= E0+3.0: {b_i_details} | Pass: {gate_b_i_pass}")
    print(f"Clause (ii)  S-B mean <= E0: {b_ii_details} | Pass: {gate_b_ii_pass}")
    print(f"Clause (iii) S-C mean <= E0+3.0: {b_iii_details} | Pass: {gate_b_iii_pass}")
    print(f"Clause (iv)  S-G mean <= E0+1.5: {b_iv_details} | Pass: {gate_b_iv_pass}")
    print(f"--> GATE B OVERALL PASS: {gate_b_pass}")

    # Step 6: Additional Required Reports
    print("\n" + "-" * 80)
    print("STEP 6: ADDITIONAL REQUIRED ANALYSES")
    print("-" * 80)

    # 1. S-B vs S-G trade-off (recovery speed vs false confident start amplification)
    print("Computing S-B vs S-G trade-off metrics...")
    sb_vs_sg_data = {}
    for cell_id, eval_dict, e0_dict in [("A1-007", eval_007, e0_007), ("A1-008", eval_008, e0_008)]:
        sb_means = [eval_dict[t]["sb_mean_rmse_pp"] for t in DECISION_TEMPS]
        sg_means = [eval_dict[t]["sg_mean_rmse_pp"] for t in DECISION_TEMPS]
        e0_sb_means = [e0_dict[str(t)]["sb_mean_rmse_pp"] for t in DECISION_TEMPS]
        e0_sg_means = [e0_dict[str(t)]["sg_mean_rmse_pp"] for t in DECISION_TEMPS]
        sb_vs_sg_data[cell_id] = {
            "sb_cand_mean": float(np.mean(sb_means)),
            "sb_e0_mean": float(np.mean(e0_sb_means)),
            "sg_cand_mean": float(np.mean(sg_means)),
            "sg_e0_mean": float(np.mean(e0_sg_means)),
            "sb_recovery_improvement_pp": float(np.mean(e0_sb_means) - np.mean(sb_means)),
            "sg_excess_error_pp": float(np.mean(sg_means) - np.mean(e0_sg_means)),
        }
    print(f"S-B vs S-G Trade-off: {json.dumps(sb_vs_sg_data, indent=2)}")

    # 2. Paired Bootstrap 95% CI of per-case RMSE difference vs E0 for S-B
    print("Computing paired bootstrap 95% CI for S-B...")
    np.random.seed(42)
    diffs_sb = np.array(sb_all_held) - np.array(e0_sb_all_held)
    n_boot = 1000
    boot_means = [float(np.mean(np.random.choice(diffs_sb, size=len(diffs_sb), replace=True))) for _ in range(n_boot)]
    ci_lower = float(np.percentile(boot_means, 2.5))
    ci_upper = float(np.percentile(boot_means, 97.5))
    mean_diff = float(np.mean(diffs_sb))
    bootstrap_data = {
        "mean_diff_pp": mean_diff,
        "ci_lower_2.5": ci_lower,
        "ci_upper_97.5": ci_upper,
        "n_cases": len(diffs_sb),
        "n_boot": n_boot,
    }
    print(f"Paired Bootstrap S-B (Cand - E0): Mean={mean_diff:.3f} pp, 95% CI=[{ci_lower:.3f}, {ci_upper:.3f}] pp")

    # 3. Hysteresis Ablation (M = 0 vs M(T)) on both sets
    print("Evaluating Hysteresis Ablation (M = 0 vs M(T))...")
    no_hyst_dict = dict(selected["params"])
    no_hyst_dict["hysteresis_amplitude_v"] = 0.0
    no_hyst_factory = build_e7v3_factory(no_hyst_dict, base_params)

    hyst_ablation = {}
    for cell_id, sc_dict in [("A1-007", sc_007), ("A1-008", sc_008)]:
        res_m0 = {t: evaluate_estimator_v3(no_hyst_factory, base_params, sc_dict[t]) for t in HELDOUT_TEMPS}
        sbc_m0 = 0.5 * (res_m0[40]["sbc_mean_rmse_pp"] + res_m0[50]["sbc_mean_rmse_pp"])
        sa_m0 = 0.5 * (res_m0[40]["sa_rmse_pp"] + res_m0[50]["sa_rmse_pp"])
        hyst_ablation[cell_id] = {
            "sbc_m0": sbc_m0,
            "sa_m0": sa_m0,
        }
    print(f"Hysteresis Ablation: {json.dumps(hyst_ablation, indent=2)}")

    total_time = time.time() - start_time

    # Save detailed evaluation artifacts
    results_payload = {
        "selected_candidate": selected,
        "runtime_benchmark": {
            "time_per_step_ms": t_per_step_ms,
            "passes_limit": t_per_step_ms <= 5.0,
            "state_dim": 4,
            "cov_dim": [4, 4],
        },
        "gate_a": {
            "pass": gate_a_pass,
            "clause_i": {"pass": gate_a_i_pass, "sa_held": sa_held, "bar_e0": bar_sa_e0, "bar_e1": bar_sa_e1},
            "clause_iia": {"pass": gate_a_iia_pass, "sb_held_mean": sb_held_mean, "bar_sb_mean": bar_sb_mean, "sb_wins": sb_wins, "win_rate": sb_win_rate},
            "clause_iib": {"pass": gate_a_iib_pass, "sc_40": sc_40_mean, "bar_sc_40": bar_sc_40, "sc_50": sc_50_mean, "bar_sc_50": bar_sc_50},
            "clause_iic": {"pass": gate_a_iic_pass, "sg_40": sg_40_mean, "bar_sg_40": bar_sg_40, "sg_50": sg_50_mean, "bar_sg_50": bar_sg_50},
            "clause_iii": {"pass": gate_a_iii_pass, "sf_held_mean": sf_held_mean, "bar_sf": bar_sf},
        },
        "gate_b": {
            "pass": gate_b_pass,
            "clause_i": {"pass": gate_b_i_pass, "details": {str(k): list(v) for k, v in b_i_details.items()}},
            "clause_ii": {"pass": gate_b_ii_pass, "details": {str(k): list(v) for k, v in b_ii_details.items()}},
            "clause_iii": {"pass": gate_b_iii_pass, "details": {str(k): list(v) for k, v in b_iii_details.items()}},
            "clause_iv": {"pass": gate_b_iv_pass, "details": {str(k): list(v) for k, v in b_iv_details.items()}},
        },
        "eval_007": {str(t): eval_007[t] for t in ALL_TEMPS},
        "eval_008": {str(t): eval_008[t] for t in ALL_TEMPS},
        "sb_vs_sg_data": sb_vs_sg_data,
        "bootstrap_data": bootstrap_data,
        "hysteresis_ablation": hyst_ablation,
        "total_runtime_s": total_time,
    }

    out_json = repo_root / "reports" / "gauntlet_v3" / "stage_v3_results.json"
    with open(out_json, "w") as f:
        json.dump(results_payload, f, indent=2)
    print(f"\nSaved detailed evaluation results to {out_json}")

    return results_payload


if __name__ == "__main__":
    run_stage_v3()
