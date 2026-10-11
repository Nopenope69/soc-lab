"""Software correctness verification tests (Cases a, b, c) and informational runs.

Label: "software correctness, not accuracy evidence"
Tolerance across all tests: 0.05 percentage points of SOC (5e-4 absolute).
"""

import math
import numpy as np
import pytest

from soc.assumptions.loader import load_assumptions
from soc.estimators.base import ParamSet
from soc.estimators.e0_coulomb import E0CoulombCounting
from soc.estimators.e1_ekf import E1ExtendedKalmanFilter
from soc.estimators.e2_ekf_hysteresis import E2EKFHysteresis
from soc.eval.metrics import converge_time_2pct, converge_time_5pct, plateau_rmse_20_80
from soc.models.plant import PlantSimulator


LABEL = "software correctness, not accuracy evidence"
TOLERANCE = 5e-4  # 0.05 percentage points


# =====================================================================
# Case (a): Zero Initial Offset Stability on Matched Noiseless Data
# =====================================================================

def test_case_a_e0_zero_offset_exact():
    """Case (a) E0: software correctness, not accuracy evidence.

    E0 started at the true SOC on noiseless data from its own model (hysteresis M=0).
    Max absolute error over the run must remain <= 1e-12 (exact Coulomb integration).
    """
    assumptions, _, _ = load_assumptions(cli_overrides=[
        "plant.initial_soc=0.80",
        "plant.hysteresis_amplitude_v=0.0",
        "sensors.current_offset_a=0.0",
        "sensors.current_gain_error=0.0",
        "sensors.current_noise_sigma_a=0.0",
        "sensors.voltage_noise_sigma_v=0.0",
        "sensors.voltage_quantisation_v=0.0",
        "sensors.dropout_rate=0.0",
        "sensors.temperature_noise_sigma_c=0.0",
    ])
    params = ParamSet.from_assumptions(assumptions)
    plant = PlantSimulator(assumptions)
    est = E0CoulombCounting(params)
    est.reset(0.80)

    # 300 steps of dynamic pulse duty: 50A discharge, 0A rest, -30A charge
    max_err = 0.0
    for k in range(300):
        if k < 100:
            i_val = 50.0
        elif k < 180:
            i_val = 0.0
        else:
            i_val = -30.0

        meas, truth = plant.step(i_val, 25.0, 1.0)
        out = est.step(meas)
        err = abs(out.soc - truth.soc)
        if err > max_err:
            max_err = err

    assert max_err <= 1e-12, (
        f"[{LABEL}] Case (a) E0 max error was {max_err:.2e}, expected <= 1e-12"
    )


def test_case_a_e1_zero_offset_under_tolerance():
    """Case (a) E1: software correctness, not accuracy evidence.

    E1 started at the true SOC on noiseless data from its own model (hysteresis M=0).
    Max absolute error over the run must remain under 5e-4 tolerance.
    """
    assumptions, _, _ = load_assumptions(cli_overrides=[
        "plant.initial_soc=0.80",
        "plant.hysteresis_amplitude_v=0.0",
        "sensors.current_offset_a=0.0",
        "sensors.current_gain_error=0.0",
        "sensors.current_noise_sigma_a=0.0",
        "sensors.voltage_noise_sigma_v=0.0",
        "sensors.voltage_quantisation_v=0.0",
        "sensors.dropout_rate=0.0",
        "sensors.temperature_noise_sigma_c=0.0",
    ])
    params = ParamSet.from_assumptions(assumptions)
    plant = PlantSimulator(assumptions)
    est = E1ExtendedKalmanFilter(params)
    est.reset(0.80)

    max_err = 0.0
    for k in range(300):
        if k < 100:
            i_val = 50.0
        elif k < 180:
            i_val = 0.0
        else:
            i_val = -30.0

        meas, truth = plant.step(i_val, 25.0, 1.0)
        out = est.step(meas)
        err = abs(out.soc - truth.soc)
        if err > max_err:
            max_err = err

    assert max_err <= TOLERANCE, (
        f"[{LABEL}] Case (a) E1 max error was {max_err:.2e}, expected <= {TOLERANCE}"
    )


