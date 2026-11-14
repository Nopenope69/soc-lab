"""Unit tests for E10 Hybrid Multi-Physics PINN + Adaptive EKF (PINN-AEKF) Estimator.

Tests:
1. Instantiation and default state
2. Estimator Protocol conformance and isolation
3. reset(soc0, soc_std) behavior
4. Step execution and bounded SOC output in [0, 1]
5. Dropout handling
6. Registry lookup via get_estimator("E10", params)
7. Adaptive covariance tracking (Sage-Husa dynamics)
8. Streaming runtime (< 5 ms per step)
"""

import inspect
import time
from typing import get_type_hints
import numpy as np
import pytest

from soc.assumptions.loader import load_assumptions
from soc.estimators.base import ParamSet, SocEstimate, Estimator
from soc.estimators.e10_pinn_aekf import E10PINNAEKFEstimator
from soc.estimators.registry import get_estimator
from soc.models.plant import Measurement


@pytest.fixture
def params() -> ParamSet:
    assumptions, _, _ = load_assumptions(profile="calce_a123_v4")
    return ParamSet.from_assumptions(assumptions, matched=True)


def test_e10_initialisation(params):
    """Verify E10 initializes physics tables, PINN model, and adaptive covariance cleanly."""
    est = E10PINNAEKFEstimator(params)
    assert isinstance(est, Estimator)
    assert est.pinn is not None
    assert est.model_loaded is True
    assert est.r_adaptive > 0.0


def test_e10_isolation(params):
    """Verify E10 conforms strictly to Estimator protocol and argument signature."""
    hints = get_type_hints(E10PINNAEKFEstimator.step)
    params_keys = list(inspect.signature(E10PINNAEKFEstimator.step).parameters.keys())
    assert params_keys == ["self", "measurement"]
    assert hints.get("measurement") is Measurement
    assert hints.get("return") is SocEstimate


def test_e10_reset(params):
    """Verify reset clears filter states, covariance, and resets adaptive measurement noise."""
    est = E10PINNAEKFEstimator(params)
    est.reset(0.80, soc_std=0.005)

    assert est.x[0] == pytest.approx(0.80)
    assert est.p[0, 0] == pytest.approx(0.005 ** 2)
    assert est.r_adaptive == pytest.approx(0.0001)


def test_e10_step_and_bounds(params):
    """Verify step produces a valid SocEstimate bounded within [0, 1]."""
    est = E10PINNAEKFEstimator(params)
    est.reset(0.50)

    for i in range(15):
        meas = Measurement(v=3.28 - 0.01 * i, i=1.5, temp_c=25.0, dt=1.0, dropout=False)
        out = est.step(meas)
        assert isinstance(out, SocEstimate)
        assert 0.0 <= out.soc <= 1.0
        assert out.soc_std >= 0.0
        assert out.voltage_residual is not None
        assert out.innovation_variance is not None


def test_e10_dropout_handling(params):
    """Verify estimator survives missing measurements without NaN or failure."""
    est = E10PINNAEKFEstimator(params)
    est.reset(0.60)

    est.step(Measurement(v=3.28, i=2.0, temp_c=25.0, dt=1.0, dropout=False))
    out_drop = est.step(Measurement(v=float("nan"), i=float("nan"), temp_c=float("nan"), dt=1.0, dropout=True))

    assert isinstance(out_drop, SocEstimate)
    assert 0.0 <= out_drop.soc <= 1.0
    assert not np.isnan(out_drop.soc)


def test_e10_registry_lookup(params):
    """Verify E10 is registered in the central estimator registry."""
    for name in ["E10", "e10", "e10_pinn_aekf"]:
        est = get_estimator(name, params)
        assert isinstance(est, E10PINNAEKFEstimator)


def test_e10_sage_husa_adaptation(params):
    """Verify that Sage-Husa adapts R_adaptive dynamically within specified [R_min, R_max]."""
    est = E10PINNAEKFEstimator(params, r_min=1e-5, r_max=0.04)
    est.reset(0.50)

    # Inject noisy voltage measurements to trigger covariance adaptation
    r_initial = est.r_adaptive
    for i in range(20):
        # Apply varying voltage offset to simulate high measurement noise
        v_offset = 0.05 if i % 2 == 0 else -0.05
        meas = Measurement(v=3.28 + v_offset, i=1.0, temp_c=25.0, dt=1.0, dropout=False)
        est.step(meas)

    assert est.r_adaptive > r_initial
    assert est.r_min <= est.r_adaptive <= est.r_max


def test_e10_runtime(params):
    """Verify combined PINN inference + AEKF step runtime is under 5 ms."""
    est = E10PINNAEKFEstimator(params)
    est.reset(0.50)

    meas = Measurement(v=3.28, i=1.5, temp_c=25.0, dt=1.0, dropout=False)

    # Warmup
    for _ in range(10):
        est.step(meas)

    # Benchmark 100 steps
    n_iters = 100
    t0 = time.perf_counter()
    for _ in range(n_iters):
        est.step(meas)
    elapsed = time.perf_counter() - t0
    ms_per_step = (elapsed / n_iters) * 1000.0

    print(f"\nE10 PINN-AEKF Streaming Latency: {ms_per_step:.3f} ms/step")
    assert ms_per_step < 5.0, f"Streaming step too slow: {ms_per_step:.3f} ms/step"
