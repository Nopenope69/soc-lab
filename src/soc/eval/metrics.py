"""Metric calculation engine for SOC estimation evaluation.

All SOC-related metrics operate on fractional SOC values (0 to 1).
Reports convert to percentage points for display.

Units convention:
    - SOC and SOC errors: fractions (0 to 1)
    - Time: seconds
    - Computation speed: milliseconds per step

NaN handling:
    All metric functions raise ValueError on NaN input. Dropped samples
    are handled upstream by the runner, which holds the last estimate and
    excludes dropped steps from the error series before calling metrics.
    This module never receives NaN in its inputs.

Timing convention:
    At sample k the plant applies current i_k to state x_k. The measurement
    carries v_k = terminal voltage at x_k under i_k, and i_k. Truth recorded
    at sample k is the state after the step, x_(k+1). Estimator.step(v_k,
    i_k, T_k, dt) returns the estimate of x_(k+1). Metrics compare
    estimate[k] with truth[k], both referring to the same instant.

Configuration parameters:
    Every number not in the structural allowlist {0, 1, 2, -1, 3600, 1000, 60}
    arrives as an explicit argument from config, with no default baked into src/:
    - percentile for p95_error
    - convergence threshold for converge_time_2pct / converge_time_5pct
    - soc_min and soc_max plateau bounds for plateau_rmse_20_80
    - reversal deadband for detect_reversals and post_reversal_error_60s
    - seconds_per_day horizon for drift_24h
"""

from typing import List
import numpy as np


def _validate_no_nan(arr: np.ndarray, name: str) -> None:
    """Raise ValueError if any element is NaN."""
    if np.any(np.isnan(arr)):
        raise ValueError(f"{name} contains NaN values; dropped samples must be filtered upstream")


def _validate_inputs(
    truth: np.ndarray, estimate: np.ndarray, time_s: np.ndarray
) -> None:
    """Validate metric inputs: no NaN, matching lengths."""
    _validate_no_nan(truth, "truth")
    _validate_no_nan(estimate, "estimate")
    _validate_no_nan(time_s, "time_s")
    if len(truth) != len(estimate) or len(truth) != len(time_s):
        raise ValueError(
            f"Length mismatch: truth={len(truth)}, estimate={len(estimate)}, time_s={len(time_s)}"
        )
    if len(truth) == 0:
        raise ValueError("Input arrays must not be empty")


def rmse(truth: np.ndarray, estimate: np.ndarray) -> float:
    """Root mean squared error of SOC estimates.

    Units: SOC fraction (0 to 1).
    Formula: sqrt(mean((estimate - truth)^2))

    Raises ValueError on NaN input or empty arrays.
    """
    _validate_no_nan(truth, "truth")
    _validate_no_nan(estimate, "estimate")
    if len(truth) != len(estimate):
        raise ValueError("truth and estimate must have the same length")
    if len(truth) == 0:
        raise ValueError("Input arrays must not be empty")
    error = estimate - truth
    return float(np.sqrt(np.mean(error ** 2)))


def mae(truth: np.ndarray, estimate: np.ndarray) -> float:
    """Mean absolute error of SOC estimates.

    Units: SOC fraction (0 to 1).
    Formula: mean(|estimate - truth|)

    Raises ValueError on NaN input or empty arrays.
    """
    _validate_no_nan(truth, "truth")
    _validate_no_nan(estimate, "estimate")
    if len(truth) != len(estimate):
        raise ValueError("truth and estimate must have the same length")
    if len(truth) == 0:
        raise ValueError("Input arrays must not be empty")
    return float(np.mean(np.abs(estimate - truth)))


def max_abs_error(truth: np.ndarray, estimate: np.ndarray) -> float:
    """Maximum absolute error of SOC estimates.

    Units: SOC fraction (0 to 1).
    Formula: max(|estimate - truth|)

    Raises ValueError on NaN input or empty arrays.
    """
    _validate_no_nan(truth, "truth")
    _validate_no_nan(estimate, "estimate")
    if len(truth) != len(estimate):
        raise ValueError("truth and estimate must have the same length")
    if len(truth) == 0:
        raise ValueError("Input arrays must not be empty")
    return float(np.max(np.abs(estimate - truth)))


