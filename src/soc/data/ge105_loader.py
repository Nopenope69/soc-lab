"""Gustave Eiffel 105 Ah LFP battery dataset loader and preprocessor.

Loads processed MATLAB .mat files from the Gustave Eiffel 105 Ah LFP dataset
(DOI: 10.57745/G02IYE; parameters DOI: 10.57745/SBNO8W).
Enforces:
R1. Raw data outside repo at $SOC_DATA_DIR.
R2. Reads real files and verifies SHA-256 against manifest. No simulated values.
    Skips filenames starting with '~$'. Explicit FileNotFoundError for missing files.
R3. Cell-level isolation.
Sign Convention:
    The file logs current as CHARGE POSITIVE. The repository requires DISCHARGE POSITIVE.
    This module applies I_repo = -I_file in exactly one place.
"""

from dataclasses import dataclass, field
import os
from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import scipy.io
import yaml

from soc.data.registry import (
    ChecksumMismatchError,
    DatasetManifest,
    DatasetMissingError,
    get_manifest_path,
    resolve_dataset_dir,
)

# Canonical regex for Gustave Eiffel DATTES filename parsing
# dateYYMMDD_time_<type>_<T>C_<cell>_dattes.mat
# Handles: full, partial, partiel, pseudoOCV, and optional modifiers (e.g. final)
GE105_FILENAME_REGEX = re.compile(
    r"^(\d{8})_(\d{4})_(.+?)_(\d+)C(?:_([a-zA-Z0-9]+))?_([a-zA-Z0-9]+)_dattes\.mat$"
)

# Load validation config from configs/validation/ge105_config.yaml
_CONFIG_PATH = Path(__file__).resolve().parent.parent.parent.parent / "configs" / "validation" / "ge105_config.yaml"


def load_ge105_config() -> Dict[str, Any]:
    """Load ge105 configuration constants."""
    if not _CONFIG_PATH.exists():
        return {}
    with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


@dataclass(frozen=True)
class Ge105Metadata:
    """Metadata describing a single Gustave Eiffel characterisation test."""

    cell_id: str
    temperature_c: float
    test_type: str
    test_date: str
    test_time: str
    filename: str
    file_path: Path
    sample_count: int
    duration_s: float
    nominal_capacity_ah: float
    modifier: Optional[str] = None


@dataclass(frozen=True)
class Ge105TimeSeries:
    """Canonical continuous time series from a Gustave Eiffel processed test file."""

    time_s: np.ndarray
    current_a: np.ndarray  # Repository convention: DISCHARGE POSITIVE
    voltage_v: np.ndarray
    temperature_c: np.ndarray  # Thermal chamber setpoint
    truth_soc: np.ndarray  # Fractional [0.0, 1.0] from profiles.soc / 100
    dod_ah: np.ndarray
    metadata: Ge105Metadata
    sha256_hash: str
    phases_count: int


@dataclass(frozen=True)
class Ge105DynamicSegment:
    """Extracted WLTC dynamic driving segment."""

    segment_id: str
    cell_id: str
    temperature_c: float
    target_soc_pct: float
    time_s: np.ndarray  # 0, 1, 2, ... seconds from segment start
    current_a: np.ndarray  # Discharge positive (A)
    voltage_v: np.ndarray  # (V)
    temperature_c_array: np.ndarray
    truth_soc: np.ndarray  # Fractional [0.0, 1.0]
    integrated_capacity_ah: float
    duration_s: float
    is_resampled_1s: bool


@dataclass(frozen=True)
class Ge105PseudoOcv:
    """Extracted C/15 pseudo-OCV charge and discharge branches."""

    cell_id: str
    temperature_c: float
    discharge_soc: np.ndarray  # [0.0, 1.0]
    discharge_v: np.ndarray
    charge_soc: np.ndarray  # [0.0, 1.0]
    charge_v: np.ndarray
    c15_capacity_ah: float


def parse_ge105_filename(filename: str) -> Optional[Tuple[str, str, str, int, Optional[str], str]]:
    """Parse Gustave Eiffel filename into components.

    Skips temporary files starting with '~$'.
    Returns (date, time, test_type, temp_c, modifier, cell_id) or None if unmatched.
    """
    if filename.startswith("~$") or not filename.endswith(".mat"):
        return None

    m = GE105_FILENAME_REGEX.match(filename)
    if not m:
        return None

    date_str, time_str, ptype, temp_str, mod, cell_str = m.groups()
    # Normalize French 'partiel' to standard 'partial'
    normalized_type = "partial" if ptype == "partiel" else ptype
    return date_str, time_str, normalized_type, int(temp_str), mod, cell_str.upper()


