"""Diagnostic D7: Initial-offset insensitivity on E2.

Primary scope: Cell A1-007, 25 C, US06 and FUDS.
Offsets:
- -20 pp (z0 = 0.80)
- -10 pp (z0 = 0.90)
- +10 pp (z0 = 1.10 -> clipped to 1.00)
- -5 pp  (z0 = 0.95)

Outputs:
- Initial P and Q diagonal elements.
- Estimator SOC trajectories for the first 600 s.
- Time and number of steps to converge to baseline.
- Analysis of clipping, initial covariance, process noise, and measurement update gain.
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

OFFSETS_PP = [0.0, -20.0, -10.0, 10.0, -5.0]

def run_d7():
    print("=== D7. Initial-Offset Insensitivity on E2 ===\n")
    raw_dir = get_raw_dir(repo_root)
    reports_dir = repo_root / "reports" / "diagnostics"
    reports_dir.mkdir(parents=True, exist_ok=True)

    param_sets = build_param_sets("calce_a123")
    p_e2 = param_sets["E2"]

    # Inspect initial P and Q
    est_temp = get_estimator("E2", p_e2)
    est_temp.reset(1.0)
    p_diag = np.diag(est_temp.p)
    q_diag = np.array([
        p_e2.process_noise_q_soc,
        p_e2.process_noise_q_rc,
        p_e2.process_noise_q_rc,
        p_e2.process_noise_q_hysteresis
    ])
    print(f"Initial P diagonal [SOC, RC1, RC2, H]: {p_diag}")
    print(f"Process noise Q diagonal:              {q_diag}")
    print(f"Measurement noise R_v:                 {p_e2.measurement_noise_r_v} V^2 (sigma = {np.sqrt(p_e2.measurement_noise_r_v)*1000:.2f} mV)")

    ocv_p, dyn_p = get_file_paths(raw_dir, 25, "A1-007")
    ocv_data = load_ocv_file(ocv_p, 25.0, "A1-007")

    trajectories = []

    for prof in ["US06", "FUDS"]:
        print(f"\n--- Profile: {prof} (25 C, Cell A1-007) ---")
        cyc = load_dynamic_cycle(dyn_p, 25.0, "A1-007", prof, ocv_data.c20_capacity_ah)
        time_s = cyc.time_s
        dt_arr = np.diff(time_s, prepend=time_s[0])
        idx_600 = np.searchsorted(time_s, 600.0)

        # Baseline run
        est_base = get_estimator("E2", p_e2)
        est_base.reset(1.0)
        base_soc = np.empty(idx_600, dtype=float)
        for k in range(idx_600):
            meas = Measurement(
                v=float(cyc.voltage_v[k]),
                i=float(cyc.current_a[k]),
                temp_c=float(cyc.temperature_measured_c[k]),
                dt=float(dt_arr[k]),
                dropout=False,
            )
            out = est_base.step(meas)
            base_soc[k] = out.soc

        for off in OFFSETS_PP:
            est = get_estimator("E2", p_e2)
            z0_target = 1.0 + off / 100.0
            est.reset(z0_target)
            actual_z0 = float(est.x[0])

            soc_hist = np.empty(idx_600, dtype=float)
            k_gain_soc_hist = np.empty(idx_600, dtype=float)

            for k in range(idx_600):
                meas = Measurement(
                    v=float(cyc.voltage_v[k]),
                    i=float(cyc.current_a[k]),
                    temp_c=float(cyc.temperature_measured_c[k]),
                    dt=float(dt_arr[k]),
                    dropout=False,
                )
                out = est.step(meas)
                soc_hist[k] = out.soc
                # compute kalman gain at step k if needed

            # Print snapshot points at t = 0, 10, 30, 60, 120, 300, 600 s
            eval_times = [0.0, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0, 600.0]
            snap_str = []
            for t_val in eval_times:
                t_idx = min(int(np.searchsorted(time_s[:idx_600], t_val)), idx_600 - 1)
                snap_str.append(f"t={t_val:3.0f}s: {soc_hist[t_idx]*100.0:5.2f}%")

            diff_from_base = np.abs(soc_hist - base_soc) * 100.0
            # Time to converge within 0.1 pp of baseline
            conv_idx = np.where(diff_from_base < 0.1)[0]
            t_conv = time_s[conv_idx[0]] if len(conv_idx) > 0 else "> 600 s"
            steps_conv = conv_idx[0] if len(conv_idx) > 0 else "> 600"

            print(f"Offset {off:+5.1f} pp (Reset z0={actual_z0:.4f}) -> Conv to base (<0.1 pp) in {t_conv if isinstance(t_conv, str) else f'{t_conv:.1f} s'} ({steps_conv} steps)")
            print(f"   Snapshots: {' | '.join(snap_str[:4])}")
            print(f"              {' | '.join(snap_str[4:])}")

            for k in range(idx_600):
                trajectories.append({
                    "profile": prof,
                    "offset_pp": off,
                    "time_s": time_s[k],
                    "truth_soc": cyc.truth_soc[k],
                    "est_soc": soc_hist[k],
                    "base_soc": base_soc[k],
                    "abs_diff_pp": diff_from_base[k],
                })

    df_traj = pd.DataFrame(trajectories)
    out_csv = reports_dir / "d7_initial_offset_trajectories.csv"
    df_traj.to_csv(out_csv, index=False)
    print(f"\nSaved offset trajectory CSV to: {out_csv}")

if __name__ == "__main__":
    run_d7()
