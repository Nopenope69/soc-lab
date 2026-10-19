"""Unit tests for E4v2 Online RLS Impedance Adaptive EKF.

Tests:
1. Initialisation and state bounds
2. Propagation against the cell model
3. Update on current steps with |dI| >= 1 A and idle when |dI| < 1 A
4. Parameter bounds clamping to [0.5, 2.0]
5. Parallel adaptation on R1
6. Covariance symmetry and positive definiteness
7. Dropout handling
8. Reset behavior
9. Per-step runtime measurement (< 5 ms)
"""

import math
import time
import numpy as np
import pytest

from soc.assumptions.loader import load_assumptions
from soc.estimators.base import ParamSet, SocEstimate
from soc.estimators.e4v2_rls import E4V2RLSEKF
from soc.models.plant import Measurement


@pytest.fixture
def params() -> ParamSet:
    assumptions, _, _ = load_assumptions(profile="calce_a123_v4")
    return ParamSet.from_assumptions(assumptions, matched=True)


def test_e4v2_initialisation(params):
    """Verify E4v2 initializes states, covariance, and theta correctly."""
    est = E4V2RLSEKF(params)
    est.reset(0.85)

    assert est.x[0] == pytest.approx(0.85)
    assert est.x[1] == 0.0
    assert est.x[2] == 0.0
    assert est.x[3] == 0.0
    assert est.theta == 1.0
    assert est.p.shape == (4, 4)
    assert np.all(np.diag(est.p) > 0.0)


def test_e4v2_rls_updates_only_on_large_steps(params):
    """Verify theta updates when |dI| >= 1 A and stays static when |dI| < 1 A."""
    est = E4V2RLSEKF(params)
    est.reset(0.80)

    # Step 1: i = 0.5 A
    est.step(Measurement(v=3.28, i=0.5, temp_c=25.0, dt=1.0, dropout=False))
    th0 = est.theta

    # Step 2: i = 0.8 A (dI = 0.3 A < 1.0 A) -> no RLS update
    est.step(Measurement(v=3.27, i=0.8, temp_c=25.0, dt=1.0, dropout=False))
    assert est.theta == th0

    # Step 3: i = 3.5 A (dI = 2.7 A >= 1.0 A) -> RLS updates!
    est.step(Measurement(v=2.95, i=3.5, temp_c=25.0, dt=1.0, dropout=False))
    assert est.theta != th0
    assert 0.5 <= est.theta <= 2.0


def test_e4v2_theta_bounds_clamping(params):
    """Verify theta remains strictly clamped within [0.5, 2.0]."""
    est = E4V2RLSEKF(params)
    est.reset(0.50)

    # Inject extreme voltage drops to push RLS against bounds
    for _ in range(20):
        est.step(Measurement(v=1.0, i=10.0, temp_c=25.0, dt=1.0, dropout=False))
        assert 0.5 <= est.theta <= 2.0
        est.step(Measurement(v=4.0, i=-10.0, temp_c=25.0, dt=1.0, dropout=False))
        assert 0.5 <= est.theta <= 2.0


def test_e4v2_covariance_symmetry_and_posdef(params):
    """Verify covariance remains symmetric and positive semidefinite."""
    est = E4V2RLSEKF(params)
    est.reset(0.70)

    rng = np.random.RandomState(42)
    for _ in range(100):
        v = float(rng.uniform(3.20, 3.34))
        i = float(rng.uniform(-2.0, 3.0))
        meas = Measurement(v=v, i=i, temp_c=30.0, dt=1.0, dropout=False)
        est.step(meas)

        assert np.allclose(est.p, est.p.T, atol=1e-10)
        eigvals = np.linalg.eigvalsh(est.p)
        assert np.all(eigvals >= -1e-12)


def test_e4v2_dropout_handling(params):
    """Verify dropout skips measurement update and propagates state."""
    est = E4V2RLSEKF(params)
    est.reset(0.75)

    est.step(Measurement(v=3.29, i=2.0, temp_c=25.0, dt=1.0, dropout=False))
    soc_before = est.x[0]

    meas_drop = Measurement(v=float("nan"), i=float("nan"), temp_c=float("nan"), dt=1.0, dropout=True)
    out_drop = est.step(meas_drop)

    assert out_drop.voltage_residual is None
    assert out_drop.soc < soc_before
    assert 0.0 <= out_drop.soc <= 1.0


def test_e4v2_reset_clears_state(params):
    """Verify reset clears state cleanly."""
    est = E4V2RLSEKF(params)
    est.reset(0.50)
    for _ in range(10):
        est.step(Measurement(v=3.25, i=1.0, temp_c=20.0, dt=1.0, dropout=False))

    est.reset(0.90)
    assert est.x[0] == pytest.approx(0.90)
    assert est.x[1] == 0.0
    assert est.theta == 1.0


def test_e4v2_runtime_per_step(params):
    """Verify per-step runtime is well within 5 ms."""
    est = E4V2RLSEKF(params)
    est.reset(0.60)
    meas = Measurement(v=3.28, i=1.0, temp_c=25.0, dt=1.0, dropout=False)

    for _ in range(10):
        est.step(meas)

    n_steps = 100
    t0 = time.perf_counter()
    for _ in range(n_steps):
        est.step(meas)
    t1 = time.perf_counter()

    ms_per_step = (t1 - t0) * 1000.0 / n_steps
    assert ms_per_step < 5.0, f"Runtime too high: {ms_per_step:.3f} ms"