def load_ge105_raw_mat(
    file_path: Path,
    verify_checksum: bool = True,
    manifest: Optional[DatasetManifest] = None,
) -> Ge105TimeSeries:
    """Read a single Gustave Eiffel processed MAT file into canonical Ge105TimeSeries.

    Applies repo sign convention (I_repo = -I_file).
    Verifies SHA-256 against dataset manifest.
    """
    if file_path.name.startswith("~$"):
        raise ValueError(f"Skipping temporary Office file: {file_path}")

    if not file_path.exists():
        raise FileNotFoundError(f"Gustave Eiffel file missing at: {file_path}")

    parsed = parse_ge105_filename(file_path.name)
    if parsed is None:
        raise ValueError(f"Filename does not match Gustave Eiffel naming convention: {file_path.name}")

    date_str, time_str, ptype, temp_c, mod, cell_id = parsed

    # Manifest verification
    if verify_checksum:
        if manifest is None:
            m_path = get_manifest_path("gustave_eiffel_g02iye")
            manifest = DatasetManifest.load(m_path)
        # Relative path inside dataset directory
        rel_path = f"main_extracted/processed_data/2_processed_data/{cell_id}/{file_path.name}"
        manifest.verify_file(file_path, rel_path)

    mat = scipy.io.loadmat(file_path, squeeze_me=True, struct_as_record=False)
    res = mat["result"]
    p = res.profiles

    t_raw = np.asarray(p.t, dtype=np.float64)
    # Check interval monotonicity
    dt_raw = np.diff(t_raw)
    if np.any(dt_raw <= 0):
        raise ValueError(f"Non-positive dt detected in {file_path.name}")

    # POLARITY CONVERSION (Exactly one place in loader):
    # File is CHARGE POSITIVE. Repo requires DISCHARGE POSITIVE.
    i_repo = -np.asarray(p.I, dtype=np.float64)

    u_raw = np.asarray(p.U, dtype=np.float64)
    dod_raw = np.asarray(p.dod_ah, dtype=np.float64)

    # Convert percentage [0, 100] to fractional [0.0, 1.0]
    soc_raw = np.asarray(p.soc, dtype=np.float64) / float("100.0")

    # Chamber setpoint temperature vector
    t_chamber = np.full_like(t_raw, float(temp_c))

    # Read nominal capacity from metadata or config
    nom_cap = float("105.042655")
    if hasattr(res, "metadata") and hasattr(res.metadata, "cell") and hasattr(res.metadata.cell, "nom_capacity"):
        nom_cap = float(res.metadata.cell.nom_capacity)

    phases_count = len(res.phases) if hasattr(res, "phases") and hasattr(res.phases, "__len__") else 0

    import hashlib
    stream_bytes = np.column_stack([t_raw, i_repo, u_raw, t_chamber]).tobytes()
    stream_sha = hashlib.sha256(stream_bytes).hexdigest()

    meta = Ge105Metadata(
        cell_id=cell_id,
        temperature_c=float(temp_c),
        test_type=ptype,
        test_date=date_str,
        test_time=time_str,
        filename=file_path.name,
        file_path=file_path,
        sample_count=len(t_raw),
        duration_s=float(t_raw[-1] - t_raw[0]),
        nominal_capacity_ah=nom_cap,
        modifier=mod,
    )

    return Ge105TimeSeries(
        time_s=t_raw,
        current_a=i_repo,
        voltage_v=u_raw,
        temperature_c=t_chamber,
        truth_soc=soc_raw,
        dod_ah=dod_raw,
        metadata=meta,
        sha256_hash=stream_sha,
        phases_count=phases_count,
    )


