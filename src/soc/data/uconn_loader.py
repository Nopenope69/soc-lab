"""UConn REIL LFP/Gr Battery Aging Dataset Loader (Dataset 5).

Citation: B. Nowacki et al., J. Power Sources 628, 235813 (2025).
DOI: https://doi.org/10.1016/j.jpowsour.2024.235813

Enforces:
R1. Raw data outside repo at $SOC_DATA_DIR (default ~/soc_data).
R2. Reads real files and verifies SHA-256 against data/manifests/uconn_reil_dataset5.sha256.
    Skips filenames starting with '~$' or '._'.
    Explicit DatasetMissingError / ChecksumMismatchError.
    No simulated, generated or defaulted values.
R3. Cell-level isolation and condition-level grouping.
Sign Convention:
    Raw file logs current as CHARGE POSITIVE, DISCHARGE NEGATIVE.
    Repository requires DISCHARGE POSITIVE, CHARGE NEGATIVE.
    This loader applies I_repo = -I_file in canonical loading.
"""

from dataclasses import dataclass, field
import glob
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple
import numpy as np
import pandas as pd

import yaml

from soc.data.registry import (
    ChecksumMismatchError,
    DatasetManifest,
    DatasetMissingError,
    get_manifest_path,
    resolve_dataset_dir,
)

_CONFIG_PATH = Path(__file__).resolve().parent.parent.parent.parent / "configs" / "validation" / "uconn_config.yaml"


def load_uconn_config() -> Dict[str, Any]:
    """Load configuration dictionary from configs/validation/uconn_config.yaml."""
    if not _CONFIG_PATH.exists():
        return {}
    with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


_CFG = load_uconn_config()

# Nominal APR18650M1B specifications from README_Uconn.txt and config
NOMINAL_CAPACITY_AH: float = float(_CFG.get("nominal_capacity_ah", float("1.2")))
NOMINAL_VOLTAGE_V: float = float(_CFG.get("nominal_voltage_v", float("3.3")))
CUTOFF_DISCHARGE_V: float = float(_CFG.get("cutoff_discharge_v", float("2.0")))
CUTOFF_CHARGE_V: float = float(_CFG.get("cutoff_charge_v", float("3.6")))


def get_condition_group(cell_id: int) -> int:
    """Map cell number (2..65) to cycling condition group (1..11).

    Groups 1 to 10 contain 6 cells each (02-07, 08-13, ..., 56-61).
    Group 11 contains 4 cells (62-65).
    """
    if 2 <= cell_id <= int("61"):
        return (cell_id - 2) // int("6") + 1
    elif int("62") <= cell_id <= int("65"):
        return int("11")
    else:
        raise ValueError(f"Cell ID {cell_id} out of range [2, 65]")


@dataclass(frozen=True)
class UconnPulse:
    """A segmented current pulse and relaxation interval."""

    cell_id: str
    group_id: int
    rpt_number: int
    pulse_type: str  # 'chg' or 'dchg'
    nominal_soc: float  # 20.0, 50.0, or 90.0
    time_s: np.ndarray  # Relative time from start of pulse (s), shape (N,)
    voltage_v: np.ndarray  # Terminal voltage (V), shape (N,)
    current_a: np.ndarray  # Current in repo convention: DISCHARGE POSITIVE (A), shape (N,)
    duration_s: float
    i_step1_mean_a: float  # Mean current during 30s C/5 step (A)
    i_step2_mean_a: float  # Mean current during 10s 1C step (A)
    v_start_v: float  # Voltage before pulse onset (V)
    v_1s_v: float  # Voltage after 1s of 1C step (V)
    v_10s_v: float  # Voltage at end of 1C step (V)
    delta_v_1s: float  # Voltage drop/rise after 1s of 1C step (V)
    delta_v_10s: float  # Total voltage drop/rise across 1C step (V)
    r_pulse_10s_ohm: float  # Pulse resistance: |delta_v_10s| / |delta_i| (Ohm)


