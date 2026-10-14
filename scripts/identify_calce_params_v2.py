"""Parameter identification script v2 for CALCE A123 dataset.

Fits 2RC parameters on DST only, per temperature, with hysteresis state inside
the residual:
  v_model = v_ocv + M * h - R0 * i - v1 - v2
where:
  - v_ocv is the symmetric mean of charge and discharge branches (monotonized)
  - M is the C/20 plateau-median half-gap corrected for 55 mA from Task A1
  - gamma = 50.0 is unobservable (UNIDENTIFIED)
  - v1, v2, and h are initialized from rest: v1(0)=0, v2(0)=0, h(0)=0.0 (neutral rest convention)

Also fits a second variant:
  - M = 0
  - OCV taken from the C/20 discharge branch only (monotonized)
  - v_model = v_ocv_dis - R0 * i - v1 - v2

Outputs:
  - configs/assumptions/profiles/calce_a123_v2.yaml
  - configs/assumptions/profiles/calce_a123_a1008_v2.yaml
  - configs/assumptions/profiles/calce_a123_v2_m0.yaml
  - configs/assumptions/profiles/calce_a123_a1008_v2_m0.yaml
"""

from pathlib import Path
import sys
import numpy as np
import scipy.optimize as opt
import yaml

repo_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo_root))

from soc.data.calce_loader import load_ocv_file, load_dynamic_cycle, get_raw_dir
from soc.models.cell_2rc import Cell2RCModel
from scripts.evaluate_calce import get_file_paths

TEMPS = [-10, 0, 10, 20, 25, 30, 40, 50]
GATING_TEMPS = [20, 25, 30, 40, 50]
SOC_GRID = [0.0, 0.05, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 1.0]

# M(T) corrected plateau-median half-gap from A1 audit (V)
M_CORRECTED_HALF_GAP = {
    "A1-007": {
        -10: 0.0592,
        0: 0.0436,
        10: 0.0381,
        20: 0.02685,
        25: 0.01701,
        30: 0.02421,
        40: 0.02143,
        50: 0.01977,
    },
    "A1-008": {
        -10: 0.0607,
        0: 0.0418,
        10: 0.0370,
        20: 0.02421,
        25: 0.01551,
        30: 0.02173,
        40: 0.01902,
        50: 0.01442,
    }
}

