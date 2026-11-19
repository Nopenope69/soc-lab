#!/usr/bin/env python3
"""Regenerate capacity sensitivity analysis on Gustave Eiffel 105 Ah dev partition.

Evaluates E0 and E7v3 (via deliverable/bms_soc_ref.py) on dev cells BUGE388 and BUGE389
under 12 nominal-initialisation dynamic WLTC scenarios across 25 °C, 40 °C, and 0 °C,
comparing baseline nominal capacity (105.042655 Ah) against per-file measured nominal
capacity from file metadata.
"""

from dataclasses import asdict
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
    extract_wltc_segments,
    load_ge105_config,
    load_ge105_raw_mat,
)
from soc.data.registry import resolve_dataset_dir


def run_e0(current_a: np.ndarray, time_s: np.ndarray, soc0: float, nom_cap_ah: float, eta: float = 0.998) -> np.ndarray:
    """Coulomb counting matching scripts/validation/ge105_eval_dev.py.

    Current sign convention: positive is discharge, negative is charge.
    Efficiency: eta applied for charge (i < 0), 1.0 for discharge (i >= 0).
    """
    soc = float(soc0)
    soc_hist = [soc]
    for k in range(len(current_a) - 1):
        dt = time_s[k + 1] - time_s[k]
        i = current_a[k]
        eff = eta if i < 0 else 1.0
        soc = soc - (eff * i * dt) / (3600.0 * nom_cap_ah)
        soc_hist.append(soc)
    return np.array(soc_hist)


def run_bms(cal: CellCalibration, v_v: np.ndarray, i_a: np.ndarray, t_c: np.ndarray, t_s: np.ndarray, z0: float) -> np.ndarray:
    """Run reference BMS estimator with nominal initialization."""
    ref = BmsSocEstimatorRef(cal)
    ref.reset(z0, soc_std=0.10)
    soc_hist = []
    for k in range(len(t_s)):
        dt_k = (t_s[k] - t_s[k - 1]) if k > 0 else 1.0
        res = ref.step(v=float(v_v[k]), i=float(i_a[k]), temp_c=float(t_c[k]), dt=float(dt_k))
        soc_hist.append(res.soc)
    return np.array(soc_hist)