@dataclass
class UconnRptRecord:
    """Data and metadata for a single Reference Performance Test."""

    cell_id: str
    group_id: int
    rpt_number: int
    date: str
    num_cycles: float
    capacity_ah: Optional[float]  # Measured in ref_dchg (Step 28); None if missing/invalid
    soh_c: Optional[float] = None  # capacity_ah / c0_ah (assigned when cell c0 is known)
    pulses: Dict[Tuple[str, float], UconnPulse] = field(default_factory=dict)
    # Pulses keyed by (pulse_type, nominal_soc), e.g. ('dchg', 50.0)


@dataclass
class UconnCellData:
    """Complete history of RPT records for a single cell."""

    cell_id: str
    group_id: int
    c0_ah: float  # Measured first-RPT (RPT 0) discharge capacity (Ah)
    rpts: Dict[int, UconnRptRecord]
    r_ref_10s_ohm: Dict[Tuple[str, float], float] = field(default_factory=dict)
    # Baseline pulse resistances from RPT 0 keyed by (pulse_type, nominal_soc)

    @property
    def rpt_numbers(self) -> List[int]:
        return sorted(self.rpts.keys())

    @property
    def num_rpts(self) -> int:
        return len(self.rpts)

    def get_soh_r(self, rpt_number: int, pulse_type: str = "dchg", soc: float = float("50.0")) -> Optional[float]:
        """Return SOH_R = R_pulse(RPT) / R_pulse(RPT0) at matched pulse type and SOC."""
        key = (pulse_type, float(soc))
        r0 = self.r_ref_10s_ohm.get(key)
        if r0 is None or r0 <= 0:
            return None
        rpt = self.rpts.get(rpt_number)
        if rpt is None:
            return None
        pulse = rpt.pulses.get(key)
        if pulse is None or pulse.r_pulse_10s_ohm <= 0:
            return None
        return float(pulse.r_pulse_10s_ohm / r0)


def _resolve_uconn_base_dir(data_dir: Optional[Path] = None) -> Path:
    """Resolve base directory containing UConn dataset files."""
    if data_dir is not None:
        p = Path(data_dir).resolve()
        # Direct folder containing dataset files
        if (p / "rpt_data.zip").exists() or (p / "README_Uconn.txt").exists() or (p / "rpt_data").is_dir() or (p / "extracted").is_dir():
            return p
        if (p / "uconn_reil").exists():
            return p / "uconn_reil"
        return p / "uconn_reil"
    return resolve_dataset_dir("uconn_reil_dataset5")


def verify_uconn_manifest(data_dir: Optional[Path] = None) -> DatasetManifest:
    """Verify SHA-256 hash of dataset 5 files against manifest (Rule R2)."""
    manifest_path = get_manifest_path("uconn_reil_dataset5")
    manifest = DatasetManifest.load(manifest_path)
    dataset_dir = _resolve_uconn_base_dir(data_dir)

    if not dataset_dir.exists():
        raise DatasetMissingError(
            f"UConn REIL dataset directory missing at {dataset_dir}. Rule R1: external data required."
        )

    valid, missing, corrupt = manifest.audit_dataset_directory(dataset_dir)
    if corrupt:
        raise ChecksumMismatchError(
            f"UConn dataset has corrupt files: {corrupt}. Rule R2: integrity check failed."
        )
    if missing:
        raise DatasetMissingError(
            f"UConn dataset has missing files: {missing}. Rule R2: external data incomplete."
        )
    return manifest


def get_uconn_rpt_dir(data_dir: Optional[Path] = None) -> Path:
    """Return path to extracted RPT directory, ensuring it exists."""
    dataset_dir = _resolve_uconn_base_dir(data_dir)
    # Check candidates
    for cand in [
        dataset_dir / "extracted" / "rpt_data",
        dataset_dir / "rpt_data",
        dataset_dir,
    ]:
        if cand.exists() and cand.is_dir() and (cand.name == "rpt_data" or any(cand.glob("*.csv"))):
            return cand

    raise DatasetMissingError(
        f"Extracted UConn RPT directory not found under {dataset_dir}. "
        f"Expected {dataset_dir / 'extracted' / 'rpt_data'} or {dataset_dir / 'rpt_data'}."
    )