def fit_cell_parameters_v2(cell_id: str, m_zero_variant: bool = False):
    raw_dir = get_raw_dir(repo_root)
    variant_name = "M=0 Reference (Discharge OCV)" if m_zero_variant else "Joint Identification with Hysteresis (v2)"
    print(f"\n========================================================")
    print(f"IDENTIFYING PARAMETERS ({variant_name}) FOR {cell_id}")
    print(f"========================================================")

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
        "fit_rmse_mv": {},
    }

    m_table = M_CORRECTED_HALF_GAP[cell_id]

    for t in TEMPS:
        print(f"\n--- Temperature {t} C ---")
        ocv_p, dyn_p = get_file_paths(raw_dir, t, cell_id)
        ocv = load_ocv_file(ocv_p, float(t), cell_id)

        dis_soc, dis_v = ocv.discharge_soc, ocv.discharge_v
        chg_soc, chg_v = ocv.charge_soc, ocv.charge_v

        if ocv.excluded_soc_range is not None:
            low, high = ocv.excluded_soc_range
            mask_dis = (dis_soc < low) | (dis_soc > high)
            dis_soc = dis_soc[mask_dis]
            dis_v = dis_v[mask_dis]

        idx_dis = np.argsort(dis_soc)
        dis_soc_sorted = dis_soc[idx_dis]
        dis_v_sorted = dis_v[idx_dis]

        idx_chg = np.argsort(chg_soc)
        chg_soc_sorted = chg_soc[idx_chg]
        chg_v_sorted = chg_v[idx_chg]

        v_dis_grid = np.interp(SOC_GRID, dis_soc_sorted, dis_v_sorted)
        v_chg_grid = np.interp(SOC_GRID, chg_soc_sorted, chg_v_sorted)

        if m_zero_variant:
            # Variant: M=0, OCV from discharge branch only
            v_ocv_base = np.copy(v_dis_grid)
            m_eff = 0.0
        else:
            # Primary v2: symmetric mean OCV, M from A1
            v_ocv_base = 0.5 * (v_dis_grid + v_chg_grid)
            m_eff = m_table[t]

        # Monotonize OCV table
        v_ocv_mono = np.copy(v_ocv_base)
        if v_ocv_mono[0] < 2.0:
            v_ocv_mono[0] = 2.0
        for i in range(len(v_ocv_mono) - 1):
            if v_ocv_mono[i+1] <= v_ocv_mono[i]:
                v_ocv_mono[i+1] = v_ocv_mono[i] + 0.001
        for i in range(len(v_ocv_mono) - 2, -1, -1):
            if v_ocv_mono[i] >= v_ocv_mono[i+1]:
                v_ocv_mono[i] = v_ocv_mono[i+1] - 0.001
        if v_ocv_mono[0] < 2.0:
            diff = 2.0 - v_ocv_mono[0]
            v_ocv_mono += diff

        # Load DST (training data only)
        dst = load_dynamic_cycle(dyn_p, float(t), cell_id, "DST", ocv.c20_capacity_ah)
        t_meas = float(np.round(np.mean(dst.temperature_measured_c), 1))
        t_key = f"{t_meas:.1f}"

        time_s = dst.time_s
        i_stream = dst.current_a
        v_stream = dst.voltage_v
        z_stream = dst.truth_soc
        dt_full = np.diff(time_s, prepend=time_s[0])
        stride = 4 if len(time_s) > 2000 else 2
        idx_sub = np.arange(0, len(time_s), stride)

        v_ocv_stream = np.interp(z_stream, SOC_GRID, v_ocv_mono)

        # Precompute hysteresis state trajectory h(t) with h(0) = 0.0
        gamma = 50.0  # UNIDENTIFIED
        cap_ah = ocv.c20_capacity_ah
        eta = 0.998

        h_arr = np.zeros_like(i_stream)
        h_val = 0.0  # Neutral rest convention
        for k in range(len(i_stream)):
            h_arr[k] = h_val
            h_val = Cell2RCModel.step_hysteresis(
                h_val, float(i_stream[k]), float(dt_full[k]), cap_ah, gamma, eta
            )

        # Residual function with hysteresis state inside the loop
        def residuals(p):
            r0, r1, tau1, r2, tau2 = p
            alpha1 = np.exp(-dt_full / tau1)
            alpha2 = np.exp(-dt_full / tau2)
            v1 = np.zeros_like(i_stream)
            v2 = np.zeros_like(i_stream)
            for k in range(len(i_stream) - 1):
                v1[k+1] = alpha1[k+1] * v1[k] + r1 * (1.0 - alpha1[k+1]) * i_stream[k]
                v2[k+1] = alpha2[k+1] * v2[k] + r2 * (1.0 - alpha2[k+1]) * i_stream[k]
            v_model = v_ocv_stream + (m_eff * h_arr) - (r0 * i_stream) - v1 - v2
            return (v_stream - v_model)[idx_sub]

        init_p = [0.10, 0.03, 15.0, 0.04, 80.0]
        if t <= 0:
            init_p = [0.15, 0.05, 20.0, 0.08, 120.0]

        bnds = (
            [0.01, 0.001, 2.0, 0.001, 10.0],
            [0.45, 0.30, 100.0, 0.30, 600.0]
        )

        res = opt.least_squares(residuals, init_p, bounds=bnds, xtol=1e-3, ftol=1e-3)
        r0, r1, tau1, r2, tau2 = res.x
        v_rmse_mv = float(np.sqrt(np.mean(res.fun**2)) * 1000.0)

        print(f"Fitted 2RC (T={t_meas}°C): R0={r0:.5f}Ω, R1={r1:.5f}Ω, tau1={tau1:.1f}s, R2={r2:.5f}Ω, tau2={tau2:.1f}s")
        print(f"Fit RMSE on DST: {v_rmse_mv:.2f} mV (M={m_eff*1000:.1f} mV)")

        results["temps_measured"].append(t_meas)
        results["nominal_capacity_ah"][t_key] = round(float(ocv.c20_capacity_ah), 4)
        results["ocv_table"][t_key] = [round(float(x), 4) for x in v_ocv_mono]
        results["r0_table"][t_key] = round(float(r0), 5)
        results["r1_table"][t_key] = round(float(r1), 5)
        results["tau1_table"][t_key] = round(float(tau1), 2)
        results["r2_table"][t_key] = round(float(r2), 5)
        results["tau2_table"][t_key] = round(float(tau2), 2)
        results["m_hyst_table"][t_key] = round(float(m_eff), 5)
        results["fit_rmse_mv"][t_key] = round(v_rmse_mv, 2)

    return results

