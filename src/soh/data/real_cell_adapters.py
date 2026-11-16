"""Real-cell data adapters, reference measurement qualification, and dataset provenance.

Maintains strict provenance metadata and reference qualification across:
1. LG M50T (21700 NMC-811 / Graphite-Si, 5.0 Ah)
2. CALCE A123 (A123 LiFePO4, measured capacity about 1.06 Ah (A1-007) and about 1.09 Ah (A1-008) at 25 C, format unverified)
3. Oxford Battery Degradation Dataset (Kokam Pouch NMC-LCO, 0.74 Ah)
4. MIT / Stanford Fast-Charging Dataset (Severson et al. 2019, A123 LFP, 1.1 Ah)

Mandatory Qualification Constraints:
- CALCE characterization cycles must NOT be classified as pristine BOL ground truth.
- Real resistance SOH validation must NOT be claimed without standardized, comparable
  DCIR / HPPC reference measurements.
"""

from dataclasses import dataclass, field
from enum import Enum
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import numpy as np

from soh.common.contracts import CycleRecord
from soh.common.protocols import (
    CellReferenceSpec,
    ReferenceMeasurementProtocol,
    ReferenceProvenance,
    ReferenceProvenanceType,
)
from soh.data.base_loader import SohBatteryData, SohDataset
from soh.data.calce_aging import CalceAgingDataLoader
from soh.data.pybamm_simulator import PybammDegradationSimulator


class DatasetSource(str, Enum):
    """Recognized open benchmark and laboratory battery degradation datasets."""

    LG_M50T = "LG_M50T_Chen2020"
    CALCE_A123 = "CALCE_A123_APR18650M1A"
    OXFORD = "Oxford_Battery_Degradation_Kokam"
    MIT_STANFORD = "MIT_Stanford_FastCharging_Severson"


class DatasetCategory(str, Enum):
    """Rigorous classification of dataset generation pedigree."""

    EXPERIMENTAL = "EXPERIMENTAL"  # Physical cells tested in laboratory or field cyclers
    SIMULATION = "SIMULATION"      # Physics-based continuum/electrochemical simulations (e.g. PyBaMM)
    DERIVED = "DERIVED"            # Secondary feature datasets or synthesized variations


@dataclass
class DatasetProvenanceRecord:
    """Rigorous documentation of real-cell data origin, protocol, and limitations."""

    dataset_source: DatasetSource
    dataset_category: DatasetCategory
    chemistry: str
    form_factor: str
    nominal_capacity_ah: float
    nominal_voltage_v: float
    voltage_range_v: Tuple[float, float]
    provenance_type: ReferenceProvenanceType
    is_pristine_bol: bool
    is_resistance_validated: bool
    resistance_measurement_protocol: Optional[str]
    qualification_notes: str
    citation: str
    cell_identifiers: List[str] = field(default_factory=list)
    batch_identifiers: List[str] = field(default_factory=list)
    ground_truth_protocol: str = "Standard 0.5C Reference Measurement Protocol"
    bol_capacity_measurement_ah: Optional[float] = None
    operating_temperature_c: float = 25.0


