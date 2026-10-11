"""Analytic unit tests for all evaluation metrics and model checks.

Every metric calculator is tested against closed-form mathematical solutions.
Units convention:
    - SOC and SOC errors: fractions (0 to 1)
    - Time: seconds
    - Computation speed: milliseconds per step

All parameters not in structural allowlist are passed explicitly as arguments.
"""

import math
import numpy as np
import pytest

from soc.assumptions.loader import load_assumptions, SECONDS_PER_DAY
from soc.models.plant import PlantSimulator
from soc.models.cell_2rc import Cell2RCModel
from soc.eval.metrics import (
    rmse,
    mae,
    max_abs_error,
    p95_error,
    converge_time,
    converge_time_2pct,
    converge_time_5pct,
    plateau_rmse_20_80,
    detect_reversals,
    post_reversal_error_60s,
    drift_24h,
    ms_per_step,
)
from soc.eval.model_checks import check_ocv_table_error_mv


# =====================================================================
# 1. RMSE Analytic Tests
# =====================================================================

def test_rmse_constant_error_closed_form():
    """Constant error e(t) = c yields RMSE = |c|."""
    c = 0.03
    truth = np.linspace(0.2, 0.8, 50)
    estimate = truth + c
    assert pytest.approx(rmse(truth, estimate), abs=1e-12) == c


def test_rmse_alternating_error_closed_form():
    """Alternating error [+c, -c, +c, -c] yields RMSE = c."""
    c = 0.025
    truth = np.full(100, 0.5)
    pattern = np.array([c, -c] * 50)
    estimate = truth + pattern
    assert pytest.approx(rmse(truth, estimate), abs=1e-12) == c


# =====================================================================
# 2. MAE Analytic Tests
# =====================================================================

def test_mae_constant_error_closed_form():
    """Constant error e(t) = -c yields MAE = c."""
    c = 0.04
    truth = np.linspace(0.1, 0.9, 40)
    estimate = truth - c
    assert pytest.approx(mae(truth, estimate), abs=1e-12) == c


def test_mae_varying_errors_closed_form():
    """Errors [+0.01, -0.02, +0.03, -0.04] yield MAE = (0.01+0.02+0.03+0.04)/4 = 0.025."""
    truth = np.zeros(4)
    estimate = np.array([0.01, -0.02, 0.03, -0.04])
    assert pytest.approx(mae(truth, estimate), abs=1e-12) == 0.025


# =====================================================================
# 3. max_abs_error Analytic Tests
# =====================================================================

def test_max_abs_error_closed_form():
    """Errors with peak -0.07 yield max_abs_error = 0.07."""
    truth = np.full(5, 0.5)
    estimate = np.array([0.51, 0.43, 0.52, 0.48, 0.50])
    assert pytest.approx(max_abs_error(truth, estimate), abs=1e-12) == 0.07


# =====================================================================
# 4. p95_error Analytic & Hand-Calculated Tests
# =====================================================================

def test_p95_error_hand_calculated_linear_interpolation():
    """Hand-calculated test for linear-interpolation 95th percentile:
    11 samples with errors [0.00, 0.01, 0.02, ..., 0.10].
    Index q*(N-1) = 0.95 * 10 = 9.5 (halfway between index 9 [0.09] and index 10 [0.10]).
    Linear interpolation yields: 0.09 + 0.5 * (0.10 - 0.09) = 0.095 exactly.
    """
    truth = np.zeros(11)
    # Errors strictly 0.00, 0.01, 0.02, ..., 0.10
    errs = np.array([0.00, 0.01, 0.02, 0.03, 0.04, 0.05, 0.06, 0.07, 0.08, 0.09, 0.10])
    estimate = truth + errs

    computed = p95_error(truth, estimate, percentile=95.0)
    expected_hand_calc = 0.095
    assert pytest.approx(computed, abs=1e-12) == expected_hand_calc


