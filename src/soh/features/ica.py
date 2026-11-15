"""Incremental Capacity Analysis (ICA) feature extraction.

Implements:
1. Charge throughput integration Q(t) = int |I| dt / 3600.
2. Uniform voltage-grid resampling.
3. Regularized filtering (Savitzky-Golay and Gaussian smoothing).
4. Numerical dQ/dV derivative extraction.
5. Peak detection, tracking, area integration, and peak shift calculation.
6. Temperature drift and current stability quality scoring.
7. Explicit failure handling for unobservable or insufficient curves.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Tuple
import numpy as np
from scipy.ndimage import gaussian_filter1d
from scipy.signal import find_peaks, savgol_filter

from soh.common.contracts import FeatureQualityRecord


@dataclass
class IcaConfig:
    """Configuration parameters for ICA derivative extraction and peak tracking."""

    voltage_grid_step_v: float = 0.005  # 5 mV uniform grid
    savgol_window_len: int = 15         # Must be odd
    savgol_polyorder: int = 2
    gaussian_sigma: float = 2.0
    min_peak_prominence: float = 0.2    # Minimum peak prominence [Ah/V]
    min_peak_height: float = 0.3        # Minimum peak height [Ah/V]
    peak_integration_halfwidth_v: float = 0.05  # +/- 50 mV around peak for area
    max_current_cv: float = 0.12        # Current stability threshold
    max_temp_drift_c: float = 4.0       # Maximum allowable temperature drift during charging
    min_voltage_span_v: float = 0.15    # Minimum charging voltage range


@dataclass
class IcaFeatures:
    """Extracted Incremental Capacity Analysis features."""

    peak_voltage_v: float
    peak_height_ah_per_v: float
    peak_area_ah: float
    peak_voltage_shift_v: float
    v_grid: np.ndarray
    dq_dv: np.ndarray
    all_peak_voltages: List[float] = field(default_factory=list)
    all_peak_heights: List[float] = field(default_factory=list)

    def to_feature_dict(self) -> dict:
        return {
            "ica_peak_voltage_v": self.peak_voltage_v,
            "ica_peak_height": self.peak_height_ah_per_v,
            "ica_peak_area": self.peak_area_ah,
            "ica_peak_shift_v": self.peak_voltage_shift_v,
        }


class IcaFeatureExtractor:
    """Modular ICA feature extractor with quality evaluation."""

    def __init__(self, config: Optional[IcaConfig] = None):
        self.config = config or IcaConfig()

    def extract_from_charge_segment(
        self,
        time_s: np.ndarray,
        voltage_v: np.ndarray,
        current_a: np.ndarray,
        temp_c: np.ndarray,
        v_min_override: Optional[float] = None,
        v_max_override: Optional[float] = None,
        bol_peak_voltage_v: Optional[float] = None,
    ) -> Tuple[Optional[IcaFeatures], FeatureQualityRecord]:
        """Extract ICA curve and peaks from a constant-current charging segment."""
        reasons: List[str] = []

        if len(voltage_v) < 20:
            reasons.append("Charge segment contains fewer than 20 points.")
            return None, FeatureQualityRecord(is_eligible=False, failure_reasons=reasons)

        # 1. Temperature drift check
        temp_drift = float(np.max(temp_c) - np.min(temp_c)) if len(temp_c) > 0 else 0.0
        if temp_drift > self.config.max_temp_drift_c:
            reasons.append(
                f"Temperature drift {temp_drift:.2f}°C > maximum {self.config.max_temp_drift_c:.2f}°C."
            )

        # 2. Current stability check (charging current is negative: I < 0)
        mean_curr = float(np.mean(current_a))
        std_curr = float(np.std(current_a))
        if mean_curr >= -0.05:
            reasons.append(f"Mean current {mean_curr:.3f}A is not charging (< -0.05A).")

        curr_cv = std_curr / max(1e-6, abs(mean_curr))
        if curr_cv > self.config.max_current_cv:
            reasons.append(
                f"Current CV {curr_cv:.3f} > maximum {self.config.max_current_cv:.3f}."
            )

        # 3. Voltage span check
        v_span = float(np.max(voltage_v) - np.min(voltage_v))
        if v_span < self.config.min_voltage_span_v:
            reasons.append(
                f"Voltage span {v_span:.3f}V < minimum {self.config.min_voltage_span_v:.3f}V."
            )

        if len(reasons) > 0:
            return None, FeatureQualityRecord(
                is_eligible=False,
                current_stability_cv=curr_cv,
                temperature_drift_c_per_s=temp_drift / max(1.0, float(time_s[-1] - time_s[0])),
                failure_reasons=reasons,
            )

        # 4. Integrate charge Q(t) in Ah: Q = int |I| dt / 3600
        dt = np.diff(time_s, prepend=time_s[0])
        q_cum_ah = np.cumsum(np.abs(current_a) * dt) / 3600.0

        # Sort strictly by voltage to eliminate local non-monotonic noise
        sort_idx = np.argsort(voltage_v)
        v_sorted = voltage_v[sort_idx]
        q_sorted = q_cum_ah[sort_idx]

        # Deduplicate identical voltage values
        _, unique_idx = np.unique(v_sorted, return_index=True)
        v_clean = v_sorted[unique_idx]
        q_clean = q_sorted[unique_idx]

        # Determine voltage grid boundaries
        v_start = max(float(v_clean[0]), v_min_override if v_min_override else float(v_clean[0]))
        v_end = min(float(v_clean[-1]), v_max_override if v_max_override else float(v_clean[-1]))

        if (v_end - v_start) < self.config.min_voltage_span_v:
            reasons.append(f"Resampling grid span {v_end - v_start:.3f}V is too small.")
            return None, FeatureQualityRecord(is_eligible=False, failure_reasons=reasons)

        v_grid = np.arange(v_start, v_end, self.config.voltage_grid_step_v)
        if len(v_grid) < 15:
            reasons.append(f"Resampled grid points ({len(v_grid)}) too few for derivative filter.")
            return None, FeatureQualityRecord(is_eligible=False, failure_reasons=reasons)

        # Resample Q onto uniform voltage grid
        q_grid = np.interp(v_grid, v_clean, q_clean)

        # 5. Dual-stage smoothing: Savitzky-Golay followed by gentle Gaussian filter
        window_len = self.config.savgol_window_len
        if window_len >= len(q_grid):
            window_len = len(q_grid) - 1 if (len(q_grid) - 1) % 2 != 0 else len(q_grid) - 2
        window_len = max(5, window_len)

        try:
            q_savgol = savgol_filter(q_grid, window_length=window_len, polyorder=self.config.savgol_polyorder)
            q_smooth = gaussian_filter1d(q_savgol, sigma=self.config.gaussian_sigma)
        except Exception as e:
            reasons.append(f"Smoothing filter failed: {str(e)}")
            return None, FeatureQualityRecord(is_eligible=False, failure_reasons=reasons)

        # 6. Numerical dQ/dV derivative
        dq_dv = np.gradient(q_smooth, self.config.voltage_grid_step_v)

        # Estimate derivative SNR (ratio of smoothed signal power to high-frequency residual power)
        raw_dq_dv = np.gradient(q_grid, self.config.voltage_grid_step_v)
        residual = raw_dq_dv - dq_dv
        signal_var = float(np.var(dq_dv))
        noise_var = float(np.var(residual))
        snr_db = float(10.0 * np.log10(max(1e-9, signal_var / max(1e-12, noise_var))))

        # 7. Peak detection
        raw_peak_indices, properties = find_peaks(
            dq_dv,
            prominence=self.config.min_peak_prominence,
            height=self.config.min_peak_height,
        )

        # Exclude filter boundary artifacts within 4 samples of grid edges
        edge_margin = 4
        peak_indices = [
            idx for idx in raw_peak_indices if edge_margin <= idx < (len(v_grid) - edge_margin)
        ]

        if len(peak_indices) == 0:
            reasons.append("No prominent incremental capacity peak detected in charging window.")
            return None, FeatureQualityRecord(
                is_eligible=False,
                snr_db=snr_db,
                current_stability_cv=curr_cv,
                failure_reasons=reasons,
            )

        # Identify dominant peak (largest height / area)
        dominant_idx = peak_indices[np.argmax(dq_dv[peak_indices])]
        peak_v = float(v_grid[dominant_idx])
        peak_h = float(dq_dv[dominant_idx])

        # Integrate peak area within halfwidth
        area_mask = (v_grid >= (peak_v - self.config.peak_integration_halfwidth_v)) & (
            v_grid <= (peak_v + self.config.peak_integration_halfwidth_v)
        )
        peak_area = float(np.trapezoid(dq_dv[area_mask], v_grid[area_mask])) if np.any(area_mask) else 0.0

        # Peak voltage shift relative to BOL or nominal
        ref_peak_v = bol_peak_voltage_v if bol_peak_voltage_v is not None else peak_v
        peak_shift = peak_v - ref_peak_v

        all_p_v = [float(v_grid[idx]) for idx in peak_indices]
        all_p_h = [float(dq_dv[idx]) for idx in peak_indices]

        ica_feats = IcaFeatures(
            peak_voltage_v=peak_v,
            peak_height_ah_per_v=peak_h,
            peak_area_ah=peak_area,
            peak_voltage_shift_v=peak_shift,
            v_grid=v_grid,
            dq_dv=dq_dv,
            all_peak_voltages=all_p_v,
            all_peak_heights=all_p_h,
        )

        quality = FeatureQualityRecord(
            is_eligible=True,
            snr_db=snr_db,
            current_stability_cv=curr_cv,
            temperature_drift_c_per_s=temp_drift / max(1.0, float(time_s[-1] - time_s[0])),
        )

        return ica_feats, quality
