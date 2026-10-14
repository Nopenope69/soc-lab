"""Parameter identification script for CALCE A123 dataset.

Fits 2RC parameters and extracts OCV/hysteresis curves across temperatures
for Cell A1-007 and Cell A1-008, outputting validated profile YAML files.
"""

from pathlib import Path
import numpy as np
import scipy.optimize as opt
import yaml

from soc.data.calce_loader import load_ocv_file, load_dynamic_cycle, get_raw_dir

TEMPS = [-10, 0, 10, 20, 25, 30, 40, 50]
SOC_GRID = [0.0, 0.05, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 1.0]

def get_file_paths(raw_dir: Path, temp: int, cell: str):
    # OCV path
    if temp == -10:
        ocv_pattern = "*OCV-10*"
    elif temp == 25:
        ocv_pattern = "*OCV25*"
    else:
        ocv_pattern = f"*OCV{temp}-*"

    ocv_dirs = [p for p in raw_dir.glob(ocv_pattern) if p.is_dir()]
    if not ocv_dirs:
        raise FileNotFoundError(f"No OCV folder for {temp}C")
    ocv_cands = [p for p in ocv_dirs[0].rglob(f"*{cell}*.xlsx") if not p.name.startswith("~$")]
    if not ocv_cands:
        raise FileNotFoundError(f"Cannot find OCV file for {temp}C {cell}")
    ocv_path = ocv_cands[0]

    # Dynamic path
    if temp == -10:
        dyn_pattern = "*DST-US06-FUDS-N10*"
    elif temp == 20:
        dyn_pattern = "*DST-US06-FUDS-20*"
    else:
        dyn_pattern = f"*DST-US06-FUDS-{temp}*"

    dyn_dirs = [p for p in raw_dir.glob(dyn_pattern) if p.is_dir()]
    if not dyn_dirs:
        raise FileNotFoundError(f"No dynamic folder for {temp}C")
        
    if temp == 20:
        # Prefer the canonical 20120817 rerun
        dyn_cands = [p for p in dyn_dirs[0].rglob(f"*{cell}*20120817.xlsx") if not p.name.startswith("~$") and "newprofile" not in p.name]
    else:
        dyn_cands = [p for p in dyn_dirs[0].rglob(f"*{cell}*.xlsx") if not p.name.startswith("~$")]
        
    if not dyn_cands:
        dyn_cands = [p for p in dyn_dirs[0].rglob(f"*{cell}*") if not p.name.startswith("~$") and ("xlsx" in p.name or "xls" in p.name)]
    if not dyn_cands:
        raise FileNotFoundError(f"Cannot find dynamic file for {temp}C {cell}")
    dyn_path = dyn_cands[0]

    return ocv_path, dyn_path


