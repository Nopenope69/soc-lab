"""Reference measurement protocols and cell-specific specifications.

Provides qualified definitions of Capacity SOH and Resistance SOH against
standard reference measurement conditions (temperature, C-rate, cutoff voltages,
and HPPC pulse parameters) rather than unqualified instantaneous readings.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional, Tuple
from pydantic import BaseModel, Field


class ReferenceProvenanceType(str, Enum):
    """Source classification and pedigree for baseline cell health references."""

    FACTORY_ACCEPTANCE_TEST = "FACTORY_ACCEPTANCE_TEST"          # Pristine cell measured in-factory under exact RMP
    MANUFACTURER_SPECIFICATION = "MANUFACTURER_SPECIFICATION"     # Datasheet nominal characterization
    CHARACTERIZATION_CYCLE = "CHARACTERIZATION_CYCLE"             # Laboratory characterization test / initial reference cycle
    FLEET_DERIVED_CONSENSUS = "FLEET_DERIVED_CONSENSUS"           # Statistical median across deployed fleet
    ELECTROCHEMICAL_MODEL = "ELECTROCHEMICAL_MODEL"               # Inverted OCV / physics model curve
    UNAVAILABLE_DEGRADED_ENTRY = "UNAVAILABLE_DEGRADED_ENTRY"     # Unknown BOL / second-life pack entry
    SYNTHETIC = "SYNTHETIC"                                       # Analytical formula or synthetic simulation


class ReferenceProvenance(BaseModel):
    """Explicit metadata declaring how the BOL reference was obtained."""

    provenance_type: ReferenceProvenanceType = Field(
        default=ReferenceProvenanceType.FACTORY_ACCEPTANCE_TEST,
        description="Pedigree category of the reference",
    )
    confidence_score: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Confidence in reference accuracy (0.0 to 1.0)",
    )
    protocol_id: str = Field(
        default="RMP_STD_25C",
        description="Standardized measurement protocol identifier",
    )
    temperature_c: float = Field(
        default=25.0,
        description="Temperature at reference characterization [°C]",
    )
    c_rate: float = Field(
        default=0.5,
        description="Charge/discharge rate during characterization [C]",
    )
    source_notes: str = Field(
        default="Standard factory calibration",
        description="Detailed provenance audit trail",
    )
    is_pristine_bol: bool = Field(
        default=True,
        description="Whether this reference is a pristine BOL baseline or laboratory characterization",
    )
    qualification_notes: Optional[str] = Field(
        default=None,
        description="Detailed reference qualification and limitation notes",
    )
    confidence_interval_95: Optional[Tuple[float, float]] = Field(
        default=None,
        description="95% confidence interval for reference measurement",
    )


class CellReferenceSpec(BaseModel):
    """Chemistry- and cell-specific reference qualification parameters."""

    cell_id: str = Field(description="Unique cell / model identifier")
    chemistry: str = Field(description="Electrochemical chemistry: LFP, NMC, NCA, etc.")
    nominal_capacity_ah: float = Field(gt=0.0, description="Manufacturer rated nominal capacity [Ah]")
    v_max: float = Field(gt=0.0, description="Upper charge cutoff voltage [V]")
    v_min: float = Field(gt=0.0, description="Lower discharge cutoff voltage [V]")
    t_ref_c: float = Field(default=25.0, description="Standard reference temperature [°C]")
    c_rate_ref_discharge: float = Field(default=0.5, gt=0.0, description="Reference discharge C-rate")
    c_rate_ref_charge: float = Field(default=0.5, gt=0.0, description="Reference charge C-rate")
    hppc_soc_ref: float = Field(default=0.5, ge=0.0, le=1.0, description="Reference HPPC SOC level (0..1)")
    hppc_pulse_duration_s: float = Field(default=10.0, gt=0.0, description="HPPC discharge pulse duration [s]")
    hppc_pulse_c_rate: float = Field(default=1.0, gt=0.0, description="HPPC discharge pulse C-rate")
    nominal_resistance_ohm: Optional[float] = Field(default=None, gt=0.0, description="Rated BOL DCIR at reference conditions [Ω]")
    provenance: ReferenceProvenance = Field(
        default_factory=ReferenceProvenance,
        description="BOL reference provenance and confidence metadata",
    )


@dataclass(frozen=True)
class ReferenceMeasurementProtocol:
    """Standardized Reference Measurement Protocol (RMP) helper."""

    spec: CellReferenceSpec

    def compute_soh_c_rated(self, measured_capacity_ah: float) -> float:
        """Compute rated-relative capacity SOH: C_actual / C_rated."""
        if self.spec.nominal_capacity_ah <= 0:
            raise ValueError("Nominal capacity must be positive.")
        return measured_capacity_ah / self.spec.nominal_capacity_ah

    def compute_soh_c_bol(self, measured_capacity_ah: float, bol_capacity_ah: float) -> float:
        """Compute measured BOL-relative capacity retention: C_actual / C_BOL."""
        if measured_capacity_ah <= 0:
            raise ValueError("Measured capacity must be positive.")
        if bol_capacity_ah <= 0:
            raise ValueError("BOL capacity must be positive.")
        return measured_capacity_ah / bol_capacity_ah

    def compute_soh_r_bol(self, measured_resistance_ohm: float, bol_resistance_ohm: float) -> float:
        """Compute measured BOL-relative resistance SOH: R_BOL / R_actual.
        
        Healthy cell is 1.0; when resistance doubles (200% DCIR), SOH_R becomes 0.5.
        """
        if measured_resistance_ohm <= 0:
            raise ValueError("Measured resistance must be positive.")
        if bol_resistance_ohm <= 0:
            raise ValueError("BOL resistance must be positive.")
        return bol_resistance_ohm / measured_resistance_ohm

    def compute_soh_r_rated(self, measured_resistance_ohm: float) -> Optional[float]:
        """Compute rated-relative resistance SOH: R_rated / R_actual."""
        if self.spec.nominal_resistance_ohm is None or self.spec.nominal_resistance_ohm <= 0:
            return None
        if measured_resistance_ohm <= 0:
            raise ValueError("Measured resistance must be positive.")
        return self.spec.nominal_resistance_ohm / measured_resistance_ohm

    def is_reference_temperature(self, temp_c: float, tolerance_c: float = 2.0) -> bool:
        """Check if temperature is within reference bounds."""
        return abs(temp_c - self.spec.t_ref_c) <= tolerance_c