def p95_error(truth: np.ndarray, estimate: np.ndarray, percentile: float) -> float:
    """Percentile of absolute error distribution (nominally 95th percentile).

    Uses linear interpolation method (np.percentile method='linear').

    Units: SOC fraction (0 to 1).
    Args:
        truth: Ground-truth SOC array (fractions).
        estimate: Estimated SOC array (fractions).
        percentile: Percentile rank, e.g. from config (e.g. 95.0).
                    No default is baked into src/; passed by caller.

    Raises:
        ValueError on NaN input or empty arrays.
    """
    _validate_no_nan(truth, "truth")
    _validate_no_nan(estimate, "estimate")
    if len(truth) != len(estimate):
        raise ValueError("truth and estimate must have the same length")
    if len(truth) == 0:
        raise ValueError("Input arrays must not be empty")
    abs_err = np.abs(estimate - truth)
    return float(np.percentile(abs_err, percentile, method="linear"))


def converge_time(
    truth: np.ndarray,
    estimate: np.ndarray,
    time_s: np.ndarray,
    threshold: float,
) -> float:
    """Smallest time t_c such that |error| <= threshold for all samples from t_c to end.

    Units: time in seconds. Returns float('inf') if the final sample exceeds
    the threshold (i.e., never converged).

    The convergence time is measured from the time vector time_s, supporting
    unevenly spaced timestamps. It is the earliest time after which the error
    never exceeds the threshold again.

    Raises:
        ValueError on NaN input or empty arrays.
    """
    _validate_inputs(truth, estimate, time_s)
    abs_err = np.abs(estimate - truth)

    # If the final sample exceeds threshold, convergence never happened
    if abs_err[-1] > threshold:
        return float("inf")

    # Search backwards: find the last sample that exceeds threshold
    exceeds = np.where(abs_err > threshold)[0]
    if len(exceeds) == 0:
        # Error is always within threshold from the start
        return float(time_s[0])

    last_exceed_idx = int(exceeds[-1])
    # Convergence starts at the sample after the last exceedance
    converge_idx = last_exceed_idx + 1
    if converge_idx >= len(time_s):
        return float("inf")
    return float(time_s[converge_idx])


def converge_time_2pct(
    truth: np.ndarray,
    estimate: np.ndarray,
    time_s: np.ndarray,
    threshold: float,
) -> float:
    """Convergence time to within threshold (nominally 0.02).

    Units: time in seconds. Returns float('inf') if never converged.
    Threshold must be supplied by caller from filter.convergence_threshold_2pct.

    Raises ValueError on NaN input.
    """
    return converge_time(truth, estimate, time_s, threshold)


def converge_time_5pct(
    truth: np.ndarray,
    estimate: np.ndarray,
    time_s: np.ndarray,
    threshold: float,
) -> float:
    """Convergence time to within threshold (nominally 0.05).

    Units: time in seconds. Returns float('inf') if never converged.
    Threshold must be supplied by caller from filter.convergence_threshold_5pct.

    Raises ValueError on NaN input.
    """
    return converge_time(truth, estimate, time_s, threshold)


def plateau_rmse_20_80(
    truth: np.ndarray,
    estimate: np.ndarray,
    soc_min: float,
    soc_max: float,
) -> float:
    """RMSE evaluated strictly over samples where truth SOC is in [soc_min, soc_max].

    Nominally [0.20, 0.80] passed from duty/bars assumptions.
    Units: SOC fraction (0 to 1).
    Returns float('nan') when no samples fall in the SOC range, and the
    report shows 'n/a'.

    Raises ValueError on NaN input.
    """
    _validate_no_nan(truth, "truth")
    _validate_no_nan(estimate, "estimate")
    if len(truth) != len(estimate):
        raise ValueError("truth and estimate must have the same length")
    if len(truth) == 0:
        raise ValueError("Input arrays must not be empty")

    mask = (truth >= soc_min) & (truth <= soc_max)
    if not np.any(mask):
        return float("nan")

    error = estimate[mask] - truth[mask]
    return float(np.sqrt(np.mean(error ** 2)))


