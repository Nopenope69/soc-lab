"""TEMPEST 280 Ah Prismatic LFP Cell Dataset Loader.

Dataset: EU TEMPEST project (University of Bath), Zenodo record 19632939.
Cell: 280 Ah commercial prismatic LFP cell (designated 'LIC').
Temperatures: 15 °C, 20 °C, 25 °C, 30 °C, 35 °C.

Enforces:
R1. Raw data lives outside repository at $SOC_DATA_DIR/tempest_280ah/.
R2. Loader reads real files and verifies SHA-256 against data/manifests/tempest_zenodo.sha256.
    No simulated, synthetic, or defaulted values.
R3. Skips temporary Office lock files starting with '~$'.
R4. Applies repository sign convention: DISCHARGE POSITIVE (I_repo = -I_file).
R5. Converts surface temperature from Kelvin to Celsius (T_c = T_k - 273.15).
R6. Drops all-NaN cycler export delimiter lines (',,,') cleanly.
R7. Normalizes column headers across files, including 15C_hppc.csv.
R8. Parameters and physical thresholds loaded from configs/validation/tempest_config.yaml.
"""

from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Sequence, Tuple
import yaml

import numpy as np
import pandas as pd

from soc.data.registry import (
    ChecksumMismatchError,
    DatasetManifest,
    get_manifest_path,
    get_repo_root,
    get_soc_data_dir,
    resolve_dataset_dir,
)

TEMPEST_DATASET_ID = "tempest_zenodo"