def verify_physical_dataset_manifest(dataset_id: str) -> None:
    """Guard: anything labelled physical must be loaded from files whose hashes are in data/manifests."""
    manifest_path = Path("data/manifests") / f"{dataset_id}.sha256"
    if not manifest_path.exists():
        raise ValueError(
            f"Provenance Guard Failure: physical dataset '{dataset_id}' has no manifest at {manifest_path}. "
            "Rule R2: physical datasets must be backed by a verified manifest in data/manifests/."
        )
    with open(manifest_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
    if any(line.strip().startswith("# Status: NOT_DOWNLOADED") for line in lines):
        raise ValueError(
            f"Provenance Guard Failure: physical dataset '{dataset_id}' status is NOT_DOWNLOADED. "
            "Cannot claim physical qualification without files on disk."
        )
    hash_lines = [l for l in lines if l.strip() and not l.strip().startswith("#")]
    if len(hash_lines) == 0:
        raise ValueError(
            f"Provenance Guard Failure: manifest for physical dataset '{dataset_id}' contains zero verified hashes."
        )


# Registry of verified real-cell dataset provenance contracts
DATASET_PROVENANCE_REGISTRY: Dict[DatasetSource, DatasetProvenanceRecord] = {
    DatasetSource.LG_M50T: DatasetProvenanceRecord(
        dataset_source=DatasetSource.LG_M50T,
        dataset_category=DatasetCategory.SIMULATION,
        chemistry="NMC-811 / Graphite-Si",
        form_factor="21700 Cylindrical",
        nominal_capacity_ah=5.0,
        nominal_voltage_v=3.63,
        voltage_range_v=(2.50, 4.20),
        provenance_type=ReferenceProvenanceType.ELECTROCHEMICAL_MODEL,
        is_pristine_bol=True,
        is_resistance_validated=True,
        resistance_measurement_protocol="PyBaMM Chen2020 SPM/DFN electrochemical model simulation with calibrated SEI parameters",
        qualification_notes="ELECTROCHEMICAL SIMULATION BENCHMARK, NOT physically measured LG cell hardware. Represents physics-governed continuum model (Chen et al. 2020). Pristine factory acceptance reference.",
        citation="Chen et al., J. Electrochem. Soc. 167 (2020) 080534",
        cell_identifiers=["PYBAMM_CELL_25C_1C", "PYBAMM_CELL_45C_1C", "PYBAMM_CELL_15C_1C", "PYBAMM_CELL_25C_05C"],
        batch_identifiers=["SIMULATION_CHEN2020"],
        ground_truth_protocol="PyBaMM DFN integration (0.5C CC-CV at 25°C to 2.5V cutoff)",
        bol_capacity_measurement_ah=5.00,
        operating_temperature_c=25.0,
    ),
    DatasetSource.CALCE_A123: DatasetProvenanceRecord(
        dataset_source=DatasetSource.CALCE_A123,
        dataset_category=DatasetCategory.SIMULATION,
        chemistry="LiFePO4 (LFP) / Graphite",
        form_factor="A123 LiFePO4, format unverified",
        nominal_capacity_ah=1.10,
        nominal_voltage_v=3.30,
        voltage_range_v=(2.00, 3.60),
        provenance_type=ReferenceProvenanceType.SYNTHETIC,
        is_pristine_bol=False,
        is_resistance_validated=False,
        resistance_measurement_protocol="Instantaneous cycler load perturbation. Non-standardized; NOT equivalent to standardized DCIR HPPC.",
        qualification_notes="SYNTHETIC cohort generated via analytical degradation formula with seeded RNG (default_rng(202)). Not real laboratory data files. Resistance ground truth is unvalidated.",
        citation="Center for Advanced Life Cycle Engineering (CALCE), University of Maryland (synthetic analytical reproduction)",
        cell_identifiers=["SYN_CALCE_CS2_35", "SYN_CALCE_CS2_36", "SYN_CALCE_CS2_37", "SYN_CALCE_CS2_38"],
        batch_identifiers=["SYN_BATCH_CALCE_CS2"],
        ground_truth_protocol="Synthetic analytical degradation curve (2.0V - 3.6V at 25°C)",
        bol_capacity_measurement_ah=1.06,
        operating_temperature_c=25.0,
    ),
    DatasetSource.OXFORD: DatasetProvenanceRecord(
        dataset_source=DatasetSource.OXFORD,
        dataset_category=DatasetCategory.SIMULATION,
        chemistry="NMC-LCO blend / Graphite",
        form_factor="Kokam 740mAh Pouch Cell (SLPB533459H4)",
        nominal_capacity_ah=0.74,
        nominal_voltage_v=3.70,
        voltage_range_v=(2.70, 4.20),
        provenance_type=ReferenceProvenanceType.SYNTHETIC,
        is_pristine_bol=False,
        is_resistance_validated=False,
        resistance_measurement_protocol="Periodic characterization at 40°C (simulated). Resistance SOH unvalidated on physical cells.",
        qualification_notes="SYNTHETIC cohort generated via analytical degradation formula (fade = 0.0012*k**0.55 + 0.00015*k) with seeded RNG (default_rng(101)). Not real laboratory data files.",
        citation="Howey et al., Oxford Battery Intelligence Lab (synthetic analytical reproduction)",
        cell_identifiers=["SYN_OXFORD_CELL_01", "SYN_OXFORD_CELL_02", "SYN_OXFORD_CELL_03", "SYN_OXFORD_CELL_04"],
        batch_identifiers=["SYN_BATCH_KOKAM_SLPB533459H4_2014"],
        ground_truth_protocol="Synthetic analytical power-law curve at 40°C",
        bol_capacity_measurement_ah=0.74,
        operating_temperature_c=40.0,
    ),
    DatasetSource.MIT_STANFORD: DatasetProvenanceRecord(
        dataset_source=DatasetSource.MIT_STANFORD,
        dataset_category=DatasetCategory.SIMULATION,
        chemistry="LiFePO4 (LFP) / Graphite",
        form_factor="A123 18650 Cylindrical",
        nominal_capacity_ah=1.10,
        nominal_voltage_v=3.30,
        voltage_range_v=(2.00, 3.60),
        provenance_type=ReferenceProvenanceType.SYNTHETIC,
        is_pristine_bol=False,
        is_resistance_validated=False,
        resistance_measurement_protocol="Estimated discharge voltage drop (simulated). Resistance SOH unvalidated on physical cells.",
        qualification_notes="SYNTHETIC cohort generated via analytical degradation formula with knee rollover at cycle 45 and seeded RNG (default_rng(202)); manufacturing batch metadata available. Not real laboratory data files.",
        citation="Severson et al., Nature Energy 4 (2019) 383–391 (synthetic analytical reproduction)",
        cell_identifiers=["SYN_MIT_CELL_BATCH_2017-05-12_01", "SYN_MIT_CELL_BATCH_2017-06-30_02", "SYN_MIT_CELL_BATCH_2017-05-12_03", "SYN_MIT_CELL_BATCH_2017-06-30_04"],
        batch_identifiers=["SYN_BATCH_2017-05-12", "SYN_BATCH_2017-06-30"],
        ground_truth_protocol="Synthetic analytical knee-rollover curve",
        bol_capacity_measurement_ah=1.08,
        operating_temperature_c=30.0,
    ),
}


class RealCellDataLoader:
    """Unified loader and validator for standardized real-cell battery degradation datasets."""

    def __init__(self, raw_data_dir: Optional[Path] = None):
        self.raw_data_dir = raw_data_dir or Path("data/raw")

    def load_calce_a123_synthetic(
        self, cell_ids: Optional[List[str]] = None, num_cells: int = 4, num_cycles: int = 25
    ) -> SohDataset:
        """Load synthetic CALCE A123 cohort generated via analytical formulas.
        
        Analytical degradation formula with seeded RNG (default_rng(202)).
        Cell IDs and batch IDs prefixed with SYN_.
        """
        provenance = DATASET_PROVENANCE_REGISTRY[DatasetSource.CALCE_A123]
        dataset = SohDataset()
        rng = np.random.default_rng(202)
        cids = cell_ids or [f"SYN_CALCE_CS2_{35+i}" for i in range(num_cells)]
        cids = [cid if cid.startswith("SYN_") else f"SYN_{cid}" for cid in cids]

        for i, cid in enumerate(cids):
            spec = CellReferenceSpec(
                cell_id=cid,
                chemistry=provenance.chemistry,
                nominal_capacity_ah=provenance.nominal_capacity_ah,
                v_max=provenance.voltage_range_v[1],
                v_min=provenance.voltage_range_v[0],
                t_ref_c=25.0,
                nominal_resistance_ohm=0.015,
                provenance=ReferenceProvenance(
                    provenance_type=ReferenceProvenanceType.SYNTHETIC,
                    is_pristine_bol=provenance.is_pristine_bol,
                    qualification_notes=provenance.qualification_notes,
                ),
            )
            bdata = SohBatteryData(cell_id=cid, spec=spec)
            bol_cap = provenance.nominal_capacity_ah * rng.normal(0.96, 0.01)  # Non-pristine received cell
            bol_res = 0.015 * rng.normal(1.04, 0.02)
            bdata.bol_capacity_ah = bol_cap
            bdata.bol_resistance_ohm = bol_res

            deg_rate_c = 0.00045 + 0.00005 * rng.standard_normal()
            deg_rate_r = 0.00085 + 0.00010 * rng.standard_normal()

            for c in range(num_cycles):
                cap = max(0.4, bol_cap * (1.0 - deg_rate_c * c) + rng.normal(0, 0.001))
                res = max(0.01, bol_res * (1.0 + deg_rate_r * c) + rng.normal(0, 0.0001))

                t_points = np.linspace(0, 3600, 150)
                soc_prof = np.linspace(0.1, 0.95, 150)
                v_points = 3.0 + 0.35 * soc_prof + rng.normal(0, 0.001, 150)
                i_points = np.ones(150) * (provenance.nominal_capacity_ah * 0.5)

                rec = CycleRecord(
                    cycle_index=c,
                    time_s=t_points,
                    voltage_v=v_points,
                    current_a=i_points,
                    temp_c=np.ones(150) * 25.0,
                    ah_throughput=float(c * provenance.nominal_capacity_ah * 2.0),
                    measured_capacity_ah=cap,
                    measured_resistance_ohm=res,
                    soh_c_bol_true=cap / bol_cap,
                    soh_c_rated_true=cap / provenance.nominal_capacity_ah,
                    soh_r_bol_true=bol_res / res,
                    soh_r_rated_true=0.015 / res,
                    metadata={"source": "SYN_CALCE_A123", "batch_id": "SYN_BATCH_CALCE_CS2"},
                )
                bdata.cycles.append(rec)
            dataset.add_battery(bdata)

        return dataset

    def load_calce_a123(self, *args, **kwargs) -> SohDataset:
        """Alias for load_calce_a123_synthetic."""
        return self.load_calce_a123_synthetic(*args, **kwargs)

    def load_lg_m50t_pybamm(self, num_cycles: int = 15) -> SohDataset:
        """Load LG M50T 21700 electrochemical benchmark cohort."""
        sim = PybammDegradationSimulator()
        dataset = sim.generate_cohort(num_cycles=num_cycles, chemistry_param="Chen2020")
        provenance = DATASET_PROVENANCE_REGISTRY[DatasetSource.LG_M50T]

        for cid, bdata in dataset.batteries.items():
            bdata.spec.provenance = ReferenceProvenance(
                provenance_type=provenance.provenance_type,
                is_pristine_bol=provenance.is_pristine_bol,
                qualification_notes=provenance.qualification_notes,
            )

        return dataset

    def create_oxford_synthetic_cohort(self, num_cells: int = 4, num_cycles: int = 40) -> SohDataset:
        """Create synthetic reference cohort matching Oxford specifications via analytical power-law formulas:
        
        Kokam 740mAh pouch cells modeled at 40°C.
        Cell IDs and batch IDs prefixed with SYN_.
        """
        provenance = DATASET_PROVENANCE_REGISTRY[DatasetSource.OXFORD]
        dataset = SohDataset()

        spec = CellReferenceSpec(
            cell_id="SYN_OXFORD_KOKAM_740MAH",
            chemistry=provenance.chemistry,
            nominal_capacity_ah=provenance.nominal_capacity_ah,
            v_max=provenance.voltage_range_v[1],
            v_min=provenance.voltage_range_v[0],
            t_ref_c=40.0,
            nominal_resistance_ohm=0.035,
            provenance=ReferenceProvenance(
                provenance_type=ReferenceProvenanceType.SYNTHETIC,
                is_pristine_bol=provenance.is_pristine_bol,
                qualification_notes=provenance.qualification_notes,
            ),
        )

        rng = np.random.default_rng(101)
        for i in range(num_cells):
            cid = f"SYN_OXFORD_CELL_0{i+1}"
            bol_cap = provenance.nominal_capacity_ah * rng.normal(1.0, 0.01)
            bol_res = 0.035 * rng.normal(1.0, 0.02)
            bdata = SohBatteryData(cell_id=cid, spec=spec, bol_capacity_ah=bol_cap, bol_resistance_ohm=bol_res)

            for k in range(num_cycles):
                # 40°C accelerated thermal degradation formula
                fade = 0.0012 * (k ** 0.55) + 0.00015 * k
                soh_c = max(0.60, min(1.0, 1.0 - fade))
                r_growth = 1.0 + 0.003 * (k ** 0.65)
                soh_r = 1.0 / r_growth

                t_pts = np.linspace(0, 3600, 60)
                v_pts = np.linspace(3.0, 4.2, 60)
                i_pts = np.full_like(t_pts, -0.74)
                temp_pts = np.full_like(t_pts, 40.0)

                rec = CycleRecord(
                    cycle_index=k,
                    time_s=t_pts,
                    voltage_v=v_pts,
                    current_a=i_pts,
                    temp_c=temp_pts,
                    ah_throughput=k * bol_cap * 2.0,
                    measured_capacity_ah=bol_cap * soh_c,
                    measured_resistance_ohm=bol_res * r_growth,
                    soh_c_bol_true=soh_c,
                    soh_c_rated_true=soh_c,
                    soh_r_bol_true=soh_r,
                    soh_r_rated_true=soh_r,
                    metadata={"temp_c_avg": 40.0, "current_a_avg": 0.74, "soc_avg": 0.50, "batch_id": "SYN_BATCH_OXFORD_KOKAM"},
                )
                bdata.cycles.append(rec)

            dataset.add_battery(bdata)

        return dataset

    def create_oxford_reference_cohort(self, *args, **kwargs) -> SohDataset:
        """Alias for create_oxford_synthetic_cohort."""
        return self.create_oxford_synthetic_cohort(*args, **kwargs)

    def create_mit_stanford_synthetic_cohort(
        self, num_cells: int = 4, num_cycles: int = 60
    ) -> SohDataset:
        """Create synthetic reference cohort matching MIT/Stanford specifications via analytical knee-rollover formulas:
        
        A123 1.1 Ah LFP cylindrical cells with batch metadata and knee-point rollover.
        Cell IDs and batch IDs prefixed with SYN_.
        """
        provenance = DATASET_PROVENANCE_REGISTRY[DatasetSource.MIT_STANFORD]
        dataset = SohDataset()

        spec = CellReferenceSpec(
            cell_id="SYN_MIT_A123_1.1AH",
            chemistry=provenance.chemistry,
            nominal_capacity_ah=provenance.nominal_capacity_ah,
            v_max=provenance.voltage_range_v[1],
            v_min=provenance.voltage_range_v[0],
            t_ref_c=30.0,
            nominal_resistance_ohm=0.015,
            provenance=ReferenceProvenance(
                provenance_type=ReferenceProvenanceType.SYNTHETIC,
                is_pristine_bol=provenance.is_pristine_bol,
                qualification_notes=provenance.qualification_notes,
            ),
        )

        batches = ["SYN_BATCH_2017-05-12", "SYN_BATCH_2017-06-30"]
        rng = np.random.default_rng(202)

        for i in range(num_cells):
            batch_id = batches[i % len(batches)]
            cid = f"SYN_MIT_CELL_{batch_id}_0{i+1}"
            bol_cap = provenance.nominal_capacity_ah * rng.normal(1.0, 0.012)
            bol_res = 0.015 * rng.normal(1.0, 0.025)
            bdata = SohBatteryData(cell_id=cid, spec=spec, bol_capacity_ah=bol_cap, bol_resistance_ohm=bol_res)

            # Knee point near cycle 45 for this accelerated cohort
            n_knee = 45.0
            for k in range(num_cycles):
                fade_linear = 0.0008 * k
                fade_knee = 0.035 / (1.0 + np.exp(-max(-10.0, min(10.0, (k - n_knee) / 4.0))))
                soh_c = max(0.50, min(1.0, 1.0 - (fade_linear + fade_knee)))

                r_mult = 1.0 + 0.005 * k + 0.05 * ((k / n_knee) ** 2.0)
                soh_r = 1.0 / r_mult

                t_pts = np.linspace(0, 3600, 60)
                v_pts = np.linspace(2.5, 3.6, 60)
                i_pts = np.full_like(t_pts, -4.0)  # High rate fast charge ~4C
                temp_pts = np.full_like(t_pts, 30.0)

                rec = CycleRecord(
                    cycle_index=k,
                    time_s=t_pts,
                    voltage_v=v_pts,
                    current_a=i_pts,
                    temp_c=temp_pts,
                    ah_throughput=k * bol_cap * 2.0,
                    measured_capacity_ah=bol_cap * soh_c,
                    measured_resistance_ohm=bol_res * r_mult,
                    soh_c_bol_true=soh_c,
                    soh_c_rated_true=soh_c,
                    soh_r_bol_true=soh_r,
                    soh_r_rated_true=soh_r,
                    metadata={
                        "temp_c_avg": 30.0,
                        "batch_id": batch_id,
                        "charging_policy": "4C_fast_charge",
                        "soc_avg": 0.50,
                    },
                )
                bdata.cycles.append(rec)

            dataset.add_battery(bdata)

        return dataset

    def create_mit_stanford_reference_cohort(self, *args, **kwargs) -> SohDataset:
        """Alias for create_mit_stanford_synthetic_cohort."""
        return self.create_mit_stanford_synthetic_cohort(*args, **kwargs)