def detect_reversals(
    current: np.ndarray, deadband: float
) -> np.ndarray:
    """Detect charge/discharge reversals using deadband-filtered current.

    A reversal is registered only when current crosses from > +deadband to
    < -deadband or vice versa. Transitions into or out of the deadband
    [-deadband, +deadband] do not trigger reversals.

    Units: current in Amps, deadband in Amps.

    Returns array of integer indices where reversals occurred.

    Raises ValueError on NaN input.
    """
    _validate_no_nan(current, "current")

    if len(current) == 0:
        return np.array([], dtype=int)

    reversals = []
    last_direction = 0  # 0 = undecided

    for k in range(len(current)):
        i_val = current[k]
        if i_val > deadband:
            if last_direction == -1:
                reversals.append(k)
            last_direction = 1
        elif i_val < -deadband:
            if last_direction == 1:
                reversals.append(k)
            last_direction = -1
        # Within deadband: no direction change

    return np.array(reversals, dtype=int)


def post_reversal_error_60s(
    truth: np.ndarray,
    estimate: np.ndarray,
    time_s: np.ndarray,
    current: np.ndarray,
    deadband: float,
    window_duration_s: float = 60,
) -> float:
    """Maximum absolute error in the window following each deadband-filtered reversal.

    Units: SOC fraction (0 to 1).
    Returns 0.0 if no reversals are detected.

    Args:
        truth: Ground-truth SOC array.
        estimate: Estimated SOC array.
        time_s: Time vector in seconds (supports uneven timestamps).
        current: Applied/measured current array in Amperes.
        deadband: Current reversal deadband threshold in Amperes.
        window_duration_s: Evaluation window length in seconds (default 60).

    Raises ValueError on NaN input.
    """
    _validate_inputs(truth, estimate, time_s)
    _validate_no_nan(current, "current")

    reversal_indices = detect_reversals(current, deadband)
    if len(reversal_indices) == 0:
        return float(0)

    abs_err = np.abs(estimate - truth)
    max_err = float(0)

    for rev_idx in reversal_indices:
        t_rev = time_s[rev_idx]
        window_mask = (time_s >= t_rev) & (time_s <= t_rev + window_duration_s)
        if np.any(window_mask):
            window_max = float(np.max(abs_err[window_mask]))
            if window_max > max_err:
                max_err = window_max

    return max_err


def drift_24h(
    truth: np.ndarray,
    estimate: np.ndarray,
    time_s: np.ndarray,
    seconds_per_day: float,
) -> float:
    """Least-squares slope of signed error, scaled to 24 hours.

    Units: SOC fraction (0 to 1) per 24 hours.
    Formula: drift_24h = beta * seconds_per_day
    where beta is the slope from least-squares linear fit of
    e_k = estimate_k - truth_k vs time_s.

    Args:
        truth: Ground-truth SOC array.
        estimate: Estimated SOC array.
        time_s: Time vector in seconds (supports uneven timestamps).
        seconds_per_day: Scaling horizon in seconds (nominally 86400.0 from config).

    Raises ValueError on NaN input.
    """
    _validate_inputs(truth, estimate, time_s)

    signed_error = estimate - truth

    n = len(time_s)
    if n < 2:
        raise ValueError("Need at least 2 samples for drift computation")

    t_mean = np.mean(time_s)
    e_mean = np.mean(signed_error)
    t_centered = time_s - t_mean
    e_centered = signed_error - e_mean

    var_t = np.sum(t_centered ** 2)
    if var_t == 0:
        return float(0)

    cov_te = np.sum(t_centered * e_centered)
    beta = cov_te / var_t

    return float(beta * seconds_per_day)


def ms_per_step(step_durations_s: List[float]) -> float:
    """Average CPU execution time per step in milliseconds.

    Takes a list of per-step durations measured by the runner with
    time.perf_counter. This function never times anything itself.

    Units: milliseconds.

    Raises ValueError on NaN input.
    """
    arr = np.asarray(step_durations_s, dtype=float)
    _validate_no_nan(arr, "step_durations_s")
    if len(arr) == 0:
        raise ValueError("step_durations_s must not be empty")
    return float(np.mean(arr) * 1000)
