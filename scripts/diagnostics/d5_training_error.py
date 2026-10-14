"""Diagnostic D5: Training error on DST vs US06/FUDS.

Reports:
- DST fit error: voltage RMSE in mV and SOC RMSE in pp for E0, E2, E5 v1, E5 v2, E6
  at each gating temperature (20, 25, 30, 40, 50 C) for Cell A1-007.
- Comparison against US06 and FUDS baseline RMSE from Table 1 of the verdict.
- Assesses whether DST SOC error is also ~30 pp (testing training vs generalization error).
"""

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

GATING_TEMPS = [20, 25, 30, 40, 50]
ESTIMATOR_NAMES = ["E0", "E2", "E5 v1", "E5 v2", "E6"]

# Baseline results from Table 1 of reports/calce_a123_verdict.md
VERDICT_TABLE_1 = {
    (20, "US06"): {"E0": 0.10, "E2": 32.60, "E5 v1": 31.88, "E5 v2": 32.85, "E6": 25.21},
    (20, "FUDS"): {"E0": 0.11, "E2": 27.83, "E5 v1": 24.53, "E5 v2": 28.77, "E6": 23.92},
    (25, "US06"): {"E0": 0.01, "E2": 32.48, "E5 v1": 31.90, "E5 v2": 32.55, "E6": 25.01},
    (25, "FUDS"): {"E0": 0.02, "E2": 27.59, "E5 v1": 24.07, "E5 v2": 28.19, "E6": 21.81},
    (30, "US06"): {"E0": 0.51, "E2": 34.55, "E5 v1": 31.91, "E5 v2": 33.85, "E6": 26.76},
    (30, "FUDS"): {"E0": 0.52, "E2": 29.81, "E5 v1": 26.87, "E5 v2": 28.36, "E6": 23.13},
    (40, "US06"): {"E0": 0.89, "E2": 32.47, "E5 v1": 31.93, "E5 v2": 33.92, "E6": 25.33},
    (40, "FUDS"): {"E0": 0.91, "E2": 28.39, "E5 v1": 26.38, "E5 v2": 27.85, "E6": 21.68},
    (50, "US06"): {"E0": 0.94, "E2": 35.06, "E5 v1": 34.30, "E5 v2": 35.17, "E6": 26.68},
    (50, "FUDS"): {"E0": 0.95, "E2": 29.37, "E5 v1": 26.55, "E5 v2": 29.38, "E6": 22.16},
}

def run_d5():
    print("=== D5. Training Error on DST vs US06/FUDS ===\n")
    raw_dir = get_raw_dir(repo_root)
    reports_dir = repo_root / "reports" / "diagnostics"
    reports_dir.mkdir(parents=True, exist_ok=True)

    param_sets = build_param_sets("calce_a123")

    results = []

    for temp in GATING_TEMPS:
        ocv_p, dyn_p = get_file_paths(raw_dir, temp, "A1-007")
        ocv_data = load_ocv_file(ocv_p, float(temp), "A1-007")
        dst = load_dynamic_cycle(dyn_p, float(temp), "A1-007", "DST", ocv_data.c20_capacity_ah)

        time_s = dst.time_s
        n_samples = len(time_s)
        dt_arr = np.diff(time_s, prepend=time_s[0])

        for est_name in ESTIMATOR_NAMES:
            p = param_sets[est_name]
            real_name = "E5" if est_name.startswith("E5") else est_name
            est = get_estimator(real_name, p)
            est.reset(1.0)

            soc_preds = np.empty(n_samples, dtype=float)
            v_resids = []

            for k in range(n_samples):
                dt = float(dt_arr[k]) if k > 0 else (float(time_s[1] - time_s[0]) if n_samples > 1 else 1.0)
                meas = Measurement(
                    v=float(dst.voltage_v[k]),
                    i=float(dst.current_a[k]),
                    temp_c=float(dst.temperature_measured_c[k]),
                    dt=dt,
                    dropout=False,
                )
                out = est.step(meas)
                soc_preds[k] = out.soc
                if out.voltage_residual is not None:
                    v_resids.append(out.voltage_residual)

            err_pp = (soc_preds - dst.truth_soc) * 100.0
            soc_rmse = float(np.sqrt(np.mean(err_pp ** 2)))
            v_rmse_mv = float(np.sqrt(np.mean(np.array(v_resids) ** 2)) * 1000.0) if v_resids else float("nan")

            us06_rmse = VERDICT_TABLE_1.get((temp, "US06"), {}).get(est_name, float("nan"))
            fuds_rmse = VERDICT_TABLE_1.get((temp, "FUDS"), {}).get(est_name, float("nan"))

            results.append({
                "Temp (C)": temp,
                "Estimator": est_name,
                "DST SOC RMSE (pp)": soc_rmse,
                "DST V RMSE (mV)": v_rmse_mv,
                "US06 SOC RMSE (pp)": us06_rmse,
                "FUDS SOC RMSE (pp)": fuds_rmse,
            })

    df = pd.DataFrame(results)
    print(df.to_string(index=False))

    out_csv = reports_dir / "d5_training_error_dst.csv"
    df.to_csv(out_csv, index=False)
    print(f"\nSaved DST training error results to: {out_csv}")

    # Summarize key finding
    e2_dst_mean = df[df["Estimator"] == "E2"]["DST SOC RMSE (pp)"].mean()
    print(f"\nMean E2 DST training SOC RMSE across gating temperatures: {e2_dst_mean:.2f} pp")
    if e2_dst_mean > 20.0:
        print("CONFIRMED: The failure is already present on the TRAINING set (DST). It is NOT overfitting or drive-cycle generalization failure.")

if __name__ == "__main__":
    run_d5()
