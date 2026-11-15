"""Unit tests for calibration contract and calibration exporter."""

import math
from pathlib import Path
import pytest

from deliverable.calibration import CellCalibration, default_calce_calibration
from deliverable.bms_soc_ref import BmsSocEstimatorRef
from scripts.export_calibration import export_calce_calibration, export_flexipod_calibration
from soc.assumptions.loader import load_assumptions
from soc.estimators.base import ParamSet


def _get_table_val(tbl, t_float):
    k1 = f"{t_float:.1f}"
    k2 = str(t_float)
    if k1 in tbl:
        return tbl[k1]
    if k2 in tbl:
        return tbl[k2]
    raise KeyError(f"Key {t_float} not found in table with keys {list(tbl.keys())}")


def test_calce_calibration_matches_paramset():
    """Verify research ParamSet and calce_a123_v4.json agree on every single parameter."""
    assumptions, _, _ = load_assumptions(profile="calce_a123_v4")
    paramset = ParamSet.from_assumptions(assumptions, matched=True)
    calib = CellCalibration.from_json(Path("deliverable/calibrations/calce_a123_v4.json"))

    assert calib.calibration_id == "calce_a123_v4"
    assert calib.validation_status == "DEVELOPMENT_VALIDATED_CALCE_20_50C"
    assert calib.nominal_capacity_ah == pytest.approx(paramset.nominal_capacity_ah)
    assert calib.coulombic_efficiency == pytest.approx(paramset.coulombic_efficiency)
    assert calib.hysteresis_gamma == pytest.approx(paramset.hysteresis_gamma)

    assert list(calib.temperatures_c) == [float(t) for t in paramset.temperatures_c]
    assert list(calib.soc_grid) == [float(s) for s in paramset.soc_grid]

    # Verify OCV table
    for t_str, row in calib.ocv_table.items():
        t_val = float(t_str)
        ref_row = _get_table_val(paramset.ocv_table, t_val)
        assert len(row) == len(ref_row)
        for val, ref_val in zip(row, ref_row):
            assert val == pytest.approx(ref_val, abs=1e-6)

    # Verify impedance tables
    for t_str, r0 in calib.r0_table.items():
        assert r0 == pytest.approx(_get_table_val(paramset.r0_table, float(t_str)))
    for t_str, r1 in calib.r1_table.items():
        assert r1 == pytest.approx(_get_table_val(paramset.r1_table, float(t_str)))
    for t_str, tau1 in calib.tau1_table.items():
        assert tau1 == pytest.approx(_get_table_val(paramset.tau1_table, float(t_str)))
    for t_str, r2 in calib.r2_table.items():
        assert r2 == pytest.approx(_get_table_val(paramset.r2_table, float(t_str)))
    for t_str, tau2 in calib.tau2_table.items():
        assert tau2 == pytest.approx(_get_table_val(paramset.tau2_table, float(t_str)))


def test_flexipod_calibration_matches_paramset():
    """Verify research ParamSet and flexipod_100ah_v1.json agree on every single parameter."""
    assumptions, _, _ = load_assumptions(profile="flexipod_100ah_v1")
    paramset = ParamSet.from_assumptions(assumptions, matched=True)
    calib = CellCalibration.from_json(Path("deliverable/calibrations/flexipod_100ah_v1.json"))

    assert calib.calibration_id == "flexipod_100ah_v1"
    assert "NOT_VALIDATED" in calib.validation_status
    assert calib.nominal_capacity_ah == pytest.approx(paramset.nominal_capacity_ah)
    assert calib.hysteresis_gamma == pytest.approx(paramset.hysteresis_gamma)

    assert list(calib.temperatures_c) == [float(t) for t in paramset.temperatures_c]
    assert list(calib.soc_grid) == [float(s) for s in paramset.soc_grid]

    for t_str, row in calib.ocv_table.items():
        t_val = float(t_str)
        ref_row = _get_table_val(paramset.ocv_table, t_val)
        assert len(row) == len(ref_row)
        for val, ref_val in zip(row, ref_row):
            assert val == pytest.approx(ref_val, abs=1e-6)


def test_calibration_strict_validation():
    """Verify strict validation catches corrupted calibration entries."""
    cal = default_calce_calibration()

    # Non-monotonic temperature grid
    bad_temps = list(cal.temperatures_c)
    bad_temps[1] = bad_temps[0] - 1.0
    bad_cal = CellCalibration(
        **{**cal.__dict__, "temperatures_c": bad_temps}
    )
    with pytest.raises(ValueError, match="temperatures_c must be strictly increasing"):
        bad_cal.validate()

    # Negative nominal capacity
    bad_cap_cal = CellCalibration(
        **{**cal.__dict__, "nominal_capacity_ah": -1.0}
    )
    with pytest.raises(ValueError, match="nominal_capacity_ah must be positive"):
        bad_cap_cal.validate()

    # Mismatched Q(T) table lengths
    bad_q_cal = CellCalibration(
        **{**cal.__dict__, "q_table_ah": cal.q_table_ah[:-1]}
    )
    with pytest.raises(ValueError, match="q_table_temps_c and q_table_ah length mismatch"):
        bad_q_cal.validate()


def test_flexipod_capacity_scaling_at_100a():
    """Verify FlexiPod 100Ah calibration at 100 A for 60 s drops SOC by ~1.75 pp (~0.0175), not 100+ pp."""
    calib = CellCalibration.from_json(Path("deliverable/calibrations/flexipod_100ah_v1.json"))
    est = BmsSocEstimatorRef(calib)
    est.reset(0.90, soc_std=0.01)

    # Discharge at 100 A for 60 seconds (60 steps of 1.0 s)
    # Using missing voltage (math.nan) to isolate pure Coulomb counting / time propagation
    for _ in range(60):
        est.step(v=math.nan, i=100.0, temp_c=25.0, dt=1.0)

    delta_soc = 0.90 - est.x[0]
    # Expected: 100 A * 60 s = 6000 As = 1.6667 Ah / 95.15 Ah ~ 0.017516 fraction (~1.75 pp)
    assert 0.016 <= delta_soc <= 0.019, f"Delta SOC was {delta_soc}, expected ~0.0175"
    assert est.x[0] > 0.85, f"SOC crashed to {est.x[0]} (indicating 1.06 Ah pack size!)"

