"""Model-level validation checks (e.g. T1 static OCV check).

T1 compares a model OCV table against a reference OCV table on a shared
SOC grid, returning maximum absolute error and RMS error in millivolts.
"""

from typing import Dict, List, Tuple
import numpy as np


def check_ocv_table_error_mv(
    model_ocv_v: np.ndarray,
    reference_ocv_v: np.ndarray,
) -> Tuple[float, float]:
    """Compute OCV error in mV between a model OCV curve and a reference curve.

    Both arrays must be evaluated on the same shared SOC grid.

    Returns:
        (max_error_mv, rms_error_mv):
            - max_error_mv: Maximum absolute difference in millivolts.
            - rms_error_mv: Root mean square difference in millivolts.

    Raises:
        ValueError: If inputs have different lengths, are empty, or contain NaN.
    """
    model_arr = np.asarray(model_ocv_v, dtype=float)
    ref_arr = np.asarray(reference_ocv_v, dtype=float)

    if np.any(np.isnan(model_arr)) or np.any(np.isnan(ref_arr)):
        raise ValueError("Inputs must not contain NaN values")
    if len(model_arr) != len(ref_arr):
        raise ValueError(
            f"Length mismatch: model has {len(model_arr)}, reference has {len(ref_arr)}"
        )
    if len(model_arr) == 0:
        raise ValueError("Input arrays must not be empty")

    diff_v = model_arr - ref_arr
    diff_mv = diff_v * 1000

    max_err_mv = float(np.max(np.abs(diff_mv)))
    rms_err_mv = float(np.sqrt(np.mean(diff_mv ** 2)))

    return max_err_mv, rms_err_mv
