"""Cell calibration data contract and validation for BMS State of Charge (SOC) estimation.

Zero external dependencies: pure standard library only (dataclasses, json, hashlib, typing, pathlib).
"""

from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Union


@dataclass(frozen=True)
class CellCalibration:
    """Complete cell-specific and tuning-specific calibration container."""

    calibration_id: str
    schema_version: str
    validation_status: str

    # Grid definitions
    temperatures_c: List[float]
    soc_grid: List[float]

    # 2D OCV Table (V) and 1D impedance tables indexed by temperature string
    ocv_table: Dict[str, List[float]]
    r0_table: Dict[str, float]
    r1_table: Dict[str, float]
    tau1_table: Dict[str, float]
    r2_table: Dict[str, float]
    tau2_table: Dict[str, float]

    # Temperature-scheduled capacity Q(T) (Ah)
    q_table_temps_c: List[float]
    q_table_ah: List[float]

    # Temperature-scheduled hysteresis amplitude M(T) (V)
    m_table_temps_c: List[float]
    m_table_v: List[float]

    # Cell physical ratings
    nominal_capacity_ah: float
    coulombic_efficiency: float = 0.998
    hysteresis_gamma: float = 50.0

    # Estimator process and measurement noise
    process_noise_q_soc: float = 2.0e-09
    process_noise_q_rc: float = 1.1198164932559382e-05
    process_noise_q_hysteresis: float = 0.00017150882346504795
    measurement_noise_r_v: float = 0.0008610323423725228

    # RLS impedance adaptation parameters
    e4_rls_forgetting_factor: float = 0.9990
    rls_di_threshold_a: float = 1.0
    rls_theta_min: float = 0.5
    rls_theta_max: float = 2.0

    # Observability gating and step capping
    e5_slope_ref: float = 0.20
    e5_cap_plateau: float = 2.0e-05
    e5_cap_knee: float = 0.01
    e5_sigma_ocv_model_v: float = 0.02

    # Initialization uncertainty
    initial_soc_std: float = 0.10
    initial_rc_current_std_a: float = 0.10
    initial_hysteresis_std: float = 0.10

    # Valid operational envelope and plausible signal limits
    temp_min_c: float = 20.0
    temp_max_c: float = 50.0
    voltage_min_v: float = 2.0
    voltage_max_v: float = 3.7
    current_min_a: float = -50.0
    current_max_a: float = 150.0

    def validate(self) -> None:
        """Strict validation of monotonic grids, positive quantities, and dimensions."""
        if not self.calibration_id or not isinstance(self.calibration_id, str):
            raise ValueError("calibration_id must be a non-empty string")
        if not self.schema_version or not isinstance(self.schema_version, str):
            raise ValueError("schema_version must be a non-empty string")
        if not self.validation_status or not isinstance(self.validation_status, str):
            raise ValueError("validation_status must be a non-empty string")

        # Monotonic grids
        if len(self.temperatures_c) < 2:
            raise ValueError("temperatures_c must contain at least 2 points")
        for i in range(1, len(self.temperatures_c)):
            if self.temperatures_c[i] <= self.temperatures_c[i - 1]:
                raise ValueError(f"temperatures_c must be strictly increasing: {self.temperatures_c}")

        if len(self.soc_grid) < 2:
            raise ValueError("soc_grid must contain at least 2 points")
        for i in range(1, len(self.soc_grid)):
            if self.soc_grid[i] <= self.soc_grid[i - 1]:
                raise ValueError(f"soc_grid must be strictly increasing: {self.soc_grid}")

        if self.soc_grid[0] < 0.0 or self.soc_grid[-1] > 1.0:
            raise ValueError(f"soc_grid must span within [0.0, 1.0]: [{self.soc_grid[0]}, {self.soc_grid[-1]}]")

        # Q(T) grid and lengths
        if len(self.q_table_temps_c) != len(self.q_table_ah):
            raise ValueError(f"q_table_temps_c and q_table_ah length mismatch: {len(self.q_table_temps_c)} vs {len(self.q_table_ah)}")
        for i in range(1, len(self.q_table_temps_c)):
            if self.q_table_temps_c[i] <= self.q_table_temps_c[i - 1]:
                raise ValueError("q_table_temps_c must be strictly increasing")
        for q in self.q_table_ah:
            if q <= 0.0:
                raise ValueError(f"All q_table_ah entries must be positive: {q}")

        # M(T) grid and lengths
        if len(self.m_table_temps_c) != len(self.m_table_v):
            raise ValueError(f"m_table_temps_c and m_table_v length mismatch: {len(self.m_table_temps_c)} vs {len(self.m_table_v)}")
        for i in range(1, len(self.m_table_temps_c)):
            if self.m_table_temps_c[i] <= self.m_table_temps_c[i - 1]:
                raise ValueError("m_table_temps_c must be strictly increasing")
        for m in self.m_table_v:
            if m <= 0.0:
                raise ValueError(f"All m_table_v entries must be positive: {m}")

        # OCV table checks
        soc_len = len(self.soc_grid)
        for t in self.temperatures_c:
            key1 = f"{t:.1f}"
            key2 = str(t)
            key = key1 if key1 in self.ocv_table else (key2 if key2 in self.ocv_table else None)
            if key is None:
                raise ValueError(f"Missing temperature key '{key1}' in ocv_table")
            row = self.ocv_table[key]
            if len(row) != soc_len:
                raise ValueError(f"ocv_table row for {t} has length {len(row)}, expected {soc_len}")
            for j in range(1, len(row)):
                if row[j] < row[j - 1]:
                    raise ValueError(f"ocv_table must be non-decreasing with SOC: {row}")

        # Impedance tables
        table_names = [
            ("r0_table", self.r0_table),
            ("r1_table", self.r1_table),
            ("tau1_table", self.tau1_table),
            ("r2_table", self.r2_table),
            ("tau2_table", self.tau2_table),
        ]
        for name, tbl in table_names:
            for t in self.temperatures_c:
                k1 = f"{t:.1f}"
                k2 = str(t)
                k = k1 if k1 in tbl else (k2 if k2 in tbl else None)
                if k is None:
                    raise ValueError(f"Missing temperature key '{k1}' in {name}")
                if tbl[k] <= 0.0:
                    raise ValueError(f"Value for {name}[{k}] must be positive: {tbl[k]}")

        # Scalars
        if self.nominal_capacity_ah <= 0.0:
            raise ValueError(f"nominal_capacity_ah must be positive: {self.nominal_capacity_ah}")
        if self.coulombic_efficiency <= 0.0 or self.coulombic_efficiency > 1.0:
            raise ValueError(f"coulombic_efficiency must be in (0, 1]: {self.coulombic_efficiency}")
        if self.hysteresis_gamma <= 0.0:
            raise ValueError(f"hysteresis_gamma must be positive: {self.hysteresis_gamma}")

        # Envelope
        if self.temp_min_c >= self.temp_max_c:
            raise ValueError(f"temp_min_c ({self.temp_min_c}) must be < temp_max_c ({self.temp_max_c})")
        if self.voltage_min_v >= self.voltage_max_v:
            raise ValueError(f"voltage_min_v ({self.voltage_min_v}) must be < voltage_max_v ({self.voltage_max_v})")
        if self.current_min_a >= self.current_max_a:
            raise ValueError(f"current_min_a ({self.current_min_a}) must be < current_max_a ({self.current_max_a})")

    def sha256(self) -> str:
        """Compute SHA-256 fingerprint over sorted, canonical JSON representation."""
        data = asdict(self)
        canon = json.dumps(data, indent=2, sort_keys=True).encode("utf-8")
        return hashlib.sha256(canon).hexdigest()

    def to_json(self, path_or_buf: Optional[Union[str, Path]] = None) -> str:
        """Serialize calibration to formatted JSON string and optionally save to file."""
        self.validate()
        payload = asdict(self)
        payload["sha256"] = self.sha256()
        text = json.dumps(payload, indent=2, sort_keys=True)
        if path_or_buf is not None:
            p = Path(path_or_buf)
            p.parent.mkdir(parents=True, exist_ok=True)
            with open(p, "w", encoding="utf-8") as f:
                f.write(text)
        return text

    @classmethod
    def from_json(cls, json_str_or_path: Union[str, Path]) -> "CellCalibration":
        """Deserialize and validate calibration from JSON file path or string."""
        p = Path(str(json_str_or_path))
        if p.exists() and p.is_file():
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
        else:
            data = json.loads(str(json_str_or_path))

        data.pop("sha256", None)
        inst = cls(**data)
        inst.validate()
        return inst