def test_p95_error_closed_form():
    """95 samples at 0.01 error and 5 samples at 0.10 error yields linear percentile 0.0145."""
    truth = np.zeros(100)
    errs = np.array([0.01] * 95 + [0.10] * 5)
    estimate = truth + errs
    # In numpy linear method: 0.95 * 99 = 94.05 -> index 94 (0.01) + 0.05*(0.10 - 0.01) = 0.0145
    p95 = p95_error(truth, estimate, percentile=95.0)
    expected = 0.0145
    assert pytest.approx(p95, abs=1e-12) == expected


# =====================================================================
# 5. converge_time Analytic Tests (Uniform & Uneven Timestamps)
# =====================================================================

def test_converge_time_exponential_decay_closed_form():
    """Error decaying as e(t) = 0.10 * exp(-t / tau) crosses threshold at closed-form t*.

    For threshold theta:
        0.10 * exp(-t* / tau) = theta  =>  t* = tau * ln(0.10 / theta)
    For tau = 10 s, dt = 1 s:
        theta = 0.05: t* = 10 * ln(2) ~= 6.931 s => sample at t=7 s (e(7) ~= 0.0497 <= 0.05)
        theta = 0.02: t* = 10 * ln(5) ~= 16.094 s => sample at t=17 s (e(17) ~= 0.0183 <= 0.02)
    """
    tau = 10.0
    time_s = np.arange(0, 100, dtype=float)
    error = 0.10 * np.exp(-time_s / tau)
    truth = np.full_like(time_s, 0.5)
    estimate = truth + error

    # 5% threshold: closed form crossing is t = 7.0 s
    t_conv_5 = converge_time_5pct(truth, estimate, time_s, threshold=0.05)
    assert t_conv_5 == 7.0

    # 2% threshold: closed form crossing is t = 17.0 s
    t_conv_2 = converge_time_2pct(truth, estimate, time_s, threshold=0.02)
    assert t_conv_2 == 17.0


def test_converge_time_uneven_timestamps():
    """Verify that converge_time strictly uses the time vector on unevenly spaced samples."""
    # Uneven timestamps: [0.0, 1.5, 3.2, 7.8, 15.0, 30.0]
    time_s = np.array([0.0, 1.5, 3.2, 7.8, 15.0, 30.0])
    truth = np.full_like(time_s, 0.5)
    # Errors: [0.10, 0.08, 0.06, 0.04, 0.01, 0.005]
    estimate = truth + np.array([0.10, 0.08, 0.06, 0.04, 0.01, 0.005])

    # Threshold 0.05:
    # Samples at t=0.0 (0.10), t=1.5 (0.08), t=3.2 (0.06) exceed 0.05.
    # At t=7.8, error is 0.04 <= 0.05, and all subsequent samples are <= 0.05.
    # Must return exact timestamp 7.8 (not the integer sample index 3).
    t_conv = converge_time(truth, estimate, time_s, threshold=0.05)
    assert t_conv == 7.8


def test_converge_time_late_spike_pushes_result_past_spike():
    """A late spike above threshold pushes the convergence time past the spike."""
    tau = 10.0
    time_s = np.arange(0, 100, dtype=float)
    error = 0.10 * np.exp(-time_s / tau)
    # Inject a late spike at t = 50 s exceeding threshold 0.05
    error[50] = 0.08
    truth = np.full_like(time_s, 0.5)
    estimate = truth + error

    t_conv = converge_time_5pct(truth, estimate, time_s, threshold=0.05)
    assert t_conv == 51.0


def test_converge_time_returns_inf_when_not_converged():
    """When the final sample exceeds the threshold, converge_time returns float('inf')."""
    time_s = np.arange(0, 50, dtype=float)
    truth = np.full_like(time_s, 0.5)
    estimate = truth + 0.10

    t_conv_2 = converge_time_2pct(truth, estimate, time_s, threshold=0.02)
    t_conv_5 = converge_time_5pct(truth, estimate, time_s, threshold=0.05)
    assert math.isinf(t_conv_2)
    assert math.isinf(t_conv_5)