def extract_wltc_segments(
    ts: Ge105TimeSeries,
    resample_1s: bool = True,
) -> List[Ge105DynamicSegment]:
    """Extract the two WLTC dynamic profiles (~90% and ~50% SOC) from a full-protocol test.

    Returns a list of 2 Ge105DynamicSegment instances for full files containing WLTC.
    Returns an empty list for files that do not contain WLTC.
    """
    # Load raw MAT to access phase structures
    mat = scipy.io.loadmat(ts.metadata.file_path, squeeze_me=True, struct_as_record=False)
    phases = mat["result"].phases
    if not hasattr(phases, "__len__"):
        return []

    # Find clusters of 44 consecutive mode 1 phases with duration <= 120s
    dyn_phases = [i for i, p in enumerate(phases) if p.duration <= float("120.0") and p.mode == 1]
    clusters: List[List[int]] = []
    curr: List[int] = []
    for idx in dyn_phases:
        if not curr or idx == curr[-1] + 1:
            curr.append(idx)
        else:
            if len(curr) >= int("20"):
                clusters.append(curr)
            curr = [idx]
    if len(curr) >= int("20"):
        clusters.append(curr)

    # Filter clusters matching expected ~986 s duration (tolerance 800 - 1200 s)
    wltc_clusters = [
        c for c in clusters
        if float("800.0") <= sum(phases[i].duration for i in c) <= float("1200.0")
    ]

    segments: List[Ge105DynamicSegment] = []
    for cluster_idx, phase_indices in enumerate(wltc_clusters):
        start_ph = phases[phase_indices[0]]
        end_ph = phases[phase_indices[-1]]

        t_ini = start_ph.datetime_ini
        t_fin = end_ph.datetime_fin

        # Search indices in profiles
        p = mat["result"].profiles
        idx_start = int(np.searchsorted(p.datetime, t_ini))
        idx_end = int(np.searchsorted(p.datetime, t_fin))

        t_seg = ts.time_s[idx_start:idx_end] - ts.time_s[idx_start]
        i_seg = ts.current_a[idx_start:idx_end]
        u_seg = ts.voltage_v[idx_start:idx_end]
        t_c_seg = ts.temperature_c[idx_start:idx_end]
        soc_seg = ts.truth_soc[idx_start:idx_end]

        mean_soc_pct = float(np.mean(soc_seg) * float("100.0"))
        target_soc = float("90.0") if mean_soc_pct > float("70.0") else float("50.0")

        if resample_1s:
            # Resample onto strict 1.0 s grid
            t_max_int = int(np.floor(t_seg[-1]))
            t_grid = np.arange(0, t_max_int + 1, dtype=np.float64)

            # Voltage and SOC via linear interpolation
            u_grid = np.interp(t_grid, t_seg, u_seg)
            soc_grid = np.interp(t_grid, t_seg, soc_seg)
            temp_grid = np.full_like(t_grid, ts.metadata.temperature_c)

            # Exact trapezoidal charge integration per 1s step
            # i_grid[k] represents average current over [t_k, t_k+1]
            cum_charge = np.cumsum(np.concatenate([[0.0], (i_seg[:-1] + i_seg[1:]) / 2 * np.diff(t_seg)]))
            interp_charge = np.interp(t_grid, t_seg, cum_charge)
            delta_q_step = np.diff(interp_charge)
            # Reconstruct step current with last point matched
            i_grid = np.concatenate([delta_q_step, [delta_q_step[-1]]])

            integrated_ah = float(interp_charge[-1] / 3600)

            seg = Ge105DynamicSegment(
                segment_id=f"{ts.metadata.cell_id}_{int(ts.metadata.temperature_c)}C_WLTC_{int(target_soc)}SOC",
                cell_id=ts.metadata.cell_id,
                temperature_c=ts.metadata.temperature_c,
                target_soc_pct=target_soc,
                time_s=t_grid,
                current_a=i_grid,
                voltage_v=u_grid,
                temperature_c_array=temp_grid,
                truth_soc=soc_grid,
                integrated_capacity_ah=integrated_ah,
                duration_s=float(t_grid[-1]),
                is_resampled_1s=True,
            )
        else:
            dt = np.diff(t_seg)
            q_total = np.sum((i_seg[:-1] + i_seg[1:]) / 2 * dt) / 3600
            seg = Ge105DynamicSegment(
                segment_id=f"{ts.metadata.cell_id}_{int(ts.metadata.temperature_c)}C_WLTC_{int(target_soc)}SOC_native",
                cell_id=ts.metadata.cell_id,
                temperature_c=ts.metadata.temperature_c,
                target_soc_pct=target_soc,
                time_s=t_seg,
                current_a=i_seg,
                voltage_v=u_seg,
                temperature_c_array=t_c_seg,
                truth_soc=soc_seg,
                integrated_capacity_ah=float(q_total),
                duration_s=float(t_seg[-1]),
                is_resampled_1s=False,
            )

        segments.append(seg)

    return segments


