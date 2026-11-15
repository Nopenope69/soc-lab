"""Synchronized Raw Telemetry Recording Format and Replay Harness.

Implements standard data contracts for raw battery cycling and pulse telemetry:
- Cell identifier (cell_id)
- Chemistry (chemistry)
- Cell batch (batch_id)
- Timestamp (timestamp_s)
- Voltage (voltage_v)
- Current (current_a)
- Temperature (temp_c)
- SOC (soc)
- Charge throughput (ah_throughput)
- Pulse identifier (pulse_id)
- Reference test protocol (reference_protocol)
- Ground-truth measurement and provenance (ground_truth_metadata)

Enforces exact deterministic replay across all SOH and SOC estimators.
"""

from dataclasses import asdict, dataclass, field
import json
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional
import numpy as np

from soh.common.contracts import CycleRecord


@dataclass
class SynchronizedTelemetryRecord:
    """Individual synchronized telemetry sample recorded by battery test bench or BMS.
    
    Contains exactly 12 standardized fields:
    1. cell_id
    2. chemistry
    3. batch_id
    4. timestamp_s
    5. voltage_v
    6. current_a
    7. temp_c
    8. soc
    9. ah_throughput
    10. pulse_id
    11. reference_protocol
    12. ground_truth_metadata
    """

    cell_id: str
    chemistry: str
    batch_id: str
    timestamp_s: float
    voltage_v: float
    current_a: float
    temp_c: float
    soc: Optional[float] = None
    ah_throughput: float = 0.0
    pulse_id: Optional[str] = None
    reference_protocol: str = "USABC_HPPC_10S"
    ground_truth_metadata: Dict[str, Any] = field(default_factory=dict)

    def __init__(
        self,
        cell_id: str,
        chemistry: str,
        batch_id: str,
        timestamp_s: float,
        voltage_v: float,
        current_a: float,
        temp_c: float,
        soc: Optional[float] = None,
        ah_throughput: float = 0.0,
        pulse_id: Optional[str] = None,
        reference_protocol: str = "USABC_HPPC_10S",
        ground_truth_metadata: Optional[Dict[str, Any]] = None,
        ground_truth_soh_c: Optional[float] = None,
        ground_truth_soh_r: Optional[float] = None,
        provenance_category: Optional[str] = None,
        **kwargs: Any,
    ):
        self.cell_id = cell_id
        self.chemistry = chemistry
        self.batch_id = batch_id
        self.timestamp_s = timestamp_s
        self.voltage_v = voltage_v
        self.current_a = current_a
        self.temp_c = temp_c
        self.soc = soc
        self.ah_throughput = ah_throughput
        self.pulse_id = pulse_id
        self.reference_protocol = reference_protocol

        gt_meta = dict(ground_truth_metadata or {})
        if ground_truth_soh_c is not None:
            gt_meta["ground_truth_soh_c"] = ground_truth_soh_c
        if ground_truth_soh_r is not None:
            gt_meta["ground_truth_soh_r"] = ground_truth_soh_r
        if provenance_category is not None:
            gt_meta["provenance_category"] = provenance_category
        gt_meta.update(kwargs)
        self.ground_truth_metadata = gt_meta

    @property
    def ground_truth_soh_c(self) -> Optional[float]:
        return self.ground_truth_metadata.get("ground_truth_soh_c", self.ground_truth_metadata.get("soh_c_true"))

    @property
    def ground_truth_soh_r(self) -> Optional[float]:
        return self.ground_truth_metadata.get("ground_truth_soh_r", self.ground_truth_metadata.get("soh_r_true"))

    @property
    def provenance_category(self) -> str:
        return str(self.ground_truth_metadata.get("provenance_category", "EXPERIMENTAL"))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cell_id": self.cell_id,
            "chemistry": self.chemistry,
            "batch_id": self.batch_id,
            "timestamp_s": self.timestamp_s,
            "voltage_v": self.voltage_v,
            "current_a": self.current_a,
            "temp_c": self.temp_c,
            "soc": self.soc,
            "ah_throughput": self.ah_throughput,
            "pulse_id": self.pulse_id,
            "reference_protocol": self.reference_protocol,
            "ground_truth_metadata": self.ground_truth_metadata,
        }


