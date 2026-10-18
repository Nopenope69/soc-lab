"""Unit tests for E5v3 Observability-Gated EKF.

Tests:
1. Initialisation and state bounds
2. Propagation against cell model
3. Observability gating on plateau vs knee
4. Plateau step capping
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
from soc.estimators.e5v3 import E5V3ObservabilityEKF
from soc.models.plant import Measurement


@pytest.fixture
def params() -> ParamSet:
    assumptions, _, _ = load_assumptions(profile="calce_a123_v3")
    return ParamSet.from_assumptions(assumptions, matched=True)


def test_e5v3_initialisation(params):
    """Verify E5v3 initializes state and covariance correctly."""
    est = E5V3ObservabilityEKF(params)
    est.reset(0.85)

    assert est.x[0] == pytest.approx(0.85)
    assert est.x[1] == 0.0
    assert est.x[2] == 0.0
    assert est.x[3] == 0.0
    assert est.p.shape == (4, 4)
    assert np.all(np.diag(est.p) > 0.0)


def test_e5v3_observability_gating_and_capping(params):
    """Verify observability gating g < 1 and step capping on the flat plateau."""
    est = E5V3ObservabilityEKF(params)
    est.reset(0.50)  # Mid-plateau where dOCV/dSOC is flat (~0.01 - 0.05 V/unit)

    # Large voltage error
    meas = Measurement(v=3.50, i=1.0, temp_c=25.0, dt=1.0, dropout=False)
    out = est.step(meas)

    # On plateau, g must be small (< 0.5)
    assert est.last_applied_g < 0.5
    # The applied delta SOC must be capped by cap_plateau + (cap_knee - cap_plateau)*g
    expected_cap = est.cap_plateau + (est.cap_knee - est.cap_plateau) * est.last_applied_g
    assert abs(est.last_applied_delta_soc) <= expected_cap + 1e-6
    assert 0.0 <= out.soc <= 1.0


def test_e5v3_covariance_symmetry_and_posdef(params):
    """Verify covariance remains symmetric and positive semidefinite."""
    est = E5V3ObservabilityEKF(params)
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


def test_e5v3_dropout_handling(params):
    """Verify dropout skips measurement update and propagates state."""
    est = E5V3ObservabilityEKF(params)
    est.reset(0.75)

    est.step(Measurement(v=3.29, i=2.0, temp_c=25.0, dt=1.0, dropout=False))
    soc_before = est.x[0]

    meas_drop = Measurement(v=float("nan"), i=float("nan"), temp_c=float("nan"), dt=1.0, dropout=True)
    out_drop = est.step(meas_drop)

    assert out_drop.voltage_residual is None
    assert out_drop.soc < soc_before
    assert 0.0 <= out_drop.soc <= 1.0


def test_e5v3_reset_clears_state(params):
    """Verify reset clears state cleanly."""
    est = E5V3ObservabilityEKF(params)
    est.reset(0.50)
    for _ in range(10):
        est.step(Measurement(v=3.25, i=1.0, temp_c=20.0, dt=1.0, dropout=False))

    est.reset(0.90)
    assert est.x[0] == pytest.approx(0.90)
    assert est.x[1] == 0.0


def test_e5v3_runtime_per_step(params):
    """Verify per-step runtime is well within 5 ms."""
    est = E5V3ObservabilityEKF(params)
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
    print(f"\nE5v3 measured runtime: {ms_per_step:.3f} ms / step")
    assert ms_per_step < 5.0