def fit_cell_parameters(cell_id: str):
    raw_dir = get_raw_dir()
    print(f"\n==========================================")
    print(f"IDENTIFYING PARAMETERS FOR CELL {cell_id}")
    print(f"==========================================")
    
    results = {
        "temps_measured": [],
        "nominal_capacity_ah": {},
        "ocv_table": {},
        "r0_table": {},
        "r1_table": {},
        "tau1_table": {},
        "r2_table": {},
        "tau2_table": {},
        "m_hyst_table": {},
    }
    
    for t in TEMPS:
        print(f"\n--- Temperature {t} C ---")
        ocv_p, dyn_p = get_file_paths(raw_dir, t, cell_id)
        
        # 1. Load OCV
        ocv = load_ocv_file(ocv_p, float(t), cell_id)
        print(f"OCV C/20 capacity: {ocv.c20_capacity_ah:.4f} Ah")
        
        # 2. Extract OCV curves
        dis_soc = ocv.discharge_soc
        dis_v = ocv.discharge_v
        chg_soc = ocv.charge_soc
        chg_v = ocv.charge_v
        
        # If 10C artifact: exclude [0.75, 0.78]
        if ocv.excluded_soc_range is not None:
            low, high = ocv.excluded_soc_range
            mask_dis = (dis_soc < low) | (dis_soc > high)
            dis_soc = dis_soc[mask_dis]
            dis_v = dis_v[mask_dis]
            print(f"Excluded [{low}, {high}] from 10C discharge branch.")
            
        # Monotonic sorting for interpolation
        idx_dis = np.argsort(dis_soc)
        dis_soc_sorted = dis_soc[idx_dis]
        dis_v_sorted = dis_v[idx_dis]
        
        idx_chg = np.argsort(chg_soc)
        chg_soc_sorted = chg_soc[idx_chg]
        chg_v_sorted = chg_v[idx_chg]
        
        v_dis_grid = np.interp(SOC_GRID, dis_soc_sorted, dis_v_sorted)
        v_chg_grid = np.interp(SOC_GRID, chg_soc_sorted, chg_v_sorted)
        
        v_ocv_raw = 0.5 * (v_dis_grid + v_chg_grid)
        m_hyst_raw = 0.5 * (v_chg_grid - v_dis_grid)
        
        # Enforce strict monotonicity on OCV grid (min slope 1 mV per point)
        v_ocv_mono = np.copy(v_ocv_raw)
        for i in range(len(v_ocv_mono) - 1):
            if v_ocv_mono[i+1] <= v_ocv_mono[i]:
                v_ocv_mono[i+1] = v_ocv_mono[i] + 0.001
        for i in range(len(v_ocv_mono) - 2, -1, -1):
            if v_ocv_mono[i] >= v_ocv_mono[i+1]:
                v_ocv_mono[i] = v_ocv_mono[i+1] - 0.001

        # 3. Load DST
        dst = load_dynamic_cycle(dyn_p, float(t), cell_id, "DST", ocv.c20_capacity_ah)
        t_meas = float(np.round(np.mean(dst.temperature_measured_c), 1))
        t_key = f"{t_meas:.1f}"
        print(f"Measured mean T: {t_meas} C (key: '{t_key}')")
        print(f"DST duration: {dst.time_s[-1]:.1f} s, integrated Ah: {dst.integrated_capacity_ah:.4f}")
        print(f"Capacity diff vs cycler: {dst.capacity_diff_ah:.5f} Ah ({dst.capacity_diff_pct*100:.3f}%)")
        print(f"Final SOC at cutoff: {dst.final_soc:.4f}")
        
        # 4. Fit 2RC on DST
        time_s = dst.time_s
        i_stream = dst.current_a
        v_stream = dst.voltage_v
        z_stream = dst.truth_soc
        
        v_ocv_stream = np.interp(z_stream, SOC_GRID, v_ocv_mono)
        
        # Subsampled least squares (stride 4)
        stride = 4 if len(time_s) > 2000 else 2
        idx_sub = np.arange(0, len(time_s), stride)
        dt_full = np.diff(time_s, prepend=time_s[0])
        
        def residuals(p):
            r0, r1, tau1, r2, tau2 = p
            alpha1 = np.exp(-dt_full / tau1)
            alpha2 = np.exp(-dt_full / tau2)
            v1 = np.zeros_like(i_stream)
            v2 = np.zeros_like(i_stream)
            for k in range(len(i_stream) - 1):
                v1[k+1] = alpha1[k+1] * v1[k] + r1 * (1.0 - alpha1[k+1]) * i_stream[k]
                v2[k+1] = alpha2[k+1] * v2[k] + r2 * (1.0 - alpha2[k+1]) * i_stream[k]
            v_model = v_ocv_stream - r0 * i_stream - v1 - v2
            return (v_stream - v_model)[idx_sub]

        init_p = [0.10, 0.03, 15.0, 0.04, 80.0]
        # At very low temperature (-10C), resistance is higher
        if t <= 0:
            init_p = [0.15, 0.05, 20.0, 0.08, 120.0]
            
        bnds = (
            [0.01, 0.001, 2.0, 0.001, 10.0],
            [0.45, 0.30, 100.0, 0.30, 600.0]
        )
        
        res = opt.least_squares(residuals, init_p, bounds=bnds, xtol=1e-3, ftol=1e-3)
        r0, r1, tau1, r2, tau2 = res.x
        v_rmse_mv = np.sqrt(np.mean(res.fun**2)) * 1000.0
        print(f"Fitted 2RC: R0={r0:.4f} Ohm, R1={r1:.4f} Ohm, tau1={tau1:.1f} s, R2={r2:.4f} Ohm, tau2={tau2:.1f} s")
        print(f"Fit voltage RMSE on DST: {v_rmse_mv:.2f} mV")
        
        results["temps_measured"].append(t_meas)
        results["nominal_capacity_ah"][t_key] = round(float(ocv.c20_capacity_ah), 4)
        results["ocv_table"][t_key] = [round(float(x), 4) for x in v_ocv_mono]
        results["r0_table"][t_key] = round(float(r0), 5)
        results["r1_table"][t_key] = round(float(r1), 5)
        results["tau1_table"][t_key] = round(float(tau1), 2)
        results["r2_table"][t_key] = round(float(r2), 5)
        results["tau2_table"][t_key] = round(float(tau2), 2)
        results["m_hyst_table"][t_key] = round(float(np.mean(m_hyst_raw)), 4)
        
    return results