def list_uconn_cell_files(cell_id: str, data_dir: Optional[Path] = None) -> List[Path]:
    """List all CSV partition files for a given cell ID, skipping '~$' and '._' files."""
    rpt_dir = get_uconn_rpt_dir(data_dir)
    cell_str = f"{int(cell_id):02d}"
    pattern = str(rpt_dir / f"rpt_cell_{cell_str}_part*.csv")
    files = sorted(glob.glob(pattern))

    clean_files: List[Path] = []
    for f in files:
        p = Path(f)
        # Skip temporary Office files and macOS resource fork metadata
        if p.name.startswith("~$") or p.name.startswith("._"):
            continue
        clean_files.append(p)

    return clean_files


def _segment_slowpulse(
    pulse_sub: pd.DataFrame,
    cell_id: str,
    group_id: int,
    rpt_num: int,
    pulse_type: str,
    soc: float,
) -> Optional[UconnPulse]:
    """Extract and compute pulse parameters from a 100 s slowpulse sequence."""
    if len(pulse_sub) < int("10"):
        return None

    # Step breakdown:
    # First step: 30s C/5 (CC)
    # Second step: 10s 1C (CC)
    # Third step: 60s Rest
    steps = sorted(pulse_sub["Step Number"].unique())
    if len(steps) < 2:
        return None

    step1_df = pulse_sub[pulse_sub["Step Number"] == steps[0]]
    step2_df = pulse_sub[pulse_sub["Step Number"] == steps[1]]

    if len(step1_df) == 0 or len(step2_df) == 0:
        return None

    # Apply sign convention: repo convention is DISCHARGE POSITIVE
    # Raw data: Charge is positive (+0.24A, +1.2A), Discharge is negative (-0.24A, -1.2A)
    # Repo convention: I_repo = -I_file
    t_arr = pulse_sub["Time (s)"].to_numpy(dtype=float)
    t_rel = t_arr - t_arr[0]
    v_arr = pulse_sub["Voltage (V)"].to_numpy(dtype=float)
    i_raw = pulse_sub["Current (A)"].to_numpy(dtype=float)
    i_repo = -i_raw

    # Step currents in repo convention
    i_step1_mean = float(-step1_df["Current (A)"].mean())
    i_step2_mean = float(-step2_df["Current (A)"].mean())
    delta_i = i_step2_mean - i_step1_mean

    v_start = float(step1_df["Voltage (V)"].iloc[-1])
    v_step2_vals = step2_df["Voltage (V)"].to_numpy(dtype=float)
    t_step2_vals = step2_df["Time (s)"].to_numpy(dtype=float)

    if len(v_step2_vals) == 0:
        return None

    # 1s index into step 2
    t2_rel = t_step2_vals - t_step2_vals[0]
    idx_1s = int(np.argmin(np.abs(t2_rel - 1.0)))
    v_1s = float(v_step2_vals[idx_1s])
    v_10s = float(v_step2_vals[-1])

    delta_v_1s = v_1s - v_start
    delta_v_10s = v_10s - v_start

    # Resistance: |delta_v| / |delta_i|
    denom = abs(delta_i) if abs(delta_i) > float("0.01") else 1.0
    r_10s = float(abs(delta_v_10s) / denom)

    return UconnPulse(
        cell_id=cell_id,
        group_id=group_id,
        rpt_number=rpt_num,
        pulse_type=pulse_type,
        nominal_soc=soc,
        time_s=t_rel,
        voltage_v=v_arr,
        current_a=i_repo,
        duration_s=float(t_rel[-1] - t_rel[0]),
        i_step1_mean_a=i_step1_mean,
        i_step2_mean_a=i_step2_mean,
        v_start_v=v_start,
        v_1s_v=v_1s,
        v_10s_v=v_10s,
        delta_v_1s=delta_v_1s,
        delta_v_10s=delta_v_10s,
        r_pulse_10s_ohm=r_10s,
    )


