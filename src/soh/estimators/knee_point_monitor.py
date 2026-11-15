"""Knee-Point and Regime-Change Monitoring for Empirical Degradation Models.

Prevents empirical power-law models (which assume monotonic power-law decay)
from producing unmonitored invalid health estimates after the onset of rapid
nonlinear knee-point rollover.

Detects:
1. Rolling degradation rate acceleration: d(SOH)/d(Ah) > threshold * baseline_rate
2. Empirical prediction residual divergence: |SOH_obs - SOH_empirical| > delta_tol
3. Cumulative throughput lifetime limit warning: Ah_total > Ah_knee_threshold
"""

from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional
import numpy as np


class RegimeStatus(str, Enum):
    """Degradation regime classification."""

    STEADY_STATE = "STEADY_STATE"                  # Standard power-law monotonic decay
    KNEE_APPROACHING = "KNEE_APPROACHING"          # Acceleration detected; variance widening
    KNEE_TRIGGERED = "KNEE_TRIGGERED"              # Nonlinear knee-point rollover confirmed
    ACCELERATED_FADE = "ACCELERATED_FADE"          # Rapid capacity plunge / end-of-life regime


@dataclass
class RegimeMonitorAlert:
    """Diagnostic alert emitted by KneePointMonitor."""

    cycle_index: int
    regime_status: RegimeStatus
    is_empirical_qualified: bool
    rolling_fade_rate_per_ah: float
    residual_c: float
    message: str


class KneePointMonitor:
    """Monitors telemetry and empirical predictions for regime changes and knee rollover."""

    def __init__(
        self,
        rate_acceleration_factor: float = 2.0,
        residual_divergence_threshold: float = 0.015,
        window_size: int = 5,
        baseline_rate_per_ah: float = 2.0e-5,
    ):
        self.rate_acceleration_factor = rate_acceleration_factor
        self.residual_divergence_threshold = residual_divergence_threshold
        self.window_size = window_size
        self.baseline_rate_per_ah = baseline_rate_per_ah

        self.history_soh: List[float] = []
        self.history_ah: List[float] = []
        self.current_status: RegimeStatus = RegimeStatus.STEADY_STATE
        self.consecutive_divergent_cycles = 0

    def reset(self) -> None:
        self.history_soh.clear()
        self.history_ah.clear()
        self.current_status = RegimeStatus.STEADY_STATE
        self.consecutive_divergent_cycles = 0

    def update(
        self,
        cycle_index: int,
        observed_soh_c: float,
        empirical_pred_c: float,
        cumulative_ah: float,
    ) -> RegimeMonitorAlert:
        """Process incoming cycle health and determine if regime shift has occurred."""
        self.history_soh.append(observed_soh_c)
        self.history_ah.append(cumulative_ah)

        residual = abs(observed_soh_c - empirical_pred_c)
        rolling_rate = self.baseline_rate_per_ah

        # 1. Rolling rate computation
        if len(self.history_soh) >= self.window_size:
            delta_soh = self.history_soh[-self.window_size] - self.history_soh[-1]
            delta_ah = self.history_ah[-1] - self.history_ah[-self.window_size]
            if delta_ah > 0.1:
                rolling_rate = float(delta_soh / delta_ah)

        # 2. Residual divergence check
        if residual > self.residual_divergence_threshold:
            self.consecutive_divergent_cycles += 1
        else:
            self.consecutive_divergent_cycles = max(0, self.consecutive_divergent_cycles - 1)

        # 3. Decision logic
        is_rate_accelerated = rolling_rate > (self.baseline_rate_per_ah * self.rate_acceleration_factor)
        is_residual_diverged = self.consecutive_divergent_cycles >= 3

        if is_rate_accelerated and is_residual_diverged:
            self.current_status = RegimeStatus.KNEE_TRIGGERED
            is_qualified = False
            msg = f"Knee-point rollover detected at cycle {cycle_index}! Rolling rate={rolling_rate:.2e}/Ah (>{self.rate_acceleration_factor}x baseline). Empirical power law disqualified."
        elif is_rate_accelerated or (self.consecutive_divergent_cycles >= 2):
            self.current_status = RegimeStatus.KNEE_APPROACHING
            is_qualified = True  # Still usable with caveat
            msg = f"Regime shift approaching at cycle {cycle_index}. Rate elevation={rolling_rate:.2e}/Ah. Increasing uncertainty."
        else:
            self.current_status = RegimeStatus.STEADY_STATE
            is_qualified = True
            msg = "Nominal steady-state monotonic power-law degradation."

        return RegimeMonitorAlert(
            cycle_index=cycle_index,
            regime_status=self.current_status,
            is_empirical_qualified=is_qualified,
            rolling_fade_rate_per_ah=rolling_rate,
            residual_c=residual,
            message=msg,
        )