def default_calce_calibration() -> CellCalibration:
    """Return default validated calibration for CALCE A123 26650 cells."""
    json_path = Path(__file__).resolve().parent / "calibrations" / "calce_a123_v4.json"
    if json_path.exists():
        return CellCalibration.from_json(json_path)

    # Embedded fallback if JSON file is not present on disk
    temps_c = [-7.4, 0.6, 10.3, 20.1, 27.3, 32.0, 41.9, 52.4]
    soc_grid = [0.0, 0.05, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 1.0]
    ocv_table = {
        "-7.4": [2.2780, 2.9689, 3.1292, 3.2251, 3.2653, 3.2807, 3.2890, 3.2964, 3.3082, 3.3297, 3.3472, 3.3661, 3.5594],
        "0.6": [2.3369, 3.0740, 3.1898, 3.2416, 3.2753, 3.2902, 3.2960, 3.3010, 3.3108, 3.3362, 3.3474, 3.3619, 3.5551],
        "10.3": [2.3131, 3.0843, 3.2024, 3.2444, 3.2771, 3.2954, 3.3005, 3.3053, 3.3128, 3.3432, 3.3529, 3.3699, 3.5381],
        "20.1": [2.2935, 3.0866, 3.2066, 3.2471, 3.2795, 3.3001, 3.3043, 3.3081, 3.3164, 3.3439, 3.3511, 3.3655, 3.5498],
        "27.3": [2.2544, 3.0936, 3.2089, 3.2488, 3.2810, 3.3027, 3.3062, 3.3093, 3.3184, 3.3447, 3.3502, 3.3632, 3.5488],
        "32.0": [2.3200, 3.0854, 3.2074, 3.2474, 3.2795, 3.3021, 3.3062, 3.3097, 3.3176, 3.3434, 3.3490, 3.3616, 3.5640],
        "41.9": [2.2826, 3.0849, 3.2085, 3.2477, 3.2793, 3.3048, 3.3086, 3.3116, 3.3200, 3.3444, 3.3496, 3.3614, 3.5694],
        "52.4": [2.2823, 3.0834, 3.2085, 3.2467, 3.2787, 3.3065, 3.3104, 3.3131, 3.3210, 3.3441, 3.3489, 3.3601, 3.5678],
    }
    r0_table = {"-7.4": 0.26464, "0.6": 0.19804, "10.3": 0.17281, "20.1": 0.15951, "27.3": 0.15851, "32.0": 0.15500, "41.9": 0.15359, "52.4": 0.15371}
    r1_table = {"-7.4": 0.05039, "0.6": 0.04068, "10.3": 0.02288, "20.1": 0.02116, "27.3": 0.01960, "32.0": 0.01392, "41.9": 0.01130, "52.4": 0.00977}
    tau1_table = {"-7.4": 39.45, "0.6": 23.57, "10.3": 27.90, "20.1": 24.90, "27.3": 22.51, "32.0": 18.60, "41.9": 16.53, "52.4": 16.75}
    r2_table = {"-7.4": 0.09463, "0.6": 0.10817, "10.3": 0.04175, "20.1": 0.02722, "27.3": 0.02651, "32.0": 0.01899, "41.9": 0.01462, "52.4": 0.01128}
    tau2_table = {"-7.4": 600.0, "0.6": 600.0, "10.3": 210.41, "20.1": 599.98, "27.3": 600.0, "32.0": 218.24, "41.9": 207.27, "52.4": 600.0}
    q_temps = [20.0, 25.0, 30.0, 40.0, 50.0]
    q_ah = [1.065214687790664, 1.0635616695823449, 1.0730061548855323, 1.0801900610401025, 1.0809567995408316]
    m_temps = [20.0, 25.0, 30.0, 40.0, 50.0]
    m_v = [0.02701, 0.01719, 0.02436, 0.02155, 0.01988]

    return CellCalibration(
        calibration_id="calce_a123_v4",
        schema_version="1.0",
        validation_status="DEVELOPMENT_VALIDATED_CALCE_20_50C",
        temperatures_c=temps_c,
        soc_grid=soc_grid,
        ocv_table=ocv_table,
        r0_table=r0_table,
        r1_table=r1_table,
        tau1_table=tau1_table,
        r2_table=r2_table,
        tau2_table=tau2_table,
        q_table_temps_c=q_temps,
        q_table_ah=q_ah,
        m_table_temps_c=m_temps,
        m_table_v=m_v,
        nominal_capacity_ah=1.0635616695823449,
    )
