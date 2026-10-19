"""Unit tests for D3 Innovation-Gated EKF.

Tests:
1. Initialisation and state bounds
2. Propagation against the cell model
3. Innovation gating triggers on plateau with large innovation and small P_soc
4. Innovation gating does NOT trigger in knees or when P_soc is high
5. Covariance symmetry and positive definiteness
6. Dropout handling
7. Reset behavior
8. Per-step runtime measurement (< 5 ms)
"""

import math
import time
import numpy as np
import pytest

from soc.assumptions.loader import load_assumptions
from soc.estimators.base import ParamSet, SocEstimate
from soc.estimators.innovation_gating import D3InnovationGatedEKF
from soc.models.plant import Measurement


@pytest.fixture
def params() -> ParamSet:
    assumptions, _, _ = load_assumptions(profile="calce_a123_v4")
    return ParamSet.from_assumptions(assumptions, matched=True)


def test_d3_initialisation(params):
    """Verify D3 initializes states and covariance correctly."""
    est = D3InnovationGatedEKF(params)
    est.reset(0.85)

    assert est.x[0] == pytest.approx(0.85)
    assert est.x[1] == 0.0
    assert est.x[2] == 0.0
    assert est.x[3] == 0.0
    assert est.p.shape == (4, 4)
    assert np.all(np.diag(est.p) > 0.0)
    assert est.last_gating_triggered is False


def test_d3_innovation_gating_triggers_on_plateau_with_low_uncertainty(params):
    """Verify that when P_soc is small, on plateau, and innovation is large, gating triggers."""
    est = D3InnovationGatedEKF(params)
    est.k_gate = 2.0
    est.slope_threshold = 0.1
    est.p_soc_threshold = 1e-3
    est.reset(0.50)  # Plateau
    est.p[0, 0] = 1e-4  # Low SOC uncertainty

    # Large voltage error (0.2 V innovation)
    meas = Measurement(v=3.50, i=1.0, temp_c=25.0, dt=1.0, dropout=False)
    out = est.step(meas)

    assert est.last_gating_triggered is True
    # SOC correction was skipped/zeroed, so SOC only moves by Coulomb integration
    expected_coulomb = 0.50 - (1.0 * 1.0) / (3600.0 * params.nominal_capacity_ah)
    assert out.soc == pytest.approx(expected_coulomb, rel=1e-3)


def test_d3_innovation_gating_does_not_trigger_when_uncertainty_high(params):
    """Verify that when P_soc is large (e.g. after wrong start), gating does NOT trigger."""
    est = D3InnovationGatedEKF(params)
    est.k_gate = 2.0
    est.slope_threshold = 0.1
    est.p_soc_threshold = 1e-3
    est.reset(0.50)
    est.p[0, 0] = 0.01  # High SOC uncertainty (sigma = 10%)

    meas = Measurement(v=3.50, i=1.0, temp_c=25.0, dt=1.0, dropout=False)
    out = est.step(meas)

    # Gating should NOT trigger because filter knows its SOC estimate is uncertain
    assert est.last_gating_triggered is False


def test_d3_innovation_gating_does_not_trigger_in_knees(params):
    """Verify that in the steep knees (high dOCV/dSOC), gating does NOT trigger."""
    est = D3InnovationGatedEKF(params)
    est.k_gate = 2.0
    est.slope_threshold = 0.05
    est.p_soc_threshold = 1e-3
    est.reset(0.95)  # Knee region
    est.p[0, 0] = 1e-4

    meas = Measurement(v=3.55, i=1.0, temp_c=25.0, dt=1.0, dropout=False)
    est.step(meas)

    assert est.last_gating_triggered is False


def test_d3_covariance_symmetry_and_posdef(params):
    """Verify covariance remains symmetric and positive semidefinite."""
    est = D3InnovationGatedEKF(params)
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


def test_d3_dropout_handling(params):
    """Verify dropout skips measurement update and propagates state."""
    est = D3InnovationGatedEKF(params)
    est.reset(0.75)

    est.step(Measurement(v=3.29, i=2.0, temp_c=25.0, dt=1.0, dropout=False))
    soc_before = est.x[0]

    meas_drop = Measurement(v=float("nan"), i=float("nan"), temp_c=float("nan"), dt=1.0, dropout=True)
    out_drop = est.step(meas_drop)

    assert out_drop.voltage_residual is None
    assert out_drop.soc < soc_before
    assert 0.0 <= out_drop.soc <= 1.0


def test_d3_reset_clears_state(params):
    """Verify reset clears state cleanly."""
    est = D3InnovationGatedEKF(params)
    est.reset(0.50)
    for _ in range(10):
        est.step(Measurement(v=3.25, i=1.0, temp_c=20.0, dt=1.0, dropout=False))

    est.reset(0.90)
    assert est.x[0] == pytest.approx(0.90)
    assert est.x[1] == 0.0


def test_d3_runtime_per_step(params):
    """Verify per-step runtime is well within 5 ms."""
    est = D3InnovationGatedEKF(params)
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
