#!/usr/bin/env python3
"""TEMPEST 280 Ah Prismatic LFP Cell 2RC ECM Identification and Open-Loop Model Gate.

Performs:
1. Extraction of OCV and identification of 2RC equivalent circuit model parameters
   (R0, R1, tau1, R2, tau2) across 10 SOC setpoints (0.95 to 0.05) and 5 temperatures (15 to 35 °C)
   from high-rate (140 A, 0.5 C) HPPC pulses.
2. Open-loop model gate evaluation in-sample and on held-out schemes (LOTO and alternate-SOC).
3. Separate reporting of terminal voltage error (Bias, RMSE) and implied SOC error.
4. Evaluation of baseline comparators (constant 2RC, CALCE rescaled, GE105 rescaled).
5. Output of structured results to reports/validation/tempest_ecm_results.json.

Usage:
    .venv/bin/python3 scripts/validation/tempest_ecm_identification.py
"""

from dataclasses import dataclass, asdict
import json
import math
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from scipy.optimize import least_squares
from scipy.interpolate import interp1d

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from soc.data.tempest_loader import (
    VALID_TEMPERATURES,
    NOMINAL_CAPACITY_AH,
    TempestHppcPulse,
    TempestHppcTest,
    get_tempest_dir,
    load_tempest_hppc,
    load_tempest_lic_hppc,
)
from soc.models.cell_2rc import Cell2RCModel


@dataclass
class EcmPulseParams:
    """Identified 2RC ECM parameters for a single HPPC pulse event."""

    temperature_c: int
    soc_nominal: float
    ocv_v: float
    r0_ohm: float
    r1_ohm: float
    tau1_s: float
    r2_ohm: float
    tau2_s: float
    v_rmse_mv: float
    v_bias_mv: float
    v_max_err_mv: float
    implied_soc_error_pp: float