def test_converge_time_already_converged_from_start():
    """When all samples are within threshold, converge_time returns time_s[0]."""
    time_s = np.array([10.0, 11.0, 12.0])
    truth = np.full_like(time_s, 0.5)
    estimate = truth + 0.005

    assert converge_time_2pct(truth, estimate, time_s, threshold=0.02) == 10.0
    assert converge_time_5pct(truth, estimate, time_s, threshold=0.05) == 10.0


# =====================================================================
# 6. plateau_rmse_20_80 Analytic Tests
# =====================================================================

def test_plateau_rmse_20_80_analytic_closed_form():
    """Calculates RMSE strictly for samples where truth SOC in [soc_min, soc_max]."""
    truth = np.array([0.10, 0.20, 0.50, 0.80, 0.90])
    errors = np.array([0.50, 0.02, -0.04, 0.02, 0.50])
    estimate = truth + errors

    # Samples in [0.20, 0.80] are indices 1, 2, 3: errors [0.02, -0.04, 0.02]
    # MSE = (0.0004 + 0.0016 + 0.0004) / 3 = 0.0024 / 3 = 0.0008
    expected_rmse = math.sqrt(0.0008)
    computed = plateau_rmse_20_80(truth, estimate, soc_min=0.20, soc_max=0.80)
    assert pytest.approx(computed, abs=1e-12) == expected_rmse


def test_plateau_rmse_20_80_returns_nan_when_no_samples_in_range():
    """Returns NaN when no truth samples fall within [soc_min, soc_max]."""
    truth = np.array([0.05, 0.10, 0.15, 0.85, 0.95])
    estimate = truth + 0.01
    computed = plateau_rmse_20_80(truth, estimate, soc_min=0.20, soc_max=0.80)
    assert math.isnan(computed)


# =====================================================================
# 7. Reversal Detection & post_reversal_error_60s Analytic Tests
# =====================================================================

def test_reversal_detection_noisy_rest_produces_zero_reversals():
    """Sensor noise at rest within deadband [-2.0, 2.0] A produces zero reversals."""
    deadband = 2.0
    rng = np.random.default_rng(42)
    current = np.clip(rng.normal(0, 0.5, 1000), -1.8, 1.8)

    reversals = detect_reversals(current, deadband)
    assert len(reversals) == 0

    truth = np.full(1000, 0.5)
    estimate = truth + 0.01
    time_s = np.arange(1000, dtype=float)
    err_60s = post_reversal_error_60s(truth, estimate, time_s, current, deadband=deadband)
    assert err_60s == 0.0


def test_reversal_detection_clean_square_wave_exact_count():
    """Square wave [+10, -10, +10, -10] A produces exactly 3 reversals."""
    deadband = 2.0
    seg1 = np.full(100, 10.0)
    seg2 = np.full(100, -10.0)
    seg3 = np.full(100, 10.0)
    seg4 = np.full(100, -10.0)
    current = np.concatenate([seg1, seg2, seg3, seg4])

    reversals = detect_reversals(current, deadband)
    assert len(reversals) == 3
    assert list(reversals) == [100, 200, 300]


def test_post_reversal_error_60s_analytic_window():
    """Evaluates max absolute error within the 60 s window after reversals."""
    deadband = 2.0
    time_s = np.arange(200, dtype=float)
    current = np.concatenate([np.full(100, 10.0), np.full(100, -10.0)])

    truth = np.full(200, 0.5)
    estimate = truth.copy()
    # Inject error bump of 0.035 at t = 125 s (within window)
    estimate[125] = truth[125] + 0.035
    # Inject error bump of 0.080 at t = 180 s (outside window)
    estimate[180] = truth[180] + 0.080

    computed = post_reversal_error_60s(truth, estimate, time_s, current, deadband=deadband)
    assert pytest.approx(computed, abs=1e-12) == 0.035


