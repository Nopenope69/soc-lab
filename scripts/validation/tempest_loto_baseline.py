"""Per-fold constant-parameter baseline evaluation for TEMPEST 280 Ah.

Computes, for every Leave-One-Temperature-Out (LOTO) fold and both Alternate-SOC folds,
a constant-parameter baseline (parameters averaged over training temperatures or SOC points)
under the same gates:
  - Mean Voltage Bias <= 2.0 mV
  - Voltage RMSE <= 6.0 mV
  - Implied Plateau SOC Error <= 2.5 pp

Labelled: 'post-hoc extension, not in the committed spec if the spec did not require it'.
Compares linear interpolation against constant-parameter baselines.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any, Dict, List
import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validation.tempest_ecm_identification import TempestEcmIdentifier, VALID_TEMPERATURES


def evaluate_loto_and_altsoc_baselines() -> Dict[str, Any]:
    ecm_json_path = REPO_ROOT / "reports" / "validation" / "tempest_ecm_results.json"
    if not ecm_json_path.exists():
        raise FileNotFoundError(f"Missing {ecm_json_path}")

    with open(ecm_json_path, "r", encoding="utf-8") as f:
        ecm_data = json.load(f)

    # Load HPPC tests for voltage simulation
    identifier = TempestEcmIdentifier()

    # Index identified parameters by temperature
    params_by_t: Dict[int, List[Dict[str, Any]]] = {t: [] for t in VALID_TEMPERATURES}
    for p in ecm_data["in_sample_pulse_parameters"]:
        params_by_t[p["temperature_c"]].append(p)

    plateau_slopes: Dict[int, float] = {
        15: 1.356,
        20: 1.366,
        25: 1.386,
        30: 1.402,
        35: 1.422,
    }

    # 1. Leave-One-Temperature-Out (LOTO)
    loto_comparison: List[Dict[str, Any]] = []

    for val_t in VALID_TEMPERATURES:
        train_temps = [t for t in VALID_TEMPERATURES if t != val_t]
        val_test = identifier.tests[val_t]

        interp_rmses: List[float] = []
        interp_biases: List[float] = []
        interp_socs: List[float] = []

        const_rmses: List[float] = []
        const_biases: List[float] = []
        const_socs: List[float] = []

        for k in range(len(val_test.discharge_pulses)):
            _, raw_win = identifier.fit_single_pulse(val_test, k)
            t_win = raw_win["t_win"]
            i_win = raw_win["i_win"]
            v_win = raw_win["v_win"]

            t_arr = np.array(train_temps, dtype=float)
            r0_tr = [params_by_t[t][k]["r0_ohm"] for t in train_temps]
            r1_tr = [params_by_t[t][k]["r1_ohm"] for t in train_temps]
            tau1_tr = [params_by_t[t][k]["tau1_s"] for t in train_temps]
            r2_tr = [params_by_t[t][k]["r2_ohm"] for t in train_temps]
            tau2_tr = [params_by_t[t][k]["tau2_s"] for t in train_temps]
            ocv_tr = [params_by_t[t][k]["ocv_v"] for t in train_temps]

            # Linear interpolation / extrapolation
            r0_i = float(np.interp(val_t, t_arr, r0_tr))
            r1_i = float(np.interp(val_t, t_arr, r1_tr))
            tau1_i = float(np.interp(val_t, t_arr, tau1_tr))
            r2_i = float(np.interp(val_t, t_arr, r2_tr))
            tau2_i = float(np.interp(val_t, t_arr, tau2_tr))
            ocv_i = float(np.interp(val_t, t_arr, ocv_tr))

            v_sim_i = identifier.simulate_2rc_window(t_win, i_win, ocv_i, r0_i, r1_i, tau1_i, r2_i, tau2_i)
            res_i = v_win - v_sim_i
            rmse_i = float(np.sqrt(np.mean(res_i**2)) * 1000.0)
            bias_i = float(np.mean(res_i) * 1000.0)
            soc_i = rmse_i / plateau_slopes[val_t]

            interp_rmses.append(rmse_i)
            interp_biases.append(abs(bias_i))
            interp_socs.append(soc_i)

            # Constant baseline: mean parameters across training temperatures for this SOC point
            r0_c = float(np.mean(r0_tr))
            r1_c = float(np.mean(r1_tr))
            tau1_c = float(np.mean(tau1_tr))
            r2_c = float(np.mean(r2_tr))
            tau2_c = float(np.mean(tau2_tr))
            ocv_c = float(np.mean(ocv_tr))

            v_sim_c = identifier.simulate_2rc_window(t_win, i_win, ocv_c, r0_c, r1_c, tau1_c, r2_c, tau2_c)
            res_c = v_win - v_sim_c
            rmse_c = float(np.sqrt(np.mean(res_c**2)) * 1000.0)
            bias_c = float(np.mean(res_c) * 1000.0)
            soc_c = rmse_c / plateau_slopes[val_t]

            const_rmses.append(rmse_c)
            const_biases.append(abs(bias_c))
            const_socs.append(soc_c)

        m_interp_rmse = float(np.mean(interp_rmses))
        m_interp_bias = float(np.mean(interp_biases))
        m_interp_soc = float(np.mean(interp_socs))
        interp_pass = (m_interp_bias <= 2.0) and (m_interp_rmse <= 6.0) and (m_interp_soc <= 2.5)

        m_const_rmse = float(np.mean(const_rmses))
        m_const_bias = float(np.mean(const_biases))
        m_const_soc = float(np.mean(const_socs))
        const_pass = (m_const_bias <= 2.0) and (m_const_rmse <= 6.0) and (m_const_soc <= 2.5)

        rel_comparison = "interp_beats_const" if m_interp_rmse < m_const_rmse else "const_beats_interp"

        loto_comparison.append({
            "held_out_temperature_c": val_t,
            "train_temperatures_c": train_temps,
            "interpolation": {
                "mean_rmse_mv": round(m_interp_rmse, 3),
                "mean_bias_mv": round(m_interp_bias, 3),
                "mean_implied_soc_error_pp": round(m_interp_soc, 3),
                "bias_gate_pass": m_interp_bias <= 2.0,
                "rmse_gate_pass": m_interp_rmse <= 6.0,
                "soc_gate_pass": m_interp_soc <= 2.5,
                "verdict": "PASS" if interp_pass else "FAIL",
            },
            "constant_baseline_posthoc": {
                "label": "post-hoc extension, not in the committed spec if the spec did not require it",
                "mean_rmse_mv": round(m_const_rmse, 3),
                "mean_bias_mv": round(m_const_bias, 3),
                "mean_implied_soc_error_pp": round(m_const_soc, 3),
                "bias_gate_pass": m_const_bias <= 2.0,
                "rmse_gate_pass": m_const_rmse <= 6.0,
                "soc_gate_pass": m_const_soc <= 2.5,
                "verdict": "PASS" if const_pass else "FAIL",
            },
            "rmse_difference_mv": round(m_interp_rmse - m_const_rmse, 3),
            "relative_performance": rel_comparison,
        })

    # 2. Alternate-SOC Holdout Folds
    alt_soc_comparison: List[Dict[str, Any]] = []
    folds_def = [
        ("ALT_ODD_FIT", [0, 2, 4, 6, 8], [1, 3, 5, 7, 9]),
        ("ALT_EVEN_FIT", [1, 3, 5, 7, 9], [0, 2, 4, 6, 8]),
    ]

    for fold_name, train_idxs, val_idxs in folds_def:
        interp_rmses = []
        interp_biases = []
        interp_socs = []

        const_rmses = []
        const_biases = []
        const_socs = []

        for t in VALID_TEMPERATURES:
            test = identifier.tests[t]
            t_params = params_by_t[t]

            soc_tr = np.array([t_params[k]["soc_nominal"] for k in train_idxs])
            sort_o = np.argsort(soc_tr)
            soc_tr_s = soc_tr[sort_o]
            r0_tr = np.array([t_params[k]["r0_ohm"] for k in train_idxs])[sort_o]
            r1_tr = np.array([t_params[k]["r1_ohm"] for k in train_idxs])[sort_o]
            tau1_tr = np.array([t_params[k]["tau1_s"] for k in train_idxs])[sort_o]
            r2_tr = np.array([t_params[k]["r2_ohm"] for k in train_idxs])[sort_o]
            tau2_tr = np.array([t_params[k]["tau2_s"] for k in train_idxs])[sort_o]
            ocv_tr = np.array([t_params[k]["ocv_v"] for k in train_idxs])[sort_o]

            r0_c = float(np.mean(r0_tr))
            r1_c = float(np.mean(r1_tr))
            tau1_c = float(np.mean(tau1_tr))
            r2_c = float(np.mean(r2_tr))
            tau2_c = float(np.mean(tau2_tr))
            ocv_c = float(np.mean(ocv_tr))

            for val_k in val_idxs:
                _, raw_win = identifier.fit_single_pulse(test, val_k)
                val_soc = t_params[val_k]["soc_nominal"]
                t_win = raw_win["t_win"]
                i_win = raw_win["i_win"]
                v_win = raw_win["v_win"]

                r0_i = float(np.interp(val_soc, soc_tr_s, r0_tr))
                r1_i = float(np.interp(val_soc, soc_tr_s, r1_tr))
                tau1_i = float(np.interp(val_soc, soc_tr_s, tau1_tr))
                r2_i = float(np.interp(val_soc, soc_tr_s, r2_tr))
                tau2_i = float(np.interp(val_soc, soc_tr_s, tau2_tr))
                ocv_i = float(np.interp(val_soc, soc_tr_s, ocv_tr))

                v_sim_i = identifier.simulate_2rc_window(t_win, i_win, ocv_i, r0_i, r1_i, tau1_i, r2_i, tau2_i)
                res_i = v_win - v_sim_i
                rmse_i = float(np.sqrt(np.mean(res_i**2)) * 1000.0)
                bias_i = float(np.mean(res_i) * 1000.0)
                soc_i = rmse_i / plateau_slopes[t]

                interp_rmses.append(rmse_i)
                interp_biases.append(abs(bias_i))
                interp_socs.append(soc_i)

                v_sim_c = identifier.simulate_2rc_window(t_win, i_win, ocv_c, r0_c, r1_c, tau1_c, r2_c, tau2_c)
                res_c = v_win - v_sim_c
                rmse_c = float(np.sqrt(np.mean(res_c**2)) * 1000.0)
                bias_c = float(np.mean(res_c) * 1000.0)
                soc_c = rmse_c / plateau_slopes[t]

                const_rmses.append(rmse_c)
                const_biases.append(abs(bias_c))
                const_socs.append(soc_c)

        m_interp_rmse = float(np.mean(interp_rmses))
        m_interp_bias = float(np.mean(interp_biases))
        m_interp_soc = float(np.mean(interp_socs))
        interp_pass = (m_interp_bias <= 2.0) and (m_interp_rmse <= 6.0) and (m_interp_soc <= 2.5)

        m_const_rmse = float(np.mean(const_rmses))
        m_const_bias = float(np.mean(const_biases))
        m_const_soc = float(np.mean(const_socs))
        const_pass = (m_const_bias <= 2.0) and (m_const_rmse <= 6.0) and (m_const_soc <= 2.5)

        rel_comparison = "interp_beats_const" if m_interp_rmse < m_const_rmse else "const_beats_interp"

        alt_soc_comparison.append({
            "fold_id": fold_name,
            "interpolation": {
                "mean_rmse_mv": round(m_interp_rmse, 3),
                "mean_bias_mv": round(m_interp_bias, 3),
                "mean_implied_soc_error_pp": round(m_interp_soc, 3),
                "bias_gate_pass": m_interp_bias <= 2.0,
                "rmse_gate_pass": m_interp_rmse <= 6.0,
                "soc_gate_pass": m_interp_soc <= 2.5,
                "verdict": "PASS" if interp_pass else "FAIL",
            },
            "constant_baseline_posthoc": {
                "label": "post-hoc extension, not in the committed spec if the spec did not require it",
                "mean_rmse_mv": round(m_const_rmse, 3),
                "mean_bias_mv": round(m_const_bias, 3),
                "mean_implied_soc_error_pp": round(m_const_soc, 3),
                "bias_gate_pass": m_const_bias <= 2.0,
                "rmse_gate_pass": m_const_rmse <= 6.0,
                "soc_gate_pass": m_const_soc <= 2.5,
                "verdict": "PASS" if const_pass else "FAIL",
            },
            "rmse_difference_mv": round(m_interp_rmse - m_const_rmse, 3),
            "relative_performance": rel_comparison,
        })

    results = {
        "metadata": {
            "title": "Per-fold Constant Parameter Baseline Evaluation for TEMPEST 280 Ah",
            "spec_status": "post-hoc extension, not in the committed spec if the spec did not require it",
            "gates": {
                "bias_mv_max": 2.0,
                "rmse_mv_max": 6.0,
                "implied_soc_error_pp_max": 2.5,
            },
        },
        "loto_comparison": loto_comparison,
        "alt_soc_comparison": alt_soc_comparison,
    }

    out_path = REPO_ROOT / "reports" / "validation" / "tempest_loto_baseline.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    print("=== TEMPEST LOTO & ALT-SOC BASELINE COMPARISON ===")
    print("\n--- 1. Leave-One-Temperature-Out (LOTO) ---")
    for row in loto_comparison:
        t = row["held_out_temperature_c"]
        i_r = row["interpolation"]["mean_rmse_mv"]
        i_b = row["interpolation"]["mean_bias_mv"]
        i_s = row["interpolation"]["mean_implied_soc_error_pp"]
        i_v = row["interpolation"]["verdict"]
        c_r = row["constant_baseline_posthoc"]["mean_rmse_mv"]
        c_b = row["constant_baseline_posthoc"]["mean_bias_mv"]
        c_s = row["constant_baseline_posthoc"]["mean_implied_soc_error_pp"]
        c_v = row["constant_baseline_posthoc"]["verdict"]
        rel = row["relative_performance"]
        print(f"T={t:2d} °C | Interp: {i_r:5.2f} mV (Bias {i_b:5.2f}, SOC {i_s:5.2f} pp, {i_v}) | Const: {c_r:5.2f} mV (Bias {c_b:5.2f}, SOC {c_s:5.2f} pp, {c_v}) | {rel}")

    print("\n--- 2. Alternate-SOC Holdout Folds ---")
    for row in alt_soc_comparison:
        fid = row["fold_id"]
        i_r = row["interpolation"]["mean_rmse_mv"]
        i_b = row["interpolation"]["mean_bias_mv"]
        i_s = row["interpolation"]["mean_implied_soc_error_pp"]
        i_v = row["interpolation"]["verdict"]
        c_r = row["constant_baseline_posthoc"]["mean_rmse_mv"]
        c_b = row["constant_baseline_posthoc"]["mean_bias_mv"]
        c_s = row["constant_baseline_posthoc"]["mean_implied_soc_error_pp"]
        c_v = row["constant_baseline_posthoc"]["verdict"]
        rel = row["relative_performance"]
        print(f"Fold {fid:12s} | Interp: {i_r:5.2f} mV (Bias {i_b:5.2f}, SOC {i_s:5.2f} pp, {i_v}) | Const: {c_r:5.2f} mV (Bias {c_b:5.2f}, SOC {c_s:5.2f} pp, {c_v}) | {rel}")

    print(f"\nSaved baseline comparison to: {out_path}")
    return results


if __name__ == "__main__":
    evaluate_loto_and_altsoc_baselines()
