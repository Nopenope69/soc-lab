"""Tests for E6 Residual Bias Compensation Dual Extended Kalman Filter (RBC-DEKF).

Tests:
1. With noiseless data and a constant OCV offset injected into the estimator model,
   theta must converge toward the offset and SOC error must shrink compared with E2.
2. The four-step execution order (state predict, state update, bias predict, bias update)
   is strictly respected.
3. Dropped samples execute predict-only.
4. When rbc_use_hysteresis_state is false, the hysteresis state is absent (3 states).
"""

import math
import numpy as np
import pytest

from soc.assumptions.loader import load_assumptions
from soc.estimators.base import ParamSet, SocEstimate
from soc.estimators.e2_ekf_hysteresis import E2EKFHysteresis
from soc.estimators.e6_rbc_dekf import E6RBCDEKF
from soc.models.plant import Measurement, PlantSimulator


def test_constant_ocv_offset_convergence_and_soc_error_reduction():
    """Test 1: Constant OCV offset in estimator model.

    theta must converge toward the offset and SOC error must shrink compared with E2.
    """
    offset_mv = 10.0  # +10 mV injected offset into estimator model
    offset_v = offset_mv / 1000.0

    # Load noiseless baseline configuration
    assumptions, _, _ = load_assumptions(cli_overrides=[
        "plant.initial_soc=0.50",
        "plant.hysteresis_amplitude_v=0.005",
        "sensors.current_offset_a=0.0",
        "sensors.current_gain_error=0.0",
        "sensors.current_noise_sigma_a=0.0",
        "sensors.voltage_noise_sigma_v=0.0",
        "sensors.voltage_quantisation_v=0.0",
        "sensors.dropout_rate=0.0",
        "sensors.temperature_noise_sigma_c=0.0",
        f"estimator_model.mismatch.ocv_offset_mv={offset_mv}",
    ])

    plant = PlantSimulator(assumptions)
    plant.reset(0.50)

    # ParamSets for E2 and E6 (both with mismatch applied)
    params_e2 = ParamSet.from_assumptions(assumptions, matched=False)
    params_e6 = ParamSet.from_assumptions(assumptions, matched=False)

    est_e2 = E2EKFHysteresis(params_e2)
    est_e6 = E6RBCDEKF(params_e6)

    est_e2.reset(0.50)
    est_e6.reset(0.50)

    # Run dynamic cycle on the plateau (500 steps)
    e2_errors = []
    e6_errors = []
    thetas = []

    dt = 1.0
    temp_c = 25.0

    for step_idx in range(500):
        # Pulse current pattern (+10 A discharge, 0 A rest, -10 A charge)
        phase = step_idx % 60
        if phase < 20:
            i_app = 10.0
        elif phase < 40:
            i_app = 0.0
        else:
            i_app = -10.0

        meas, truth = plant.step(i_app, temp_c, dt)

        out_e2 = est_e2.step(meas)
        out_e6 = est_e6.step(meas)

        e2_errors.append(out_e2.soc - truth.soc)
        e6_errors.append(out_e6.soc - truth.soc)
        thetas.append(est_e6.theta)

    e2_rmse = float(np.sqrt(np.mean(np.array(e2_errors) ** 2)))
    e6_rmse = float(np.sqrt(np.mean(np.array(e6_errors) ** 2)))
    e2_max_err = float(np.max(np.abs(np.array(e2_errors))))
    e6_max_err = float(np.max(np.abs(np.array(e6_errors))))

    final_theta = est_e6.theta
    # Estimator model OCV is +10 mV above truth.
    # Therefore, predicted terminal voltage is 10 mV higher than true voltage.
    # Measurement innovation is z - (V_model + theta) = V_true - (V_true + 10 mV + theta).
    # Residual bias theta must converge toward -10 mV (-0.010 V) to compensate the +10 mV error.
    expected_theta = -offset_v

    # Verify theta convergence toward offset (-0.010 V from 0.0 V)
    assert final_theta < -0.003, (
        f"Final theta {final_theta:.5f} V must move significantly toward expected offset {expected_theta:.5f} V"
    )
    assert abs(final_theta - expected_theta) < abs(0.0 - expected_theta), (
        f"Final theta {final_theta:.5f} V did not move toward offset {expected_theta:.5f} V from 0.0"
    )

    # Verify SOC error shrinks compared with E2
    assert e6_rmse < e2_rmse, (
        f"E6 RMSE ({e6_rmse * 100:.3f}%) must be lower than E2 RMSE ({e2_rmse * 100:.3f}%)"
    )
    assert e6_max_err < e2_max_err, (
        f"E6 max error ({e6_max_err * 100:.3f}%) must be lower than E2 max error ({e2_max_err * 100:.3f}%)"
    )


