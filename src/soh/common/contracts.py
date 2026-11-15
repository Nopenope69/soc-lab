"""Data contracts for the SOH estimation subsystem.

Defines immutable/validated schemas for raw measurements, cycle records,
health states, quality records, and estimator predictions.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional
import numpy as np
from pydantic import BaseModel, Field


class EstimationStatus(str, Enum):
    """Estimation outcome status."""

    VALID = "VALID"
    INSUFFICIENT_INFORMATION = "INSUFFICIENT_INFORMATION"
    LOW_QUALITY_FEATURE = "LOW_QUALITY_FEATURE"
    OUTLIER_REJECTED = "OUTLIER_REJECTED"
    CONVERGENCE_FAILURE = "CONVERGENCE_FAILURE"
    SKIPPED_DROPOUT = "SKIPPED_DROPOUT"


class QualificationStatus(str, Enum):
    """Independent qualification status for battery health estimates."""

    QUALIFIED = "QUALIFIED"                      # Validated against independent reference ground truth
    PROVISIONALLY_QUALIFIED = "PROVISIONALLY_QUALIFIED"  # Validated under restricted operating conditions
    UNVALIDATED = "UNVALIDATED"                  # Lacks standardized reference measurement or unproven
    EXPERIMENTAL = "EXPERIMENTAL"                # Under research evaluation, not qualified for control
    REJECTED = "REJECTED"                        # Failed qualification criteria or unobservable


@dataclass(frozen=True)
class SohMeasurement:
    """Estimator-facing time-series measurement step."""

    time_s: float
    v: float
    i: float
    temp_c: float
    dt_s: float
    dropout: bool = False


@dataclass
class CycleRecord:
    """Complete cycle profile containing time-series and reference ground truths."""

    cycle_index: int
    time_s: np.ndarray
    voltage_v: np.ndarray
    current_a: np.ndarray
    temp_c: np.ndarray
    ah_throughput: float
    measured_capacity_ah: Optional[float] = None
    measured_resistance_ohm: Optional[float] = None
    soh_c_bol_true: Optional[float] = None
    soh_c_rated_true: Optional[float] = None
    soh_r_bol_true: Optional[float] = None
    soh_r_rated_true: Optional[float] = None
    metadata: Dict[str, float] = field(default_factory=dict)


@dataclass
class SOHState:
    """Current multi-dimensional health state of the battery."""

    soh_c_bol: float
    soh_c_rated: float
    soh_r_bol: float
    soh_r_rated: Optional[float] = None
    cycle_index: int = 0
    timestamp_s: float = 0.0
    # 2x2 covariance matrix for [soh_c_bol, soh_r_bol]
    covariance: np.ndarray = field(
        default_factory=lambda: np.diag([1e-4, 1e-4])
    )
    # Legacy fields
    is_c_qualified: bool = False
    is_r_qualified: bool = False
    qualification_status_c: QualificationStatus = QualificationStatus.UNVALIDATED
    qualification_status_r: QualificationStatus = QualificationStatus.UNVALIDATED
    # 4-state independent qualification fields
    is_c_point_qualified: bool = False
    is_c_uncertainty_qualified: bool = False
    is_r_point_qualified: bool = False
    is_r_uncertainty_qualified: bool = False
    qual_c_point: QualificationStatus = QualificationStatus.UNVALIDATED
    qual_c_uncertainty: QualificationStatus = QualificationStatus.UNVALIDATED
    qual_r_point: QualificationStatus = QualificationStatus.UNVALIDATED
    qual_r_uncertainty: QualificationStatus = QualificationStatus.UNVALIDATED

    def __post_init__(self):
        if self.is_c_qualified and not self.is_c_point_qualified:
            self.is_c_point_qualified = True
        if self.is_r_qualified and not self.is_r_point_qualified:
            self.is_r_point_qualified = True
        if self.qualification_status_c != QualificationStatus.UNVALIDATED and self.qual_c_point == QualificationStatus.UNVALIDATED:
            self.qual_c_point = self.qualification_status_c
        if self.qualification_status_r != QualificationStatus.UNVALIDATED and self.qual_r_point == QualificationStatus.UNVALIDATED:
            self.qual_r_point = self.qualification_status_r

        self.is_c_point_qualified = (self.qual_c_point == QualificationStatus.QUALIFIED)
        self.is_c_uncertainty_qualified = (self.qual_c_uncertainty == QualificationStatus.QUALIFIED)
        self.is_r_point_qualified = (self.qual_r_point == QualificationStatus.QUALIFIED)
        self.is_r_uncertainty_qualified = (self.qual_r_uncertainty == QualificationStatus.QUALIFIED)

        self.is_c_qualified = self.is_c_point_qualified
        self.is_r_qualified = self.is_r_point_qualified
        self.qualification_status_c = self.qual_c_point
        self.qualification_status_r = self.qual_r_point

    @property
    def std_c(self) -> float:
        """Standard deviation of capacity SOH estimate."""
        return float(np.sqrt(max(1e-12, self.covariance[0, 0])))

    @property
    def std_r(self) -> float:
        """Standard deviation of resistance SOH estimate."""
        return float(np.sqrt(max(1e-12, self.covariance[1, 1])))


@dataclass
class FeatureQualityRecord:
    """Diagnostic feature quality and observability record."""

    is_eligible: bool
    snr_db: Optional[float] = None
    current_stability_cv: Optional[float] = None
    temperature_drift_c_per_s: Optional[float] = None
    jacobian_condition_number: Optional[float] = None
    fit_rmse_mv: Optional[float] = None
    failure_reasons: List[str] = field(default_factory=list)


@dataclass
class SohEstimate:
    """Output emitted by an SOH estimator on a window or step."""

    soh_c: Optional[float] = None
    soh_r: Optional[float] = None
    variance_c: Optional[float] = None
    variance_r: Optional[float] = None
    status: EstimationStatus = EstimationStatus.VALID
    quality: FeatureQualityRecord = field(
        default_factory=lambda: FeatureQualityRecord(is_eligible=True)
    )
    features_used: Dict[str, float] = field(default_factory=dict)
    confidence_interval_95_c: Optional[tuple[float, float]] = None
    confidence_interval_95_r: Optional[tuple[float, float]] = None
    # Legacy fields
    qualification_status_c: QualificationStatus = QualificationStatus.UNVALIDATED
    qualification_status_r: QualificationStatus = QualificationStatus.UNVALIDATED
    # 4-state independent qualification fields
    qual_c_point: QualificationStatus = QualificationStatus.UNVALIDATED
    qual_c_uncertainty: QualificationStatus = QualificationStatus.UNVALIDATED
    qual_r_point: QualificationStatus = QualificationStatus.UNVALIDATED
    qual_r_uncertainty: QualificationStatus = QualificationStatus.UNVALIDATED

    def __post_init__(self):
        if self.qualification_status_c != QualificationStatus.UNVALIDATED and self.qual_c_point == QualificationStatus.UNVALIDATED:
            self.qual_c_point = self.qualification_status_c
        if self.qualification_status_r != QualificationStatus.UNVALIDATED and self.qual_r_point == QualificationStatus.UNVALIDATED:
            self.qual_r_point = self.qualification_status_r
        self.qualification_status_c = self.qual_c_point
        self.qualification_status_r = self.qual_r_point

    @property
    def is_c_point_qualified(self) -> bool:
        return self.qual_c_point == QualificationStatus.QUALIFIED

    @property
    def is_c_uncertainty_qualified(self) -> bool:
        return self.qual_c_uncertainty == QualificationStatus.QUALIFIED

    @property
    def is_r_point_qualified(self) -> bool:
        return self.qual_r_point == QualificationStatus.QUALIFIED

    @property
    def is_r_uncertainty_qualified(self) -> bool:
        return self.qual_r_uncertainty == QualificationStatus.QUALIFIED

    @property
    def is_c_qualified(self) -> bool:
        return self.is_c_point_qualified

    @property
    def is_r_qualified(self) -> bool:
        return self.is_r_point_qualified


@dataclass
class PartialWindow:
    """Extracted time-window from battery telemetry."""

    window_id: str
    cycle_index: int
    time_s: np.ndarray
    voltage_v: np.ndarray
    current_a: np.ndarray
    temp_c: np.ndarray
    delta_v: float
    delta_soc: float
    duration_s: float
    ah_charged: float
    is_charging: bool
    is_discharging: bool
    dropout_fraction: float
