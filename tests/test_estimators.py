"""Unit tests for E0, E1, E2 estimators and registry."""

import math
import pytest

from soc.assumptions.loader import load_assumptions
from soc.estimators.base import Estimator, ParamSet, SocEstimate
from soc.estimators.e0_coulomb import E0CoulombCounting
from soc.estimators.e1_ekf import E1ExtendedKalmanFilter
from soc.estimators.e2_ekf_hysteresis import E2EKFHysteresis
from soc.estimators.e5_observability_ekf import E5ObservabilityEKF
from soc.estimators.e6_rbc_dekf import E6RBCDEKF
from soc.estimators.registry import (
    get_estimator,
    list_registered_estimators,
    ESTIMATOR_REGISTRY,
)
from soc.models.plant import Measurement


@pytest.fixture
def params() -> ParamSet:
    assumptions, _, _ = load_assumptions()
    return ParamSet.from_assumptions(assumptions)


def test_estimators_conform_to_protocol(params):
    """Verify that E0, E1, E2, E5, and E6 satisfy the runtime Estimator Protocol."""
    for cls in [E0CoulombCounting, E1ExtendedKalmanFilter, E2EKFHysteresis, E5ObservabilityEKF, E6RBCDEKF]:
        est = cls(params)
        assert isinstance(est, Estimator)


def test_registry_instantiates_implemented_estimators(params):
    """Verify that get_estimator instantiates E0, E1, E2, E5, and E6 cleanly."""
    for name in ["E0", "E1", "E2", "E5", "E6"]:
        est = get_estimator(name, params)
        assert isinstance(est, Estimator)


def test_registry_stubs_raise_not_implemented_error(params):
    """Verify that E3, E4, and E7 raise NotImplementedError at construction."""
    for name in ["E3", "E4", "E7"]:
        with pytest.raises(NotImplementedError, match="scheduled for Phase 4"):
            get_estimator(name, params)


def test_registry_rejects_unknown_estimator_name(params):
    """Verify that an unrecognized estimator name raises KeyError."""
    with pytest.raises(KeyError, match="Unknown estimator 'E99'"):
        get_estimator("E99", params)


def test_registry_lists_all_e0_to_e7():
    """Verify that registry contains exactly E0 through E7."""
    registered = list_registered_estimators()
    expected = ["E0", "E1", "E2", "E3", "E4", "E5", "E6", "E7"]
    assert sorted(registered) == sorted(expected)


def test_dropout_handling_skips_update_and_holds_last_current(params):
    """Verify that on dropped samples (NaN measurements), estimators skip update

    and propagate using the last valid current and temperature.
    """
    for cls in [E0CoulombCounting, E1ExtendedKalmanFilter, E2EKFHysteresis, E5ObservabilityEKF, E6RBCDEKF]:
        est = cls(params)
        est.reset(0.80)

        # 1. Send normal step at 50 A
        meas1 = Measurement(v=3.28, i=50.0, temp_c=25.0, dt=1.0, dropout=False)
        out1 = est.step(meas1)
        soc1 = out1.soc

        # 2. Send dropped step (dropout=True, NaN measurements)
        meas_drop = Measurement(
            v=float("nan"),
            i=float("nan"),
            temp_c=float("nan"),
            dt=1.0,
            dropout=True,
        )
        out_drop = est.step(meas_drop)

        # Estimator must propagate with held last current (50 A)
        expected_delta = (50.0 * 1.0) / (3600.0 * params.nominal_capacity_ah)
        assert out_drop.soc == pytest.approx(soc1 - expected_delta, rel=1e-3)
        assert out_drop.anchor_used is False
        assert out_drop.voltage_residual is None
        assert out_drop.innovation_variance is None


def test_e0_rest_anchor_triggers_after_threshold():
    """Verify that E0 rest anchor triggers after sustained rest period."""
    assumptions, _, _ = load_assumptions(cli_overrides=["soc_definition.rest_anchor_enabled=true"])
    params_anchor = ParamSet.from_assumptions(assumptions)
    est = E0CoulombCounting(params_anchor)
    # Start E0 at wrong SOC 0.50
    est.reset(0.50)

    # Rest condition: i = 0.05 A <= rest_current_threshold_a (0.1 A)
    # Terminal voltage corresponds to SOC 0.80 at 25 C (approx 3.33 V)
    v_80 = 3.330
    dt = 100.0  # 100 s per step, rest threshold is 600 s

    # Step for 5 steps (500 s) -> not yet triggered
    for _ in range(5):
        meas = Measurement(v=v_80, i=0.05, temp_c=25.0, dt=dt, dropout=False)
        out = est.step(meas)
        assert out.anchor_used is False

    # Step 6 and 7 -> passes 600 s threshold -> rest anchor triggers!
    meas = Measurement(v=v_80, i=0.05, temp_c=25.0, dt=dt, dropout=False)
    out = est.step(meas)
    assert out.anchor_used is True
    # Inverted SOC from 3.33 V at 25 C should be near 0.80
    assert out.soc == pytest.approx(0.80, abs=0.02)


def test_e0_full_charge_anchor_pulse_and_cv_taper(params):
    """Verify that a 2C charge pulse followed by rest does not anchor,

    while a continuous CV taper to the cutoff anchors after full_charge_hold_s.
    """
    est = E0CoulombCounting(params)
    est.reset(0.50)

    # 1. 2C charge pulse (-200 A for 100 Ah cell) with terminal voltage exceeding threshold
    v_high = 3.60
    meas_pulse = Measurement(v=v_high, i=-200.0, temp_c=25.0, dt=1.0, dropout=False)
    out_pulse = est.step(meas_pulse)
    assert out_pulse.anchor_used is False, "Charge pulse at -200 A must not anchor"

    # Followed by rest (i = 0 A) with voltage remaining elevated above threshold
    for _ in range(120):
        meas_rest = Measurement(v=v_high, i=0.0, temp_c=25.0, dt=1.0, dropout=False)
        out_rest = est.step(meas_rest)
        assert out_rest.anchor_used is False, "Rest after charge pulse must not trigger full-charge anchor"

    # 2. CV taper to cutoff: negative current charging at low rate (|i| <= 0.5 A, i < 0)
    # Must hold continuously for full_charge_hold_s (60 s)
    taper_current = -0.4  # Negative (charging) and <= i_thresh (0.5 A)
    for step_idx in range(59):
        meas_taper = Measurement(v=v_high, i=taper_current, temp_c=25.0, dt=1.0, dropout=False)
        out_taper = est.step(meas_taper)
        assert out_taper.anchor_used is False, f"Step {step_idx} (< 60 s hold) must not anchor yet"

    # Step 60: reaches full_charge_hold_s (60.0 s) -> MUST anchor!
    meas_taper_final = Measurement(v=v_high, i=taper_current, temp_c=25.0, dt=1.0, dropout=False)
    out_final = est.step(meas_taper_final)
    assert out_final.anchor_used is True, "Sustained CV taper for 60 s must trigger full-charge anchor"
    assert out_final.soc == pytest.approx(params.full_charge_anchor_soc, abs=1e-3)