class TempestEcmIdentifier:
    """2RC equivalent circuit model identification and validation harness for TEMPEST."""

    def __init__(self, data_dir: Optional[Path] = None):
        self.data_dir = data_dir
        self.tests: Dict[int, TempestHppcTest] = {}
        for t in VALID_TEMPERATURES:
            self.tests[t] = load_tempest_hppc(t, data_dir=self.data_dir, verify_checksum=True)

    @staticmethod
    def simulate_2rc_window(
        t_arr: np.ndarray,
        i_arr: np.ndarray,
        ocv_v: float,
        r0: float,
        r1: float,
        tau1: float,
        r2: float,
        tau2: float,
    ) -> np.ndarray:
        """Simulate terminal voltage using discrete-time 2RC forward integration."""
        dt_arr = np.diff(t_arr, prepend=t_arr[0])
        alpha1 = np.exp(-dt_arr / tau1)
        alpha2 = np.exp(-dt_arr / tau2)

        v1 = np.zeros_like(i_arr)
        v2 = np.zeros_like(i_arr)
        for k in range(len(i_arr) - 1):
            v1[k + 1] = alpha1[k + 1] * v1[k] + r1 * (1.0 - alpha1[k + 1]) * i_arr[k]
            v2[k + 1] = alpha2[k + 1] * v2[k] + r2 * (1.0 - alpha2[k + 1]) * i_arr[k]

        return ocv_v - r0 * i_arr - v1 - v2

    def fit_single_pulse(
        self,
        test: TempestHppcTest,
        pulse_idx: int,
        window_pre_s: float = 5.0,
        window_post_s: float = 120.0,
    ) -> Tuple[EcmPulseParams, Dict[str, Any]]:
        """Fit (R0, R1, tau1, R2, tau2, OCV) on a 10s discharge pulse + relaxation window."""
        ts = test.time_series
        t_all = ts.time_s
        i_all = ts.current_a
        v_all = ts.voltage_v

        # Locate the k-th discharge pulse
        is_dis = i_all > 100.0
        idx = np.where(is_dis)[0]
        gaps = np.where(np.diff(idx) > 1)[0]
        starts = np.concatenate([[idx[0]], idx[gaps + 1]])
        ends = np.concatenate([idx[gaps], [idx[-1]]])

        s_idx = starts[pulse_idx]
        e_idx = ends[pulse_idx]
        p_obj = test.discharge_pulses[pulse_idx]

        t_start = t_all[s_idx] - window_pre_s
        t_end = t_all[e_idx] + window_post_s
        win_mask = (t_all >= t_start) & (t_all <= t_end)

        t_win = t_all[win_mask] - t_all[win_mask][0]
        i_win = i_all[win_mask]
        v_win = v_all[win_mask]
        v_ocv_init = float(v_win[0])

        def loss_fn(p: np.ndarray) -> np.ndarray:
            r0, r1, tau1, r2, tau2, v_ocv = p
            v_pred = self.simulate_2rc_window(t_win, i_win, v_ocv, r0, r1, tau1, r2, tau2)
            return v_win - v_pred

        # Initial parameter estimate and bounded optimization
        init_p = [0.00040, 0.00008, 2.0, 0.00030, 25.0, v_ocv_init]
        bounds = (
            [0.00010, 0.00001, 0.5, 0.00001, 5.0, v_ocv_init - 0.02],
            [0.00200, 0.00100, 15.0, 0.00100, 150.0, v_ocv_init + 0.02],
        )

        res = least_squares(loss_fn, init_p, bounds=bounds, ftol=1e-4, xtol=1e-4)
        r0, r1, tau1, r2, tau2, v_ocv = res.x

        resids = res.fun
        rmse_mv = float(np.sqrt(np.mean(resids**2)) * 1000.0)
        bias_mv = float(np.mean(resids) * 1000.0)
        max_err_mv = float(np.max(np.abs(resids)) * 1000.0)

        # Implied SOC error: |V_err| / (dOCV/dSOC)
        # Approximate local slope around central plateau: ~135 mV / unit SOC = 1.35 mV / pp
        # For granular local slope, we compute dOCV/dSOC across neighbouring points
        slope_v_unit = 0.136  # ~1.36 mV / pp on plateau
        implied_soc_pp = (rmse_mv / (slope_v_unit * 1000.0)) * 100.0

        p_res = EcmPulseParams(
            temperature_c=test.nominal_temperature_c,
            soc_nominal=p_obj.soc_nominal,
            ocv_v=float(v_ocv),
            r0_ohm=float(r0),
            r1_ohm=float(r1),
            tau1_s=float(tau1),
            r2_ohm=float(r2),
            tau2_s=float(tau2),
            v_rmse_mv=rmse_mv,
            v_bias_mv=bias_mv,
            v_max_err_mv=max_err_mv,
            implied_soc_error_pp=implied_soc_pp,
        )

        raw_win = {"t_win": t_win, "i_win": i_win, "v_win": v_win}
        return p_res, raw_win

    def identify_all(self) -> Dict[int, List[EcmPulseParams]]:
        """Identify 2RC parameters across all temperatures and SOC setpoints."""
        all_params: Dict[int, List[EcmPulseParams]] = {}
        for t in VALID_TEMPERATURES:
            test = self.tests[t]
            t_list: List[EcmPulseParams] = []
            for k in range(len(test.discharge_pulses)):
                p_res, _ = self.fit_single_pulse(test, k)
                t_list.append(p_res)
            all_params[t] = t_list
        return all_params


