"""Evaluation and Benchmark Script for E8 Physics-Guided Residual GRU.

Compares:
- E0 (Coulomb Counting Baseline)
- E1 (Standard 2RC EKF)
- E7v3 (Composite Adaptive EKF baseline from Gauntlet V3)
- E8 (Physics-Guided Residual GRU)

Evaluates on:
1. S-A (Full Profile matched start) across DST, US06, and FUDS at 20, 30, 40, 50 C.
2. S-B (Mid-plateau initial SOC error of +-5, +-10 pp) on cross-profile US06.
"""

from dataclasses import replace
import json
import math
from pathlib import Path
import sys
from typing import Dict, List, Tuple
import numpy as np

repo_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo_root))

from soc.assumptions.loader import load_assumptions
from soc.estimators.base import ParamSet, SocEstimate
from soc.estimators.e0_coulomb import E0CoulombCounting
from soc.estimators.e1_ekf import E1ExtendedKalmanFilter
from soc.estimators.e7v3 import E7V3CompositeFilter
from soc.estimators.e8_residual_gru import E8ResidualGRUEstimator
from soc.models.plant import Measurement
from scripts.gauntlet_scenarios import prepare_scenario_data, ScenarioDataSet


def run_single_simulation(
    estimator,
    data: ScenarioDataSet,
    start_soc: float,
    soc_std: float = 0.01,
) -> Tuple[np.ndarray, float, float, float]:
    """Run an estimator through a scenario and calculate error metrics.

    Returns:
        est_soc: array of estimated SOC
        rmse_pp: Root-Mean-Square Error in percentage points
        mae_pp: Mean Absolute Error in percentage points
        max_err_pp: Maximum Absolute Error in percentage points
    """
    if hasattr(estimator, "reset"):
        try:
            estimator.reset(start_soc, soc_std=soc_std)
        except TypeError:
            estimator.reset(start_soc)

    n = len(data.truth_soc)
    est_soc = np.zeros(n, dtype=float)

    for i in range(n):
        meas = Measurement(
            v=float(data.voltage_v[i]),
            i=float(data.current_a[i]),
            temp_c=float(data.temp_measured_c[i]),
            dt=float(data.dt_arr[i]),
            dropout=False,
        )
        out = estimator.step(meas)
        est_soc[i] = out.soc

    err_pp = (est_soc - data.truth_soc) * 100.0
    rmse_pp = float(np.sqrt(np.mean(err_pp ** 2)))
    mae_pp = float(np.mean(np.abs(err_pp)))
    max_err_pp = float(np.max(np.abs(err_pp)))

    return est_soc, rmse_pp, mae_pp, max_err_pp


def run_benchmark():
    assumptions, _, _ = load_assumptions(profile="calce_a123_v4")
    params = ParamSet.from_assumptions(assumptions, matched=True)

    estimators = {
        "E0": lambda: E0CoulombCounting(params),
        "E1": lambda: E1ExtendedKalmanFilter(params),
        "E7v3": lambda: E7V3CompositeFilter(params),
        "E8": lambda: E8ResidualGRUEstimator(params),
    }

    results = {"s_a": {}, "s_b_us06": {}}

    print("\n" + "=" * 80)
    print("BENCHMARK 1: S-A (Full Matched Profile) across Temperatures and Cycles")
    print("=" * 80)
    print(f"{'Profile':<8} {'Temp':<6} {'E0 RMSE':<10} {'E1 RMSE':<10} {'E7v3 RMSE':<12} {'E8 RMSE':<10} {'E8 Gain vs E7v3':<16}")
    print("-" * 80)

    for prof in ["DST", "US06", "FUDS"]:
        for t in [20, 30, 40, 50]:
            data = prepare_scenario_data(t, profile=prof)
            key = f"{prof}_{t}C"
            results["s_a"][key] = {}

            row = {}
            for name, factory in estimators.items():
                est = factory()
                _, rmse, mae, max_err = run_single_simulation(
                    est, data, data.start_soc, soc_std=0.005
                )
                row[name] = rmse
                results["s_a"][key][name] = {
                    "rmse_pp": rmse,
                    "mae_pp": mae,
                    "max_err_pp": max_err,
                }

            gain_str = f"{(row['E7v3'] - row['E8']) / row['E7v3'] * 100:+.1f}%"
            print(f"{prof:<8} {t:>2} C   {row['E0']:<10.3f} {row['E1']:<10.3f} {row['E7v3']:<12.3f} {row['E8']:<10.3f} {gain_str:<16}")

    print("\n" + "=" * 80)
    print("BENCHMARK 2: S-B Mid-Plateau Initial SOC Errors on Cross-Profile US06 (25 C)")
    print("=" * 80)
    print(f"{'True SOC':<10} {'Offset':<8} {'Start SOC':<10} {'E0 RMSE':<10} {'E1 RMSE':<10} {'E7v3 RMSE':<12} {'E8 RMSE':<10} {'E8 Gain':<10}")
    print("-" * 80)

    data_us06 = prepare_scenario_data(25, profile="US06")
    for z_target in [0.80, 0.60, 0.40, 0.20]:
        cross = np.where(data_us06.truth_soc <= z_target)[0]
        if len(cross) == 0:
            continue
        idx_start = cross[0]
        sub_data = ScenarioDataSet(
            temp_c=data_us06.temp_c,
            cell_id=data_us06.cell_id,
            profile=data_us06.profile,
            time_s=data_us06.time_s[idx_start:] - data_us06.time_s[idx_start],
            dt_arr=data_us06.dt_arr[idx_start:],
            current_a=data_us06.current_a[idx_start:],
            voltage_v=data_us06.voltage_v[idx_start:],
            temp_measured_c=data_us06.temp_measured_c[idx_start:],
            truth_soc=data_us06.truth_soc[idx_start:],
            cap_c20=data_us06.cap_c20,
            start_soc=data_us06.truth_soc[idx_start],
            i1_truth=data_us06.i1_truth[idx_start:],
            i2_truth=data_us06.i2_truth[idx_start:],
            h_truth=data_us06.h_truth[idx_start:],
            v_model_truth=data_us06.v_model_truth[idx_start:],
            ocv_mono=data_us06.ocv_mono,
        )

        for offset in [-0.10, -0.05, 0.05, 0.10]:
            s0 = min(max(data_us06.truth_soc[idx_start] + offset, 0.05), 0.98)
            sb_key = f"z{int(z_target*100)}_off{int(offset*100):+d}"
            results["s_b_us06"][sb_key] = {}

            row_sb = {}
            for name, factory in estimators.items():
                est = factory()
                _, rmse, mae, max_err = run_single_simulation(
                    est, sub_data, s0, soc_std=0.08
                )
                row_sb[name] = rmse
                results["s_b_us06"][sb_key][name] = {
                    "rmse_pp": rmse,
                    "mae_pp": mae,
                    "max_err_pp": max_err,
                }

            gain_sb = f"{(row_sb['E7v3'] - row_sb['E8']) / row_sb['E7v3'] * 100:+.1f}%"
            print(f"{z_target*100:>4.0f}%     {offset*100:>+3.0f} pp   {s0:<10.4f} {row_sb['E0']:<10.3f} {row_sb['E1']:<10.3f} {row_sb['E7v3']:<12.3f} {row_sb['E8']:<10.3f} {gain_sb:<10}")

    out_json = repo_root / "reports" / "e8_benchmark_results.json"
    with open(out_json, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nSaved full benchmark results to {out_json}")


if __name__ == "__main__":
    run_benchmark()
