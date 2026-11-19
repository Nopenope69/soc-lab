"""Unit tests for UConn REIL LFP/Gr Battery Aging Dataset Loader (Dataset 5).

Verifies:
- Manifest hash verification (Rule R2).
- Skipping '~$' and '._' temporary files.
- Sign convention canonicalization: I_repo = -I_file (discharge positive).
- Units (V, A, s, Ah).
- Slowpulse segmentation (30s C/5 + 10s 1C + 60s rest).
- Exclusion of missing labels (no defaulting to 1.0).
- Registry integration.
"""

from pathlib import Path
import tempfile
import numpy as np
import pandas as pd
import pytest

from soc.data.registry import (
    ChecksumMismatchError,
    DatasetMissingError,
    get_dataset_loader,
    load_uconn_reil_dataset5,
)
from soc.data.uconn_loader import (
    CUTOFF_DISCHARGE_V,
    NOMINAL_CAPACITY_AH,
    UconnCellData,
    _segment_slowpulse,
    get_condition_group,
    get_uconn_rpt_dir,
    list_uconn_cell_files,
    load_uconn_cell_data,
    verify_uconn_manifest,
)


def test_condition_group_mapping():
    """Verify condition group mapping for 64 cells across 11 groups."""
    assert get_condition_group(2) == 1
    assert get_condition_group(7) == 1
    assert get_condition_group(8) == 2
    assert get_condition_group(13) == 2
    assert get_condition_group(56) == 10
    assert get_condition_group(61) == 10
    assert get_condition_group(62) == 11
    assert get_condition_group(65) == 11

    with pytest.raises(ValueError):
        get_condition_group(1)
    with pytest.raises(ValueError):
        get_condition_group(66)


def test_manifest_verification_on_real_data():
    """Verify real UConn manifest integrity against $SOC_DATA_DIR."""
    manifest = verify_uconn_manifest()
    assert manifest.dataset_id == "uconn_reil_dataset5"
    assert manifest.licence == "CC BY 4.0"
    assert len(manifest.expected_hashes) >= 2


def test_manifest_checksum_mismatch_raised():
    """Verify ChecksumMismatchError is raised if file is corrupted (Rule R2)."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        # Create a fake corrupt rpt_data.zip
        (tmp_path / "rpt_data.zip").write_text("corrupted content")
        (tmp_path / "README_Uconn.txt").write_text("fake readme")

        with pytest.raises(ChecksumMismatchError):
            verify_uconn_manifest(data_dir=tmp_path)


def test_temporary_file_skip():
    """Verify '~$' and '._' files are skipped when discovering cell partitions."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        # Mock extracted/rpt_data structure
        extracted_dir = tmp_path / "extracted" / "rpt_data"
        extracted_dir.mkdir(parents=True)

        valid_part0 = extracted_dir / "rpt_cell_02_part0.csv"
        valid_part1 = extracted_dir / "rpt_cell_02_part1.csv"
        lock_file = extracted_dir / "~$rpt_cell_02_part0.csv"
        dot_file = extracted_dir / "._rpt_cell_02_part0.csv"

        valid_part0.touch()
        valid_part1.touch()
        lock_file.touch()
        dot_file.touch()

        found = [p.resolve() for p in list_uconn_cell_files("02", data_dir=tmp_path)]
        assert len(found) == 2
        assert valid_part0.resolve() in found
        assert valid_part1.resolve() in found
        assert lock_file.resolve() not in found
        assert dot_file.resolve() not in found


def test_sign_canonicalization_and_pulse_segmentation():
    """Verify sign canonicalization (I_repo = -I_file) and pulse segmentation."""
    # Synthetic DataFrame simulating raw file logging
    # In raw file: CC Chg has positive current (+0.24A, +1.20A)
    # Repo standard requires I_repo = -I_file (< 0 for charge)
    times = np.arange(0, 101, 1.0)
    currents_raw = np.zeros_like(times)
    # 30s C/5 charge (+0.24A in raw file)
    currents_raw[0:31] = 0.24
    # 10s 1C charge (+1.20A in raw file)
    currents_raw[31:42] = 1.20
    # 60s Rest (0.0A)
    currents_raw[42:101] = 0.0

    voltages = np.zeros_like(times)
    voltages[0:31] = 3.25
    voltages[31:42] = 3.30
    voltages[42:101] = 3.26

    step_nums = np.zeros_like(times, dtype=int)
    step_nums[0:31] = 4
    step_nums[31:42] = 5
    step_nums[42:101] = 6

    df = pd.DataFrame({
        "Time (s)": times,
        "Voltage (V)": voltages,
        "Current (A)": currents_raw,
        "Step Number": step_nums,
    })

    pulse = _segment_slowpulse(df, cell_id="02", group_id=1, rpt_num=0, pulse_type="chg", soc=20.0)
    assert pulse is not None
    assert pulse.nominal_soc == 20.0
    assert pulse.pulse_type == "chg"
    # Repo sign check: charging current must be negative in repo convention
    assert pulse.current_a[0] == pytest.approx(-0.24, abs=1e-3)
    assert pulse.i_step1_mean_a == pytest.approx(-0.24, abs=1e-3)
    assert pulse.i_step2_mean_a == pytest.approx(-1.20, abs=1e-3)
    assert pulse.v_start_v == pytest.approx(3.25, abs=1e-3)
    assert pulse.v_10s_v == pytest.approx(3.30, abs=1e-3)
    assert pulse.duration_s == pytest.approx(100.0, abs=1e-2)
    # Pulse resistance: delta_v / delta_i
    # delta_v = 3.30 - 3.25 = 0.05 V; delta_i = -1.20 - (-0.24) = -0.96 A
    # r = 0.05 / 0.96 = 0.05208 Ohm
    assert pulse.r_pulse_10s_ohm == pytest.approx(0.05 / 0.96, abs=1e-4)