def test_case_a_e2_zero_offset_under_tolerance():
    """Case (a) E2: software correctness, not accuracy evidence.

    E2 started at the true SOC on noiseless data from its own model (nominal hysteresis).
    Max absolute error over the run must remain under 5e-4 tolerance.
    """
    assumptions, _, _ = load_assumptions(cli_overrides=[
        "plant.initial_soc=0.80",
        "sensors.current_offset_a=0.0",
        "sensors.current_gain_error=0.0",
        "sensors.current_noise_sigma_a=0.0",
        "sensors.voltage_noise_sigma_v=0.0",
        "sensors.voltage_quantisation_v=0.0",
        "sensors.dropout_rate=0.0",
        "sensors.temperature_noise_sigma_c=0.0",
    ])
    params = ParamSet.from_assumptions(assumptions)
    plant = PlantSimulator(assumptions)
    est = E2EKFHysteresis(params)
    est.reset(0.80)

    max_err = 0.0
    for k in range(300):
        if k < 100:
            i_val = 50.0
        elif k < 180:
            i_val = 0.0
        else:
            i_val = -30.0

        meas, truth = plant.step(i_val, 25.0, 1.0)
        out = est.step(meas)
        err = abs(out.soc - truth.soc)
        if err > max_err:
            max_err = err

    assert max_err <= TOLERANCE, (
        f"[{LABEL}] Case (a) E2 max error was {max_err:.2e}, expected <= {TOLERANCE}"
    )


# =====================================================================
# Case (b): 10-Point Initial Offset Knee-Crossing Convergence
# =====================================================================

def test_case_b_e1_knee_crossing_convergence():
    """Case (b) E1: software correctness, not accuracy evidence.

    E1 started 10 percentage points off (+0.10: true 0.25, est 0.35).
    Duty used: continuous 70 A discharge for 900 s from SOC 0.25 crossing the
    lower knee (< 0.15 SOC) down to ~0.075 SOC.
    Final error must converge to <= 5e-4.
    """
    assumptions, _, _ = load_assumptions(cli_overrides=[
        "plant.initial_soc=0.25",
        "plant.hysteresis_amplitude_v=0.0",
        "sensors.current_offset_a=0.0",
        "sensors.current_gain_error=0.0",
        "sensors.current_noise_sigma_a=0.0",
        "sensors.voltage_noise_sigma_v=0.0",
        "sensors.voltage_quantisation_v=0.0",
        "sensors.dropout_rate=0.0",
        "sensors.temperature_noise_sigma_c=0.0",
    ])
    params = ParamSet.from_assumptions(assumptions)
    plant = PlantSimulator(assumptions)
    est = E1ExtendedKalmanFilter(params)
    est.reset(0.35)  # +0.10 initial offset

    final_err = 0.0
    for k in range(900):
        meas, truth = plant.step(70.0, 25.0, 1.0)
        out = est.step(meas)
        final_err = abs(out.soc - truth.soc)

    assert final_err <= TOLERANCE, (
        f"[{LABEL}] Case (b) E1 final error was {final_err:.2e}, expected <= {TOLERANCE}"
    )


def test_case_b_e2_knee_crossing_convergence():
    """Case (b) E2: software correctness, not accuracy evidence.

    E2 started 10 percentage points off (+0.10: true 0.25, est 0.35).
    Duty used: continuous 70 A discharge for 900 s from SOC 0.25 crossing the
    lower knee (< 0.15 SOC) down to ~0.075 SOC with nominal hysteresis.
    Final error must converge to <= 5e-4.
    """
    assumptions, _, _ = load_assumptions(cli_overrides=[
        "plant.initial_soc=0.25",
        "sensors.current_offset_a=0.0",
        "sensors.current_gain_error=0.0",
        "sensors.current_noise_sigma_a=0.0",
        "sensors.voltage_noise_sigma_v=0.0",
        "sensors.voltage_quantisation_v=0.0",
        "sensors.dropout_rate=0.0",
        "sensors.temperature_noise_sigma_c=0.0",
    ])
    params = ParamSet.from_assumptions(assumptions)
    plant = PlantSimulator(assumptions)
    est = E2EKFHysteresis(params)
    est.reset(0.35)  # +0.10 initial offset

    final_err = 0.0
    for k in range(900):
        meas, truth = plant.step(70.0, 25.0, 1.0)
        out = est.step(meas)
        final_err = abs(out.soc - truth.soc)

    assert final_err <= TOLERANCE, (
        f"[{LABEL}] Case (b) E2 final error was {final_err:.2e}, expected <= {TOLERANCE}"
    )


