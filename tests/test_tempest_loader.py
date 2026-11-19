"""Unit tests for TEMPEST 280 Ah Prismatic LFP Cell Loader.

Tests:
1. Sign convention: repository convention is DISCHARGE POSITIVE (I_repo = -I_file).
2. Units: time in s, current in A, voltage in V, temperature in K and C (T_c = T_k - 273.15).
3. Step segmentation: HPPC pulse segmentation yields 10 discharge and 10 charge pulses across expected SOC grid.
4. '~$' skip: files with prefix '~$' raise ValueError.
5. Hash verification: files verified against data/manifests/tempest_zenodo.sha256.
6. Header normalization: 15C_hppc.csv loaded identically despite non-standard raw headers.
7. Registry integration: registry functions load tempest_zenodo with verified facts.
"""

from pathlib import Path
import pytest
import numpy as np

from soc.data.registry import (
    ChecksumMismatchError,
    get_dataset_loader,
    get_manifest_path,
    get_soc_data_dir,
    resolve_dataset_dir,
)
from soc.data.tempest_loader import (
    TEMPEST_DATASET_ID,
    VALID_TEMPERATURES,
    NOMINAL_CAPACITY_AH,
    TempestTimeSeries,
    TempestCapacityTest,
    TempestHppcTest,
    get_tempest_dir,
    load_tempest_capacity,
    load_tempest_hppc,
    load_tempest_lic_capacity,
    load_tempest_lic_entropy,
    load_tempest_lic_hppc,
    load_tempest_raw_csv,
    segment_tempest_hppc_pulses,
    verify_tempest_manifest,
)


@pytest.fixture(scope="module")
def tempest_data_dir() -> Path:
    """Fixture providing path to TEMPEST dataset root."""
    d = get_tempest_dir()
    if not d.exists() or not (d / "25C_capacity.csv").exists():
        pytest.skip(f"TEMPEST data directory not found at {d}")
    return d


def test_tempest_loader_tilde_skip():
    """Verify loader rejects temporary Office lock files starting with '~$'."""
    with pytest.raises(ValueError, match="Skipping temporary Office file"):
        load_tempest_raw_csv(Path("/fake/path/~$25C_capacity.csv"), verify_checksum=False)


def test_tempest_loader_hash_verification(tempest_data_dir: Path):
    """Verify SHA-256 hash manifest verification passes on real data and fails on corruption."""
    # 1. Manifest audit on real files
    all_valid, errors = verify_tempest_manifest()
    assert all_valid, f"Manifest verification failed with errors: {errors}"
    assert len(errors) == 0

    # 2. Corrupt hash triggers ChecksumMismatchError
    target_file = tempest_data_dir / "25C_capacity.csv"
    from soc.data.registry import DatasetManifest
    fake_manifest = DatasetManifest(
        dataset_id=TEMPEST_DATASET_ID,
        source_url="UNVERIFIED",
        doi="UNVERIFIED",
        licence="UNVERIFIED",
        version="UNVERIFIED",
        download_date="UNVERIFIED",
        expected_hashes={"25C_capacity.csv": "0" * 64},
    )
    with pytest.raises(ChecksumMismatchError, match="SHA-256 mismatch"):
        load_tempest_raw_csv(target_file, verify_checksum=True, manifest=fake_manifest)


def test_tempest_loader_sign_convention(tempest_data_dir: Path):
    """Verify repository sign convention: DISCHARGE POSITIVE (I_repo = -I_file)."""
    ts = load_tempest_raw_csv(tempest_data_dir / "25C_capacity.csv", verify_checksum=True)

    # In raw file: CC charge has Current_A ~ +28.0 A, CC discharge has Current_A ~ -28.0 A
    # In repo convention: CC discharge must have current_a ~ +28.0 A, CC charge must have current_a ~ -28.0 A
    dis_indices = np.where(ts.current_a > 20.0)[0]
    chg_indices = np.where(ts.current_a < -20.0)[0]

    assert len(dis_indices) > 0, "No discharge points detected"
    assert len(chg_indices) > 0, "No charge points detected"

    # During discharge (repo current > 0), voltage should decline
    v_dis_start = ts.voltage_v[dis_indices[0]]
    v_dis_end = ts.voltage_v[dis_indices[-1]]
    assert v_dis_start > v_dis_end, f"During discharge, voltage should decline: start {v_dis_start}V <= end {v_dis_end}V"
    assert v_dis_end <= 2.52, f"Discharge cutoff should terminate near 2.50V, got {v_dis_end}V"

    # During charge (repo current < 0), voltage should rise
    v_chg_start = ts.voltage_v[chg_indices[0]]
    v_chg_end = ts.voltage_v[chg_indices[-1]]
    assert v_chg_start < v_chg_end, f"During charge, voltage should rise: start {v_chg_start}V >= end {v_chg_end}V"
    assert v_chg_end >= 3.64, f"Charge cutoff should reach near 3.65V, got {v_chg_end}V"