def test_four_step_order_is_respected():
    """Test 2: Verify four-step execution order is strictly respected.

    Sequence:
    1. State-filter prediction and voltage prediction
    2. State-filter update using previous theta_{k-1|k-1}
    3. Residual-bias filter prediction and voltage prediction using x_{k|k}
    4. Residual-bias filter update
    """
    assumptions, _, _ = load_assumptions()
    params = ParamSet.from_assumptions(assumptions)
    est = E6RBCDEKF(params)
    est.reset(0.80)

    # Spy on execution order and arguments
    call_log = []

    orig_step_1 = est.step_1_state_predict
    orig_step_2 = est.step_2_state_update
    orig_step_3 = est.step_3_bias_predict
    orig_step_4 = est.step_4_bias_update

    def mock_step_1(dt, i_prop, temp_prop):
        call_log.append("state_predict")
        return orig_step_1(dt, i_prop, temp_prop)

    def mock_step_2(v_meas, v_hat, i_prop, temp_prop, theta_prev):
        call_log.append(("state_update", theta_prev))
        return orig_step_2(v_meas, v_hat, i_prop, temp_prop, theta_prev)

    def mock_step_3(i_prop, temp_prop):
        call_log.append("bias_predict")
        return orig_step_3(i_prop, temp_prop)

    def mock_step_4(v_meas, v_hat_x):
        call_log.append("bias_update")
        return orig_step_4(v_meas, v_hat_x)

    est.step_1_state_predict = mock_step_1
    est.step_2_state_update = mock_step_2
    est.step_3_bias_predict = mock_step_3
    est.step_4_bias_update = mock_step_4

    # Set known initial theta
    est.theta = 0.015

    meas = Measurement(v=3.28, i=20.0, temp_c=25.0, dt=1.0, dropout=False)
    out = est.step(meas)

    # 1. Order of execution must be strictly 1, 2, 3, 4
    step_names = [c[0] if isinstance(c, tuple) else c for c in call_log]
    assert step_names == ["state_predict", "state_update", "bias_predict", "bias_update"]

    # 2. State update must receive the PREVIOUS theta (0.015)
    state_update_call = call_log[1]
    assert state_update_call[1] == pytest.approx(0.015)

    # 3. Check internal last_execution_order attribute
    assert est.last_execution_order == ["state_predict", "state_update", "bias_predict", "bias_update"]


def test_dropped_samples_execute_predict_only():
    """Test 3: Dropped samples execute predict-only for both state and bias filters."""
    assumptions, _, _ = load_assumptions()
    params = ParamSet.from_assumptions(assumptions)
    est = E6RBCDEKF(params)
    est.reset(0.80)

    # Normal step to establish baseline
    meas1 = Measurement(v=3.28, i=30.0, temp_c=25.0, dt=1.0, dropout=False)
    out1 = est.step(meas1)
    p_soc_before = est.p[0, 0]
    p_theta_before = est.p_theta
    theta_before = est.theta

    # Dropped sample
    meas_drop = Measurement(
        v=float("nan"),
        i=float("nan"),
        temp_c=float("nan"),
        dt=1.0,
        dropout=True,
    )
    out_drop = est.step(meas_drop)

    # Check that execution order performed only predict steps
    assert est.last_execution_order == ["state_predict", "bias_predict"]
    assert "state_update" not in est.last_execution_order
    assert "bias_update" not in est.last_execution_order

    # Outputs must have None for measurement residuals
    assert out_drop.voltage_residual is None
    assert out_drop.innovation_variance is None
    assert out_drop.kalman_gain_soc is None

    # Bias estimate held in prediction (theta_k|k-1 = theta_k-1|k-1)
    assert out_drop.theta == pytest.approx(theta_before)

    # Covariances must grow by process noise
    assert est.p_theta > p_theta_before
    assert est.p_theta == pytest.approx(p_theta_before + params.rbc_q_theta)


def test_hysteresis_state_absent_when_flag_false():
    """Test 4: When rbc_use_hysteresis_state is false, hysteresis state is absent."""
    assumptions, _, _ = load_assumptions(cli_overrides=[
        "filter.rbc_use_hysteresis_state=false",
    ])
    params = ParamSet.from_assumptions(assumptions)
    assert params.rbc_use_hysteresis_state is False

    est = E6RBCDEKF(params)
    assert est.use_hysteresis is False

    # State vector length must be exactly 3: [soc, i1, i2]
    assert len(est.x) == 3
    assert est.p.shape == (3, 3)

    est.reset(0.75)
    assert len(est.x) == 3
    assert est.p.shape == (3, 3)

    # Execute a step
    meas = Measurement(v=3.28, i=10.0, temp_c=25.0, dt=1.0, dropout=False)
    out = est.step(meas)

    assert len(est.x) == 3
    assert est.p.shape == (3, 3)
    assert 0.0 <= out.soc <= 1.0