# =====================================================================
# 8. drift_24h Analytic Tests (Uniform & Uneven Timestamps)
# =====================================================================

def test_drift_24h_linear_ramp_analytic_closed_form():
    """Linear error ramp e(t) = a * t yields drift_24h = a * 86400."""
    time_s = np.arange(0, 3600, dtype=float)
    a = 1e-6
    truth = np.full_like(time_s, 0.5)
    estimate = truth + a * time_s

    computed_drift = drift_24h(truth, estimate, time_s, seconds_per_day=SECONDS_PER_DAY)
    expected_drift = a * 86400.0
    assert pytest.approx(computed_drift, rel=1e-9) == expected_drift


def test_drift_24h_uneven_timestamps():
    """Verify that drift_24h strictly uses the time vector on unevenly spaced samples."""
    # Uneven timestamps spanning 1000 seconds
    time_s = np.array([0.0, 10.0, 50.0, 200.0, 1000.0])
    a = 2.5e-6
    b = 0.02
    truth = np.full_like(time_s, 0.5)
    # Perfectly linear error on these uneven timestamps
    estimate = truth + (a * time_s + b)

    computed = drift_24h(truth, estimate, time_s, seconds_per_day=SECONDS_PER_DAY)
    expected = a * 86400.0
    assert pytest.approx(computed, rel=1e-9) == expected


def test_drift_24h_zero_slope_on_constant_error():
    """Constant error has zero slope, yielding drift_24h = 0.0."""
    time_s = np.arange(0, 1000, dtype=float)
    truth = np.full_like(time_s, 0.5)
    estimate = truth + 0.03

    computed = drift_24h(truth, estimate, time_s, seconds_per_day=SECONDS_PER_DAY)
    assert pytest.approx(computed, abs=1e-12) == 0.0


# =====================================================================
# 9. ms_per_step Analytic Tests
# =====================================================================

def test_ms_per_step_analytic_closed_form():
    """List of step durations [0.001, 0.002, 0.003] s yields mean = 2.0 ms."""
    durations = [0.001, 0.002, 0.003]
    assert pytest.approx(ms_per_step(durations), abs=1e-12) == 2.0


# =====================================================================
# 10. NaN Input Rejection Tests
# =====================================================================

@pytest.mark.parametrize(
    "func_name",
    [
        "rmse",
        "mae",
        "max_abs_error",
        "p95_error",
        "plateau_rmse_20_80",
    ],
)
def test_metrics_raise_value_error_on_nan(func_name):
    """All metric functions raise ValueError when input contains NaN."""
    truth = np.array([0.5, float("nan"), 0.5])
    estimate = np.array([0.5, 0.5, 0.5])

    funcs = {
        "rmse": lambda t, e: rmse(t, e),
        "mae": lambda t, e: mae(t, e),
        "max_abs_error": lambda t, e: max_abs_error(t, e),
        "p95_error": lambda t, e: p95_error(t, e, percentile=95.0),
        "plateau_rmse_20_80": lambda t, e: plateau_rmse_20_80(t, e, soc_min=0.20, soc_max=0.80),
    }
    with pytest.raises(ValueError, match="NaN"):
        funcs[func_name](truth, estimate)


def test_converge_time_raises_on_nan():
    """converge_time raises ValueError on NaN."""
    with pytest.raises(ValueError, match="NaN"):
        converge_time(np.array([float("nan")]), np.array([0.5]), np.array([0.0]), threshold=0.02)


def test_post_reversal_error_raises_on_nan():
    """post_reversal_error_60s raises ValueError on NaN."""
    with pytest.raises(ValueError, match="NaN"):
        post_reversal_error_60s(
            np.array([0.5]), np.array([0.5]), np.array([0.0]), np.array([float("nan")]), deadband=2.0
        )


def test_drift_24h_raises_on_nan():
    """drift_24h raises ValueError on NaN."""
    with pytest.raises(ValueError, match="NaN"):
        drift_24h(np.array([0.5, float("nan")]), np.array([0.5, 0.5]), np.array([0.0, 1.0]), seconds_per_day=86400.0)


