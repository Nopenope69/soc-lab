"""Diagnostic D4: Open-loop voltage test (most important).

Drives the identified 2RC (+ hysteresis) model with TRUTH SOC and measured current,
without an estimator, per gating temperature (20, 25, 30, 40, 50 C) for DST, US06, FUDS.

Reports:
1. Voltage RMSE (mV) and max error (mV) with hysteresis on (M = 64.6 mV) and off (M = 0).
2. Voltage residual vs truth SOC.
3. Predicted time to 2.0 V cutoff vs measured time.
4. Inherited SOC error: residual / (dOCV/dSOC) as a function of SOC.
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
from soc.data.calce_loader import load_ocv_file, load_dynamic_cycle, get_raw_dir
from soc.estimators.base import ParamSet
from soc.models.tables import InterpolatedTable2D
from soc.models.cell_2rc import Cell2RCModel
from scripts.evaluate_calce import get_file_paths, build_param_sets

GATING_TEMPS = [20, 25, 30, 40, 50]
PROFILES = ["DST", "US06", "FUDS"]

def run_d4():
    print("=== D4. Open-Loop Voltage Test ===\n")
    raw_dir = get_raw_dir(repo_root)
    reports_dir = repo_root / "reports" / "diagnostics"
    reports_dir.mkdir(parents=True, exist_ok=True)

    param_sets = build_param_sets("calce_a123")
    base_params = param_sets["E2"]

    temps = list(base_params.temperatures_c)
    socs = list(base_params.soc_grid)

    ocv_table = InterpolatedTable2D(temps, socs, base_params.ocv_table)
    r0_table = InterpolatedTable2D(temps, socs, base_params.r0_table)
    r1_table = InterpolatedTable2D(temps, socs, base_params.r1_table)
    tau1_table = InterpolatedTable2D(temps, socs, base_params.tau1_table)
    r2_table = InterpolatedTable2D(temps, socs, base_params.r2_table)
    tau2_table = InterpolatedTable2D(temps, socs, base_params.tau2_table)

    m_hyst_val = base_params.hysteresis_amplitude_v
    gamma = base_params.hysteresis_gamma
    cap_ah = base_params.nominal_capacity_ah
    eta = base_params.coulombic_efficiency

    summary_rows = []
    traces_for_plotting = []

    for temp in GATING_TEMPS:
        ocv_p, dyn_p = get_file_paths(raw_dir, temp, "A1-007")
        ocv_data = load_ocv_file(ocv_p, float(temp), "A1-007")

        for prof in PROFILES:
            cyc = load_dynamic_cycle(dyn_p, float(temp), "A1-007", prof, ocv_data.c20_capacity_ah)
            time_s = cyc.time_s
            n_samples = len(time_s)
            dt_arr = np.diff(time_s, prepend=time_s[0])
            i_arr = cyc.current_a
            v_meas = cyc.voltage_v
            z_truth = cyc.truth_soc
            temp_meas = cyc.temperature_measured_c

            for hyst_mode in ["hyst_on", "hyst_off"]:
                m_eff = m_hyst_val if hyst_mode == "hyst_on" else 0.0

                v_model = np.empty(n_samples, dtype=float)
                v_res = np.empty(n_samples, dtype=float)
                docv_dz_arr = np.empty(n_samples, dtype=float)
                soc_inherited_err_pp = np.empty(n_samples, dtype=float)

                i1 = 0.0
                i2 = 0.0
                h = 0.0

                for k in range(n_samples):
                    dt = float(dt_arr[k]) if k > 0 else (float(time_s[1] - time_s[0]) if n_samples > 1 else 1.0)
                    cur_t = float(temp_meas[k])
                    cur_i = float(i_arr[k])
                    cur_z = float(z_truth[k])

                    r0 = r0_table.lookup(cur_z, cur_t)
                    r1 = r1_table.lookup(cur_z, cur_t)
                    r2 = r2_table.lookup(cur_z, cur_t)
                    tau1 = tau1_table.lookup(cur_z, cur_t)
                    tau2 = tau2_table.lookup(cur_z, cur_t)
                    ocv = ocv_table.lookup(cur_z, cur_t)
                    docv_dz = ocv_table.derivative_soc(cur_z, cur_t)

                    # Voltage equation
                    v_mod = ocv + m_eff * h - r1 * i1 - r2 * i2 - r0 * cur_i
                    res = float(v_meas[k]) - v_mod

                    v_model[k] = v_mod
                    v_res[k] = res
                    docv_dz_arr[k] = docv_dz
                    # Inherited SOC error = residual / (docv_dz) * 100 pp
                    # clamp derivative denominator to prevent div by zero
                    denom = max(abs(docv_dz), 1e-4) * np.sign(docv_dz if docv_dz != 0 else 1.0)
                    soc_inherited_err_pp[k] = (res / denom) * 100.0

                    # Propagate RC and hysteresis states forward
                    i1 = Cell2RCModel.step_rc_current(i1, cur_i, dt, tau1)
                    i2 = Cell2RCModel.step_rc_current(i2, cur_i, dt, tau2)
                    h = Cell2RCModel.step_hysteresis(h, cur_i, dt, cap_ah, gamma, eta)

                v_rmse_mv = float(np.sqrt(np.mean(v_res ** 2)) * 1000.0)
                v_max_err_mv = float(np.max(np.abs(v_res)) * 1000.0)
                mean_res_mv = float(np.mean(v_res) * 1000.0)

                # Cutoff times: measured time is time_s[-1]
                t_meas_cutoff = float(time_s[-1])
                # Predicted cutoff: first index where v_model <= 2.0 V
                cutoff_pred_idx = np.where(v_model <= 2.0)[0]
                t_pred_cutoff = float(time_s[cutoff_pred_idx[0]]) if len(cutoff_pred_idx) > 0 else float("nan")

                summary_rows.append({
                    "Temp (C)": temp,
                    "Profile": prof,
                    "Hysteresis": hyst_mode,
                    "V RMSE (mV)": v_rmse_mv,
                    "V Max Err (mV)": v_max_err_mv,
                    "V Mean Res (mV)": mean_res_mv,
                    "Meas Cutoff (s)": t_meas_cutoff,
                    "Pred Cutoff (s)": t_pred_cutoff,
                    "Cutoff Delta (s)": t_pred_cutoff - t_meas_cutoff if not np.isnan(t_pred_cutoff) else float("nan"),
                    "Median Inherited SOC Err (pp)": float(np.median(np.abs(soc_inherited_err_pp))),
                    "Max Inherited SOC Err (pp)": float(np.max(np.abs(soc_inherited_err_pp))),
                })

                if temp == 25:
                    traces_for_plotting.append(pd.DataFrame({
                        "profile": prof,
                        "hysteresis": hyst_mode,
                        "time_s": time_s,
                        "truth_soc": z_truth,
                        "v_meas": v_meas,
                        "v_model": v_model,
                        "v_res_mv": v_res * 1000.0,
                        "docv_dz_mv_pp": docv_dz_arr * 10.0,  # V/unit -> mV/pp is * 1000/100 = 10
                        "soc_inherited_err_pp": soc_inherited_err_pp,
                    }))

    df_summary = pd.DataFrame(summary_rows)
    print("--- Open-Loop Voltage Model Simulation Summary ---")
    print(df_summary.to_string(index=False))

    # Save summary CSV
    summary_csv = reports_dir / "d4_open_loop_voltage_summary.csv"
    df_summary.to_csv(summary_csv, index=False)
    print(f"\nSaved summary to: {summary_csv}")

    # Plot 25 C traces: Residual vs Truth SOC and Inherited SOC Error vs Truth SOC
    df_plots = pd.concat(traces_for_plotting, ignore_index=True)
    plots_csv = reports_dir / "d4_traces_25c.csv"
    df_plots.to_csv(plots_csv, index=False)

    fig, axes = plt.subplots(3, 2, figsize=(14, 12), sharex="col")
    for row_idx, prof in enumerate(PROFILES):
        sub_on = df_plots[(df_plots["profile"] == prof) & (df_plots["hysteresis"] == "hyst_on")]
        sub_off = df_plots[(df_plots["profile"] == prof) & (df_plots["hysteresis"] == "hyst_off")]

        # Col 0: Voltage Residual vs Truth SOC
        ax0 = axes[row_idx, 0]
        ax0.plot(sub_on["truth_soc"] * 100.0, sub_on["v_res_mv"], label="Hyst On (M=64.6 mV)", color="crimson")
        ax0.plot(sub_off["truth_soc"] * 100.0, sub_off["v_res_mv"], label="Hyst Off (M=0)", color="teal")
        ax0.axhline(0, color="black", linestyle="--", alpha=0.5)
        ax0.set_title(f"{prof} 25°C: Voltage Residual (V_meas - V_model)")
        ax0.set_ylabel("Residual (mV)")
        ax0.set_xlim(100, 0)
        ax0.grid(True, linestyle=":", alpha=0.6)
        ax0.legend(loc="upper left")

        # Col 1: Inherited SOC Error vs Truth SOC
        ax1 = axes[row_idx, 1]
        ax1.plot(sub_on["truth_soc"] * 100.0, sub_on["soc_inherited_err_pp"], label="Hyst On", color="crimson")
        ax1.plot(sub_off["truth_soc"] * 100.0, sub_off["soc_inherited_err_pp"], label="Hyst Off", color="teal")
        ax1.axhline(0, color="black", linestyle="--", alpha=0.5)
        ax1.set_title(f"{prof} 25°C: Implied SOC Error [Res / (dOCV/dSOC)]")
        ax1.set_ylabel("Implied Error (pp)")
        ax1.set_xlim(100, 0)
        ax1.set_ylim(-100, 100)
        ax1.grid(True, linestyle=":", alpha=0.6)
        ax1.legend(loc="upper left")

    axes[2, 0].set_xlabel("Truth SOC (%) [100% -> 0%]")
    axes[2, 1].set_xlabel("Truth SOC (%) [100% -> 0%]")
    fig.tight_layout()
    plot_png = reports_dir / "d4_open_loop_residuals_25c.png"
    fig.savefig(plot_png, dpi=150)
    plt.close(fig)
    print(f"Saved plot to: {plot_png}")

if __name__ == "__main__":
    run_d4()