def load_tempest_config() -> Dict[str, Any]:
    """Load configuration from configs/validation/tempest_config.yaml."""
    cfg_path = get_repo_root() / "configs" / "validation" / "tempest_config.yaml"
    if not cfg_path.exists():
        raise FileNotFoundError(f"TEMPEST configuration missing at: {cfg_path}")
    with open(cfg_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


_CONFIG = load_tempest_config()
VALID_TEMPERATURES: Tuple[int, ...] = tuple(_CONFIG["cell"]["tested_temperatures_c"])
NOMINAL_CAPACITY_AH: float = float(_CONFIG["cell"]["nominal_capacity_ah"])
LFP_V_MIN: float = float(_CONFIG["cell"]["voltage_limit_min"])
LFP_V_MAX: float = float(_CONFIG["cell"]["voltage_limit_max"])
KELVIN_OFFSET: float = float(_CONFIG["physical"]["kelvin_offset"])
READ_CHUNK_SIZE: int = int(_CONFIG["physical"]["read_chunk_size_bytes"])
MIN_CURRENT_EPSILON: float = float(_CONFIG["physical"]["min_current_epsilon_a"])
HASH_TRUNC_LEN: int = int(_CONFIG["physical"]["hash_truncate_len"])
CAP_CURRENT_THRESH: float = float(_CONFIG["protocols"]["capacity_test"]["current_threshold_a"])
HPPC_PULSE_THRESH: float = float(_CONFIG["protocols"]["hppc_test"]["pulse_threshold_a"])
HPPC_SOC_GRID: List[float] = list(_CONFIG["protocols"]["hppc_test"]["soc_grid"])


@dataclass(frozen=True)
class TempestTimeSeries:
    """Canonical continuous time series from a TEMPEST test file."""

    time_s: np.ndarray  # Monotonic time from start (s)
    current_a: np.ndarray  # Repository convention: DISCHARGE POSITIVE (A)
    voltage_v: np.ndarray  # Terminal voltage (V)
    temperature_c: np.ndarray  # Surface temperature (deg C)
    temperature_k: np.ndarray  # Raw surface temperature (K)
    file_type: str  # 'capacity' or 'hppc'
    nominal_temperature_c: int  # 15, 20, 25, 30, or 35
    source_filename: str  # e.g. '25C_capacity.csv'


@dataclass(frozen=True)
class TempestCapacityTest:
    """Capacity characterisation test at a fixed chamber temperature."""

    time_series: TempestTimeSeries
    nominal_temperature_c: int
    charge_ah: float  # CC-CV charge Ah
    discharge_ah: float  # CC discharge Ah to 2.5V cutoff
    mean_discharge_current_a: float  # Mean discharge current (A, repo convention positive)
    discharge_duration_s: float
    c_rate: float  # Discharge C-rate relative to 280 Ah nominal (nominal 0.1 C)


@dataclass(frozen=True)
class TempestHppcPulse:
    """Extracted HPPC current pulse event."""

    pulse_index: int  # 1 through 10
    soc_nominal: float  # 0.95, 0.85, ..., 0.05
    pulse_type: str  # 'discharge' (repo I > 0) or 'charge' (repo I < 0)
    time_rel_s: np.ndarray  # Relative time from pulse onset (s), shape (N,)
    current_a: np.ndarray  # Current in repo convention: DISCHARGE POSITIVE (A)
    voltage_v: np.ndarray  # Terminal voltage (V)
    duration_s: float  # Total pulse duration (~10.0 s)
    mean_current_a: float  # Mean current during pulse (A)
    v_start_v: float  # Terminal voltage immediately before pulse onset (V)
    v_end_v: float  # Terminal voltage at end of pulse (V)
    delta_v_10s: float  # Terminal voltage change over 10s pulse (V)
    r_10s_ohm: float  # 10s resistance = abs(delta_v_10s) / abs(mean_current_a) (Ohm)


@dataclass(frozen=True)
class TempestHppcTest:
    """HPPC characterisation test across 10 SOC setpoints at a fixed chamber temperature."""

    time_series: TempestTimeSeries
    nominal_temperature_c: int
    pulses: List[TempestHppcPulse]
    discharge_pulses: List[TempestHppcPulse]
    charge_pulses: List[TempestHppcPulse]
    soc_points: List[float]


def get_tempest_dir(custom_data_dir: Optional[Path] = None) -> Path:
    """Locate the TEMPEST dataset root directory adhering to $SOC_DATA_DIR."""
    return resolve_dataset_dir(TEMPEST_DATASET_ID, custom_data_dir=custom_data_dir)


def verify_tempest_manifest(
    data_dir: Optional[Path] = None,
) -> Tuple[bool, List[str]]:
    """Verify SHA-256 hashes of all TEMPEST files against dataset manifest.

    Returns:
        (all_valid, list_of_error_strings)
    """
    manifest_path = get_manifest_path(TEMPEST_DATASET_ID)
    if not manifest_path.exists():
        return False, [f"Manifest file missing: {manifest_path}"]

    target_dir = get_tempest_dir(custom_data_dir=data_dir)
    if not target_dir.exists() or not target_dir.is_dir():
        return False, [f"TEMPEST data directory missing: {target_dir}"]

    manifest = DatasetManifest.load(manifest_path)
    valid, missing, corrupt = manifest.audit_dataset_directory(target_dir)

    errors = []
    for f in missing:
        errors.append(f"Missing file: {f}")
    for f, expected, actual in corrupt:
        errors.append(f"Corrupt file: {f} (expected {expected[:HASH_TRUNC_LEN]}..., actual {actual[:HASH_TRUNC_LEN]}...)")

    return (len(missing) == 0 and len(corrupt) == 0), errors


def compute_file_sha256(file_path: Path) -> str:
    """Compute standard SHA-256 hex digest of a file."""
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(READ_CHUNK_SIZE):
            h.update(chunk)
    return h.hexdigest().lower()


def load_tempest_raw_csv(
    file_path: Path,
    verify_checksum: bool = True,
    manifest: Optional[DatasetManifest] = None,
) -> TempestTimeSeries:
    """Load and normalize a TEMPEST capacity or HPPC raw CSV file.

    Enforces:
    - Skips files with prefix '~$'
    - Validates SHA-256 checksum against manifest if verify_checksum is True
    - Drops delimiter/empty rows (lines containing ',,,')
    - Normalizes column names (handles '15C_hppc.csv' channel header naming)
    - Converts surface temperature from Kelvin to Celsius
    - Applies repository convention: DISCHARGE POSITIVE (I_repo = -I_file)
    """
    file_path = Path(file_path).resolve()

    if file_path.name.startswith("~$"):
        raise ValueError(f"Skipping temporary Office file: {file_path.name}")

    if not file_path.exists():
        raise FileNotFoundError(f"TEMPEST file not found: {file_path}")

    # Parse filename metadata
    match = re.match(r"^(\d{2})C_(capacity|hppc)\.csv$", file_path.name)
    if not match:
        raise ValueError(
            f"Filename does not match TEMPEST naming pattern (XXC_capacity.csv or XXC_hppc.csv): {file_path.name}"
        )

    nominal_temp_c = int(match.group(1))
    file_type = match.group(2)

    if nominal_temp_c not in VALID_TEMPERATURES:
        raise ValueError(f"Unsupported nominal temperature: {nominal_temp_c} °C (expected one of {VALID_TEMPERATURES})")

    # Checksum verification
    if verify_checksum:
        if manifest is None:
            manifest_path = get_manifest_path(TEMPEST_DATASET_ID)
            if manifest_path.exists():
                manifest = DatasetManifest.load(manifest_path)

        if manifest is not None and file_path.name in manifest.expected_hashes:
            expected_hash = manifest.expected_hashes[file_path.name].lower()
            actual_hash = compute_file_sha256(file_path)
            if actual_hash != expected_hash:
                raise ChecksumMismatchError(
                    f"SHA-256 mismatch for {file_path.name}: expected {expected_hash}, got {actual_hash}"
                )

    # Read CSV
    df = pd.read_csv(file_path)

    # Drop delimiter rows where all fields are NaN (cycler step boundary lines e.g. ',,,')
    df = df.dropna(how="all").copy()

    # Normalize column names
    col_map: Dict[str, str] = {}
    for col in df.columns:
        c_clean = col.strip()
        if c_clean in ("Time_s", "Time(Sec)"):
            col_map[col] = "time_s"
        elif c_clean in ("Current_A", "Current(A)"):
            col_map[col] = "current_a"
        elif c_clean in ("Voltage_V", "Voltage(V)"):
            col_map[col] = "voltage_v"
        elif "Temperature" in c_clean or "T_mid" in c_clean:
            col_map[col] = "temperature_k"

    df = df.rename(columns=col_map)
    required_cols = {"time_s", "current_a", "voltage_v", "temperature_k"}
    missing_cols = required_cols - set(df.columns)
    if missing_cols:
        raise ValueError(f"Missing required columns {missing_cols} in file {file_path.name}")

    time_s = df["time_s"].to_numpy(dtype=float)
    raw_current = df["current_a"].to_numpy(dtype=float)
    voltage_v = df["voltage_v"].to_numpy(dtype=float)
    temperature_k = df["temperature_k"].to_numpy(dtype=float)

    # Repository convention: DISCHARGE POSITIVE (I_repo = -I_file)
    current_a = -raw_current

    # Temperature conversion: K -> C
    temperature_c = temperature_k - KELVIN_OFFSET

    return TempestTimeSeries(
        time_s=time_s,
        current_a=current_a,
        voltage_v=voltage_v,
        temperature_c=temperature_c,
        temperature_k=temperature_k,
        file_type=file_type,
        nominal_temperature_c=nominal_temp_c,
        source_filename=file_path.name,
    )


def load_tempest_capacity(
    temperature_c: int,
    data_dir: Optional[Path] = None,
    verify_checksum: bool = True,
) -> TempestCapacityTest:
    """Load and process a capacity characterisation test."""
    if temperature_c not in VALID_TEMPERATURES:
        raise ValueError(f"Invalid temperature {temperature_c} °C; must be one of {VALID_TEMPERATURES}")

    root_dir = get_tempest_dir(custom_data_dir=data_dir)
    file_path = root_dir / f"{temperature_c}C_capacity.csv"

    ts = load_tempest_raw_csv(file_path, verify_checksum=verify_checksum)

    # In repo convention: discharge is positive (current_a > CAP_CURRENT_THRESH)
    # Charge is negative (current_a < -CAP_CURRENT_THRESH)
    dt = np.diff(ts.time_s)
    # prepend initial dt assuming same rate
    if len(dt) > 0:
        dt_full = np.concatenate([[dt[0]], dt])
    else:
        dt_full = np.array([1.0])

    dis_mask = ts.current_a > CAP_CURRENT_THRESH
    chg_mask = ts.current_a < -CAP_CURRENT_THRESH

    # Integration of capacity (Ah)
    if np.any(dis_mask):
        dis_ah = float(np.sum(ts.current_a[dis_mask] * dt_full[dis_mask]) / 3600.0)
        mean_dis_i = float(np.mean(ts.current_a[dis_mask]))
        dis_dur = float(np.sum(dt_full[dis_mask]))
    else:
        dis_ah = 0.0
        mean_dis_i = 0.0
        dis_dur = 0.0

    if np.any(chg_mask):
        chg_ah = float(np.sum(-ts.current_a[chg_mask] * dt_full[chg_mask]) / 3600.0)
    else:
        chg_ah = 0.0

    c_rate = mean_dis_i / NOMINAL_CAPACITY_AH if mean_dis_i > 0 else 0.0

    return TempestCapacityTest(
        time_series=ts,
        nominal_temperature_c=temperature_c,
        charge_ah=chg_ah,
        discharge_ah=dis_ah,
        mean_discharge_current_a=mean_dis_i,
        discharge_duration_s=dis_dur,
        c_rate=c_rate,
    )


def segment_tempest_hppc_pulses(ts: TempestTimeSeries) -> List[TempestHppcPulse]:
    """Segment high-rate HPPC pulses (~140 A, 10 s) from a continuous HPPC time series.

    In repository convention:
    - Discharge pulse: current_a > HPPC_PULSE_THRESH (raw I < -100 A)
    - Charge pulse: current_a < -HPPC_PULSE_THRESH (raw I > +100 A)

    The protocol evaluates 10 SOC setpoints (0.95, 0.85, ..., 0.05).
    At each setpoint, a discharge pulse is applied, followed by 20 min rest,
    followed by a charge pulse and 20 min rest.
    """
    i = ts.current_a
    t = ts.time_s
    v = ts.voltage_v

    # Identify continuous pulse regions
    is_dis = i > HPPC_PULSE_THRESH
    is_chg = i < -HPPC_PULSE_THRESH

    def find_intervals(mask: np.ndarray) -> List[Tuple[int, int]]:
        idx = np.where(mask)[0]
        if len(idx) == 0:
            return []
        gaps = np.where(np.diff(idx) > 1)[0]
        starts = np.concatenate([[idx[0]], idx[gaps + 1]])
        ends = np.concatenate([idx[gaps], [idx[-1]]])
        return list(zip(starts, ends))

    dis_intervals = find_intervals(is_dis)
    chg_intervals = find_intervals(is_chg)

    pulses: List[TempestHppcPulse] = []

    # Process discharge pulses
    for idx, (s, e) in enumerate(dis_intervals):
        soc_val = HPPC_SOC_GRID[idx] if idx < len(HPPC_SOC_GRID) else 0.0
        t_pulse = t[s : e + 1]
        t_rel = t_pulse - t_pulse[0]
        i_pulse = i[s : e + 1]
        v_pulse = v[s : e + 1]
        v_start = float(v[s - 1]) if s > 0 else float(v[s])
        v_end = float(v_pulse[-1])
        dur = float(t_rel[-1])
        i_mean = float(np.mean(i_pulse))
        delta_v = v_end - v_start
        r_10s = abs(delta_v) / abs(i_mean) if abs(i_mean) > MIN_CURRENT_EPSILON else 0.0

        pulses.append(
            TempestHppcPulse(
                pulse_index=idx + 1,
                soc_nominal=soc_val,
                pulse_type="discharge",
                time_rel_s=t_rel,
                current_a=i_pulse,
                voltage_v=v_pulse,
                duration_s=dur,
                mean_current_a=i_mean,
                v_start_v=v_start,
                v_end_v=v_end,
                delta_v_10s=delta_v,
                r_10s_ohm=r_10s,
            )
        )

    # Process charge pulses
    for idx, (s, e) in enumerate(chg_intervals):
        soc_val = HPPC_SOC_GRID[idx] if idx < len(HPPC_SOC_GRID) else 0.0
        t_pulse = t[s : e + 1]
        t_rel = t_pulse - t_pulse[0]
        i_pulse = i[s : e + 1]
        v_pulse = v[s : e + 1]
        v_start = float(v[s - 1]) if s > 0 else float(v[s])
        v_end = float(v_pulse[-1])
        dur = float(t_rel[-1])
        i_mean = float(np.mean(i_pulse))
        delta_v = v_end - v_start
        r_10s = abs(delta_v) / abs(i_mean) if abs(i_mean) > MIN_CURRENT_EPSILON else 0.0

        pulses.append(
            TempestHppcPulse(
                pulse_index=idx + 1,
                soc_nominal=soc_val,
                pulse_type="charge",
                time_rel_s=t_rel,
                current_a=i_pulse,
                voltage_v=v_pulse,
                duration_s=dur,
                mean_current_a=i_mean,
                v_start_v=v_start,
                v_end_v=v_end,
                delta_v_10s=delta_v,
                r_10s_ohm=r_10s,
            )
        )

    return pulses


def load_tempest_hppc(
    temperature_c: int,
    data_dir: Optional[Path] = None,
    verify_checksum: bool = True,
) -> TempestHppcTest:
    """Load and process an HPPC characterisation test."""
    if temperature_c not in VALID_TEMPERATURES:
        raise ValueError(f"Invalid temperature {temperature_c} °C; must be one of {VALID_TEMPERATURES}")

    root_dir = get_tempest_dir(custom_data_dir=data_dir)
    file_path = root_dir / f"{temperature_c}C_hppc.csv"

    ts = load_tempest_raw_csv(file_path, verify_checksum=verify_checksum)
    all_pulses = segment_tempest_hppc_pulses(ts)

    dis_pulses = [p for p in all_pulses if p.pulse_type == "discharge"]
    chg_pulses = [p for p in all_pulses if p.pulse_type == "charge"]
    soc_points = [p.soc_nominal for p in dis_pulses]

    return TempestHppcTest(
        time_series=ts,
        nominal_temperature_c=temperature_c,
        pulses=all_pulses,
        discharge_pulses=dis_pulses,
        charge_pulses=chg_pulses,
        soc_points=soc_points,
    )


def load_tempest_lic_capacity(data_dir: Optional[Path] = None) -> pd.DataFrame:
    """Read the provided LIC_capacity_analysis.csv file."""
    root_dir = get_tempest_dir(custom_data_dir=data_dir)
    file_path = root_dir / "LIC_capacity_analysis.csv"
    if not file_path.exists():
        raise FileNotFoundError(f"LIC_capacity_analysis.csv not found at: {file_path}")
    return pd.read_csv(file_path)


def load_tempest_lic_hppc(data_dir: Optional[Path] = None) -> pd.DataFrame:
    """Read the provided LIC_hppc_analysis.csv file."""
    root_dir = get_tempest_dir(custom_data_dir=data_dir)
    file_path = root_dir / "LIC_hppc_analysis.csv"
    if not file_path.exists():
        raise FileNotFoundError(f"LIC_hppc_analysis.csv not found at: {file_path}")
    return pd.read_csv(file_path)


def load_tempest_lic_entropy(data_dir: Optional[Path] = None) -> pd.DataFrame:
    """Read the provided LIC_entropy_analysis.csv file."""
    root_dir = get_tempest_dir(custom_data_dir=data_dir)
    file_path = root_dir / "LIC_entropy_analysis.csv"
    if not file_path.exists():
        raise FileNotFoundError(f"LIC_entropy_analysis.csv not found at: {file_path}")
    return pd.read_csv(file_path)