# =====================================================================
# Case (c): Initial Offset & Full-Charge Anchor Handling
# =====================================================================

def test_case_c_e0_anchor_disabled_preserves_offset():
    """Case (c) E0: software correctness, not accuracy evidence.

    E0 started 10 percentage points off with anchors disabled.
    Error must remain within 0.1 percentage points (1e-3) of initial offset throughout.
    """
    assumptions, _, _ = load_assumptions(cli_overrides=[
        "plant.initial_soc=0.80",
        "soc_definition.anchor_enabled=false",
        "plant.hysteresis_amplitude_v=0.0",
        "sensors.current_offset_a=0.0",
        "sensors.current_gain_error=0.0",
        "sensors.current_noise_sigma_a=0.0",
        "sensors.voltage_noise_sigma_v=0.0",
        "sensors.voltage_quantisation_v=0.0",
        "sensors.dropout_rate=0.0",
        "sensors.temperature_noise_sigma_c=0.0",
    ])
    params = ParamSet.from_assumptions(assumptions)
    plant = PlantSimulator(assumptions)
    est = E0CoulombCounting(params)
    est.reset(0.90)  # +0.10 offset

    initial_offset = 0.10
    max_deviation = 0.0
    for _ in range(200):
        meas, truth = plant.step(50.0, 25.0, 1.0)
        out = est.step(meas)
        err = out.soc - truth.soc
        deviation = abs(err - initial_offset)
        if deviation > max_deviation:
            max_deviation = deviation

    assert max_deviation <= 1e-3, (
        f"[{LABEL}] Case (c) E0 offset deviation was {max_deviation:.2e}, expected <= 1e-3"
    )


def test_case_c_e0_full_charge_anchor_corrects_offset():
    """Case (c) E0: software correctness, not accuracy evidence.

    E0 started 10 percentage points off with scripted full-charge anchor event.
    After the anchor event, error must correct to under 5e-4 tolerance.
    """
    assumptions, _, _ = load_assumptions(cli_overrides=[
        "plant.initial_soc=0.999",
        "soc_definition.anchor_enabled=true",
        "soc_definition.full_charge_anchor_soc=1.0",
        "plant.hysteresis_amplitude_v=0.0",
        "sensors.current_offset_a=0.0",
        "sensors.current_gain_error=0.0",
        "sensors.current_noise_sigma_a=0.0",
        "sensors.voltage_noise_sigma_v=0.0",
        "sensors.voltage_quantisation_v=0.0",
        "sensors.dropout_rate=0.0",
        "sensors.temperature_noise_sigma_c=0.0",
    ])
    params = ParamSet.from_assumptions(assumptions)
    plant = PlantSimulator(assumptions)
    est = E0CoulombCounting(params)
    est.reset(0.899)  # 10 points off

    anchor_fired = False
    final_post_anchor_err = None
    for k in range(100):
        # Charge at -10 A for 36 s (adds 0.001 SOC to reach 1.0), then taper at -0.2 A for 64 s
        i_val = -10.0 if k < 36 else -0.2
        meas, truth = plant.step(i_val, 25.0, 1.0)
        out = est.step(meas)
        if out.anchor_used:
            anchor_fired = True
        if anchor_fired:
            final_post_anchor_err = abs(out.soc - truth.soc)

    assert anchor_fired is True, f"[{LABEL}] Full-charge anchor failed to trigger"
    assert final_post_anchor_err is not None
    assert final_post_anchor_err <= TOLERANCE, (
        f"[{LABEL}] Case (c) E0 post-anchor error was {final_post_anchor_err:.2e}, expected <= {TOLERANCE}"
    )


# =====================================================================
# Informational Tests (Not Pass/Fail for Accuracy Evidence)
# =====================================================================