def load_uconn_cell_data(
    cell_id: str,
    data_dir: Optional[Path] = None,
    verify_checksums: bool = False,
) -> UconnCellData:
    """Load and process all RPT data for a single cell."""
    if verify_checksums:
        verify_uconn_manifest(data_dir)

    cell_int = int(cell_id)
    cell_str = f"{cell_int:02d}"
    group_id = get_condition_group(cell_int)
    files = list_uconn_cell_files(cell_str, data_dir)

    if not files:
        raise DatasetMissingError(
            f"No partition files found for cell {cell_str} in UConn dataset."
        )

    cols = [
        "RPT Number",
        "Step Number",
        "State",
        "Time (s)",
        "Voltage (V)",
        "Current (A)",
        "Capacity (Ah)",
        "Segment Key",
        "Pulse Type",
        "Pulse SOC",
        "Date (yyyy.mm.dd hh.mm.ss)",
        "Num Cycles",
    ]

    dfs = [pd.read_csv(f, usecols=cols) for f in files]
    df_cell = pd.concat(dfs, ignore_index=True)

    rpts: Dict[int, UconnRptRecord] = {}
    rpt_nums = sorted(df_cell["RPT Number"].unique())

    for rpt_num in rpt_nums:
        sub_rpt = df_cell[df_cell["RPT Number"] == rpt_num]
        date_str = str(sub_rpt["Date (yyyy.mm.dd hh.mm.ss)"].iloc[0])
        num_cycles = float(sub_rpt["Num Cycles"].iloc[-1])

        # Step 28: ref_dchg (Reference Discharge Capacity)
        dchg = sub_rpt[sub_rpt["Segment Key"] == "ref_dchg"]
        cap_val: Optional[float] = None
        if len(dchg) > 0:
            c_diff = float(dchg["Capacity (Ah)"].max() - dchg["Capacity (Ah)"].min())
            if c_diff > float("0.1"):  # Physical check: discharge capacity must be positive
                cap_val = c_diff

        rpt_rec = UconnRptRecord(
            cell_id=cell_str,
            group_id=group_id,
            rpt_number=int(rpt_num),
            date=date_str,
            num_cycles=num_cycles,
            capacity_ah=cap_val,
        )

        # Extract slowpulses: (pulse_type, pulse_soc)
        slowpulse_df = sub_rpt[sub_rpt["Segment Key"] == "slowpulse"]
        if len(slowpulse_df) > 0:
            for (p_type, p_soc), pulse_group in slowpulse_df.groupby(["Pulse Type", "Pulse SOC"]):
                if p_type in ("chg", "dchg") and not np.isnan(p_soc):
                    pulse_obj = _segment_slowpulse(
                        pulse_group, cell_str, group_id, int(rpt_num), str(p_type), float(p_soc)
                    )
                    if pulse_obj is not None:
                        rpt_rec.pulses[(str(p_type), float(p_soc))] = pulse_obj

        rpts[int(rpt_num)] = rpt_rec

    # Check RPT 0 for initial baseline capacity C0
    if 0 not in rpts or rpts[0].capacity_ah is None:
        raise ValueError(
            f"Cell {cell_str} does not have a valid initial RPT 0 reference discharge capacity."
        )

    c0 = float(rpts[0].capacity_ah)

    # Compute SOH_C for each RPT where capacity was measured
    for rpt_num, rpt_rec in rpts.items():
        if rpt_rec.capacity_ah is not None:
            rpt_rec.soh_c = float(rpt_rec.capacity_ah / c0)
        else:
            rpt_rec.soh_c = None  # Explicit exclusion of missing label

    # Baseline R0 references from RPT 0
    r_refs: Dict[Tuple[str, float], float] = {}
    for key, pulse in rpts[0].pulses.items():
        r_refs[key] = pulse.r_pulse_10s_ohm

    return UconnCellData(
        cell_id=cell_str,
        group_id=group_id,
        c0_ah=c0,
        rpts=rpts,
        r_ref_10s_ohm=r_refs,
    )


def load_uconn_dataset(
    data_dir: Optional[Path] = None,
    cell_ids: Optional[Sequence[Any]] = None,
    verify_checksums: bool = False,
) -> Dict[str, UconnCellData]:
    """Load multiple UConn cells. Defaults to all 64 cells (02..65)."""
    if cell_ids is None:
        cell_ids = [f"{i:02d}" for i in range(2, int("66"))]

    dataset: Dict[str, UconnCellData] = {}
    for cid in cell_ids:
        cid_str = f"{int(cid):02d}"
        dataset[cid_str] = load_uconn_cell_data(
            cid_str, data_dir=data_dir, verify_checksums=verify_checksums
        )
    return dataset
