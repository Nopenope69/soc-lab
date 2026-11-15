"""Abstract base classes and protocols for SOH estimators.

Defines the core estimation contract:
- fit(): Offline batch calibration on cohort datasets.
- predict_window(): Online inference on extracted partial/full telemetry windows.
- update_state(): Discrete state-tracking update step.
- SupportsEmbeddedExport: Optional capability mixin for microcontrollers.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, Optional, Protocol, runtime_checkable

from soh.common.contracts import PartialWindow, SOHState, SohEstimate
from soh.data.base_loader import SohDataset


class SohEstimator(ABC):
    """Abstract base class for all SOH estimation algorithms."""

    @abstractmethod
    def fit(self, dataset: SohDataset) -> "SohEstimator":
        """Calibrate or train model on multi-battery cohort dataset."""
        ...

    @abstractmethod
    def predict_window(
        self,
        window: PartialWindow,
        features: Optional[Dict[str, float]] = None,
    ) -> SohEstimate:
        """Estimate SOH from a partial or complete telemetry window."""
        ...

    @abstractmethod
    def update_state(
        self,
        current_state: SOHState,
        estimate: SohEstimate,
        dt_s: float = 0.0,
    ) -> SOHState:
        """Update battery health state with a new estimate."""
        ...


@runtime_checkable
class SupportsEmbeddedExport(Protocol):
    """Optional protocol for estimators deployable to C embedded microcontrollers."""

    def export_c_header(self, destination: Path) -> None:
        """Export model parameters, coefficients, or lookup tables to a C header."""
        ...