def compute_capacity_sensitivity() -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Compute per-file capacity deviations and scenario metrics on dev partition."""
    config = load_ge105_config()
    base_nom_cap = float(config["cell"]["nominal_capacity_ah"])
    calib_ge105 = CellCalibration.from_json(REPO_ROOT / "deliverable" / "calibrations" / "ge105_v1.json")

    splits_path = REPO_ROOT / "configs" / "validation" / "ge105_splits.yaml"
    with open(splits_path, "r", encoding="utf-8") as f:
        splits = yaml.safe_load(f)

    dev_cells = splits["dev_cells"]["train_cells"] + splits["dev_cells"]["val_cells"]
    base_dir = resolve_dataset_dir("gustave_eiffel_g02iye")
    temps = [25, 40, 0]

    sec2_rows: List[Dict[str, Any]] = []
    sec3_rows: List[Dict[str, Any]] = []

    for cell in dev_cells:
        cell_dir = base_dir / "main_extracted" / "processed_data" / "2_processed_data" / cell
        for t in temps:
            files = sorted([f for f in cell_dir.iterdir() if f"full_{t}C" in f.name and f.name.endswith(".mat")])
            if not files:
                continue
            fpath = files[0]
            ts = load_ge105_raw_mat(fpath, verify_checksum=True)
            file_nom_cap = float(ts.metadata.nominal_capacity_ah)
            ratio = file_nom_cap / base_nom_cap
            dev_pct = (ratio - 1.0) * 100.0

            sec2_rows.append({
                "cell": cell,
                "temp": t,
                "file_name": fpath.name,
                "file_cap": file_nom_cap,
                "base_cap": base_nom_cap,
                "ratio": ratio,
                "dev_pct": dev_pct,
            })

            segs = extract_wltc_segments(ts, resample_1s=True)
            cal_dict = asdict(calib_ge105)
            cal_dict["nominal_capacity_ah"] = file_nom_cap
            cal_dict["q_table_ah"] = [round(q * ratio, 3) for q in cal_dict["q_table_ah"]]
            cal_sens = CellCalibration(**cal_dict)

            for seg in segs:
                t_s = seg.time_s
                i_a = seg.current_a
                v_v = seg.voltage_v
                t_c = seg.temperature_c_array
                z_ref = seg.truth_soc
                z0 = float(z_ref[0])

                # 1. E0 Baseline
                soc_e0_base = run_e0(i_a, t_s, z0, nom_cap_ah=base_nom_cap)
                err_e0_base = np.abs(soc_e0_base - z_ref) * 100.0

                # 2. E0 Sensitivity (per-file nom_capacity)
                soc_e0_sens = run_e0(i_a, t_s, z0, nom_cap_ah=file_nom_cap)
                err_e0_sens = np.abs(soc_e0_sens - z_ref) * 100.0

                # 3. E7v3 GE105 Baseline
                soc_bms_base = run_bms(calib_ge105, v_v, i_a, t_c, t_s, z0)
                err_bms_base = np.abs(soc_bms_base - z_ref) * 100.0

                # 4. E7v3 GE105 Sensitivity (scaled calibration)
                soc_bms_sens = run_bms(cal_sens, v_v, i_a, t_c, t_s, z0)
                err_bms_sens = np.abs(soc_bms_sens - z_ref) * 100.0

                target_soc = "~90%" if "90SOC" in seg.segment_id else "~50%"

                sec3_rows.append({
                    "cell": cell,
                    "temp": t,
                    "target_soc": target_soc,
                    "file_cap": file_nom_cap,
                    "base_cap": base_nom_cap,
                    "e0_base_max": float(np.max(err_e0_base)),
                    "e0_base_rmse": float(np.sqrt(np.mean(err_e0_base ** 2))),
                    "e0_sens_max": float(np.max(err_e0_sens)),
                    "e0_sens_rmse": float(np.sqrt(np.mean(err_e0_sens ** 2))),
                    "e0_d_rmse": float(np.sqrt(np.mean(err_e0_sens ** 2))) - float(np.sqrt(np.mean(err_e0_base ** 2))),
                    "e7_base_max": float(np.max(err_bms_base)),
                    "e7_base_rmse": float(np.sqrt(np.mean(err_bms_base ** 2))),
                    "e7_sens_max": float(np.max(err_bms_sens)),
                    "e7_sens_rmse": float(np.sqrt(np.mean(err_bms_sens ** 2))),
                    "e7_d_rmse": float(np.sqrt(np.mean(err_bms_sens ** 2))) - float(np.sqrt(np.mean(err_bms_base ** 2))),
                })

    return sec2_rows, sec3_rows


def print_tables(sec2_rows: List[Dict[str, Any]], sec3_rows: List[Dict[str, Any]]) -> None:
    print("### Section 2.1: Per-File Capacity Extraction")
    print("| Cell | Ambient Temp (°C) | Evaluated MAT File | Per-File Capacity $Q_{\\text{file}}$ (Ah) | Baseline $Q_{\\text{base}}$ (Ah) | Ratio ($Q_{\\text{file}} / Q_{\\text{base}}$) | Deviation |")
    print("|:---|:---:|:---|:---:|:---:|:---:|:---:|")
    for r in sec2_rows:
        print(f"| `{r['cell']}` | {r['temp']} | `{r['file_name']}` | {r['file_cap']:.6f} | {r['base_cap']:.6f} | {r['ratio']:.5f} | {r['dev_pct']:+.2f}% |")

    print("\n### Section 3: Capacity Sensitivity Evaluation Results")
    print("| Cell | Temp | Target SOC | File $Q_{\\text{file}}$ (Ah) | Base $Q_{\\text{base}}$ (Ah) | E0 Base (Max / RMSE pp) | E0 Sens (Max / RMSE pp) | $\\Delta$ E0 RMSE (pp) | E7v3 Base (Max / RMSE pp) | E7v3 Sens (Max / RMSE pp) | $\\Delta$ E7v3 RMSE (pp) |")
    print("|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|")
    for r in sec3_rows:
        e0_b = f"{r['e0_base_max']:.2f} / {r['e0_base_rmse']:.2f}"
        e0_s = f"{r['e0_sens_max']:.2f} / {r['e0_sens_rmse']:.2f}"
        e7_b = f"{r['e7_base_max']:.2f} / {r['e7_base_rmse']:.2f}"
        e7_s = f"{r['e7_sens_max']:.2f} / {r['e7_sens_rmse']:.2f}"
        print(f"| `{r['cell']}` | {r['temp']} °C | {r['target_soc']} | {r['file_cap']:.3f} | {r['base_cap']:.3f} | {e0_b} | {e0_s} | {r['e0_d_rmse']:+.3f} | {e7_b} | {e7_s} | {r['e7_d_rmse']:+.3f} |")


def main() -> None:
    sec2_rows, sec3_rows = compute_capacity_sensitivity()
    print_tables(sec2_rows, sec3_rows)


if __name__ == "__main__":
    main()