def test_ms_per_step_raises_on_nan():
    """ms_per_step raises ValueError on NaN."""
    with pytest.raises(ValueError, match="NaN"):
        ms_per_step([0.001, float("nan")])


# =====================================================================
# 11. T1 Model-Check OCV Error Tests
# =====================================================================

def test_t1_model_check_ocv_error_mv_known_offset():
    """T1 OCV check computes max and RMS difference in millivolts."""
    ref_ocv = np.array([2.500, 3.200, 3.300, 3.650])
    model_ocv = ref_ocv + np.array([0.002, -0.004, 0.001, 0.0])

    max_err_mv, rms_err_mv = check_ocv_table_error_mv(model_ocv, ref_ocv)
    assert pytest.approx(max_err_mv, abs=1e-9) == 4.0
    expected_rms = math.sqrt(21.0 / 4.0)
    assert pytest.approx(rms_err_mv, abs=1e-9) == expected_rms


def test_t1_model_check_raises_on_mismatch_or_nan():
    """check_ocv_table_error_mv rejects NaN and length mismatches."""
    with pytest.raises(ValueError, match="NaN"):
        check_ocv_table_error_mv(np.array([float("nan")]), np.array([3.0]))
    with pytest.raises(ValueError, match="Length mismatch"):
        check_ocv_table_error_mv(np.array([3.0, 3.1]), np.array([3.0]))


# =====================================================================
# 12. Timing Alignment Test
# =====================================================================

def test_timing_alignment_noiseless_e0_integrator_zero_error():
    """Timing alignment test:
    A noiseless E0-style integrator started at the true SOC, fed the plant
    output at a current of 200 A, has zero error at every sample.
    Shifting the estimate by one sample makes that test fail.
    """
    assumptions, _, _ = load_assumptions(cli_overrides=[
        "sensors.current_offset_a=0.0",
        "sensors.current_gain_error=0.0",
        "sensors.current_noise_sigma_a=0.0",
        "sensors.voltage_noise_sigma_v=0.0",
        "sensors.voltage_quantisation_v=0.0",
        "sensors.dropout_rate=0.0",
        "sensors.temperature_noise_sigma_c=0.0",
    ])

    plant = PlantSimulator(assumptions)
    init_soc = float(assumptions.plant.initial_soc.value)
    cap_ah = float(assumptions.plant.nominal_capacity_Ah.value)
    coulomb_eff = float(assumptions.plant.coulombic_efficiency.value)

    e0_soc = init_soc
    steps = 100
    current_applied_a = 200.0
    dt = 1.0
    temp_c = 25.0

    estimates = []
    truths = []

    for _ in range(steps):
        meas, truth = plant.step(current_applied_a, temp_c, dt)
        e0_soc = Cell2RCModel.step_soc(
            soc=e0_soc,
            i_a=meas.i,
            dt_s=meas.dt,
            capacity_ah=cap_ah,
            coulombic_efficiency=coulomb_eff,
        )
        estimates.append(e0_soc)
        truths.append(truth.soc)

    estimates_arr = np.array(estimates)
    truths_arr = np.array(truths)

    # 1. Perfectly aligned: error must be zero at every sample
    abs_errors = np.abs(estimates_arr - truths_arr)
    max_err = float(np.max(abs_errors))
    assert max_err == pytest.approx(0.0, abs=1e-15)

    # 2. Shifted by one sample: MUST FAIL the zero-error test
    shifted_estimates = estimates_arr[:-1]
    shifted_truths = truths_arr[1:]
    shifted_max_err = float(np.max(np.abs(shifted_estimates - shifted_truths)))

    expected_step_delta = (current_applied_a * dt) / (3600.0 * cap_ah)
    assert shifted_max_err == pytest.approx(expected_step_delta, rel=1e-6)
    assert shifted_max_err > 5e-4
