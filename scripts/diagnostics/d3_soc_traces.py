"""Diagnostic D3: SOC traces and error vs truth SOC.

Primary scope: cell A1-007, 25 C, profiles US06 and FUDS.
Estimators: E0, E2, E5 v1, E5 v2, E6.
Outputs:
- CSV of traces: reports/diagnostics/d3_traces_a1007_25c.csv
- PNG plots:
    reports/diagnostics/d3_soc_vs_time.png
    reports/diagnostics/d3_error_vs_truth_soc.png
- Console report:
    - First time and truth SOC where |error| > 5 pp
    - Clamping at 0 or 1
    - NaN occurrences
    - Covariance collapse
    - Estimator SOC at 2.0 V cutoff
"""

from pathlib import Path
import sys
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

repo_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(repo_root))

from soc.assumptions.loader import load_assumptions
from soc.data.calce_loader import load_ocv_file, load_dynamic_cycle, get_raw_dir, CalceCycleData
from soc.estimators.registry import get_estimator
from soc.models.plant import Measurement
from scripts.evaluate_calce import get_file_paths, build_param_sets

ESTIMATOR_NAMES = ["E0", "E2", "E5 v1", "E5 v2", "E6"]

def run_d3():
    print("=== D3. SOC Traces and Error vs Truth SOC ===\n")
    raw_dir = get_raw_dir(repo_root)
    reports_dir = repo_root / "reports" / "diagnostics"
    reports_dir.mkdir(parents=True, exist_ok=True)

    param_sets = build_param_sets("calce_a123")
    ocv_p, dyn_p = get_file_paths(raw_dir, 25, "A1-007")
    ocv_data = load_ocv_file(ocv_p, 25.0, "A1-007")

    traces_list = []

    fig_time, axes_time = plt.subplots(2, 1, figsize=(12, 10), sharex=False)
    fig_soc, axes_soc = plt.subplots(2, 1, figsize=(12, 10), sharex=False)

    colors = {
        "Truth": "black",
        "E0": "#1f77b4",
        "E2": "#ff7f0e",
        "E5 v1": "#2ca02c",
        "E5 v2": "#d62728",
        "E6": "#9467bd"
    }

    for prof_idx, prof in enumerate(["US06", "FUDS"]):
        cyc = load_dynamic_cycle(dyn_p, 25.0, "A1-007", prof, ocv_data.c20_capacity_ah)
        time_s = cyc.time_s
        n_samples = len(time_s)
        dt_arr = np.diff(time_s, prepend=time_s[0])
        truth_soc = cyc.truth_soc

        ax_t = axes_time[prof_idx]
        ax_s = axes_soc[prof_idx]

        ax_t.plot(time_s, truth_soc * 100.0, label="Truth", color=colors["Truth"], linewidth=2, linestyle="--")

        prof_df = pd.DataFrame({
            "profile": prof,
            "time_s": time_s,
            "truth_soc": truth_soc,
            "voltage_v": cyc.voltage_v,
            "current_a": cyc.current_a,
        })

        print(f"\n--- Profile: {prof} (25 C, Cell A1-007) ---")
        print(f"Total duration: {time_s[-1]:.1f} s, Cutoff truth SOC: {truth_soc[-1]*100.0:.2f}%")

        for est_name in ESTIMATOR_NAMES:
            p = param_sets[est_name]
            real_name = "E5" if est_name.startswith("E5") else est_name
            est = get_estimator(real_name, p)
            est.reset(1.0)

            soc_preds = np.empty(n_samples, dtype=float)
            cov_diag_0 = np.empty(n_samples, dtype=float)
            clamped = False
            has_nan = False

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
                if np.isnan(out.soc):
                    has_nan = True
                if out.soc <= 0.0 or out.soc >= 1.0:
                    clamped = True
                
                # Check covariance if EKF
                if hasattr(est, "P"):
                    cov_diag_0[k] = float(est.P[0, 0])
                else:
                    cov_diag_0[k] = 0.0

            err_pp = (soc_preds - truth_soc) * 100.0
            prof_df[f"{est_name}_soc"] = soc_preds
            prof_df[f"{est_name}_err_pp"] = err_pp

            # Detect first > 5 pp deviation
            dev_idx = np.where(np.abs(err_pp) > 5.0)[0]
            if len(dev_idx) > 0:
                first_k = dev_idx[0]
                t_dev = time_s[first_k]
                soc_truth_dev = truth_soc[first_k] * 100.0
                soc_est_dev = soc_preds[first_k] * 100.0
                err_dev = err_pp[first_k]
                dev_str = f"t = {t_dev:6.1f} s | truth SOC = {soc_truth_dev:5.2f}% | est SOC = {soc_est_dev:5.2f}% | err = {err_dev:+5.2f} pp"
            else:
                dev_str = "Never exceeded 5 pp"

            min_cov = float(np.min(cov_diag_0)) if hasattr(est, "P") else 0.0
            max_cov = float(np.max(cov_diag_0)) if hasattr(est, "P") else 0.0

            print(f"[{est_name:5s}] Cutoff SOC: {soc_preds[-1]*100.0:5.2f}% (Err: {err_pp[-1]:+6.2f} pp) | "
                  f"First >5 pp err: {dev_str} | "
                  f"NaN: {has_nan} | Clamped: {clamped} | "
                  f"Cov P[0,0] range: [{min_cov:.2e}, {max_cov:.2e}]")

            # Plot vs time
            ax_t.plot(time_s, soc_preds * 100.0, label=est_name, color=colors[est_name], alpha=0.85)

            # Plot error vs TRUE SOC (x-axis from 1.0 to 0)
            ax_s.plot(truth_soc * 100.0, err_pp, label=est_name, color=colors[est_name], alpha=0.85)

        ax_t.set_title(f"SOC vs Time — {prof} (A1-007, 25°C)")
        ax_t.set_xlabel("Time (s)")
        ax_t.set_ylabel("SOC (%)")
        ax_t.grid(True, linestyle=":", alpha=0.6)
        ax_t.legend(loc="lower left")

        ax_s.set_title(f"SOC Estimation Error vs True SOC — {prof} (A1-007, 25°C)")
        ax_s.set_xlabel("True SOC (%) [Discharging Left to Right: 100% -> 0%]")
        ax_s.set_ylabel("Error: Est SOC - True SOC (pp)")
        ax_s.set_xlim(100, 0)  # Invert x-axis so discharge goes left to right
        ax_s.axhline(0, color="black", linestyle="--", alpha=0.5)
        ax_s.axhline(5, color="red", linestyle=":", alpha=0.5)
        ax_s.axhline(-5, color="red", linestyle=":", alpha=0.5)
        ax_s.grid(True, linestyle=":", alpha=0.6)
        ax_s.legend(loc="upper right")

        traces_list.append(prof_df)

    # Save CSV
    df_all_traces = pd.concat(traces_list, ignore_index=True)
    csv_out = reports_dir / "d3_traces_a1007_25c.csv"
    df_all_traces.to_csv(csv_out, index=False)
    print(f"\nSaved traces CSV to: {csv_out}")

    # Save PNGs
    fig_time.tight_layout()
    png_time = reports_dir / "d3_soc_vs_time.png"
    fig_time.savefig(png_time, dpi=150)
    plt.close(fig_time)
    print(f"Saved SOC vs time plot to: {png_time}")

    fig_soc.tight_layout()
    png_soc = reports_dir / "d3_error_vs_truth_soc.png"
    fig_soc.savefig(png_soc, dpi=150)
    plt.close(fig_soc)
    print(f"Saved Error vs True SOC plot to: {png_soc}")

if __name__ == "__main__":
    run_d3()
