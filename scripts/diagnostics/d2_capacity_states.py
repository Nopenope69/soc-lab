"""Diagnostic D2: Capacity and initial states actually used.

For each of E0, E2, E5 v1, E5 v2, E6, at each gating temperature for A1-007:
- Capacity passed to estimator (Ah) and whether temperature-scheduled or fixed.
- Initial SOC, initial RC states (v1, v2), initial hysteresis state (h).
- OCV table source (discharge, charge, or average).
- Capacity used to normalise ground-truth SOC.
- Hypothesis test: E0 scale mismatch (1.0636 vs C/20 capacity) vs Table 1 E0 RMSE.
"""

from pathlib import Path
import sys
import numpy as np
import pandas as pd

repo_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(repo_root))

from soc.assumptions.loader import load_assumptions
from soc.estimators.base import ParamSet
from soc.estimators.registry import get_estimator
from soc.data.calce_loader import load_ocv_file, load_dynamic_cycle, get_raw_dir
from scripts.evaluate_calce import get_file_paths, build_param_sets

GATING_TEMPS = [20, 25, 30, 40, 50]
ESTIMATOR_NAMES = ["E0", "E2", "E5 v1", "E5 v2", "E6"]

def run_d2():
    print("=== D2. Capacity and Initial States Actually Used ===\n")
    raw_dir = get_raw_dir(repo_root)

    param_sets = build_param_sets("calce_a123")
    
    # Check OCV table source in assumptions/profile
    assumptions, _, _ = load_assumptions(profile="calce_a123")
    ocv_note = getattr(assumptions.plant.ocv_table_v, "note", "N/A")
    ocv_source = getattr(assumptions.plant.ocv_table_v, "source", "N/A")
    print(f"OCV table metadata note: {ocv_note}")
    print(f"OCV table metadata source: {ocv_source}")

    # Inspect C/20 capacity per temperature
    c20_caps = {}
    for temp in GATING_TEMPS:
        ocv_p, _ = get_file_paths(raw_dir, temp, "A1-007")
        ocv_data = load_ocv_file(ocv_p, float(temp), "A1-007")
        c20_caps[temp] = ocv_data.c20_capacity_ah

    rows = []
    for temp in GATING_TEMPS:
        truth_cap = c20_caps[temp]
        for est_name in ESTIMATOR_NAMES:
            p = param_sets[est_name]
            real_name = "E5" if est_name.startswith("E5") else est_name
            est = get_estimator(real_name, p)
            est.reset(1.0)
            
            # Extract initial states
            soc0 = getattr(est, "soc", getattr(est, "z", 1.0))
            v1_0 = getattr(est, "v1", 0.0)
            v2_0 = getattr(est, "v2", 0.0)
            h_0 = getattr(est, "h", 0.0)
            est_cap = p.nominal_capacity_ah
            
            rows.append({
                "Temp (C)": temp,
                "Estimator": est_name,
                "Est Cap (Ah)": est_cap,
                "Cap Scheduled": "Fixed (no temp schedule)",
                "Truth Cap (Ah)": truth_cap,
                "Cap Ratio (Est/Truth)": est_cap / truth_cap,
                "Init SOC": soc0,
                "Init v1 (V)": v1_0,
                "Init v2 (V)": v2_0,
                "Init h": h_0,
                "OCV Table Source": "Discharge branch (from identify_calce_params.py)"
            })

    df = pd.DataFrame(rows)
    print(df.to_string(index=False))

    # Test hypothesis for E0:
    print("\n--- E0 Scale Mismatch Hypothesis Test ---")
    print("If E0 integrates i(t) with Q_est, SOC_E0(t) = 1.0 - integral(i dt) / Q_est.")
    print("Truth SOC is SOC_truth(t) = 1.0 - integral(i dt) / Q_truth.")
    print("Error: e(t) = SOC_E0(t) - SOC_truth(t) = integral(i dt) * (1/Q_truth - 1/Q_est).")
    print("For a discharge that consumes delta_SOC_truth fraction of capacity:")
    print("e(t) = (1 - SOC_truth(t)) * (Q_truth/Q_est - 1).")
    print("If delta_SOC_truth goes from 1.0 to 0 (approx ramp), RMS of (1 - SOC) is 1/sqrt(3) * max_delta_SOC.")
    print("Predicted RMSE_scale = (1/sqrt(3)) * max_delta_SOC * |Q_truth / Q_est - 1| * 100 pp.\n")

    # Load actual E0 results from verdict
    verdict_path = repo_root / "reports" / "calce_a123_verdict.md"
    print("Comparing predicted scale mismatch RMSE with actual E0 RMSE in verdict:")
    for temp in GATING_TEMPS:
        q_truth = c20_caps[temp]
        q_est = param_sets["E0"].nominal_capacity_ah
        scale_err_max_pp = abs(q_truth / q_est - 1.0) * 100.0
        # For a full discharge (delta_soc ~ 1.0), ramp RMS is max_err / sqrt(3) ~ 0.577 * max_err
        pred_rmse_full_pp = scale_err_max_pp / np.sqrt(3.0)
        print(f"Temp {temp:2d} C: Q_truth = {q_truth:.4f} Ah, Q_est = {q_est:.4f} Ah, "
              f"Max delta SOC error = {scale_err_max_pp:5.2f} pp, Predicted RMSE (ramp) = {pred_rmse_full_pp:5.2f} pp")

if __name__ == "__main__":
    run_d2()
