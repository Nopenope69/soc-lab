"""Unit tests for Gustave Eiffel 105 Ah LFP dataset loader (ge105_loader.py).

Tests:
1. Tolerant filename parsing (standard, French 'partiel', pseudoOCV, 'final' modifier, office lock files).
2. Skipping '~$' office lock files.
3. Current sign convention (charge positive in file -> discharge positive in repo).
4. Capacity integral comparison against dod_ah (< 0.5% tolerance).
5. Signal units (V, A, SoC in [0, 1], Ah, °C).
6. dt monotonicity and 1s resampling grid.
7. WLTC segment extraction (yields 2 segments for full file).
8. Parameter loading from batt_data.mat.
"""

from pathlib import Path
import numpy as np
import pytest

from soc.data.ge105_loader import (
    extract_pseudo_ocv,
    extract_wltc_segments,
    load_ge105_ecm_parameters,
    load_ge105_raw_mat,
    parse_ge105_filename,
)
from soc.data.registry import resolve_dataset_dir


def test_ge105_tolerant_filename_parsing():
    """Verify regex parses standard, French 'partiel', pseudoOCV, and final modifiers."""
    # Standard full
    res = parse_ge105_filename("20230825_1333_full_25C_buge388_dattes.mat")
    assert res is not None
    date, time, ptype, temp, mod, cell = res
    assert (date, time, ptype, temp, mod, cell) == ("20230825", "1333", "full", 25, None, "BUGE388")

    # French spelling 'partiel' normalized to 'partial'
    res_fr = parse_ge105_filename("20230901_1054_partiel_15C_buge389_dattes.mat")
    assert res_fr is not None
    assert res_fr[2] == "partial"
    assert res_fr[3] == 15
    assert res_fr[5] == "BUGE389"

    # pseudoOCV
    res_ocv = parse_ge105_filename("20230703_1138_pseudoOCV_25C_buge390_dattes.mat")
    assert res_ocv is not None
    assert res_ocv[2] == "pseudoOCV"
    assert res_ocv[3] == 25
    assert res_ocv[5] == "BUGE390"

    # Final modifier
    res_fin = parse_ge105_filename("20230726_0918_partial_25C_final_buge390_dattes.mat")
    assert res_fin is not None
    assert res_fin[2] == "partial"
    assert res_fin[3] == 25
    assert res_fin[4] == "final"
    assert res_fin[5] == "BUGE390"

    # Office lock files must return None
    assert parse_ge105_filename("~$20230825_1333_full_25C_buge388_dattes.mat") is None
    assert parse_ge105_filename("readme.txt") is None


def test_ge105_skip_office_lock_files(tmp_path):
    """Verify that load_ge105_raw_mat skips files starting with '~$*'."""
    fake_lock = tmp_path / "~$test_lock_file.mat"
    fake_lock.write_text("dummy")
    with pytest.raises(ValueError, match="Skipping temporary Office file"):
        load_ge105_raw_mat(fake_lock, verify_checksum=False)


def test_ge105_loader_current_sign_and_capacity_integral():
    """Verify current sign inversion and integral agreement with dod_ah."""
    try:
        base_dir = resolve_dataset_dir("gustave_eiffel_g02iye")
    except Exception:
        pytest.skip("Gustave Eiffel dataset directory not resolved")

    mat_file = base_dir / "main_extracted" / "processed_data" / "2_processed_data" / "BUGE388" / "20230825_1333_full_25C_buge388_dattes.mat"
    if not mat_file.exists():
        pytest.skip(f"Test file missing: {mat_file}")

    ts = load_ge105_raw_mat(mat_file, verify_checksum=True)

    # In raw file, discharge is negative, charge is positive.
    # In repo ts, discharge MUST be positive, charge negative.
    # During 1C discharge phase (e.g. index 100,000), ts.current_a should be +105 A
    disch_samples = ts.current_a[ts.current_a > 100.0]
    assert len(disch_samples) > 1000, "Expected positive current during discharge"

    chg_samples = ts.current_a[ts.current_a < -100.0]
    assert len(chg_samples) > 1000, "Expected negative current during charge"

    # Compare integrated current vs delta dod_ah over a continuous CC discharge cycle
    # Mode CC 1C discharge is ~3550s (indices ~15000 to ~50000)
    dt = np.diff(ts.time_s)
    dq_ah = (0.5 * (ts.current_a[:-1] + ts.current_a[1:]) * dt) / 3600.0
    d_dod = np.diff(ts.dod_ah)

    # For discharge: I_repo > 0, dod increases (d_dod > 0), so dq_ah / d_dod == +1.0
    active = np.abs(ts.current_a[:-1]) > 50.0
    ratio = dq_ah[active] / d_dod[active]
    # Median ratio must be +1.0 within 0.1%
    assert np.median(ratio) == pytest.approx(1.0, rel=1e-3)

    # Full capacity integral over first discharge phase (~103.8 Ah)
    # Check that capacity diff is <= 0.5% of nominal capacity (105 Ah * 0.005 = 0.525 Ah)
    idx_start, idx_end = 15000, 50000
    int_q = np.sum(dq_ah[idx_start:idx_end])
    delta_dod = ts.dod_ah[idx_end] - ts.dod_ah[idx_start]
    assert abs(int_q - delta_dod) <= 105.0 * 0.005


