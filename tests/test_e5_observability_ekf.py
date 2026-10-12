"""Tests for E5 Observability-Gated Extended Kalman Filter (Observability-EKF).

Required Tests:
1. With a constant +5 mV OCV offset on the plateau and no other error, E5's SOC error
   must be smaller than E2's.
2. With no offset (matched), E5 matches E2 within 0.3 pp.
3. Variant flags cleanly control variance inflation, slope gating, and per-step capping.
4. Dropped measurements execute predict-only propagation.
"""

import math
import numpy as np
import pytest

from soc.assumptions.loader import load_assumptions
from soc.estimators.base import ParamSet, SocEstimate
from soc.estimators.e2_ekf_hysteresis import E2EKFHysteresis
from soc.estimators.e5_observability_ekf import E5ObservabilityEKF
from soc.models.plant import Measurement, PlantSimulator


def test_constant_pos5mv_offset_on_plateau_e5_beats_e2():
    """Test 1: With constant +5 mV OCV offset on the plateau, E5's SOC error is smaller than E2's."""
    offset_mv = 5.0

    # Noiseless setup on the flat plateau (initial SOC = 0.50)
    assumptions, _, _ = load_assumptions(cli_overrides=[
        "plant.initial_soc=0.50",
        "sensors.current_offset_a=0.0",
        "sensors.current_gain_error=0.0",
        "sensors.current_noise_sigma_a=0.0",
        "sensors.voltage_noise_sigma_v=0.0",
        "sensors.voltage_quantisation_v=0.0",
        "sensors.dropout_rate=0.0",
        "sensors.temperature_noise_sigma_c=0.0",
        "estimator_model.mismatch.r0_pct=0.0",
        "estimator_model.mismatch.r1_pct=0.0",
        "estimator_model.mismatch.tau1_pct=0.0",
        "estimator_model.mismatch.r2_pct=0.0",
        "estimator_model.mismatch.tau2_pct=0.0",
        "estimator_model.mismatch.hysteresis_amplitude_pct=0.0",
        "estimator_model.mismatch.hysteresis_gamma_pct=0.0",
        f"estimator_model.mismatch.ocv_offset_mv={offset_mv}",
        "filter.e5_enable_r_inflation=true",
        "filter.e5_enable_slope_gating=true",
        "filter.e5_enable_step_cap=true",
        "filter.e5_sigma_ocv_model_v=0.005",
        "filter.e5_slope_ref=0.2",
        "filter.e5_max_soc_step=0.001",
    ])

    plant = PlantSimulator(assumptions)
    plant.reset(0.50)

    params_e2 = ParamSet.from_assumptions(assumptions, matched=False)
    params_e5 = ParamSet.from_assumptions(assumptions, matched=False)

    est_e2 = E2EKFHysteresis(params_e2)
    est_e5 = E5ObservabilityEKF(params_e5)

    est_e2.reset(0.50)
    est_e5.reset(0.50)

    e2_errors = []
    e5_errors = []

    dt = 1.0
    temp_c = 25.0

    # Dynamic cycling across 600 steps in plateau region [0.45, 0.55]
    for step_idx in range(600):
        phase = step_idx % 60
        if phase < 20:
            i_app = 15.0
        elif phase < 40:
            i_app = 0.0
        else:
            i_app = -15.0

        meas, truth = plant.step(i_app, temp_c, dt)
        out_e2 = est_e2.step(meas)
        out_e5 = est_e5.step(meas)

        e2_errors.append(out_e2.soc - truth.soc)
        e5_errors.append(out_e5.soc - truth.soc)

    e2_rmse = float(np.sqrt(np.mean(np.array(e2_errors) ** 2)))
    e5_rmse = float(np.sqrt(np.mean(np.array(e5_errors) ** 2)))

    # Assert that E5's SOC error is smaller than E2's
    assert e5_rmse < e2_rmse, (
        f"E5 RMSE ({e5_rmse * 100:.3f} pp) must be strictly smaller than E2 RMSE ({e2_rmse * 100:.3f} pp)"
    )


def test_matched_no_offset_e5_matches_e2_within_0_3_pp():
    """Test 2: With no offset, E5 matches E2 within 0.3 pp."""
    assumptions, _, _ = load_assumptions(cli_overrides=[
        "plant.initial_soc=0.50",
        "filter.e5_enable_r_inflation=true",
        "filter.e5_enable_slope_gating=true",
        "filter.e5_enable_step_cap=true",
        "filter.e5_sigma_ocv_model_v=0.005",
        "filter.e5_slope_ref=0.2",
        "filter.e5_max_soc_step=0.001",
    ])

    plant = PlantSimulator(assumptions)
    plant.reset(0.50)

    params_e2 = ParamSet.from_assumptions(assumptions, matched=True)
    params_e5 = ParamSet.from_assumptions(assumptions, matched=True)

    est_e2 = E2EKFHysteresis(params_e2)
    est_e5 = E5ObservabilityEKF(params_e5)

    est_e2.reset(0.50)
    est_e5.reset(0.50)

    e2_socs = []
    e5_socs = []

    dt = 1.0
    temp_c = 25.0

    for step_idx in range(600):
        phase = step_idx % 60
        if phase < 20:
            i_app = 20.0
        elif phase < 40:
            i_app = 0.0
        else:
            i_app = -20.0

        meas, _ = plant.step(i_app, temp_c, dt)
        out_e2 = est_e2.step(meas)
        out_e5 = est_e5.step(meas)

        e2_socs.append(out_e2.soc)
        e5_socs.append(out_e5.soc)

    diff_pp = float(np.sqrt(np.mean((np.array(e5_socs) - np.array(e2_socs)) ** 2))) * 100.0

    assert diff_pp <= 0.30, (
        f"E5 deviation from E2 ({diff_pp:.4f} pp) exceeds the 0.30 pp threshold under matched conditions"
    )


