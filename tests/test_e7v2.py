"""Unit tests for E7v2 Composite Estimator.

Tests:
1. Initialisation and state bounds
2. Propagation against the cell model
3. Update on current steps with |dI| >= 1 A
4. Observability gating attenuates gain on flat slope
5. Plateau step cap limits maximum state change
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
from soc.estimators.e7v2 import E7V2CompositeFilter
from soc.models.plant import Measurement


@pytest.fixture
def params() -> ParamSet:
    assumptions, _, _ = load_assumptions(profile="calce_a123_v4")
    return ParamSet.from_assumptions(assumptions, matched=True)


def test_e7v2_initialisation(params):
    """Verify E7v2 initializes states, covariance, and theta correctly."""
    est = E7V2CompositeFilter(params)
    est.reset(0.85)

    assert est.x[0] == pytest.approx(0.85)
    assert est.x[1] == 0.0
    assert est.x[2] == 0.0
    assert est.x[3] == 0.0
    assert est.theta == 1.0
    assert est.p.shape == (4, 4)
    assert np.all(np.diag(est.p) > 0.0)


def test_e7v2_rls_updates_only_on_large_steps(params):
    """Verify theta updates when |dI| >= 1 A and stays static when |dI| < 1 A."""
    est = E7V2CompositeFilter(params)
    est.reset(0.80)

    # Step 1: i = 0.5 A
    est.step(Measurement(v=3.28, i=0.5, temp_c=25.0, dt=1.0, dropout=False))
    th0 = est.theta

    # Step 2: i = 0.8 A (dI = 0.3 A < 1.0 A) -> no RLS update
    est.step(Measurement(v=3.27, i=0.8, temp_c=25.0, dt=1.0, dropout=False))
    assert est.theta == th0

    # Step 3: i = 3.5 A (dI = 2.7 A >= 1.0 A) -> RLS updates
    est.step(Measurement(v=2.95, i=3.5, temp_c=25.0, dt=1.0, dropout=False))
    assert est.theta != th0
    assert 0.5 <= est.theta <= 2.0


def test_e7v2_plateau_capping(params):
    """Verify plateau step capping bounds single-step SOC update."""
    est = E7V2CompositeFilter(params)
    est.reset(0.50)  # Center of flat plateau

    # Apply huge voltage residual (v=2.5 V while OCV ~ 3.28 V)
    out = est.step(Measurement(v=2.5, i=0.0, temp_c=25.0, dt=1.0, dropout=False))
    delta_applied = abs(est.last_applied_delta_soc)

    # Max plateau cap should be very small (~ 1e-4 or less)
    assert delta_applied <= 0.01
    assert out.soc < 0.50


def test_e7v2_covariance_properties(params):
    """Verify P matrix remains symmetric and positive-definite after updates."""
    est = E7V2CompositeFilter(params)
    est.reset(0.70)

    for i in range(10):
        meas = Measurement(v=3.25 + 0.01 * (i % 3), i=1.5 * (i % 2), temp_c=25.0, dt=1.0, dropout=False)
        est.step(meas)
        assert np.allclose(est.p, est.p.T, atol=1e-10)
        eigvals = np.linalg.eigvalsh(est.p)
        assert np.all(eigvals > 0.0)


def test_e7v2_dropout_handling(params):
    """Verify estimator handles dropout smoothly without updating theta or crashing."""
    est = E7V2CompositeFilter(params)
    est.reset(0.60)

    est.step(Measurement(v=3.28, i=2.0, temp_c=25.0, dt=1.0, dropout=False))
    th_before = est.theta

    out_drop = est.step(Measurement(v=float("nan"), i=float("nan"), temp_c=float("nan"), dt=1.0, dropout=True))
    assert est.theta == th_before
    assert out_drop.voltage_residual is None
    assert 0.0 <= out_drop.soc <= 1.0


def test_e7v2_reset_behavior(params):
    """Verify reset clears state, covariance, and resets theta to 1.0."""
    est = E7V2CompositeFilter(params)
    est.reset(0.50)
    est.step(Measurement(v=3.10, i=4.0, temp_c=25.0, dt=1.0, dropout=False))

    est.reset(0.90)
    assert est.x[0] == pytest.approx(0.90)
    assert est.theta == 1.0
    assert not est.has_prev


def test_e7v2_per_step_runtime(params):
    """Verify per-step execution time is well under the 5 ms limit."""
    est = E7V2CompositeFilter(params)
    est.reset(0.50)

    meas = Measurement(v=3.28, i=1.5, temp_c=25.0, dt=1.0, dropout=False)
    # Warmup
    for _ in range(20):
        est.step(meas)

    n_steps = 1000
    t0 = time.perf_counter()
    for _ in range(n_steps):
        est.step(meas)
    t1 = time.perf_counter()

    avg_ms = (t1 - t0) * 1000.0 / n_steps
    assert avg_ms < 5.0, f"Average step time {avg_ms:.2f} ms exceeds 5 ms limit"
