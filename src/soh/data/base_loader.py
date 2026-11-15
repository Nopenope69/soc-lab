"""Base classes and containers for battery cycling aging data.

Maintains strict separation between physical batteries to prevent data leakage,
and enforces Reference Measurement Protocols on ground truth calculation.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple
import numpy as np

from soh.common.contracts import CycleRecord
from soh.common.protocols import CellReferenceSpec, ReferenceMeasurementProtocol


@dataclass
class SohBatteryData:
    """Complete multi-cycle life data for an individual physical cell."""

    cell_id: str
    spec: CellReferenceSpec
    cycles: List[CycleRecord] = field(default_factory=list)
    bol_capacity_ah: Optional[float] = None
    bol_resistance_ohm: Optional[float] = None

    @property
    def cycle_count(self) -> int:
        return len(self.cycles)

    @property
    def protocol(self) -> ReferenceMeasurementProtocol:
        return ReferenceMeasurementProtocol(self.spec)

    def compute_ground_truths(self) -> None:
        """Compute rated-relative and BOL-relative ground truth labels for all cycles."""
        if not self.cycles:
            return

        # Determine BOL capacity from cycle 0 or earliest reference cycle with valid measurement
        if self.bol_capacity_ah is None:
            for cycle in self.cycles:
                if cycle.measured_capacity_ah is not None and cycle.measured_capacity_ah > 0:
                    self.bol_capacity_ah = cycle.measured_capacity_ah
                    break

        # Determine BOL resistance from earliest reference cycle with valid resistance
        if self.bol_resistance_ohm is None:
            for cycle in self.cycles:
                if cycle.measured_resistance_ohm is not None and cycle.measured_resistance_ohm > 0:
                    self.bol_resistance_ohm = cycle.measured_resistance_ohm
                    break

        # Apply Reference Measurement Protocol to compute SOH metrics
        for cycle in self.cycles:
            if cycle.measured_capacity_ah is not None and cycle.measured_capacity_ah > 0:
                cycle.soh_c_rated_true = self.protocol.compute_soh_c_rated(cycle.measured_capacity_ah)
                if self.bol_capacity_ah is not None and self.bol_capacity_ah > 0:
                    cycle.soh_c_bol_true = self.protocol.compute_soh_c_bol(
                        cycle.measured_capacity_ah, self.bol_capacity_ah
                    )

            if cycle.measured_resistance_ohm is not None and cycle.measured_resistance_ohm > 0:
                cycle.soh_r_rated_true = self.protocol.compute_soh_r_rated(cycle.measured_resistance_ohm)
                if self.bol_resistance_ohm is not None and self.bol_resistance_ohm > 0:
                    cycle.soh_r_bol_true = self.protocol.compute_soh_r_bol(
                        cycle.measured_resistance_ohm, self.bol_resistance_ohm
                    )


@dataclass
class SohDataset:
    """Collection of batteries for multi-battery training and validation."""

    batteries: Dict[str, SohBatteryData] = field(default_factory=dict)

    def add_battery(self, battery: SohBatteryData) -> None:
        battery.compute_ground_truths()
        self.batteries[battery.cell_id] = battery

    @property
    def cell_ids(self) -> List[str]:
        return sorted(list(self.batteries.keys()))

    def split_by_battery(
        self,
        train_cell_ids: Sequence[str],
        test_cell_ids: Sequence[str],
    ) -> Tuple["SohDataset", "SohDataset"]:
        """Grouped split by physical cell identifier to strictly prevent leakage."""
        train_ds = SohDataset({cid: self.batteries[cid] for cid in train_cell_ids if cid in self.batteries})
        test_ds = SohDataset({cid: self.batteries[cid] for cid in test_cell_ids if cid in self.batteries})
        return train_ds, test_ds

    def get_all_cycles(self) -> List[Tuple[str, CycleRecord]]:
        """Return flattened list of (cell_id, cycle) pairs."""
        res = []
        for cid, bdata in self.batteries.items():
            for c in bdata.cycles:
                res.append((cid, c))
        return res


class AbstractAgingDataLoader(ABC):
    """Abstract interface for aging cycle dataset loaders."""

    @abstractmethod
    def load_battery(self, cell_id: str, data_dir: Path) -> SohBatteryData:
        """Load single battery aging data."""
        ...

    @abstractmethod
    def load_dataset(self, data_dir: Path) -> SohDataset:
        """Load full battery cohort."""
        ...
