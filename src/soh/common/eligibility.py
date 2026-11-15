"""Window eligibility and observability evaluation rules.

Ensures the pipeline rejects insufficient-information or low-quality windows
by emitting `EstimationStatus.INSUFFICIENT_INFORMATION` rather than corrupting
SOH estimates with spurious predictions.
"""

from dataclasses import dataclass, field
from typing import List, Optional
import numpy as np

from soh.common.contracts import (
    EstimationStatus,
    FeatureQualityRecord,
    PartialWindow,
)
from soh.common.units import is_charging


@dataclass
class WindowEligibilityConfig:
    """Configurable observability thresholds for partial-charge window evaluation."""

    min_duration_s: float = 20.0
    min_delta_v: float = 0.03
    min_delta_soc: float = 0.03
    max_temperature_drift_c: float = 5.0
    max_current_cv: float = 0.15
    max_dropout_fraction: float = 0.02
    min_mean_charging_current_a: float = 0.05


@dataclass
class PulseEligibilityConfig:
    """Configurable observability thresholds for transient pulse response."""

    min_pulse_duration_s: float = 3.0
    min_pulse_current_a: float = 0.2
    max_current_ripple_cv: float = 0.05
    min_relaxation_duration_s: float = 10.0
    max_fit_rmse_mv: float = 5.0
    max_jacobian_cond: float = 1e4


class WindowEvaluator:
    """Evaluates telemetry windows against physical information requirements."""

    @staticmethod
    def evaluate_partial_charge_window(
        window: PartialWindow,
        config: Optional[WindowEligibilityConfig] = None,
    ) -> FeatureQualityRecord:
        """Evaluate whether a partial-charge window carries sufficient information."""
        if config is None:
            config = WindowEligibilityConfig()

        reasons: List[str] = []

        # 1. Duration check
        if window.duration_s < config.min_duration_s:
            reasons.append(
                f"Window duration {window.duration_s:.1f}s < minimum {config.min_duration_s:.1f}s"
            )

        # 2. Voltage span check
        if abs(window.delta_v) < config.min_delta_v:
            reasons.append(
                f"Voltage span {abs(window.delta_v):.3f}V < minimum {config.min_delta_v:.3f}V"
            )

        # 3. SOC span check
        if abs(window.delta_soc) < config.min_delta_soc:
            reasons.append(
                f"SOC span {abs(window.delta_soc):.3f} < minimum {config.min_delta_soc:.3f}"
            )

        # 4. Temperature drift check
        if len(window.temp_c) > 1:
            t_drift = float(np.max(window.temp_c) - np.min(window.temp_c))
            if t_drift > config.max_temperature_drift_c:
                reasons.append(
                    f"Thermal drift {t_drift:.2f}°C > maximum {config.max_temperature_drift_c:.2f}°C"
                )
        else:
            t_drift = 0.0

        # 5. Charging current polarity & stability check
        if len(window.current_a) > 0:
            mean_curr = float(np.mean(window.current_a))
            std_curr = float(np.std(window.current_a))
            # Remember: charge current is negative (< 0)
            if mean_curr >= -config.min_mean_charging_current_a:
                reasons.append(
                    f"Mean current {mean_curr:.3f}A is not active charging (< -{config.min_mean_charging_current_a:.3f}A)"
                )
            
            curr_cv = std_curr / max(1e-6, abs(mean_curr))
            if curr_cv > config.max_current_cv:
                reasons.append(
                    f"Current coefficient of variation {curr_cv:.3f} > maximum {config.max_current_cv:.3f}"
                )
        else:
            curr_cv = 0.0
            reasons.append("Empty current array in window")

        # 6. Dropout fraction check
        if window.dropout_fraction > config.max_dropout_fraction:
            reasons.append(
                f"Dropout fraction {window.dropout_fraction:.3f} > maximum {config.max_dropout_fraction:.3f}"
            )

        is_eligible = len(reasons) == 0
        return FeatureQualityRecord(
            is_eligible=is_eligible,
            current_stability_cv=curr_cv,
            temperature_drift_c_per_s=t_drift / max(1.0, window.duration_s),
            failure_reasons=reasons,
        )