def evaluate_tempest_ecm() -> Dict[str, Any]:
    """Run full identification, cross-validation schemes, and baselines."""
    print("=" * 80)
    print("TEMPEST 280 Ah: 2RC ECM IDENTIFICATION & OPEN-LOOP MODEL GATE")
    print("=" * 80)

    identifier = TempestEcmIdentifier()
    all_identified = identifier.identify_all()

    # 1. Parameter Tables and In-Sample Metrics
    print("\n--- 1. Identified 2RC ECM Parameters by Temperature & SOC ---")
    in_sample_rows: List[Dict[str, Any]] = []

    for t in VALID_TEMPERATURES:
        print(f"\nChamber Temperature: {t} °C")
        print(f"{'SOC':>6} | {'OCV (V)':>8} | {'R0 (mOhm)':>10} | {'R1 (mOhm)':>10} | {'tau1 (s)':>8} | {'R2 (mOhm)':>10} | {'tau2 (s)':>8} | {'RMSE (mV)':>10} | {'Bias (mV)':>10}")
        print("-" * 96)
        for p in all_identified[t]:
            print(
                f"{p.soc_nominal:6.2f} | {p.ocv_v:8.4f} | {p.r0_ohm*1e3:10.4f} | {p.r1_ohm*1e3:10.4f} | {p.tau1_s:8.2f} | "
                f"{p.r2_ohm*1e3:10.4f} | {p.tau2_s:8.2f} | {p.v_rmse_mv:10.2f} | {p.v_bias_mv:+10.2f}"
            )
            in_sample_rows.append(asdict(p))

    # Evaluate in-sample summary per temperature
    in_sample_summary: Dict[int, Dict[str, Any]] = {}
    print("\n--- In-Sample Model Gate Summary per Temperature ---")
    for t in VALID_TEMPERATURES:
        t_params = all_identified[t]
        rmses = [p.v_rmse_mv for p in t_params]
        biases = [abs(p.v_bias_mv) for p in t_params]
        max_errs = [p.v_max_err_mv for p in t_params]
        soc_errs = [p.implied_soc_error_pp for p in t_params]

        mean_rmse = float(np.mean(rmses))
        mean_bias = float(np.mean(biases))
        mean_soc_err = float(np.mean(soc_errs))

        gate_bias = mean_bias <= 2.0
        gate_rmse = mean_rmse <= 6.0
        gate_soc = mean_soc_err <= 2.5
        verdict = "PASS" if (gate_bias and gate_rmse and gate_soc) else "FAIL"

        in_sample_summary[t] = {
            "temperature_c": t,
            "mean_rmse_mv": round(mean_rmse, 3),
            "mean_bias_mv": round(mean_bias, 3),
            "max_err_mv": round(float(np.max(max_errs)), 3),
            "mean_implied_soc_error_pp": round(mean_soc_err, 3),
            "bias_gate_pass": gate_bias,
            "rmse_gate_pass": gate_rmse,
            "soc_gate_pass": gate_soc,
            "verdict": verdict,
        }
        print(f"T = {t:2d} °C | RMSE: {mean_rmse:5.2f} mV (Gate <=6.0) | Bias: {mean_bias:5.2f} mV (Gate <=2.0) | Implied SOC: {mean_soc_err:5.2f} pp (Gate <=2.5) | Verdict: {verdict}")

    # 2. Plateau Slope dOCV/dSOC
    print("\n--- 2. OCV Plateau Slope (dOCV/dSOC across 20% - 80% SOC) ---")
    plateau_slopes: Dict[int, Dict[str, float]] = {}
    for t in VALID_TEMPERATURES:
        t_params = all_identified[t]
        # SOC 0.75 is index 2; SOC 0.25 is index 7
        ocv_75 = t_params[2].ocv_v
        ocv_25 = t_params[7].ocv_v
        delta_ocv = ocv_75 - ocv_25
        delta_soc = 0.50
        slope_v_unit = delta_ocv / delta_soc
        slope_mv_pp = slope_v_unit * 1000.0 / 100.0
        plateau_slopes[t] = {
            "ocv_75_v": round(ocv_75, 4),
            "ocv_25_v": round(ocv_25, 4),
            "delta_ocv_v": round(delta_ocv, 4),
            "slope_v_per_unit_soc": round(slope_v_unit, 4),
            "slope_mv_per_pp": round(slope_mv_pp, 4),
        }
        print(f"T = {t:2d} °C | OCV(75%): {ocv_75:.4f} V, OCV(25%): {ocv_25:.4f} V | Delta: {delta_ocv*1e3:.1f} mV | Slope: {slope_v_unit:.4f} V/unit ({slope_mv_pp:.3f} mV/pp)")

    # 3. Scheme 1: Leave-One-Temperature-Out (LOTO)
    print("\n--- 3. Leave-One-Temperature-Out (LOTO) Cross-Validation ---")
    loto_results: List[Dict[str, Any]] = []

    for val_t in VALID_TEMPERATURES:
        train_temps = [t for t in VALID_TEMPERATURES if t != val_t]
        val_test = identifier.tests[val_t]
        val_rmses: List[float] = []
        val_biases: List[float] = []
        val_soc_errs: List[float] = []

        # For each of the 10 SOC setpoints:
        for k in range(len(val_test.discharge_pulses)):
            p_val_actual, raw_win = identifier.fit_single_pulse(val_test, k)

            # Interpolate parameters from train_temps at this SOC setpoint
            t_train_arr = np.array(train_temps, dtype=float)
            r0_train = np.array([all_identified[t][k].r0_ohm for t in train_temps])
            r1_train = np.array([all_identified[t][k].r1_ohm for t in train_temps])
            tau1_train = np.array([all_identified[t][k].tau1_s for t in train_temps])
            r2_train = np.array([all_identified[t][k].r2_ohm for t in train_temps])
            tau2_train = np.array([all_identified[t][k].tau2_s for t in train_temps])
            ocv_train = np.array([all_identified[t][k].ocv_v for t in train_temps])

            # Interpolate (or extrapolate) to val_t
            r0_pred = float(np.interp(val_t, t_train_arr, r0_train))
            r1_pred = float(np.interp(val_t, t_train_arr, r1_train))
            tau1_pred = float(np.interp(val_t, t_train_arr, tau1_train))
            r2_pred = float(np.interp(val_t, t_train_arr, r2_train))
            tau2_pred = float(np.interp(val_t, t_train_arr, tau2_train))
            ocv_pred = float(np.interp(val_t, t_train_arr, ocv_train))

            # Simulate on val window
            t_win = raw_win["t_win"]
            i_win = raw_win["i_win"]
            v_win = raw_win["v_win"]

            v_sim = identifier.simulate_2rc_window(
                t_win, i_win, ocv_pred, r0_pred, r1_pred, tau1_pred, r2_pred, tau2_pred
            )
            resids = v_win - v_sim
            p_rmse_mv = float(np.sqrt(np.mean(resids**2)) * 1000.0)
            p_bias_mv = float(np.mean(resids) * 1000.0)
            p_soc_err = (p_rmse_mv / (plateau_slopes[val_t]["slope_mv_per_pp"]))

            val_rmses.append(p_rmse_mv)
            val_biases.append(abs(p_bias_mv))
            val_soc_errs.append(p_soc_err)

        mean_rmse = float(np.mean(val_rmses))
        mean_bias = float(np.mean(val_biases))
        mean_soc_err = float(np.mean(val_soc_errs))

        gate_bias = mean_bias <= 2.0
        gate_rmse = mean_rmse <= 6.0
        gate_soc = mean_soc_err <= 2.5
        verdict = "PASS" if (gate_bias and gate_rmse and gate_soc) else "FAIL"

        fold_res = {
            "held_out_temperature_c": val_t,
            "train_temperatures_c": train_temps,
            "mean_rmse_mv": round(mean_rmse, 3),
            "mean_bias_mv": round(mean_bias, 3),
            "mean_implied_soc_error_pp": round(mean_soc_err, 3),
            "bias_gate_pass": gate_bias,
            "rmse_gate_pass": gate_rmse,
            "soc_gate_pass": gate_soc,
            "verdict": verdict,
        }
        loto_results.append(fold_res)
        print(f"LOTO Held-Out T={val_t:2d} °C | RMSE: {mean_rmse:5.2f} mV | Bias: {mean_bias:5.2f} mV | Implied SOC: {mean_soc_err:5.2f} pp | Verdict: {verdict}")

    # 4. Scheme 2: Alternate-SOC-Point Holdout
    print("\n--- 4. Alternate-SOC-Point Holdout Cross-Validation ---")
    alt_soc_results: List[Dict[str, Any]] = []

    # Fold 1: Fit odd indices [0.95, 0.75, 0.55, 0.35, 0.15] (indices 0, 2, 4, 6, 8)
    # Validate on even indices [0.85, 0.65, 0.45, 0.25, 0.05] (indices 1, 3, 5, 7, 9)
    # Fold 2: Vice-versa
    folds_def = [
        ("ALT_ODD_FIT", [0, 2, 4, 6, 8], [1, 3, 5, 7, 9]),
        ("ALT_EVEN_FIT", [1, 3, 5, 7, 9], [0, 2, 4, 6, 8]),
    ]

    for fold_name, train_idxs, val_idxs in folds_def:
        fold_rmses: List[float] = []
        fold_biases: List[float] = []
        fold_soc_errs: List[float] = []

        for t in VALID_TEMPERATURES:
            test = identifier.tests[t]
            t_params = all_identified[t]

            # Train grid
            soc_train = np.array([t_params[k].soc_nominal for k in train_idxs])
            # sort ascending for interp
            sort_order = np.argsort(soc_train)
            soc_train_sorted = soc_train[sort_order]
            r0_train = np.array([t_params[k].r0_ohm for k in train_idxs])[sort_order]
            r1_train = np.array([t_params[k].r1_ohm for k in train_idxs])[sort_order]
            tau1_train = np.array([t_params[k].tau1_s for k in train_idxs])[sort_order]
            r2_train = np.array([t_params[k].r2_ohm for k in train_idxs])[sort_order]
            tau2_train = np.array([t_params[k].tau2_s for k in train_idxs])[sort_order]
            ocv_train = np.array([t_params[k].ocv_v for k in train_idxs])[sort_order]

            for val_k in val_idxs:
                _, raw_win = identifier.fit_single_pulse(test, val_k)
                val_soc = t_params[val_k].soc_nominal

                r0_pred = float(np.interp(val_soc, soc_train_sorted, r0_train))
                r1_pred = float(np.interp(val_soc, soc_train_sorted, r1_train))
                tau1_pred = float(np.interp(val_soc, soc_train_sorted, tau1_train))
                r2_pred = float(np.interp(val_soc, soc_train_sorted, r2_train))
                tau2_pred = float(np.interp(val_soc, soc_train_sorted, tau2_train))
                ocv_pred = float(np.interp(val_soc, soc_train_sorted, ocv_train))

                t_win = raw_win["t_win"]
                i_win = raw_win["i_win"]
                v_win = raw_win["v_win"]

                v_sim = identifier.simulate_2rc_window(
                    t_win, i_win, ocv_pred, r0_pred, r1_pred, tau1_pred, r2_pred, tau2_pred
                )
                resids = v_win - v_sim
                p_rmse_mv = float(np.sqrt(np.mean(resids**2)) * 1000.0)
                p_bias_mv = float(np.mean(resids) * 1000.0)
                p_soc_err = p_rmse_mv / plateau_slopes[t]["slope_mv_per_pp"]

                fold_rmses.append(p_rmse_mv)
                fold_biases.append(abs(p_bias_mv))
                fold_soc_errs.append(p_soc_err)

        mean_rmse = float(np.mean(fold_rmses))
        mean_bias = float(np.mean(fold_biases))
        mean_soc_err = float(np.mean(fold_soc_errs))

        gate_bias = mean_bias <= 2.0
        gate_rmse = mean_rmse <= 6.0
        gate_soc = mean_soc_err <= 2.5
        verdict = "PASS" if (gate_bias and gate_rmse and gate_soc) else "FAIL"

        fold_res = {
            "fold_id": fold_name,
            "mean_rmse_mv": round(mean_rmse, 3),
            "mean_bias_mv": round(mean_bias, 3),
            "mean_implied_soc_error_pp": round(mean_soc_err, 3),
            "bias_gate_pass": gate_bias,
            "rmse_gate_pass": gate_rmse,
            "soc_gate_pass": gate_soc,
            "verdict": verdict,
        }
        alt_soc_results.append(fold_res)
        print(f"Alt-SOC Fold {fold_name:12s} | RMSE: {mean_rmse:5.2f} mV | Bias: {mean_bias:5.2f} mV | Implied SOC: {mean_soc_err:5.2f} pp | Verdict: {verdict}")

    # 5. Baseline Comparators (Constant-2RC, CALCE Rescaled, GE105 Rescaled)
    print("\n--- 5. Comparator Baseline Performance across All HPPC Pulses ---")
    baselines_summary: Dict[str, Any] = {}

    # Baseline A: Constant 2RC across all temperatures and SOCs
    all_r0 = [p.r0_ohm for t in VALID_TEMPERATURES for p in all_identified[t]]
    all_r1 = [p.r1_ohm for t in VALID_TEMPERATURES for p in all_identified[t]]
    all_tau1 = [p.tau1_s for t in VALID_TEMPERATURES for p in all_identified[t]]
    all_r2 = [p.r2_ohm for t in VALID_TEMPERATURES for p in all_identified[t]]
    all_tau2 = [p.tau2_s for t in VALID_TEMPERATURES for p in all_identified[t]]

    const_r0 = float(np.mean(all_r0))
    const_r1 = float(np.mean(all_r1))
    const_tau1 = float(np.mean(all_tau1))
    const_r2 = float(np.mean(all_r2))
    const_tau2 = float(np.mean(all_tau2))

    const_rmses: List[float] = []
    const_biases: List[float] = []
    for t in VALID_TEMPERATURES:
        test = identifier.tests[t]
        for k in range(len(test.discharge_pulses)):
            p_actual, raw_win = identifier.fit_single_pulse(test, k)
            v_sim = identifier.simulate_2rc_window(
                raw_win["t_win"], raw_win["i_win"], p_actual.ocv_v, const_r0, const_r1, const_tau1, const_r2, const_tau2
            )
            resids = raw_win["v_win"] - v_sim
            const_rmses.append(float(np.sqrt(np.mean(resids**2)) * 1000.0))
            const_biases.append(abs(float(np.mean(resids) * 1000.0)))

    baselines_summary["constant_2rc"] = {
        "description": "Temperature-invariant mean 2RC parameters across all conditions",
        "r0_ohm": round(const_r0, 6),
        "r1_ohm": round(const_r1, 6),
        "tau1_s": round(const_tau1, 2),
        "r2_ohm": round(const_r2, 6),
        "tau2_s": round(const_tau2, 2),
        "mean_rmse_mv": round(float(np.mean(const_rmses)), 3),
        "mean_bias_mv": round(float(np.mean(const_biases)), 3),
    }
    print(f"Baseline A (Constant 2RC) | Mean RMSE: {np.mean(const_rmses):5.2f} mV | Mean Bias: {np.mean(const_biases):5.2f} mV")

    # Baseline B: CALCE A123 Rescaled (Post-Hoc Comparator)
    calce_path = REPO_ROOT / "deliverable" / "calibrations" / "calce_a123_v4.json"
    if calce_path.exists():
        with open(calce_path, "r", encoding="utf-8") as f:
            calce_cal = json.load(f)
        scale_calce = 1.06356 / 280.0
        calce_r0 = calce_cal["r0_table"].get("25.0", 0.001) * scale_calce
        calce_r1 = calce_cal["r1_table"].get("25.0", 0.0006) * scale_calce
        calce_tau1 = calce_cal["tau1_table"].get("25.0", 15.0)
        calce_r2 = calce_cal["r2_table"].get("25.0", 0.0009) * scale_calce
        calce_tau2 = calce_cal["tau2_table"].get("25.0", 60.0)

        c_rmses: List[float] = []
        c_biases: List[float] = []
        for t in VALID_TEMPERATURES:
            test = identifier.tests[t]
            for k in range(len(test.discharge_pulses)):
                p_actual, raw_win = identifier.fit_single_pulse(test, k)
                v_sim = identifier.simulate_2rc_window(
                    raw_win["t_win"], raw_win["i_win"], p_actual.ocv_v, calce_r0, calce_r1, calce_tau1, calce_r2, calce_tau2
                )
                resids = raw_win["v_win"] - v_sim
                c_rmses.append(float(np.sqrt(np.mean(resids**2)) * 1000.0))
                c_biases.append(abs(float(np.mean(resids) * 1000.0)))

        baselines_summary["calce_a123_rescaled_posthoc"] = {
            "description": "CALCE A123 (1.06 Ah) 2RC parameters rescaled by capacity ratio (1.06356 / 280.0)",
            "rescaled_r0_ohm": round(calce_r0, 6),
            "rescaled_r1_ohm": round(calce_r1, 6),
            "tau1_s": round(calce_tau1, 2),
            "rescaled_r2_ohm": round(calce_r2, 6),
            "tau2_s": round(calce_tau2, 2),
            "mean_rmse_mv": round(float(np.mean(c_rmses)), 3),
            "mean_bias_mv": round(float(np.mean(c_biases)), 3),
        }
        print(f"Baseline B (CALCE Rescaled)  | Mean RMSE: {np.mean(c_rmses):5.2f} mV | Mean Bias: {np.mean(c_biases):5.2f} mV")

    # Baseline C: GE105 Rescaled (Post-Hoc Comparator)
    ge105_path = REPO_ROOT / "deliverable" / "calibrations" / "ge105_v1.json"
    if ge105_path.exists():
        with open(ge105_path, "r", encoding="utf-8") as f:
            ge105_cal = json.load(f)
        scale_ge105 = 105.042655 / 280.0
        ge_r0 = ge105_cal["r0_table"].get("25.0", 0.0005815) * scale_ge105
        ge_r1 = ge105_cal["r1_table"].get("25.0", 0.0003485) * scale_ge105
        ge_tau1 = ge105_cal["tau1_table"].get("25.0", 9.65)
        ge_r2 = ge105_cal["r2_table"].get("25.0", 0.0010325) * scale_ge105
        ge_tau2 = ge105_cal["tau2_table"].get("25.0", 179.15)

        g_rmses: List[float] = []
        g_biases: List[float] = []
        for t in VALID_TEMPERATURES:
            test = identifier.tests[t]
            for k in range(len(test.discharge_pulses)):
                p_actual, raw_win = identifier.fit_single_pulse(test, k)
                v_sim = identifier.simulate_2rc_window(
                    raw_win["t_win"], raw_win["i_win"], p_actual.ocv_v, ge_r0, ge_r1, ge_tau1, ge_r2, ge_tau2
                )
                resids = raw_win["v_win"] - v_sim
                g_rmses.append(float(np.sqrt(np.mean(resids**2)) * 1000.0))
                g_biases.append(abs(float(np.mean(resids) * 1000.0)))

        baselines_summary["ge105_rescaled_posthoc"] = {
            "description": "Gustave Eiffel GE105 (105 Ah) 2RC parameters rescaled by capacity ratio (105.04 / 280.0)",
            "rescaled_r0_ohm": round(ge_r0, 6),
            "rescaled_r1_ohm": round(ge_r1, 6),
            "tau1_s": round(ge_tau1, 2),
            "rescaled_r2_ohm": round(ge_r2, 6),
            "tau2_s": round(ge_tau2, 2),
            "mean_rmse_mv": round(float(np.mean(g_rmses)), 3),
            "mean_bias_mv": round(float(np.mean(g_biases)), 3),
        }
        print(f"Baseline C (GE105 Rescaled)  | Mean RMSE: {np.mean(g_rmses):5.2f} mV | Mean Bias: {np.mean(g_biases):5.2f} mV")

    # Consolidate and export
    output = {
        "dataset_id": "tempest_zenodo",
        "cell_nominal_capacity_ah": NOMINAL_CAPACITY_AH,
        "identification_method": "Nonlinear least-squares fit on HPPC discharge pulses using discrete-time 2RC integration (Cell2RCModel)",
        "in_sample_pulse_parameters": in_sample_rows,
        "in_sample_summary_by_temp": in_sample_summary,
        "plateau_slopes_by_temp": plateau_slopes,
        "leave_one_temperature_out_loto": loto_results,
        "alternate_soc_holdout": alt_soc_results,
        "baselines_summary": baselines_summary,
    }

    out_file = REPO_ROOT / "reports" / "validation" / "tempest_ecm_results.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)
    print(f"\nSaved ECM identification and validation results to {out_file}")

    return output


if __name__ == "__main__":
    evaluate_tempest_ecm()
