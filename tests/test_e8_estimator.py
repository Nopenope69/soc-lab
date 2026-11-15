"""Unit tests for E8 Physics-Guided Residual GRU Estimator.

Tests:
1. Instantiation and default state
2. Estimator Protocol conformance and isolation
3. reset(soc0, soc_std) behavior
4. Step execution and bounded SOC output in [0, 1]
5. Dropout handling
6. Streaming speed (< 5 ms per step)
7. Registry lookup via get_estimator("E8", params)
"""

import inspect
import time
from typing import get_type_hints
import numpy as np
import pytest
torch = pytest.importorskip("torch")

from soc.assumptions.loader import load_assumptions
from soc.estimators.base import ParamSet, SocEstimate, Estimator
from soc.estimators.e8_residual_gru import E8ResidualGRUEstimator
from soc.estimators.registry import get_estimator
from soc.models.plant import Measurement


@pytest.fixture
def params() -> ParamSet:
    assumptions, _, _ = load_assumptions(profile="calce_a123_v4")
    return ParamSet.from_assumptions(assumptions, matched=True)


def test_e8_initialisation(params):
    """Verify E8 initializes physics filter and neural model cleanly."""
    est = E8ResidualGRUEstimator(params)
    assert isinstance(est, Estimator)
    assert est.physics_estimator is not None
    assert est.gru_model is not None
    assert est.gru_h is None


def test_e8_isolation(params):
    """Verify E8 conforms strictly to Estimator protocol and argument signature."""
    hints = get_type_hints(E8ResidualGRUEstimator.step)
    params_keys = list(inspect.signature(E8ResidualGRUEstimator.step).parameters.keys())
    assert params_keys == ["self", "measurement"]
    assert hints.get("measurement") is Measurement
    assert hints.get("return") is SocEstimate


def test_e8_reset(params):
    """Verify reset clears both physics filter states and neural hidden states."""
    est = E8ResidualGRUEstimator(params)
    est.reset(0.85, soc_std=0.005)

    assert est.physics_estimator.x[0] == pytest.approx(0.85)
    assert est.physics_estimator.p[0, 0] == pytest.approx(0.005 ** 2)
    assert est.gru_h is None
    assert est.last_applied_residual == 0.0


def test_e8_step_and_bounds(params):
    """Verify step produces a valid SocEstimate bounded within [0, 1]."""
    est = E8ResidualGRUEstimator(params)
    est.reset(0.50)

    for i in range(10):
        meas = Measurement(v=3.28 - 0.01 * i, i=1.5, temp_c=25.0, dt=1.0, dropout=False)
        out = est.step(meas)
        assert isinstance(out, SocEstimate)
        assert 0.0 <= out.soc <= 1.0
        assert out.soc_std >= 0.0


def test_e8_dropout_handling(params):
    """Verify estimator survives missing measurements without NaN or failure."""
    est = E8ResidualGRUEstimator(params)
    est.reset(0.60)

    est.step(Measurement(v=3.28, i=2.0, temp_c=25.0, dt=1.0, dropout=False))
    out_drop = est.step(Measurement(v=float("nan"), i=float("nan"), temp_c=float("nan"), dt=1.0, dropout=True))

    assert isinstance(out_drop, SocEstimate)
    assert 0.0 <= out_drop.soc <= 1.0
    assert out_drop.voltage_residual is None


def test_e8_registry_lookup(params):
    """Verify E8 is registered in the central estimator registry."""
    est = get_estimator("E8", params)
    assert isinstance(est, E8ResidualGRUEstimator)


def test_e8_runtime(params):
    """Verify combined physics + neural step runtime is well under 5 ms."""
    est = E8ResidualGRUEstimator(params)
    est.reset(0.50)

    meas = Measurement(v=3.28, i=1.5, temp_c=25.0, dt=1.0, dropout=False)
    # Warmup
    for _ in range(10):
        est.step(meas)

    n_steps = 200
    t0 = time.perf_counter()
    for _ in range(n_steps):
        est.step(meas)
    t1 = time.perf_counter()

    avg_ms = (t1 - t0) * 1000.0 / n_steps
    assert avg_ms < 5.0, f"Average step time {avg_ms:.2f} ms exceeds 5 ms limit"