def test_ge105_loader_units_and_dt_monotonicity():
    """Verify voltage, current, soc ranges and strictly positive dt."""
    try:
        base_dir = resolve_dataset_dir("gustave_eiffel_g02iye")
    except Exception:
        pytest.skip("Gustave Eiffel dataset directory not resolved")

    mat_file = base_dir / "main_extracted" / "processed_data" / "2_processed_data" / "BUGE388" / "20230825_1333_full_25C_buge388_dattes.mat"
    if not mat_file.exists():
        pytest.skip(f"Test file missing: {mat_file}")

    ts = load_ge105_raw_mat(mat_file, verify_checksum=True)

    # Voltage range (2.0 to 3.7 V)
    assert 2.0 <= ts.voltage_v.min()
    assert ts.voltage_v.max() <= 3.7

    # SoC fractional range [0.0, 1.05]
    assert 0.0 <= ts.truth_soc.min()
    assert ts.truth_soc.max() <= 1.05

    # Temperature setpoint array
    assert np.all(ts.temperature_c == 25.0)

    # Strictly positive dt
    dt = np.diff(ts.time_s)
    assert np.all(dt > 0.0)


def test_ge105_wltc_segment_extraction():
    """Verify that a full-protocol file yields exactly two 986s WLTC segments."""
    try:
        base_dir = resolve_dataset_dir("gustave_eiffel_g02iye")
    except Exception:
        pytest.skip("Gustave Eiffel dataset directory not resolved")

    mat_file = base_dir / "main_extracted" / "processed_data" / "2_processed_data" / "BUGE388" / "20230825_1333_full_25C_buge388_dattes.mat"
    if not mat_file.exists():
        pytest.skip(f"Test file missing: {mat_file}")

    ts = load_ge105_raw_mat(mat_file, verify_checksum=True)
    segs = extract_wltc_segments(ts, resample_1s=True)

    assert len(segs) == 2, f"Expected 2 WLTC segments, got {len(segs)}"
    seg1, seg2 = segs

    # Segment 1: ~90% SOC, ~986 s duration
    assert seg1.target_soc_pct == 90.0
    assert abs(seg1.duration_s - 985.0) <= 2.0
    assert 0.85 <= np.mean(seg1.truth_soc) <= 0.95
    assert seg1.is_resampled_1s

    # Segment 2: ~50% SOC, ~986 s duration
    assert seg2.target_soc_pct == 50.0
    assert abs(seg2.duration_s - 985.0) <= 2.0
    assert 0.45 <= np.mean(seg2.truth_soc) <= 0.55
    assert seg2.is_resampled_1s


def test_ge105_pseudo_ocv_extraction():
    """Verify pseudo-OCV extraction from full-protocol file."""
    try:
        base_dir = resolve_dataset_dir("gustave_eiffel_g02iye")
    except Exception:
        pytest.skip("Gustave Eiffel dataset directory not resolved")

    mat_file = base_dir / "main_extracted" / "processed_data" / "2_processed_data" / "BUGE388" / "20230825_1333_full_25C_buge388_dattes.mat"
    if not mat_file.exists():
        pytest.skip(f"Test file missing: {mat_file}")

    ts = load_ge105_raw_mat(mat_file, verify_checksum=True)
    pocv = extract_pseudo_ocv(ts)
    assert pocv is not None
    assert pocv.cell_id == "BUGE388"
    assert pocv.temperature_c == 25.0
    assert len(pocv.discharge_v) > 1000
    assert len(pocv.charge_v) > 1000
    assert 100.0 <= pocv.c15_capacity_ah <= 106.0


def test_ge105_ecm_parameters_loading():
    """Verify loading 2RC ECM parameters from batt_data.mat."""
    params = load_ge105_ecm_parameters("BUGE388", 25)
    assert params["cell_id"] == "BUGE388"
    assert params["temperature_c"] == 25
    assert params["r0"].shape == (10, 6)
    assert params["r1"].shape == (10, 6)
    assert params["c1"].shape == (10, 6)
    assert params["r2"].shape == (10, 6)
    assert params["c2"].shape == (10, 6)
    assert "ocv" in params
    assert len(params["ocv"]) == 101