def write_profile_yaml(results: dict, output_path: Path, cell_id: str):
    # Sort by temperature
    t_meas_sorted = sorted(results["temps_measured"])
    
    # 25C nominal capacity as profile reference
    c25_key = [k for k in results["nominal_capacity_ah"].keys() if abs(float(k) - 25.0) < 3.0][0]
    nom_cap = results["nominal_capacity_ah"][c25_key]
    mean_m_hyst = float(np.mean(list(results["m_hyst_table"].values())))

    profile_dict = {
        "plant": {
            "nominal_capacity_Ah": {
                "value": float(nom_cap),
                "unit": "Ah",
                "status": "measured",
                "bounds": [0.1, 500.0],
                "note": f"Measured C/20 capacity for CALCE A123 26650 cell {cell_id} at 25C",
                "source": f"CALCE A123 dataset cell {cell_id}",
            },
            "temperatures_c": {
                "value": [float(x) for x in t_meas_sorted],
                "unit": "degC",
                "status": "measured",
                "bounds": [-20.0, 60.0],
                "note": f"Measured chamber/cell temperatures for cell {cell_id}",
                "source": f"CALCE A123 dataset cell {cell_id}",
            },
            "soc_grid": {
                "value": SOC_GRID,
                "unit": "fraction",
                "status": "measured",
                "bounds": [0.0, 1.0],
                "note": "SOC grid points for parameter tables",
                "source": "Standard grid",
            },
            "ocv_table_v": {
                "value": {str(k): v for k, v in results["ocv_table"].items()},
                "unit": "V",
                "status": "measured",
                "bounds": [2.0, 4.0],
                "note": "Extracted equilibrium OCV curve from C/20 charge and discharge branches",
                "source": f"CALCE A123 dataset cell {cell_id}",
            },
            "r0_table_ohm": {
                "value": {str(k): v for k, v in results["r0_table"].items()},
                "unit": "Ohm",
                "status": "measured",
                "bounds": [0.0001, 0.50],
                "note": "Fitted ohmic resistance over measured temperature from DST",
                "source": f"CALCE A123 dataset cell {cell_id}",
            },
            "r1_table_ohm": {
                "value": {str(k): v for k, v in results["r1_table"].items()},
                "unit": "Ohm",
                "status": "measured",
                "bounds": [0.00005, 0.50],
                "note": "Fitted first RC resistance from DST",
                "source": f"CALCE A123 dataset cell {cell_id}",
            },
            "tau1_table_s": {
                "value": {str(k): v for k, v in results["tau1_table"].items()},
                "unit": "s",
                "status": "measured",
                "bounds": [0.5, 300.0],
                "note": "Fitted first RC time constant from DST",
                "source": f"CALCE A123 dataset cell {cell_id}",
            },
            "r2_table_ohm": {
                "value": {str(k): v for k, v in results["r2_table"].items()},
                "unit": "Ohm",
                "status": "measured",
                "bounds": [0.00005, 0.50],
                "note": "Fitted second RC resistance from DST",
                "source": f"CALCE A123 dataset cell {cell_id}",
            },
            "tau2_table_s": {
                "value": {str(k): v for k, v in results["tau2_table"].items()},
                "unit": "s",
                "status": "measured",
                "bounds": [1.0, 1200.0],
                "note": "Fitted second RC time constant from DST",
                "source": f"CALCE A123 dataset cell {cell_id}",
            },
            "hysteresis_amplitude_v": {
                "value": round(mean_m_hyst, 4),
                "unit": "V",
                "status": "measured",
                "bounds": [0.0, 0.1],
                "note": "Measured half-hysteresis amplitude from C/20 charge/discharge separation",
                "source": f"CALCE A123 dataset cell {cell_id}",
            },
            "hysteresis_gamma": {
                "value": 50.0,
                "unit": "dimensionless",
                "status": "placeholder",
                "bounds": [1.0, 500.0],
                "note": "Minor-loop hysteresis rate gamma (unobserved in full discharges)",
                "source": "Unobserved placeholder",
            },
        }
    }
    
    with open(output_path, "w") as f:
        yaml.dump(profile_dict, f, sort_keys=False)
    print(f"\nSuccessfully wrote profile to {output_path}")


if __name__ == "__main__":
    repo_root = Path(__file__).resolve().parent.parent
    
    # 1. Cell A1-007
    res_a1007 = fit_cell_parameters("A1-007")
    out_a1007 = repo_root / "configs" / "assumptions" / "profiles" / "calce_a123.yaml"
    write_profile_yaml(res_a1007, out_a1007, "A1-007")
    
    # 2. Cell A1-008
    res_a1008 = fit_cell_parameters("A1-008")
    out_a1008 = repo_root / "configs" / "assumptions" / "profiles" / "calce_a123_a1008.yaml"
    write_profile_yaml(res_a1008, out_a1008, "A1-008")
