"""Unit tests for SOH common units, contracts, protocols, and eligibility."""

import numpy as np
import pytest

from soh.common import (
    CURRENT_POLARITY_CHARGE,
    CURRENT_POLARITY_DISCHARGE,
    CellReferenceSpec,
    EstimationStatus,
    FeatureQualityRecord,
    PartialWindow,
    ReferenceMeasurementProtocol,
    SOHState,
    WindowEligibilityConfig,
    WindowEvaluator,
    celsius_to_kelvin,
    is_charging,
    is_discharging,
    is_resting,
)


def test_units_and_polarity():
    """Verify polarity conventions and temperature conversions."""
    assert is_discharging(2.5)
    assert not is_discharging(-2.5)
    assert is_charging(-2.5)
    assert not is_charging(2.5)
    assert is_resting(0.0)
    assert is_resting(5e-5)

    assert celsius_to_kelvin(25.0) == pytest.approx(298.15)


def test_cell_reference_spec_and_protocols():
    """Verify reference protocol SOH calculations."""
    spec = CellReferenceSpec(
        cell_id="A123_26650",
        chemistry="LFP",
        nominal_capacity_ah=2.3,
        v_max=3.65,
        v_min=2.0,
        t_ref_c=25.0,
        nominal_resistance_ohm=0.010,
    )
    protocol = ReferenceMeasurementProtocol(spec)

    # BOL capacity = 2.25 Ah, Actual = 2.025 Ah (90% BOL retention)
    soh_c_bol = protocol.compute_soh_c_bol(measured_capacity_ah=2.025, bol_capacity_ah=2.25)
    assert soh_c_bol == pytest.approx(0.90)

    # Rated relative capacity
    soh_c_rated = protocol.compute_soh_c_rated(measured_capacity_ah=2.07)
    assert soh_c_rated == pytest.approx(2.07 / 2.3)

    # Resistance: BOL = 0.010 Ohm, degraded = 0.020 Ohm (doubled -> SOH_R = 0.5)
    soh_r_bol = protocol.compute_soh_r_bol(measured_resistance_ohm=0.020, bol_resistance_ohm=0.010)
    assert soh_r_bol == pytest.approx(0.50)

    # Reference provenance defaults
    assert spec.provenance.provenance_type.value == "FACTORY_ACCEPTANCE_TEST"
    assert spec.provenance.confidence_score == 1.0

    # Invalid values raise ValueError
    with pytest.raises(ValueError):
        protocol.compute_soh_c_bol(measured_capacity_ah=-1.0, bol_capacity_ah=2.3)
    with pytest.raises(ValueError):
        protocol.compute_soh_r_bol(measured_resistance_ohm=0.0, bol_resistance_ohm=0.01)


def test_soh_state_std():
    """Verify SOHState covariance and standard deviations."""
    cov = np.diag([0.0004, 0.0009])  # std = 0.02 and 0.03
    state = SOHState(
        soh_c_bol=0.95,
        soh_c_rated=0.93,
        soh_r_bol=0.90,
        covariance=cov,
    )
    assert state.std_c == pytest.approx(0.02)
    assert state.std_r == pytest.approx(0.03)


def test_window_evaluator_eligibility():
    """Verify partial window eligibility gating."""
    evaluator = WindowEvaluator()
    config = WindowEligibilityConfig(
        min_duration_s=20.0,
        min_delta_v=0.05,
        min_delta_soc=0.05,
        max_temperature_drift_c=3.0,
        max_current_cv=0.10,
        max_dropout_fraction=0.02,
        min_mean_charging_current_a=0.5,
    )

    # 1. Valid charging window
    valid_window = PartialWindow(
        window_id="w_valid",
        cycle_index=10,
        time_s=np.linspace(0, 100, 100),
        voltage_v=np.linspace(3.1, 3.4, 100),
        current_a=np.full(100, -1.0),  # -1.0A charge
        temp_c=np.full(100, 25.0),
        delta_v=0.30,
        delta_soc=0.20,
        duration_s=100.0,
        ah_charged=0.20,
        is_charging=True,
        is_discharging=False,
        dropout_fraction=0.0,
    )
    res_valid = evaluator.evaluate_partial_charge_window(valid_window, config)
    assert res_valid.is_eligible
    assert len(res_valid.failure_reasons) == 0

    # 2. Window with too short duration and low voltage delta
    short_window = PartialWindow(
        window_id="w_short",
        cycle_index=10,
        time_s=np.linspace(0, 10, 10),
        voltage_v=np.linspace(3.20, 3.21, 10),
        current_a=np.full(10, -1.0),
        temp_c=np.full(10, 25.0),
        delta_v=0.01,
        delta_soc=0.01,
        duration_s=10.0,
        ah_charged=0.01,
        is_charging=True,
        is_discharging=False,
        dropout_fraction=0.0,
    )
    res_short = evaluator.evaluate_partial_charge_window(short_window, config)
    assert not res_short.is_eligible
    assert any("duration" in r.lower() for r in res_short.failure_reasons)
    assert any("voltage span" in r.lower() for r in res_short.failure_reasons)

    # 3. Window with non-charging current (discharging or near zero)
    discharge_window = PartialWindow(
        window_id="w_dischg",
        cycle_index=10,
        time_s=np.linspace(0, 100, 100),
        voltage_v=np.linspace(3.4, 3.2, 100),
        current_a=np.full(100, 1.0),  # positive = discharge
        temp_c=np.full(100, 25.0),
        delta_v=-0.2,
        delta_soc=-0.2,
        duration_s=100.0,
        ah_charged=0.0,
        is_charging=False,
        is_discharging=True,
        dropout_fraction=0.0,
    )
    res_dischg = evaluator.evaluate_partial_charge_window(discharge_window, config)
    assert not res_dischg.is_eligible
    assert any("active charging" in r.lower() for r in res_dischg.failure_reasons)