def test_variant_flag_isolation():
    """Test 3: Verify the 3 variants selectable by config flags:

    (a) variance inflation only
    (a)+(b) variance inflation + slope gating
    (a)+(b)+(c) variance inflation + slope gating + step cap
    """
    assumptions, _, _ = load_assumptions()
    base_params = ParamSet.from_assumptions(assumptions, matched=True)

    # Variant (a)
    p_a = ParamSet(
        **{
            **base_params.__dict__,
            "e5_enable_r_inflation": True,
            "e5_enable_slope_gating": False,
            "e5_enable_step_cap": False,
            "e5_sigma_ocv_model_v": 0.005,
        }
    )
    est_a = E5ObservabilityEKF(p_a)
    est_a.reset(0.50)
    meas = Measurement(v=3.35, i=10.0, temp_c=25.0, dt=1.0, dropout=False)
    _ = est_a.step(meas)
    assert est_a.last_applied_g == 1.0  # Slope gating disabled

    # Variant (a)+(b)
    p_ab = ParamSet(
        **{
            **base_params.__dict__,
            "e5_enable_r_inflation": True,
            "e5_enable_slope_gating": True,
            "e5_enable_step_cap": False,
            "e5_sigma_ocv_model_v": 0.005,
            "e5_slope_ref": 0.2,
        }
    )
    est_ab = E5ObservabilityEKF(p_ab)
    est_ab.reset(0.50)
    _ = est_ab.step(meas)
    assert est_ab.last_applied_g < 1.0  # Slope gating active on plateau

    # Variant (a)+(b)+(c) with fixed cap (v1 compatibility)
    p_abc_fixed = ParamSet(
        **{
            **base_params.__dict__,
            "e5_enable_r_inflation": True,
            "e5_enable_slope_gating": True,
            "e5_enable_step_cap": True,
            "e5_use_observability_cap": False,
            "e5_sigma_ocv_model_v": 0.005,
            "e5_slope_ref": 0.2,
            "e5_max_soc_step": 0.0001,  # tight fixed cap
        }
    )
    est_abc_fixed = E5ObservabilityEKF(p_abc_fixed)
    est_abc_fixed.reset(0.50)
    _ = est_abc_fixed.step(meas)
    assert abs(est_abc_fixed.last_applied_delta_soc) <= 0.0001 + 1e-9

    # Variant (a)+(b)+(c) with observability-dependent cap (v2)
    p_abc_obs = ParamSet(
        **{
            **base_params.__dict__,
            "e5_enable_r_inflation": True,
            "e5_enable_slope_gating": True,
            "e5_enable_step_cap": True,
            "e5_use_observability_cap": True,
            "e5_sigma_ocv_model_v": 0.005,
            "e5_slope_ref": 0.2,
            "e5_cap_plateau": 0.0001,
            "e5_cap_knee": 0.05,
        }
    )
    est_abc_obs = E5ObservabilityEKF(p_abc_obs)
    est_abc_obs.reset(0.50)
    _ = est_abc_obs.step(meas)
    g_meas = est_abc_obs.last_applied_g
    expected_cap = 0.0001 + (0.05 - 0.0001) * g_meas
    assert abs(est_abc_obs.last_applied_delta_soc) <= expected_cap + 1e-9


def test_dropout_handling_executes_predict_only():
    """Test 4: Dropped measurements perform time propagation only."""
    assumptions, _, _ = load_assumptions()
    params = ParamSet.from_assumptions(assumptions, matched=True)
    est = E5ObservabilityEKF(params)
    est.reset(0.70)

    # Valid step to prime last valid current
    meas_valid = Measurement(v=3.28, i=20.0, temp_c=25.0, dt=1.0, dropout=False)
    out1 = est.step(meas_valid)

    # Dropped step
    meas_drop = Measurement(v=float("nan"), i=float("nan"), temp_c=float("nan"), dt=1.0, dropout=True)
    out2 = est.step(meas_drop)

    expected_delta = (20.0 * 1.0) / (3600.0 * params.nominal_capacity_ah)
    assert out2.soc == pytest.approx(out1.soc - expected_delta, rel=1e-3)
    assert out2.voltage_residual is None
    assert out2.innovation_variance is None
