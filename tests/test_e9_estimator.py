"""Unit tests for E9 Hybrid TCN + Unscented Kalman Filter (TCN-UKF) Estimator.

Tests:
1. Instantiation and default state
2. Estimator Protocol conformance and isolation
3. reset(soc0, soc_std) behavior
4. Step execution and bounded SOC output in [0, 1]
5. Dropout handling
6. Registry lookup via get_estimator("E9", params)
7. Streaming runtime (< 5 ms per step)
"""

import inspect
import time
from typing import get_type_hints
import numpy as np
import pytest

from soc.assumptions.loader import load_assumptions
from soc.estimators.base import ParamSet, SocEstimate, Estimator
from soc.estimators.e9_tcn_ukf import E9TCNUKFEstimator
from soc.estimators.registry import get_estimator
from soc.models.plant import Measurement


@pytest.fixture
def params() -> ParamSet:
    assumptions, _, _ = load_assumptions(profile="calce_a123_v4")
    return ParamSet.from_assumptions(assumptions, matched=True)


def test_e9_initialisation(params):
    """Verify E9 initializes 2RC tables, UKF sigma weights, and TCN model cleanly."""
    est = E9TCNUKFEstimator(params)
    assert isinstance(est, Estimator)
    assert est.tcn is not None
    assert est.model_loaded is True
    assert est.window_buffer.shape == (5, 32)
    assert est.step_count == 0


def test_e9_isolation(params):
    """Verify E9 conforms strictly to Estimator protocol and argument signature."""
    hints = get_type_hints(E9TCNUKFEstimator.step)
    params_keys = list(inspect.signature(E9TCNUKFEstimator.step).parameters.keys())
    assert params_keys == ["self", "measurement"]
    assert hints.get("measurement") is Measurement
    assert hints.get("return") is SocEstimate


def test_e9_reset(params):
    """Verify reset clears UKF states, covariance, and circular history buffer."""
    est = E9TCNUKFEstimator(params)
    est.reset(0.85, soc_std=0.005)

    assert est.x[0] == pytest.approx(0.85)
    assert est.p[0, 0] == pytest.approx(0.005 ** 2)
    assert est.step_count == 0
    assert np.all(est.window_buffer == 0.0)


def test_e9_step_and_bounds(params):
    """Verify step produces a valid SocEstimate bounded within [0, 1]."""
    est = E9TCNUKFEstimator(params)
    est.reset(0.50)

    for i in range(15):
        meas = Measurement(v=3.28 - 0.01 * i, i=1.5, temp_c=25.0, dt=1.0, dropout=False)
        out = est.step(meas)
        assert isinstance(out, SocEstimate)
        assert 0.0 <= out.soc <= 1.0
        assert out.soc_std >= 0.0


def test_e9_dropout_handling(params):
    """Verify estimator survives missing measurements without NaN or failure."""
    est = E9TCNUKFEstimator(params)
    est.reset(0.60)

    est.step(Measurement(v=3.28, i=2.0, temp_c=25.0, dt=1.0, dropout=False))
    out_drop = est.step(Measurement(v=float("nan"), i=float("nan"), temp_c=float("nan"), dt=1.0, dropout=True))

    assert isinstance(out_drop, SocEstimate)
    assert 0.0 <= out_drop.soc <= 1.0
    assert not np.isnan(out_drop.soc)


def test_e9_registry_lookup(params):
    """Verify E9 is registered in the central estimator registry."""
    for name in ["E9", "e9", "e9_tcn_ukf"]:
        est = get_estimator(name, params)
        assert isinstance(est, E9TCNUKFEstimator)


def test_e9_runtime(params):
    """Verify combined TCN inference + UKF dual-observation step runtime is under 5 ms."""
    est = E9TCNUKFEstimator(params)
    est.reset(0.50)

    meas = Measurement(v=3.28, i=1.5, temp_c=25.0, dt=1.0, dropout=False)
    for _ in range(5):
        est.step(meas)

    t0 = time.perf_counter()
    n_steps = 50
    for _ in range(n_steps):
        est.step(meas)
    elapsed = time.perf_counter() - t0
    ms_per_step = (elapsed / n_steps) * 1000.0

    assert ms_per_step < 5.0, f"Expected < 5.0 ms/step, got {ms_per_step:.3f} ms"