def test_informational_rest_anchor_error_on_plateau_with_hysteresis():
    """Informational test: Rest anchor on plateau with plant hysteresis ON.

    Measures and logs the significant SOC error introduced by inverting OCV
    when terminal voltage carries unmodeled hysteresis voltage.
    """
    assumptions, _, _ = load_assumptions(cli_overrides=[
        "plant.initial_soc=0.55",
        "soc_definition.rest_anchor_enabled=true",
        "soc_definition.rest_duration_threshold_s=100.0",
        "sensors.current_offset_a=0.0",
        "sensors.current_gain_error=0.0",
        "sensors.current_noise_sigma_a=0.0",
        "sensors.voltage_noise_sigma_v=0.0",
        "sensors.voltage_quantisation_v=0.0",
        "sensors.dropout_rate=0.0",
        "sensors.temperature_noise_sigma_c=0.0",
    ])
    params = ParamSet.from_assumptions(assumptions)
    plant = PlantSimulator(assumptions)
    est = E0CoulombCounting(params)
    est.reset(0.55)

    # Discharge 50 A for 360 s to reach ~0.50 SOC with h saturated at ~ -1.0
    for _ in range(360):
        meas, truth = plant.step(50.0, 25.0, 1.0)
        est.step(meas)

    # Rest at 0 A for 150 s -> rest anchor triggers at 100 s
    anchor_error = None
    for _ in range(150):
        meas, truth = plant.step(0.0, 25.0, 1.0)
        out = est.step(meas)
        if out.anchor_used:
            anchor_error = out.soc - truth.soc

    assert anchor_error is not None
    print(f"\n[Informational] Rest anchor on plateau with hysteresis ON introduced error: {anchor_error:+.4f} ({anchor_error*100:+.2f} pp)")


