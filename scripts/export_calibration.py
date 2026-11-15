#!/usr/bin/env python3
"""Export research ParamSet calibrations to standard standalone JSON format."""

import copy
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT))

import numpy as np

from deliverable.calibration import CellCalibration
from soc.assumptions.loader import load_assumptions
from soc.estimators.base import ParamSet

# Baseline Q(T) and M(T) anchors for CALCE A123
CALCE_Q_REF = 1.0635616695823449
CALCE_M_REF = 0.02155

CALCE_TEMPS_C = [20.0, 25.0, 30.0, 40.0, 50.0]
CALCE_Q_TABLE_AH = [
    1.065214687790664,
    1.0635616695823449,
    1.0730061548855323,
    1.0801900610401025,
    1.0809567995408316,
]
CALCE_M_TABLE_V = [
    0.02701,
    0.01719,
    0.02436,
    0.02155,
    0.01988,
]


def export_calce_calibration() -> CellCalibration:
    assumptions, _, _ = load_assumptions(profile="calce_a123_v4")
    p = ParamSet.from_assumptions(assumptions, matched=True)

    # Format tables with string keys matching temperatures_c
    ocv_table = {f"{float(k):.1f}": [float(v) for v in vals] for k, vals in p.ocv_table.items()}
    r0_table = {f"{float(k):.1f}": float(v) for k, v in p.r0_table.items()}
    r1_table = {f"{float(k):.1f}": float(v) for k, v in p.r1_table.items()}
    tau1_table = {f"{float(k):.1f}": float(v) for k, v in p.tau1_table.items()}
    r2_table = {f"{float(k):.1f}": float(v) for k, v in p.r2_table.items()}
    tau2_table = {f"{float(k):.1f}": float(v) for k, v in p.tau2_table.items()}

    cal = CellCalibration(
        calibration_id="calce_a123_v4",
        schema_version="1.0",
        validation_status="DEVELOPMENT_VALIDATED_CALCE_20_50C",
        temperatures_c=[float(t) for t in p.temperatures_c],
        soc_grid=[float(s) for s in p.soc_grid],
        ocv_table=ocv_table,
        r0_table=r0_table,
        r1_table=r1_table,
        tau1_table=tau1_table,
        r2_table=r2_table,
        tau2_table=tau2_table,
        q_table_temps_c=CALCE_TEMPS_C,
        q_table_ah=CALCE_Q_TABLE_AH,
        m_table_temps_c=CALCE_TEMPS_C,
        m_table_v=CALCE_M_TABLE_V,
        nominal_capacity_ah=float(p.nominal_capacity_ah),
        coulombic_efficiency=float(p.coulombic_efficiency),
        hysteresis_gamma=float(p.hysteresis_gamma),
        process_noise_q_soc=2.0e-09,
        process_noise_q_rc=1.1198164932559382e-05,
        process_noise_q_hysteresis=0.00017150882346504795,
        measurement_noise_r_v=0.0008610323423725228,
        e4_rls_forgetting_factor=0.9990,
        rls_di_threshold_a=1.0,
        rls_theta_min=0.5,
        rls_theta_max=2.0,
        e5_slope_ref=0.20,
        e5_cap_plateau=2.0e-05,
        e5_cap_knee=0.01,
        e5_sigma_ocv_model_v=0.02,
        initial_soc_std=0.10,
        initial_rc_current_std_a=0.10,
        initial_hysteresis_std=0.10,
        temp_min_c=20.0,
        temp_max_c=50.0,
        voltage_min_v=2.0,
        voltage_max_v=3.7,
        current_min_a=-20.0,
        current_max_a=50.0,
    )
    cal.validate()
    return cal


def export_flexipod_calibration() -> CellCalibration:
    assumptions, _, _ = load_assumptions(profile="flexipod_100ah_v1")
    p = ParamSet.from_assumptions(assumptions, matched=True)

    ocv_table = {f"{float(k):.1f}": [float(v) for v in vals] for k, vals in p.ocv_table.items()}
    r0_table = {f"{float(k):.1f}": float(v) for k, v in p.r0_table.items()}
    r1_table = {f"{float(k):.1f}": float(v) for k, v in p.r1_table.items()}
    tau1_table = {f"{float(k):.1f}": float(v) for k, v in p.tau1_table.items()}
    r2_table = {f"{float(k):.1f}": float(v) for k, v in p.r2_table.items()}
    tau2_table = {f"{float(k):.1f}": float(v) for k, v in p.tau2_table.items()}

    temps_c = [float(t) for t in p.temperatures_c]
    q_scale = float(p.nominal_capacity_ah) / CALCE_Q_REF
    m_scale = float(p.hysteresis_amplitude_v) / CALCE_M_REF

    # Compute scheduled Q(T) and M(T) matching e7v3.py scaling logic
    q_table_ah = [float(np.interp(t, CALCE_TEMPS_C, CALCE_Q_TABLE_AH) * q_scale) for t in temps_c]
    m_table_v = [float(np.interp(t, CALCE_TEMPS_C, CALCE_M_TABLE_V) * m_scale) for t in temps_c]

    cal = CellCalibration(
        calibration_id="flexipod_100ah_v1",
        schema_version="1.0",
        validation_status="NOT_VALIDATED: open-loop model gate FAIL",
        temperatures_c=temps_c,
        soc_grid=[float(s) for s in p.soc_grid],
        ocv_table=ocv_table,
        r0_table=r0_table,
        r1_table=r1_table,
        tau1_table=tau1_table,
        r2_table=r2_table,
        tau2_table=tau2_table,
        q_table_temps_c=temps_c,
        q_table_ah=q_table_ah,
        m_table_temps_c=temps_c,
        m_table_v=m_table_v,
        nominal_capacity_ah=float(p.nominal_capacity_ah),
        coulombic_efficiency=float(p.coulombic_efficiency),
        hysteresis_gamma=float(p.hysteresis_gamma),
        process_noise_q_soc=2.0e-09,
        process_noise_q_rc=1.1198164932559382e-05,
        process_noise_q_hysteresis=0.00017150882346504795,
        measurement_noise_r_v=0.0008610323423725228,
        e4_rls_forgetting_factor=0.9990,
        rls_di_threshold_a=1.0,
        rls_theta_min=0.5,
        rls_theta_max=2.0,
        e5_slope_ref=0.20,
        e5_cap_plateau=2.0e-05,
        e5_cap_knee=0.01,
        e5_sigma_ocv_model_v=0.02,
        initial_soc_std=0.10,
        initial_rc_current_std_a=0.10,
        initial_hysteresis_std=0.10,
        temp_min_c=5.0,
        temp_max_c=35.0,
        voltage_min_v=2.0,
        voltage_max_v=3.65,
        current_min_a=-100.0,
        current_max_a=200.0,
    )
    cal.validate()
    return cal


def main():
    calibrations_dir = REPO_ROOT / "deliverable" / "calibrations"
    calibrations_dir.mkdir(parents=True, exist_ok=True)

    calce_cal = export_calce_calibration()
    calce_path = calibrations_dir / "calce_a123_v4.json"
    calce_cal.to_json(calce_path)
    print(f"Exported CALCE calibration: {calce_path} (sha256: {calce_cal.sha256()[:16]}...)")

    flex_cal = export_flexipod_calibration()
    flex_path = calibrations_dir / "flexipod_100ah_v1.json"
    flex_cal.to_json(flex_path)
    print(f"Exported FlexiPod calibration: {flex_path} (sha256: {flex_cal.sha256()[:16]}...)")


if __name__ == "__main__":
    main()