def test_missing_labels_exclusion_no_defaulting():
    """Verify Rule R2: missing ref_dchg results in None SOH_C, never defaulted to 1.0."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        rpt_dir = tmp_path / "extracted" / "rpt_data"
        rpt_dir.mkdir(parents=True)

        # Create synthetic CSV with RPT 0 (valid) and RPT 1 (missing ref_dchg)
        # RPT 0 has ref_dchg
        rows = [
            # RPT 0 ref_dchg
            {"RPT Number": 0, "Step Number": 28, "State": "CC DChg", "Time (s)": 0.0, "Voltage (V)": 3.4, "Current (A)": -0.4, "Capacity (Ah)": 0.0, "Segment Key": "ref_dchg", "Pulse Type": "-", "Pulse SOC": np.nan, "Date (yyyy.mm.dd hh.mm.ss)": "2025.01.01 00.00.00", "Num Cycles": 0.0},
            {"RPT Number": 0, "Step Number": 28, "State": "CC DChg", "Time (s)": 1000.0, "Voltage (V)": 2.0, "Current (A)": -0.4, "Capacity (Ah)": 1.20, "Segment Key": "ref_dchg", "Pulse Type": "-", "Pulse SOC": np.nan, "Date (yyyy.mm.dd hh.mm.ss)": "2025.01.01 00.00.00", "Num Cycles": 0.0},
            # RPT 1 lacks ref_dchg (only rest)
            {"RPT Number": 1, "Step Number": 1, "State": "Rest", "Time (s)": 2000.0, "Voltage (V)": 3.3, "Current (A)": 0.0, "Capacity (Ah)": 0.0, "Segment Key": "-", "Pulse Type": "-", "Pulse SOC": np.nan, "Date (yyyy.mm.dd hh.mm.ss)": "2025.01.05 00.00.00", "Num Cycles": 100.0},
        ]
        df = pd.DataFrame(rows)
        csv_file = rpt_dir / "rpt_cell_02_part0.csv"
        df.to_csv(csv_file, index=False)

        cell_data = load_uconn_cell_data("02", data_dir=tmp_path)
        assert cell_data.c0_ah == pytest.approx(1.20, abs=1e-3)
        assert cell_data.rpts[0].soh_c == pytest.approx(1.0, abs=1e-3)
        # RPT 1 must be None, NOT defaulted to 1.0!
        assert cell_data.rpts[1].capacity_ah is None
        assert cell_data.rpts[1].soh_c is None


def test_real_cell_loading():
    """Verify loading real Cell 02 from extracted dataset."""
    cell_data = load_uconn_cell_data("02")
    assert isinstance(cell_data, UconnCellData)
    assert cell_data.cell_id == "02"
    assert cell_data.group_id == 1
    assert cell_data.c0_ah == pytest.approx(1.212577, abs=1e-4)
    assert cell_data.num_rpts >= 30

    # Verify RPT 0 pulses
    rpt0 = cell_data.rpts[0]
    assert rpt0.soh_c == pytest.approx(1.0, abs=1e-6)
    assert ("dchg", 20.0) in rpt0.pulses
    assert ("dchg", 50.0) in rpt0.pulses
    assert ("dchg", 90.0) in rpt0.pulses
    assert ("chg", 50.0) in rpt0.pulses

    p_dchg50 = rpt0.pulses[("dchg", 50.0)]
    assert p_dchg50.duration_s == pytest.approx(100.0, abs=1.0)
    assert p_dchg50.r_pulse_10s_ohm > 0.01 and p_dchg50.r_pulse_10s_ohm < 0.10

    # SOH_R at RPT 0 must be exactly 1.0
    assert cell_data.get_soh_r(0, pulse_type="dchg", soc=50.0) == pytest.approx(1.0, abs=1e-6)


def test_registry_integration():
    """Verify loader registration in LOADER_REGISTRY."""
    loader_fn = get_dataset_loader("uconn_reil_dataset5")
    info = loader_fn(verify_checksums=False)
    assert info["dataset_id"] == "uconn_reil_dataset5"
    assert "load_cell_data" in info
    assert "load_dataset" in info
    assert "verify_manifest" in info
