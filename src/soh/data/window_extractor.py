"""Partial-charge window segmentation and extraction.

Extracts contiguous charging segments from cycle telemetry, computes segment
metadata (delta_v, delta_soc, duration, Ah throughput, dropout fraction), and
evaluates eligibility using the feature quality & observability layer.
"""

from typing import List, Optional, Tuple
import numpy as np

from soh.common.contracts import CycleRecord, PartialWindow
from soh.common.eligibility import WindowEligibilityConfig, WindowEvaluator
from soh.common.units import is_charging


class PartialChargeWindowExtractor:
    """Segments charging intervals from telemetry and evaluates observability."""

    def __init__(
        self,
        min_charging_current_a: float = 0.05,
        min_duration_s: float = 15.0,
        eval_config: Optional[WindowEligibilityConfig] = None,
    ):
        self.min_charging_current_a = min_charging_current_a
        self.min_duration_s = min_duration_s
        self.eval_config = eval_config or WindowEligibilityConfig()
        self.evaluator = WindowEvaluator()

    def extract_windows_from_cycle(
        self,
        cycle: CycleRecord,
        nominal_capacity_ah: float = 2.3,
    ) -> List[Tuple[PartialWindow, bool]]:
        """Extract all continuous charging windows from a cycle record.
        
        Returns a list of (PartialWindow, is_eligible) tuples.
        """
        curr = cycle.current_a
        time_s = cycle.time_s
        volt = cycle.voltage_v
        temp = cycle.temp_c

        n = len(curr)
        if n < 5:
            return []

        # Mask of charging samples: remember charging current is negative (< -threshold)
        chg_mask = curr < -abs(self.min_charging_current_a)

        windows: List[Tuple[PartialWindow, bool]] = []
        in_segment = False
        start_idx = 0

        for i in range(n):
            if chg_mask[i] and not in_segment:
                in_segment = True
                start_idx = i
            elif not chg_mask[i] and in_segment:
                in_segment = False
                end_idx = i
                seg_duration = time_s[end_idx - 1] - time_s[start_idx]
                if seg_duration >= self.min_duration_s:
                    win = self._build_window(
                        cycle.cycle_index,
                        len(windows),
                        time_s[start_idx:end_idx],
                        volt[start_idx:end_idx],
                        curr[start_idx:end_idx],
                        temp[start_idx:end_idx],
                        nominal_capacity_ah,
                    )
                    quality = self.evaluator.evaluate_partial_charge_window(win, self.eval_config)
                    windows.append((win, quality.is_eligible))

        # Check trailing window
        if in_segment:
            end_idx = n
            seg_duration = time_s[end_idx - 1] - time_s[start_idx]
            if seg_duration >= self.min_duration_s:
                win = self._build_window(
                    cycle.cycle_index,
                    len(windows),
                    time_s[start_idx:end_idx],
                    volt[start_idx:end_idx],
                    curr[start_idx:end_idx],
                    temp[start_idx:end_idx],
                    nominal_capacity_ah,
                )
                quality = self.evaluator.evaluate_partial_charge_window(win, self.eval_config)
                windows.append((win, quality.is_eligible))

        return windows

    def _build_window(
        self,
        cycle_index: int,
        win_idx: int,
        t_seg: np.ndarray,
        v_seg: np.ndarray,
        i_seg: np.ndarray,
        temp_seg: np.ndarray,
        nominal_capacity_ah: float,
    ) -> PartialWindow:
        dt = np.diff(t_seg, prepend=t_seg[0])
        # Charged Ah: integration of |i| * dt / 3600
        ah_charged = float(np.sum(np.abs(i_seg) * dt) / 3600.0)
        delta_v = float(v_seg[-1] - v_seg[0])
        delta_soc = ah_charged / max(0.1, nominal_capacity_ah)
        duration = float(t_seg[-1] - t_seg[0])

        # Check for NaN / dropout
        nan_count = int(np.sum(np.isnan(v_seg) | np.isnan(i_seg)))
        dropout_frac = nan_count / max(1, len(v_seg))

        return PartialWindow(
            window_id=f"c{cycle_index}_w{win_idx}",
            cycle_index=cycle_index,
            time_s=t_seg,
            voltage_v=v_seg,
            current_a=i_seg,
            temp_c=temp_seg,
            delta_v=delta_v,
            delta_soc=delta_soc,
            duration_s=duration,
            ah_charged=ah_charged,
            is_charging=True,
            is_discharging=False,
            dropout_fraction=dropout_frac,
        )