def write_profile_yaml_v2(results: dict, output_path: Path, cell_id: str, m_zero_variant: bool = False):
    t_meas_sorted = sorted(results["temps_measured"])
    c25_key = [k for k in results["nominal_capacity_ah"].keys() if abs(float(k) - 25.0) < 3.0][0]
    nom_cap = results["nominal_capacity_ah"][c25_key]

    if m_zero_variant:
        m_hyst_profile = 0.0
        m_status = "assumed"
        m_note = "Hysteresis disabled (M=0 reference variant with discharge OCV branch)"
        ocv_note = "Extracted OCV curve from C/20 discharge branch only (monotonized)"
    else:
        # Gating median half-gap
        gating_keys = [k for k in results["m_hyst_table"].keys() if 18.0 <= float(k) <= 55.0]
        gating_m = [results["m_hyst_table"][k] for k in gating_keys]
        m_hyst_profile = float(np.median(gating_m))
        m_status = "measured"
        m_note = "Plateau-median half-gap corrected for 55 mA ohmic drop across gating temperatures (Task A1)"
        ocv_note = "Extracted equilibrium OCV curve from symmetric mean of C/20 charge and discharge branches"

    profile_dict = {
        "plant": {
            "nominal_capacity_Ah": {
                "value": float(nom_cap),
                "unit": "Ah",
                "status": "measured",
                "bounds": [0.1, 500.0],
                "note": f"Measured C/20 capacity for A123 1.11 Ah LFP (APR18650M1A-class) cell {cell_id} at 25C",
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
                "note": ocv_note,
                "source": f"CALCE A123 dataset cell {cell_id}",
            },
            "r0_table_ohm": {
                "value": {str(k): v for k, v in results["r0_table"].items()},
                "unit": "Ohm",
                "status": "measured",
                "bounds": [0.0001, 0.50],
                "note": "Fitted ohmic resistance over measured temperature from DST with hysteresis in residual",
                "source": f"CALCE A123 dataset cell {cell_id}",
            },
            "r1_table_ohm": {
                "value": {str(k): v for k, v in results["r1_table"].items()},
                "unit": "Ohm",
                "status": "measured",
                "bounds": [0.00005, 0.50],
                "note": "Fitted first RC resistance from DST with hysteresis in residual",
                "source": f"CALCE A123 dataset cell {cell_id}",
            },
            "tau1_table_s": {
                "value": {str(k): v for k, v in results["tau1_table"].items()},
                "unit": "s",
                "status": "measured",
                "bounds": [0.5, 300.0],
                "note": "Fitted first RC time constant from DST with hysteresis in residual",
                "source": f"CALCE A123 dataset cell {cell_id}",
            },
            "r2_table_ohm": {
                "value": {str(k): v for k, v in results["r2_table"].items()},
                "unit": "Ohm",
                "status": "measured",
                "bounds": [0.00005, 0.50],
                "note": "Fitted second RC resistance from DST with hysteresis in residual",
                "source": f"CALCE A123 dataset cell {cell_id}",
            },
            "tau2_table_s": {
                "value": {str(k): v for k, v in results["tau2_table"].items()},
                "unit": "s",
                "status": "measured",
                "bounds": [1.0, 1200.0],
                "note": "Fitted second RC time constant from DST with hysteresis in residual",
                "source": f"CALCE A123 dataset cell {cell_id}",
            },
            "hysteresis_amplitude_v": {
                "value": round(m_hyst_profile, 5),
                "unit": "V",
                "status": m_status,
                "bounds": [0.0, 0.1],
                "note": m_note,
                "source": f"CALCE A123 dataset cell {cell_id}",
            },
            "hysteresis_gamma": {
                "value": 50.0,
                "unit": "dimensionless",
                "status": "placeholder",
                "bounds": [1.0, 500.0],
                "note": "UNIDENTIFIED: Minor-loop hysteresis rate gamma unobserved in monotonic discharges",
                "source": "Unobserved placeholder (UNIDENTIFIED)",
            },
        }
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        yaml.dump(profile_dict, f, sort_keys=False)
    print(f"Successfully wrote profile to {output_path}")

def run_identification_v2():
    profiles_dir = repo_root / "configs" / "assumptions" / "profiles"

    # 1. Primary v2 for A1-007
    res_007_v2 = fit_cell_parameters_v2("A1-007", m_zero_variant=False)
    write_profile_yaml_v2(res_007_v2, profiles_dir / "calce_a123_v2.yaml", "A1-007", m_zero_variant=False)

    # 2. Reference M=0 for A1-007
    res_007_m0 = fit_cell_parameters_v2("A1-007", m_zero_variant=True)
    write_profile_yaml_v2(res_007_m0, profiles_dir / "calce_a123_v2_m0.yaml", "A1-007", m_zero_variant=True)

    # 3. Primary v2 for A1-008
    res_008_v2 = fit_cell_parameters_v2("A1-008", m_zero_variant=False)
    write_profile_yaml_v2(res_008_v2, profiles_dir / "calce_a123_a1008_v2.yaml", "A1-008", m_zero_variant=False)

    # 4. Reference M=0 for A1-008
    res_008_m0 = fit_cell_parameters_v2("A1-008", m_zero_variant=True)
    write_profile_yaml_v2(res_008_m0, profiles_dir / "calce_a123_a1008_v2_m0.yaml", "A1-008", m_zero_variant=True)

if __name__ == "__main__":
    run_identification_v2()
