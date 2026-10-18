"""Unit tests for E6v2 Residual Bias Filter.

Tests:
1. Initialisation and state bounds
2. Propagation against the cell model
3. Decoupling verification: bias frozen on plateau, active in knees
4. Covariance symmetry and positive definiteness
5. Dropout handling
6. Reset behavior
7. Per-step runtime measurement (< 5 ms)
"""

import math
import time
import numpy as np
import pytest

from soc.assumptions.loader import load_assumptions
from soc.estimators.base import ParamSet, SocEstimate
from soc.estimators.e6v2 import E6V2ResidualBiasFilter
from soc.models.plant import Measurement


@pytest.fixture
def params() -> ParamSet:
    assumptions, _, _ = load_assumptions(profile="calce_a123_v3")
    return ParamSet.from_assumptions(assumptions, matched=True)


def test_e6v2_initialisation(params):
    """Verify E6v2 initializes state, covariance, and bias state."""
    est = E6V2ResidualBiasFilter(params)
    est.reset(0.85)

    assert est.x[0] == pytest.approx(0.85)
    assert est.x[1] == 0.0
    assert est.x[2] == 0.0
    assert est.x[3] == 0.0
    assert est.theta == 0.0
    assert est.p.shape == (4, 4)
    assert np.all(np.diag(est.p) > 0.0)


def test_e6v2_bias_decoupling_on_plateau(params):
    """Verify bias theta remains frozen on the plateau and does not absorb voltage errors."""
    est = E6V2ResidualBiasFilter(params)
    est.reset(0.50)  # Plateau where dOCV/dSOC is flat

    # Inject a 20 mV voltage offset on the plateau
    meas = Measurement(v=3.32, i=1.0, temp_c=25.0, dt=1.0, dropout=False)
    est.step(meas)

    # On plateau, theta must NOT update (frozen at 0.0)
    assert est.theta == 0.0


def test_e6v2_bias_update_in_knees(params):
    """Verify bias theta updates in the knee regions where dOCV/dSOC is steep."""
    est = E6V2ResidualBiasFilter(params)
    est.reset(0.05)  # Lower knee where dOCV/dSOC > 1.0 V/unit

    meas = Measurement(v=3.10, i=1.0, temp_c=25.0, dt=1.0, dropout=False)
    est.step(meas)

    # In steep knee, theta must update
    assert est.theta != 0.0


def test_e6v2_covariance_symmetry_and_posdef(params):
    """Verify covariance remains symmetric and positive semidefinite."""
    est = E6V2ResidualBiasFilter(params)
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


def test_e6v2_dropout_handling(params):
    """Verify dropout skips measurement update and propagates state."""
    est = E6V2ResidualBiasFilter(params)
    est.reset(0.75)

    est.step(Measurement(v=3.29, i=2.0, temp_c=25.0, dt=1.0, dropout=False))
    soc_before = est.x[0]

    meas_drop = Measurement(v=float("nan"), i=float("nan"), temp_c=float("nan"), dt=1.0, dropout=True)
    out_drop = est.step(meas_drop)

    assert out_drop.voltage_residual is None
    assert out_drop.soc < soc_before
    assert 0.0 <= out_drop.soc <= 1.0


def test_e6v2_reset_clears_state(params):
    """Verify reset clears state and bias."""
    est = E6V2ResidualBiasFilter(params)
    est.reset(0.05)
    est.step(Measurement(v=3.10, i=1.0, temp_c=25.0, dt=1.0, dropout=False))
    assert est.theta != 0.0

    est.reset(0.80)
    assert est.x[0] == pytest.approx(0.80)
    assert est.theta == 0.0


def test_e6v2_runtime_per_step(params):
    """Verify per-step runtime is well within 5 ms."""
    est = E6V2ResidualBiasFilter(params)
    est.reset(0.60)
    meas = Measurement(v=3.28, i=1.0, temp_c=25.0, dt=1.0, dropout=False)

    for _ in range(10):
        est.step(meas)

    n_steps = 100
    t0 = time.perf_counter()
    for _ in range(n_steps):
        est.step(meas)
    t1 = time.perf_counter()

    ms_per_step = (t1 - t0) / n_steps * 1000.0
    print(f"\nE6v2 measured runtime: {ms_per_step:.3f} ms / step")
    assert ms_per_step < 5.0
