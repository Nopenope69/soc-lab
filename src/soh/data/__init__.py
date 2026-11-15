"""Data loaders, containers, synthetic aging generators, and window extractors."""

from soh.data.base_loader import (
    AbstractAgingDataLoader,
    SohBatteryData,
    SohDataset,
)
from soh.data.calce_aging import CalceAgingDataLoader
from soh.data.pybamm_simulator import PybammDegradationSimulator, PybammSimulationConfig
from soh.data.real_cell_adapters import (
    DATASET_PROVENANCE_REGISTRY,
    DatasetCategory,
    DatasetProvenanceRecord,
    DatasetSource,
    RealCellDataLoader,
)
from soh.data.synthetic_aging import NonlinearAgingGenerator, SyntheticAgingGenerator
from soh.data.synchronized_telemetry import (
    SynchronizedTelemetryRecord,
    SynchronizedTelemetryReplayer,
    SynchronizedTelemetryTrace,
)
from soh.data.window_extractor import PartialChargeWindowExtractor

__all__ = [
    "AbstractAgingDataLoader",
    "CalceAgingDataLoader",
    "DatasetProvenanceRecord",
    "DatasetSource",
    "DATASET_PROVENANCE_REGISTRY",
    "NonlinearAgingGenerator",
    "PartialChargeWindowExtractor",
    "PybammDegradationSimulator",
    "PybammSimulationConfig",
    "RealCellDataLoader",
    "SohBatteryData",
    "SohDataset",
    "SynchronizedTelemetryRecord",
    "SynchronizedTelemetryReplayer",
    "SynchronizedTelemetryTrace",
    "SyntheticAgingGenerator",
]