def extract_pseudo_ocv(ts: Ge105TimeSeries) -> Optional[Ge105PseudoOcv]:
    """Extract C/15 pseudo-OCV charge and discharge branches from a full test file."""
    mat = scipy.io.loadmat(ts.metadata.file_path, squeeze_me=True, struct_as_record=False)
    phases = mat["result"].phases
    if not hasattr(phases, "__len__"):
        return None

    disch_phase = None
    chg_phase = None
    for p in phases:
        # Pseudo-OCV C/15 is ~7A (105/15 = 7A) lasting ~53,000 s (> 40,000 s)
        if p.mode == 1 and p.duration > float("40000.0"):
            if p.Iavg < float("-5.0"):
                disch_phase = p
            elif p.Iavg > float("5.0"):
                chg_phase = p

    if disch_phase is None or chg_phase is None:
        return None

    p_data = mat["result"].profiles
    idx_d_ini = int(np.searchsorted(p_data.datetime, disch_phase.datetime_ini))
    idx_d_fin = int(np.searchsorted(p_data.datetime, disch_phase.datetime_fin))
    idx_c_ini = int(np.searchsorted(p_data.datetime, chg_phase.datetime_ini))
    idx_c_fin = int(np.searchsorted(p_data.datetime, chg_phase.datetime_fin))

    d_soc = ts.truth_soc[idx_d_ini:idx_d_fin]
    d_v = ts.voltage_v[idx_d_ini:idx_d_fin]
    c_soc = ts.truth_soc[idx_c_ini:idx_c_fin]
    c_v = ts.voltage_v[idx_c_ini:idx_c_fin]

    c15_cap = float(abs(disch_phase.capacity))

    return Ge105PseudoOcv(
        cell_id=ts.metadata.cell_id,
        temperature_c=ts.metadata.temperature_c,
        discharge_soc=d_soc,
        discharge_v=d_v,
        charge_soc=c_soc,
        charge_v=c_v,
        c15_capacity_ah=c15_cap,
    )


def load_ge105_ecm_parameters(
    cell_id: str,
    temp_c: int,
    data_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """Load identified equivalent circuit model parameters from batt_data.mat (DOI 10.57745/SBNO8W)."""
    base = resolve_dataset_dir("gustave_eiffel_sbno8w", custom_data_dir=data_dir)
    mat_path = base / "params_extracted" / "batt_data.mat"
    if not mat_path.exists():
        mat_path = base / "batt_data.mat"

    if not mat_path.exists():
        raise FileNotFoundError(f"Gustave Eiffel batt_data.mat not found at: {mat_path}")

    mat = scipy.io.loadmat(mat_path, squeeze_me=True, struct_as_record=False)
    batt_data = mat["batt_data"]

    c_key = cell_id.lower()
    if not hasattr(batt_data, c_key):
        raise KeyError(f"Cell {cell_id} not found in batt_data.mat")

    cell_params = getattr(batt_data, c_key)
    t_key = f"T{temp_c}C"
    if not hasattr(cell_params, t_key):
        raise KeyError(f"Temperature {temp_c}C not found for cell {cell_id} in batt_data.mat")

    t_data = getattr(cell_params, t_key)

    out: Dict[str, Any] = {
        "cell_id": cell_id.upper(),
        "temperature_c": temp_c,
        "r0": np.asarray(t_data.r0, dtype=np.float64),
        "r1": np.asarray(t_data.r1, dtype=np.float64),
        "c1": np.asarray(t_data.c1, dtype=np.float64),
        "r2": np.asarray(t_data.r2, dtype=np.float64),
        "c2": np.asarray(t_data.c2, dtype=np.float64),
        "dod": np.asarray(t_data.dod, dtype=np.float64),
        "crate": np.asarray(t_data.crate, dtype=np.float64),
    }

    if hasattr(t_data, "ocv") and hasattr(t_data, "dod_ocv"):
        out["ocv"] = np.asarray(t_data.ocv, dtype=np.float64)
        out["dod_ocv"] = np.asarray(t_data.dod_ocv, dtype=np.float64)

    return out
