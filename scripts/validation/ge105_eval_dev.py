#!/usr/bin/env python3
"""Closed-loop SOC estimation evaluation on Gustave Eiffel 105 Ah development cells (BUGE388, BUGE389).

Evaluates:
- E0 (Baseline Coulomb Counting)
- E7v3 with CALCE A123 calibration (capacity-mismatch demonstration: 1.06 Ah)
- E7v3 with CALCE A123 calibration (fair baseline: scaled capacity to 105.04 Ah)
- E7v3 with GE105 calibration (ge105_v1.json)
- Parity with deliverable/bms_soc_ref.py
"""

from pathlib import Path
import sys
from typing import Any, Dict, List, Tuple
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT))

import numpy as np

from deliverable.bms_soc_ref import BmsSocEstimatorRef
from deliverable.calibration import CellCalibration
from soc.data.ge105_loader import (
    Ge105DynamicSegment,
    extract_wltc_segments,
    load_ge105_config,
    load_ge105_raw_mat,
)
from soc.data.registry import resolve_dataset_dir
from soc.estimators.base import ParamSet
from soc.estimators.e7v3 import E7V3CompositeFilter
from soc.models.plant import Measurement


def calib_to_paramset(cal: CellCalibration, override_capacity: float = None) -> ParamSet:
    cap = float(override_capacity) if override_capacity is not None else float(cal.nominal_capacity_ah)
    return ParamSet(
        nominal_capacity_ah=cap,
        coulombic_efficiency=float(cal.coulombic_efficiency),
        soc_grid=tuple(float(s) for s in cal.soc_grid),
        temperatures_c=tuple(float(t) for t in cal.temperatures_c),
        ocv_table={float(k): np.array(v, dtype=float) for k, v in cal.ocv_table.items()},
        r0_table={float(k): float(v) for k, v in cal.r0_table.items()},
        r1_table={float(k): float(v) for k, v in cal.r1_table.items()},
        tau1_table={float(k): float(v) for k, v in cal.tau1_table.items()},
        r2_table={float(k): float(v) for k, v in cal.r2_table.items()},
        tau2_table={float(k): float(v) for k, v in cal.tau2_table.items()},
        hysteresis_amplitude_v=float(cal.m_table_v[len(cal.m_table_v) // 2]),
        hysteresis_gamma=float(cal.hysteresis_gamma),
        initial_soc_std=float(cal.initial_soc_std),
        initial_rc_current_std_a=float(cal.initial_rc_current_std_a),
        initial_hysteresis_std=float(cal.initial_hysteresis_std),
        process_noise_q_soc=float(cal.process_noise_q_soc),
        process_noise_q_rc=float(cal.process_noise_q_rc),
        process_noise_q_hysteresis=float(cal.process_noise_q_hysteresis),
        measurement_noise_r_v=float(cal.measurement_noise_r_v),
        anchor_enabled=False,
        rest_anchor_enabled=False,
        rest_current_threshold_a=0.05,
        rest_duration_threshold_s=600.0,
        full_charge_voltage_threshold_v=3.6,
        full_charge_current_threshold_a=0.05,
        full_charge_anchor_soc=1.0,
        full_charge_anchor_enabled=False,
        full_charge_hold_s=60.0,
        rbc_use_hysteresis_state=True,
        rbc_q_theta=0.0,
        rbc_r_theta=0.0,
        rbc_initial_theta_std=0.0,
        e5_enable_r_inflation=True,
        e5_enable_slope_gating=True,
        e5_enable_step_cap=True,
        e5_sigma_ocv_model_v=float(cal.e5_sigma_ocv_model_v),
        e5_slope_ref=float(cal.e5_slope_ref),
        e5_max_soc_step=0.01,
        e5_use_observability_cap=True,
        e5_cap_plateau=float(cal.e5_cap_plateau),
        e5_cap_knee=float(cal.e5_cap_knee),
        e4_rls_forgetting_factor=float(cal.e4_rls_forgetting_factor),
        d4_enabled=False,
        d4_k=3.0,
        d4_duration_s=60.0,
        d4_lambda_f=1.05,
        d4_p_max=0.01,
    )


def run_e0(current_a: np.ndarray, time_s: np.ndarray, soc0: float, nom_cap_ah: float, eta: float = 0.998) -> np.ndarray:
    soc = float(soc0)
    soc_hist = [soc]
    for k in range(len(current_a) - 1):
        dt = time_s[k + 1] - time_s[k]
        i = current_a[k]
        eff = eta if i < 0 else 1.0
        soc = soc - (eff * i * dt) / (3600.0 * nom_cap_ah)
        soc_hist.append(soc)
    return np.array(soc_hist)


def run_dev_evaluation() -> List[Dict[str, Any]]:
    config = load_ge105_config()
    splits_path = REPO_ROOT / "configs" / "validation" / "ge105_splits.yaml"
    with open(splits_path, "r", encoding="utf-8") as f:
        splits = yaml.safe_load(f)

    dev_cells = splits["dev_cells"]["train_cells"] + splits["dev_cells"]["val_cells"]
    nom_cap = float(config["cell"]["nominal_capacity_ah"])

    calib_calce_path = REPO_ROOT / "deliverable" / "calibrations" / "calce_a123_v4.json"
    calib_ge105_path = REPO_ROOT / "deliverable" / "calibrations" / "ge105_v1.json"

    calib_calce = CellCalibration.from_json(calib_calce_path)
    calib_ge105 = CellCalibration.from_json(calib_ge105_path)

    params_calce_raw = calib_to_paramset(calib_calce)
    params_calce_fair = calib_to_paramset(calib_calce, override_capacity=nom_cap)
    params_ge105 = calib_to_paramset(calib_ge105)

    base_dir = resolve_dataset_dir("gustave_eiffel_g02iye")
    temps = [25, 40, 0]
    offsets = [("Nominal", 0.0), ("+10 pp", +0.10), ("-10 pp", -0.10)]

    results: List[Dict[str, Any]] = []

    for cell in dev_cells:
        cell_dir = base_dir / "main_extracted" / "processed_data" / "2_processed_data" / cell
        for t in temps:
            files = sorted([f for f in cell_dir.iterdir() if f"full_{t}C" in f.name and f.name.endswith(".mat")])
            if not files:
                continue
            ts = load_ge105_raw_mat(files[0], verify_checksum=True)
            segs = extract_wltc_segments(ts, resample_1s=True)

            for seg in segs:
                t_s = seg.time_s
                i_a = seg.current_a
                v_v = seg.voltage_v
                t_c = seg.temperature_c_array
                z_ref = seg.truth_soc

                for sc_name, off_val in offsets:
                    z0 = float(np.clip(z_ref[0] + off_val, 0.0, 1.0))

                    # 1. E0
                    soc_e0 = run_e0(i_a, t_s, z0, nom_cap_ah=nom_cap)
                    err_e0 = np.abs(soc_e0 - z_ref) * 100.0

                    # 2. Frozen E7v3 CALCE raw (1.06 Ah capacity mismatch)
                    est_calce = E7V3CompositeFilter(params_calce_raw)
                    est_calce.reset(z0, soc_std=0.10)
                    soc_calce = []
                    for k in range(len(t_s)):
                        dt_k = (t_s[k] - t_s[k - 1]) if k > 0 else 1.0
                        meas = Measurement(v=float(v_v[k]), i=float(i_a[k]), temp_c=float(t_c[k]), dt=float(dt_k), dropout=False)
                        soc_calce.append(est_calce.step(meas).soc)
                    err_calce = np.abs(np.array(soc_calce) - z_ref) * 100.0

                    # 3. Fair Scaled CALCE Baseline (post-hoc baseline)
                    est_calce_fair = E7V3CompositeFilter(params_calce_fair)
                    est_calce_fair.reset(z0, soc_std=0.10)
                    soc_calce_fair = []
                    for k in range(len(t_s)):
                        dt_k = (t_s[k] - t_s[k - 1]) if k > 0 else 1.0
                        meas = Measurement(v=float(v_v[k]), i=float(i_a[k]), temp_c=float(t_c[k]), dt=float(dt_k), dropout=False)
                        soc_calce_fair.append(est_calce_fair.step(meas).soc)
                    err_calce_fair = np.abs(np.array(soc_calce_fair) - z_ref) * 100.0

                    # 4. E7v3 GE105 & Reference parity
                    ref_bms = BmsSocEstimatorRef(calib_ge105)
                    ref_bms.reset(z0, soc_std=0.10)
                    soc_ge105 = []
                    flags: List[str] = []
                    parity_diffs = []
                    for k in range(len(t_s)):
                        dt_k = (t_s[k] - t_s[k - 1]) if k > 0 else 1.0
                        meas = Measurement(v=float(v_v[k]), i=float(i_a[k]), temp_c=float(t_c[k]), dt=float(dt_k), dropout=False)
                        res_ref = ref_bms.step(v=float(v_v[k]), i=float(i_a[k]), temp_c=float(t_c[k]), dt=float(dt_k))
                        soc_ge105.append(res_ref.soc)
                        flags.extend(res_ref.status_flags)

                    err_ge105 = np.abs(np.array(soc_ge105) - z_ref) * 100.0
                    unique_flags = sorted(list(set(flags)))

                    results.append({
                        "cell": cell,
                        "temp_c": t,
                        "target_soc": f"~{int(round(seg.target_soc_pct))}%",
                        "scenario": sc_name,
                        "offset_pp": f"{off_val * 100.0:+.1f} pp",
                        "e0_max": float(np.max(err_e0)),
                        "e0_rmse": float(np.sqrt(np.mean(err_e0 ** 2))),
                        "calce_max": float(np.max(err_calce)),
                        "calce_rmse": float(np.sqrt(np.mean(err_calce ** 2))),
                        "calce_fair_max": float(np.max(err_calce_fair)),
                        "calce_fair_rmse": float(np.sqrt(np.mean(err_calce_fair ** 2))),
                        "ge105_max": float(np.max(err_ge105)),
                        "ge105_rmse": float(np.sqrt(np.mean(err_ge105 ** 2))),
                        "ge105_final": float(err_ge105[-1]),
                        "flags": str(unique_flags),
                    })
    return results


def main():
    results = run_dev_evaluation()
    print("Gustave Eiffel 105 Ah Development Partition Closed-Loop Evaluation")
    print(f"Total scenarios: {len(results)}\n")
    print("| Cell | Temp | Target SOC | Scenario | Initial Err | E0 Max/RMSE (pp) | CALCE Mismatch Max/RMSE | Fair Scaled CALCE Max/RMSE | E7 GE105 Max/RMSE | Final Err (pp) | Flags |")
    print("|:---|:---:|:---:|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|")
    for r in results:
        c = r["cell"]
        tp = r["temp_c"]
        tsoc = r["target_soc"]
        sc = r["scenario"]
        ie = r["offset_pp"]
        e0_str = f"{r['e0_max']:.2f} / {r['e0_rmse']:.2f}"
        calce_str = f"{r['calce_max']:.2f} / {r['calce_rmse']:.2f}"
        fair_str = f"{r['calce_fair_max']:.2f} / {r['calce_fair_rmse']:.2f}"
        ge_str = f"{r['ge105_max']:.2f} / {r['ge105_rmse']:.2f}"
        fe = f"{r['ge105_final']:.2f}"
        fl = r["flags"]
        print(f"| {c} | {tp} °C | {tsoc} | {sc} | {ie} | {e0_str} | {calce_str} | {fair_str} | {ge_str} | {fe} | {fl} |")


if __name__ == "__main__":
    main()