def test_informational_a_e1_and_e2_plateau_rmse():
    """Informational run (a): E1 and E2 on same plateau run with plant hysteresis ON.

    Report plateau_rmse_20_80 for E1 and E2 side by side (report only, no pass/fail).
    """
    assumptions, _, _ = load_assumptions(cli_overrides=[
        "plant.initial_soc=0.50",
        "sensors.current_offset_a=0.0",
        "sensors.current_gain_error=0.0",
        "sensors.current_noise_sigma_a=0.0",
        "sensors.voltage_noise_sigma_v=0.0",
        "sensors.voltage_quantisation_v=0.0",
        "sensors.dropout_rate=0.0",
        "sensors.temperature_noise_sigma_c=0.0",
    ])
    params = ParamSet.from_assumptions(assumptions)
    plant = PlantSimulator(assumptions)
    e1 = E1ExtendedKalmanFilter(params)
    e2 = E2EKFHysteresis(params)
    e1.reset(0.50)
    e2.reset(0.50)

    truths = []
    e1_ests = []
    e2_ests = []
    for k in range(500):
        i_val = 30.0 if (k // 50) % 2 == 0 else -30.0
        meas, truth = plant.step(i_val, 25.0, 1.0)
        out1 = e1.step(meas)
        out2 = e2.step(meas)
        truths.append(truth.soc)
        e1_ests.append(out1.soc)
        e2_ests.append(out2.soc)

    truths_arr = np.array(truths)
    rmse_e1 = plateau_rmse_20_80(truths_arr, np.array(e1_ests), 0.20, 0.80)
    rmse_e2 = plateau_rmse_20_80(truths_arr, np.array(e2_ests), 0.20, 0.80)

    print(f"\n[Informational (a)] Plateau RMSE (20-80%):")
    print(f"  E1 = {rmse_e1*100:.4f} pp")
    print(f"  E2 = {rmse_e2*100:.4f} pp")


def test_informational_b_wrong_start_on_plateau():
    """Informational run (b): Wrong start on plateau.

    True SOC 0.60, estimate 0.70, noiseless and matched, 30 A discharge and charge
    pulses that stay inside 30 to 80% SOC, 3600 s.
    Report E1 and E2 error at 900 s and 3600 s and converge_time_5pct (report only).
    """
    assumptions, _, _ = load_assumptions(cli_overrides=[
        "plant.initial_soc=0.60",
        "sensors.current_offset_a=0.0",
        "sensors.current_gain_error=0.0",
        "sensors.current_noise_sigma_a=0.0",
        "sensors.voltage_noise_sigma_v=0.0",
        "sensors.voltage_quantisation_v=0.0",
        "sensors.dropout_rate=0.0",
        "sensors.temperature_noise_sigma_c=0.0",
    ])
    params = ParamSet.from_assumptions(assumptions)
    plant = PlantSimulator(assumptions)
    e1 = E1ExtendedKalmanFilter(params)
    e2 = E2EKFHysteresis(params)
    e1.reset(0.70)  # +0.10 offset
    e2.reset(0.70)  # +0.10 offset

    times = []
    truths = []
    e1_ests = []
    e2_ests = []

    e1_err_900 = None
    e2_err_900 = None

    for k in range(3600):
        # 30 A pulses alternating every 180 s (stays within [0.585, 0.600])
        i_val = 30.0 if (k // 180) % 2 == 0 else -30.0
        meas, truth = plant.step(i_val, 25.0, 1.0)
        out1 = e1.step(meas)
        out2 = e2.step(meas)

        t_now = float(k + 1)
        times.append(t_now)
        truths.append(truth.soc)
        e1_ests.append(out1.soc)
        e2_ests.append(out2.soc)

        if k + 1 == 900:
            e1_err_900 = abs(out1.soc - truth.soc)
            e2_err_900 = abs(out2.soc - truth.soc)

    truths_arr = np.array(truths)
    times_arr = np.array(times)
    e1_arr = np.array(e1_ests)
    e2_arr = np.array(e2_ests)

    e1_err_3600 = abs(e1_arr[-1] - truths_arr[-1])
    e2_err_3600 = abs(e2_arr[-1] - truths_arr[-1])

    ct_e1 = converge_time_5pct(truths_arr, e1_arr, times_arr, threshold=0.05)
    ct_e2 = converge_time_5pct(truths_arr, e2_arr, times_arr, threshold=0.05)

    ct_e1_str = "inf" if math.isinf(ct_e1) else f"{ct_e1:.1f} s"
    ct_e2_str = "inf" if math.isinf(ct_e2) else f"{ct_e2:.1f} s"

    print(f"\n[Informational (b)] Wrong start on plateau (true=0.60, est=0.70, 3600s inside plateau):")
    print(f"  E1: error@900s = {e1_err_900*100:.4f} pp, error@3600s = {e1_err_3600*100:.4f} pp, converge_time_5pct = {ct_e1_str}")
    print(f"  E2: error@900s = {e2_err_900*100:.4f} pp, error@3600s = {e2_err_3600*100:.4f} pp, converge_time_5pct = {ct_e2_str}")


def test_informational_c_wrong_start_plateau_then_lower_knee():
    """Informational run (c): Same as (b), but duty then discharges across lower knee.

    Report error before and after the crossing (report only, no pass/fail).
    """
    assumptions, _, _ = load_assumptions(cli_overrides=[
        "plant.initial_soc=0.60",
        "sensors.current_offset_a=0.0",
        "sensors.current_gain_error=0.0",
        "sensors.current_noise_sigma_a=0.0",
        "sensors.voltage_noise_sigma_v=0.0",
        "sensors.voltage_quantisation_v=0.0",
        "sensors.dropout_rate=0.0",
        "sensors.temperature_noise_sigma_c=0.0",
    ])
    params = ParamSet.from_assumptions(assumptions)
    plant = PlantSimulator(assumptions)
    e1 = E1ExtendedKalmanFilter(params)
    e2 = E2EKFHysteresis(params)
    e1.reset(0.70)
    e2.reset(0.70)

    # 1. Plateau phase for 3600 s
    for k in range(3600):
        i_val = 30.0 if (k // 180) % 2 == 0 else -30.0
        meas, truth = plant.step(i_val, 25.0, 1.0)
        out1 = e1.step(meas)
        out2 = e2.step(meas)

    e1_err_before = abs(out1.soc - truth.soc)
    e2_err_before = abs(out2.soc - truth.soc)

    # 2. Discharge across lower knee (< 0.15 SOC): 70 A discharge for 2400 s
    # 70 A * 2400 s / (3600 * 100) = 0.4667 delta SOC; 0.60 - 0.4667 = 0.1333 (< 0.15)
    for _ in range(2400):
        meas, truth = plant.step(70.0, 25.0, 1.0)
        out1 = e1.step(meas)
        out2 = e2.step(meas)

    e1_err_after = abs(out1.soc - truth.soc)
    e2_err_after = abs(out2.soc - truth.soc)

    print(f"\n[Informational (c)] Wrong start on plateau then crossing lower knee:")
    print(f"  Final plant SOC reached: {truth.soc:.4f}")
    print(f"  E1: error before knee = {e1_err_before*100:.4f} pp, error after knee = {e1_err_after*100:.4f} pp")
    print(f"  E2: error before knee = {e2_err_before*100:.4f} pp, error after knee = {e2_err_after*100:.4f} pp")

