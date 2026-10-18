"""Unit tests for E2 with Component C5 Anchoring.

Tests:
1. Initialisation and state bounds
2. Propagation against the cell model
3. Full-charge CV taper anchor trigger
4. Slope-gated rest-OCV recalibration: triggers in knee, blocked on plateau
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
from soc.estimators.e2_anchored import E2AnchoredEstimator
from soc.models.plant import Measurement


@pytest.fixture
def params() -> ParamSet:
    assumptions, _, _ = load_assumptions(profile="calce_a123_v3")
    return ParamSet.from_assumptions(assumptions, matched=True)


def test_e2_anchored_initialisation(params):
    """Verify E2Anchored initializes correctly."""
    est = E2AnchoredEstimator(params)
    est.reset(0.85)

    assert est.x[0] == pytest.approx(0.85)
    assert est.x[1] == 0.0
    assert est.p.shape == (4, 4)
    assert np.all(np.diag(est.p) > 0.0)


def test_e2_anchored_full_charge_trigger(params):
    """Verify full-charge CV taper anchor triggers when V >= 3.6 V and |I| <= 55 mA."""
    est = E2AnchoredEstimator(params)
    est.reset(0.95)

    # Apply 65 seconds of CV taper charge (V=3.60 V, I=-0.02 A)
    for _ in range(65):
        out = est.step(Measurement(v=3.60, i=-0.02, temp_c=25.0, dt=1.0, dropout=False))

    assert out.anchor_used is True
    assert out.soc == pytest.approx(1.0, abs=0.01)


def test_e2_anchored_rest_recalibration_gating(params):
    """Verify rest recalibration is blocked on plateau and allowed in knee."""
    est = E2AnchoredEstimator(params)
    est.reset(0.50)  # Plateau

    # 660s of zero current on the plateau
    for _ in range(11):
        out_plat = est.step(Measurement(v=3.30, i=0.0, temp_c=25.0, dt=60.0, dropout=False))
    # Must NOT trigger rest recalibration on flat plateau
    assert out_plat.anchor_used is False

    # Now reset near knee (0.08) where dOCV/dz > 1.0
    est.reset(0.08)
    for _ in range(11):
        out_knee = est.step(Measurement(v=3.10, i=0.0, temp_c=25.0, dt=60.0, dropout=False))
    # In steep knee, rest recalibration triggers!
    assert out_knee.anchor_used is True


def test_e2_anchored_covariance_symmetry(params):
    """Verify covariance symmetry and positive semidefiniteness."""
    est = E2AnchoredEstimator(params)
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


def test_e2_anchored_dropout(params):
    """Verify dropout skips measurement update."""
    est = E2AnchoredEstimator(params)
    est.reset(0.75)
    est.step(Measurement(v=3.29, i=2.0, temp_c=25.0, dt=1.0, dropout=False))
    soc_prev = est.x[0]

    meas_drop = Measurement(v=float("nan"), i=float("nan"), temp_c=float("nan"), dt=1.0, dropout=True)
    out_drop = est.step(meas_drop)

    assert out_drop.voltage_residual is None
    assert out_drop.soc < soc_prev


def test_e2_anchored_reset(params):
    """Verify reset clears states and anchor timers."""
    est = E2AnchoredEstimator(params)
    est.reset(0.50)
    for _ in range(10):
        est.step(Measurement(v=3.25, i=1.0, temp_c=20.0, dt=1.0, dropout=False))

    est.reset(0.90)
    assert est.x[0] == pytest.approx(0.90)
    assert est.rest_duration_s == 0.0
    assert est.charge_hold_duration_s == 0.0


def test_e2_anchored_runtime(params):
    """Verify per-step runtime is well within 5 ms."""
    est = E2AnchoredEstimator(params)
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
    print(f"\nE2Anchored measured runtime: {ms_per_step:.3f} ms / step")
    assert ms_per_step < 5.0