@dataclass
class SynchronizedTelemetryTrace:
    """Complete synchronized telemetry trace across one or multiple cycles."""

    cell_id: str
    chemistry: str
    batch_id: str
    reference_protocol: str
    records: List[SynchronizedTelemetryRecord] = field(default_factory=list)

    def append(self, record: SynchronizedTelemetryRecord) -> None:
        self.records.append(record)

    @property
    def duration_s(self) -> float:
        if not self.records:
            return 0.0
        return self.records[-1].timestamp_s - self.records[0].timestamp_s

    @property
    def sample_count(self) -> int:
        return len(self.records)

    def to_arrays(self) -> Dict[str, np.ndarray]:
        """Convert trace to synchronized NumPy arrays for vectorized estimators."""
        return {
            "time_s": np.array([r.timestamp_s for r in self.records], dtype=float),
            "voltage_v": np.array([r.voltage_v for r in self.records], dtype=float),
            "current_a": np.array([r.current_a for r in self.records], dtype=float),
            "temp_c": np.array([r.temp_c for r in self.records], dtype=float),
            "soc": np.array([r.soc if r.soc is not None else 0.5 for r in self.records], dtype=float),
            "ah_throughput": np.array([r.ah_throughput for r in self.records], dtype=float),
        }

    def to_cycle_record(self, cycle_index: int = 0) -> CycleRecord:
        """Convert synchronized trace into CycleRecord for estimator consumption."""
        arrs = self.to_arrays()
        gt_c = self.records[-1].ground_truth_soh_c if self.records else None
        gt_r = self.records[-1].ground_truth_soh_r if self.records else None
        thru = float(arrs["ah_throughput"][-1]) if len(arrs["ah_throughput"]) > 0 else 0.0

        return CycleRecord(
            cycle_index=cycle_index,
            time_s=arrs["time_s"],
            voltage_v=arrs["voltage_v"],
            current_a=arrs["current_a"],
            temp_c=arrs["temp_c"],
            ah_throughput=thru,
            soh_c_bol_true=gt_c,
            soh_c_rated_true=gt_c,
            soh_r_bol_true=gt_r,
            soh_r_rated_true=gt_r,
            metadata={
                "cell_id": self.cell_id,
                "chemistry": self.chemistry,
                "batch_id": self.batch_id,
                "reference_protocol": self.reference_protocol,
            },
        )

    def save_json(self, filepath: Path) -> None:
        filepath.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "cell_id": self.cell_id,
            "chemistry": self.chemistry,
            "batch_id": self.batch_id,
            "reference_protocol": self.reference_protocol,
            "sample_count": len(self.records),
            "records": [r.to_dict() for r in self.records],
        }
        with open(filepath, "w") as f:
            json.dump(data, f, indent=2)

    @classmethod
    def load_json(cls, filepath: Path) -> "SynchronizedTelemetryTrace":
        with open(filepath, "r") as f:
            data = json.load(f)
        trace = cls(
            cell_id=data["cell_id"],
            chemistry=data["chemistry"],
            batch_id=data["batch_id"],
            reference_protocol=data["reference_protocol"],
        )
        for r_dict in data["records"]:
            trace.append(SynchronizedTelemetryRecord(**r_dict))
        return trace

    save_to_json = save_json
    load_from_json = load_json


class SynchronizedTelemetryReplayer:
    """Deterministic telemetry stream replayer feeding identical samples to multiple estimators."""

    def __init__(self, trace: SynchronizedTelemetryTrace):
        self.trace = trace
        self._cursor = 0

    def reset(self) -> None:
        self._cursor = 0

    def __iter__(self) -> Iterator[SynchronizedTelemetryRecord]:
        return iter(self.trace.records)

    def step(self) -> Optional[SynchronizedTelemetryRecord]:
        if self._cursor < len(self.trace.records):
            rec = self.trace.records[self._cursor]
            self._cursor += 1
            return rec
        return None
