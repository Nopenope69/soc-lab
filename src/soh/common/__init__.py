"""Common contracts, units, protocols, and eligibility checks."""

from soh.common.contracts import (
    CycleRecord,
    EstimationStatus,
    FeatureQualityRecord,
    PartialWindow,
    QualificationStatus,
    SOHState,
    SohEstimate,
    SohMeasurement,
)
from soh.common.eligibility import (
    PulseEligibilityConfig,
    WindowEligibilityConfig,
    WindowEvaluator,
)
from soh.common.protocols import CellReferenceSpec, ReferenceMeasurementProtocol
from soh.common.units import (
    CURRENT_POLARITY_CHARGE,
    CURRENT_POLARITY_DISCHARGE,
    ah_to_as,
    as_to_ah,
    celsius_to_kelvin,
    is_charging,
    is_discharging,
    is_resting,
    kelvin_to_celsius,
)

__all__ = [
    "CURRENT_POLARITY_CHARGE",
    "CURRENT_POLARITY_DISCHARGE",
    "CellReferenceSpec",
    "CycleRecord",
    "EstimationStatus",
    "FeatureQualityRecord",
    "PartialWindow",
    "PulseEligibilityConfig",
    "QualificationStatus",
    "ReferenceMeasurementProtocol",
    "SOHState",
    "SohEstimate",
    "SohMeasurement",
    "WindowEligibilityConfig",
    "WindowEvaluator",
    "ah_to_as",
    "as_to_ah",
    "celsius_to_kelvin",
    "is_charging",
    "is_discharging",
    "is_resting",
    "kelvin_to_celsius",
]
