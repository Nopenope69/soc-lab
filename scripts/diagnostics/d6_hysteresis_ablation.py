"""Diagnostic D6: Hysteresis ablation on E2.

Primary scope: Cell A1-007, 25 C, profiles US06 and FUDS.
Estimator: E2 with runtime overrides:
  (i) Hysteresis amplitude = 0.0 V
  (ii) Hysteresis amplitude sign flipped: M = -0.0646 V
  (iii) Baseline: M = +0.0646 V

Reports:
- SOC RMSE (pp) for each variant on US06 and FUDS.
- OCV table branch provenance (average vs discharge vs charge).
- Analysis of whether hysteresis term is double-counted against 2RC polarization.
"""

from dataclasses import replace
from pathlib import Path
import sys
import numpy as np
import pandas as pd

repo_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(repo_root))

from soc.assumptions.loader import load_assumptions
from soc.data.calce_loader import load_ocv_file, load_dynamic_cycle, get_raw_dir
from soc.estimators.registry import get_estimator
from soc.models.plant import Measurement
from scripts.evaluate_calce import get_file_paths, build_param_sets

PROFILES = ["US06", "FUDS"]

def run_d6():
    print("=== D6. Hysteresis Ablation on Estimator E2 ===\n")
    raw_dir = get_raw_dir(repo_root)
    reports_dir = repo_root / "reports" / "diagnostics"
    reports_dir.mkdir(parents=True, exist_ok=True)

    param_sets = build_param_sets("calce_a123")
    base_params = param_sets["E2"]

    ocv_p, dyn_p = get_file_paths(raw_dir, 25, "A1-007")
    ocv_data = load_ocv_file(ocv_p, 25.0, "A1-007")

    variants = [
        ("Baseline (M = +64.6 mV)", base_params.hysteresis_amplitude_v),
        ("Ablation (M = 0 mV)", 0.0),
        ("Flipped Sign (M = -64.6 mV)", -base_params.hysteresis_amplitude_v),
    ]

    results = []

    for prof in PROFILES:
        cyc = load_dynamic_cycle(dyn_p, 25.0, "A1-007", prof, ocv_data.c20_capacity_ah)
        time_s = cyc.time_s
        n_samples = len(time_s)
        dt_arr = np.diff(time_s, prepend=time_s[0])

        for var_name, m_val in variants:
            p_override = replace(base_params, hysteresis_amplitude_v=m_val)
            est = get_estimator("E2", p_override)
            est.reset(1.0)

            soc_preds = np.empty(n_samples, dtype=float)
            v_resids = []

            for k in range(n_samples):
                dt = float(dt_arr[k]) if k > 0 else (float(time_s[1] - time_s[0]) if n_samples > 1 else 1.0)
                meas = Measurement(
                    v=float(cyc.voltage_v[k]),
                    i=float(cyc.current_a[k]),
                    temp_c=float(cyc.temperature_measured_c[k]),
                    dt=dt,
                    dropout=False,
                )
                out = est.step(meas)
                soc_preds[k] = out.soc
                if out.voltage_residual is not None:
                    v_resids.append(out.voltage_residual)

            err_pp = (soc_preds - cyc.truth_soc) * 100.0
            rmse_pp = float(np.sqrt(np.mean(err_pp ** 2)))
            mae_pp = float(np.mean(np.abs(err_pp)))
            max_err_pp = float(np.max(np.abs(err_pp)))
            final_err_pp = float(err_pp[-1])
            v_rmse_mv = float(np.sqrt(np.mean(np.array(v_resids) ** 2)) * 1000.0) if v_resids else float("nan")

            results.append({
                "Profile": prof,
                "Variant": var_name,
                "M (V)": m_val,
                "SOC RMSE (pp)": rmse_pp,
                "SOC MAE (pp)": mae_pp,
                "SOC Max Err (pp)": max_err_pp,
                "Final Err (pp)": final_err_pp,
                "EKF V RMSE (mV)": v_rmse_mv,
            })

    df = pd.DataFrame(results)
    print(df.to_string(index=False))

    csv_out = reports_dir / "d6_hysteresis_ablation.csv"
    df.to_csv(csv_out, index=False)
    print(f"\nSaved ablation results to: {csv_out}")

    print("\n--- OCV Table & Double-Counting Analysis ---")
    print("In identify_calce_params.py lines 113-114:")
    print("   v_ocv_raw = 0.5 * (v_dis_grid + v_chg_grid)")
    print("   m_hyst_raw = 0.5 * (v_chg_grid - v_dis_grid)")
    print("The OCV table was derived as the ARITHMETIC MEAN of the C/20 charge and discharge branches.")
    print("In line 156 of identify_calce_params.py, 2RC parameters were fitted using:")
    print("   v_model = v_ocv_stream - r0 * i_stream - v1 - v2  (WITHOUT M * h!)")
    print("Because DST is unidirectional discharge (mean current > 0), the optimizer fitted R0, R1, R2 to match")
    print("the voltage drop from v_ocv (average) to v_meas (discharge). Thus, the fitted resistance absorbed M!")
    print("When E2 later evaluates v_hat = v_ocv + M * h - R1*i1 - R2*i2 - R0*i, with h -> -1, it subtracts M A SECOND TIME.")

if __name__ == "__main__":
    run_d6()
