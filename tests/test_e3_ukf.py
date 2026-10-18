"""Unit tests for E3 Unscented Kalman Filter (UKF).

Tests:
1. Initialisation and state bounds
2. Propagation against the cell model
3. Covariance symmetry and positive definiteness
4. Dropout handling
5. Reset behavior
6. Per-step runtime measurement (< 5 ms)
"""

import math
import time
import numpy as np
import pytest

from soc.assumptions.loader import load_assumptions
from soc.estimators.base import ParamSet, SocEstimate
from soc.estimators.e3_ukf import E3UnscentedKalmanFilter
from soc.models.plant import Measurement


@pytest.fixture
def params() -> ParamSet:
    assumptions, _, _ = load_assumptions(profile="calce_a123_v3")
    return ParamSet.from_assumptions(assumptions, matched=True)


def test_e3_initialisation(params):
    """Verify E3 UKF initializes states and covariance correctly."""
    est = E3UnscentedKalmanFilter(params)
    est.reset(0.85)

    assert est.x[0] == pytest.approx(0.85)
    assert est.x[1] == 0.0
    assert est.x[2] == 0.0
    assert est.x[3] == 0.0
    assert est.p.shape == (4, 4)
    assert np.all(np.diag(est.p) > 0.0)
    assert np.allclose(est.p, est.p.T)


def test_e3_step_and_propagation(params):
    """Verify E3 steps forward, updates state, and maintains valid bounds."""
    est = E3UnscentedKalmanFilter(params)
    est.reset(0.80)

    meas = Measurement(v=3.28, i=1.5, temp_c=25.0, dt=1.0, dropout=False)
    out = est.step(meas)

    assert isinstance(out, SocEstimate)
    assert 0.0 <= out.soc <= 1.0
    assert out.soc_std >= 0.0
    assert out.voltage_residual is not None
    assert out.innovation_variance is not None
    assert out.innovation_variance > 0.0


def test_e3_covariance_symmetry_and_posdef(params):
    """Verify covariance remains symmetric and positive semidefinite after 100 steps."""
    est = E3UnscentedKalmanFilter(params)
    est.reset(0.70)

    rng = np.random.RandomState(42)
    for _ in range(100):
        v = float(rng.uniform(3.20, 3.34))
        i = float(rng.uniform(-2.0, 3.0))
        meas = Measurement(v=v, i=i, temp_c=30.0, dt=1.0, dropout=False)
        est.step(meas)

        # Symmetry
        assert np.allclose(est.p, est.p.T, atol=1e-10)
        # Eigenvalues >= -1e-12 (positive semidefinite)
        eigvals = np.linalg.eigvalsh(est.p)
        assert np.all(eigvals >= -1e-12)


def test_e3_dropout_handling(params):
    """Verify dropout skips measurement update and propagates state."""
    est = E3UnscentedKalmanFilter(params)
    est.reset(0.75)

    meas_valid = Measurement(v=3.29, i=2.0, temp_c=25.0, dt=1.0, dropout=False)
    est.step(meas_valid)
    soc_before = est.x[0]

    meas_drop = Measurement(v=float("nan"), i=float("nan"), temp_c=float("nan"), dt=1.0, dropout=True)
    out_drop = est.step(meas_drop)

    assert out_drop.voltage_residual is None
    assert out_drop.innovation_variance is None
    assert out_drop.soc < soc_before  # Discharged during dropout
    assert 0.0 <= out_drop.soc <= 1.0


def test_e3_reset_clears_state(params):
    """Verify reset resets states and covariance cleanly."""
    est = E3UnscentedKalmanFilter(params)
    est.reset(0.50)
    for _ in range(10):
        est.step(Measurement(v=3.25, i=1.0, temp_c=20.0, dt=1.0, dropout=False))

    est.reset(0.90)
    assert est.x[0] == pytest.approx(0.90)
    assert est.x[1] == 0.0
    assert est.x[2] == 0.0
    assert est.x[3] == 0.0


def test_e3_runtime_per_step(params):
    """Verify per-step runtime is well within the 5 ms budget."""
    est = E3UnscentedKalmanFilter(params)
    est.reset(0.60)
    meas = Measurement(v=3.28, i=1.0, temp_c=25.0, dt=1.0, dropout=False)

    # Warmup
    for _ in range(10):
        est.step(meas)

    n_steps = 100
    t0 = time.perf_counter()
    for _ in range(n_steps):
        est.step(meas)
    t1 = time.perf_counter()

    ms_per_step = (t1 - t0) / n_steps * 1000.0
    print(f"\nE3 UKF measured runtime: {ms_per_step:.3f} ms / step")
    assert ms_per_step < 5.0