def test_tempest_loader_units(tempest_data_dir: Path):
    """Verify physical units: time (s), current (A), voltage (V), temperature (K and C)."""
    ts = load_tempest_raw_csv(tempest_data_dir / "25C_capacity.csv", verify_checksum=True)

    # Time in seconds: monotonic increasing, dt ~ 1.0 s
    dt = np.diff(ts.time_s)
    assert np.all(dt > 0), "Time must be strictly monotonic"
    assert np.median(dt) == pytest.approx(1.0, rel=1e-3)

    # Current in Amperes
    assert np.max(np.abs(ts.current_a)) < 35.0, "Capacity test current magnitude should not exceed ~28 A"

    # Voltage in Volts within LFP electrochemical range
    assert np.min(ts.voltage_v) >= 2.45
    assert np.max(ts.voltage_v) <= 3.70

    # Temperature conversion: T_C = T_K - 273.15
    np.testing.assert_allclose(ts.temperature_c, ts.temperature_k - 273.15, atol=1e-5)
    # At 25 C nominal chamber setpoint, surface temperature should be in [24, 30] C
    assert 24.0 <= np.mean(ts.temperature_c) <= 30.0


def test_tempest_loader_column_normalization_15c(tempest_data_dir: Path):
    """Verify 15C_hppc.csv raw channel headers are normalized cleanly."""
    ts_15 = load_tempest_raw_csv(tempest_data_dir / "15C_hppc.csv", verify_checksum=True)
    ts_25 = load_tempest_raw_csv(tempest_data_dir / "25C_hppc.csv", verify_checksum=True)

    # Both must have the same dataclass fields populated
    assert ts_15.time_s.ndim == 1 and len(ts_15.time_s) > 300000
    assert ts_15.current_a.ndim == 1
    assert ts_15.voltage_v.ndim == 1
    assert ts_15.temperature_c.ndim == 1
    assert ts_15.temperature_k.ndim == 1

    # Surface temperature at 15 C chamber should be around 15-20 C
    assert 14.0 <= np.mean(ts_15.temperature_c) <= 20.0
    assert ts_15.nominal_temperature_c == 15
    assert ts_25.nominal_temperature_c == 25


def test_tempest_loader_capacity_integration(tempest_data_dir: Path):
    """Verify discharge capacity calculation matches LIC_capacity_analysis.csv."""
    lic_cap_df = load_tempest_lic_capacity()
    assert len(lic_cap_df) == 5

    for t_nom in VALID_TEMPERATURES:
        cap_test = load_tempest_capacity(t_nom, verify_checksum=True)
        assert cap_test.nominal_temperature_c == t_nom
        assert 295.0 < cap_test.discharge_ah < 305.0
        assert cap_test.c_rate == pytest.approx(0.1, abs=0.01)

        expected_ah = float(lic_cap_df[lic_cap_df["Temperature_C"] == t_nom]["Capacity_Ah"].iloc[0])
        # Integration should match within 0.01 Ah
        assert cap_test.discharge_ah == pytest.approx(expected_ah, abs=0.01)


def test_tempest_loader_hppc_step_segmentation(tempest_data_dir: Path):
    """Verify HPPC step segmentation extracts 10 discharge and 10 charge pulses across SOC grid."""
    hppc_test = load_tempest_hppc(25, verify_checksum=True)

    assert len(hppc_test.pulses) == 20
    assert len(hppc_test.discharge_pulses) == 10
    assert len(hppc_test.charge_pulses) == 10
    assert hppc_test.soc_points == [0.95, 0.85, 0.75, 0.65, 0.55, 0.45, 0.35, 0.25, 0.15, 0.05]

    for p in hppc_test.discharge_pulses:
        assert p.pulse_type == "discharge"
        assert p.duration_s == pytest.approx(10.0, abs=0.2)
        # In repo convention, discharge current is positive (~+140 A)
        assert p.mean_current_a == pytest.approx(140.0, abs=2.0)
        assert p.delta_v_10s < 0.0  # voltage drops during discharge
        assert 0.0002 < p.r_10s_ohm < 0.0010  # ~0.4 to 0.8 mOhm for 280 Ah LFP

    for p in hppc_test.charge_pulses:
        assert p.pulse_type == "charge"
        assert p.duration_s == pytest.approx(10.0, abs=0.2)
        # In repo convention, charge current is negative (~-140 A)
        assert p.mean_current_a == pytest.approx(-140.0, abs=2.0)
        assert p.delta_v_10s > 0.0  # voltage rises during charge
        assert 0.0002 < p.r_10s_ohm < 0.0010


def test_tempest_loader_analysis_files():
    """Verify reading of pre-computed LIC analysis files."""
    df_cap = load_tempest_lic_capacity()
    df_hppc = load_tempest_lic_hppc()
    df_entropy = load_tempest_lic_entropy()

    assert len(df_cap) == 5
    assert len(df_hppc) == 50  # 5 temps x 10 SOCs
    assert len(df_entropy) == 5  # 5 SOCs (0.1, 0.3, 0.5, 0.7, 0.9)

    assert set(df_hppc.columns) == {"Temperature_C", "SoC", "R0_Ohm", "R1_Ohm", "C1_F"}


def test_tempest_registry_loader():
    """Verify registry loader returns populated dictionary with loader methods."""
    loader_fn = get_dataset_loader("tempest_zenodo")
    res = loader_fn(verify_checksums=True)
    assert res["dataset_id"] == "tempest_zenodo"
    assert "load_capacity" in res
    assert "load_hppc" in res
    assert "load_lic_capacity" in res
