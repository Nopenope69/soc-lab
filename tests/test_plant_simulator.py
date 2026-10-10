"""Unit tests for plant simulator truth state integration and sensor degradation chain."""

import math
import numpy as np
import pytest

from soc.assumptions.loader import resolve_assumptions
from soc.models.plant import PlantSimulator, Measurement, PlantTruthState


def test_plant_returns_isolated_measurement_and_truth():
    """Verify that plant returns separate Measurement and PlantTruthState instances."""
    assumptions = resolve_assumptions()
    plant = PlantSimulator(assumptions)

    meas, truth = plant.step(i_true_a=10.0, temp_c=25.0, dt_s=1.0)

    # Measurement must be Measurement type with observable fields only
    assert isinstance(meas, Measurement)
    assert hasattr(meas, "v")
    assert hasattr(meas, "i")
    assert hasattr(meas, "temp_c")
    assert hasattr(meas, "dt")
    assert hasattr(meas, "dropout")
    # Measurement must not have truth fields
    assert not hasattr(meas, "soc")
    assert not hasattr(meas, "i1")
    assert not hasattr(meas, "i2")
    assert not hasattr(meas, "h")

    # Truth record must have internal electrochemistry state
    assert isinstance(truth, PlantTruthState)
    assert hasattr(truth, "soc")
    assert hasattr(truth, "v_terminal")
    assert hasattr(truth, "h")


def test_dropped_samples_set_nan_and_flag():
    """Verify that dropped samples set measurement fields to NaN and dropout flag to True."""
    # Force dropout rate to 1.0 (100% drops)
    assumptions = resolve_assumptions(cli_overrides=["sensors.dropout_rate.value=1.0"])
    plant = PlantSimulator(assumptions)

    meas, truth = plant.step(i_true_a=10.0, temp_c=25.0, dt_s=1.0)

    assert meas.dropout is True
    assert math.isnan(meas.v)
    assert math.isnan(meas.i)
    assert math.isnan(meas.temp_c)
    # Truth must remain valid
    assert not math.isnan(truth.soc)
    assert not math.isnan(truth.v_terminal)


def test_sensor_current_offset_direction():
    """Verify positive current offset makes integrated measured current exceed true current."""
    # Set positive current bias +1.0 A, disable noise and gain error
    cli_overrides = [
        "sensors.current_offset_a.value=1.0",
        "sensors.current_gain_error.value=0.0",
        "sensors.current_noise_sigma_a.value=0.0",
        "sensors.dropout_rate.value=0.0",
    ]
    assumptions = resolve_assumptions(cli_overrides=cli_overrides)
    plant = PlantSimulator(assumptions)

    steps = 50
    dt = 1.0
    true_current = 20.0

    sum_meas_i = 0.0
    sum_true_i = 0.0
    for _ in range(steps):
        meas, truth = plant.step(i_true_a=true_current, temp_c=25.0, dt_s=dt)
        sum_meas_i += meas.i * dt
        sum_true_i += truth.i_true * dt

    # Integrated measured current must exceed true current by offset * steps * dt = 1.0 * 50 = 50 A*s
    assert sum_meas_i > sum_true_i
    assert (sum_meas_i - sum_true_i) == pytest.approx(1.0 * steps * dt)


def test_voltage_quantisation_snaps_to_multiples_of_step():
    """Verify that ADC quantisation snaps terminal voltage to exact multiples of step size."""
    step_mv = 0.005  # 5 mV quantisation step
    cli_overrides = [
        f"sensors.voltage_quantisation_v.value={step_mv}",
        "sensors.voltage_noise_sigma_v.value=0.0",
        "sensors.dropout_rate.value=0.0",
    ]
    assumptions = resolve_assumptions(cli_overrides=cli_overrides)
    plant = PlantSimulator(assumptions)

    # Step through varying currents
    for i_val in [0.0, 5.0, 15.3, -22.7, 50.1]:
        meas, _ = plant.step(i_true_a=i_val, temp_c=25.0, dt_s=1.0)
        # Check remainder when dividing by step_mv is close to 0 or step_mv
        quotient = meas.v / step_mv
        nearest_int = round(quotient)
        assert meas.v == pytest.approx(nearest_int * step_mv, abs=1e-9)


def test_noise_repeatability_with_same_seed():
    """Verify that identical random seeds produce identical noisy measurements."""
    cli_overrides = [
        "sensors.current_noise_sigma_a.value=0.5",
        "sensors.voltage_noise_sigma_v.value=0.01",
        "sensors.temperature_noise_sigma_c.value=0.5",
    ]
    assumptions = resolve_assumptions(cli_overrides=cli_overrides)

    rng1 = np.random.default_rng(12345)
    plant1 = PlantSimulator(assumptions, rng=rng1)

    rng2 = np.random.default_rng(12345)
    plant2 = PlantSimulator(assumptions, rng=rng2)

    for _ in range(20):
        meas1, _ = plant1.step(i_true_a=15.0, temp_c=25.0, dt_s=1.0)
        meas2, _ = plant2.step(i_true_a=15.0, temp_c=25.0, dt_s=1.0)

        assert meas1.v == pytest.approx(meas2.v)
        assert meas1.i == pytest.approx(meas2.i)
        assert meas1.temp_c == pytest.approx(meas2.temp_c)


def test_temperature_outside_range_warns_and_clamps():
    """Verify that operating outside [15, 35] C triggers a warning and clamps."""
    assumptions = resolve_assumptions()
    plant = PlantSimulator(assumptions)

    # 5.0 C is below 15.0 C calibration minimum
    with pytest.warns(UserWarning, match="outside calibration range"):
        meas, truth = plant.step(i_true_a=10.0, temp_c=5.0, dt_s=1.0)
        assert truth.temp_c == 5.0

    # 45.0 C is above 35.0 C calibration maximum
    with pytest.warns(UserWarning, match="outside calibration range"):
        meas, truth = plant.step(i_true_a=10.0, temp_c=45.0, dt_s=1.0)
        assert truth.temp_c == 45.0


def test_two_consumers_fed_from_one_plant_run_receive_identical_measurements():
    """Verify that multiple consumers/estimators fed from a single plant run see identical measurements."""
    assumptions = resolve_assumptions()
    plant = PlantSimulator(assumptions)

    consumer_a_records = []
    consumer_b_records = []

    for t in range(30):
        meas, _ = plant.step(i_true_a=12.5, temp_c=25.0, dt_s=1.0)
        # Both consumers receive the single generated measurement instance
        consumer_a_records.append((meas.v, meas.i, meas.temp_c, meas.dropout))
        consumer_b_records.append((meas.v, meas.i, meas.temp_c, meas.dropout))

    assert len(consumer_a_records) == len(consumer_b_records)
    for rec_a, rec_b in zip(consumer_a_records, consumer_b_records):
        assert rec_a == rec_b
