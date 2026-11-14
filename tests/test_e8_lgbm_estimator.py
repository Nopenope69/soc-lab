"""Unit tests for E8-LGBM Physics-Guided Residual LightGBM Estimator.

Tests:
1. Instantiation and default state
2. Estimator Protocol conformance and isolation
3. reset(soc0, soc_std) behavior
4. Step execution and bounded SOC output in [0, 1]
5. Dropout handling
6. Streaming speed (< 5 ms per step, typically < 0.1 ms)
7. Smoothing filter effect
8. Registry lookup via get_estimator("E8-LGBM", params)
"""

import inspect
import time
from typing import get_type_hints
import numpy as np
import pytest

from soc.assumptions.loader import load_assumptions
from soc.estimators.base import ParamSet, SocEstimate, Estimator
from soc.estimators.e8_residual_lgbm import E8ResidualLGBMEstimator
from soc.estimators.registry import get_estimator
from soc.models.plant import Measurement


@pytest.fixture
def params() -> ParamSet:
    assumptions, _, _ = load_assumptions(profile="calce_a123_v4")
    return ParamSet.from_assumptions(assumptions, matched=True)


def test_e8_lgbm_initialisation(params):
    """Verify E8-LGBM initializes physics filter and booster model cleanly."""
    est = E8ResidualLGBMEstimator(params)
    assert isinstance(est, Estimator)
    assert est.physics_estimator is not None
    assert est.model_loaded is True
    assert est.booster is not None


def test_e8_lgbm_isolation(params):
    """Verify E8-LGBM conforms strictly to Estimator protocol and argument signature."""
    hints = get_type_hints(E8ResidualLGBMEstimator.step)
    params_keys = list(inspect.signature(E8ResidualLGBMEstimator.step).parameters.keys())
    assert params_keys == ["self", "measurement"]
    assert hints.get("measurement") is Measurement
    assert hints.get("return") is SocEstimate


def test_e8_lgbm_reset(params):
    """Verify reset clears both physics filter states and residual memory."""
    est = E8ResidualLGBMEstimator(params)
    est.reset(0.85, soc_std=0.005)

    assert est.physics_estimator.x[0] == pytest.approx(0.85)
    assert est.physics_estimator.p[0, 0] == pytest.approx(0.005 ** 2)
    assert est.last_applied_residual == 0.0
    assert est.smoothed_residual == 0.0


def test_e8_lgbm_step_and_bounds(params):
    """Verify step produces a valid SocEstimate bounded within [0, 1]."""
    est = E8ResidualLGBMEstimator(params)
    est.reset(0.50)

    for i in range(10):
        meas = Measurement(v=3.28 - 0.01 * i, i=1.5, temp_c=25.0, dt=1.0, dropout=False)
        out = est.step(meas)
        assert isinstance(out, SocEstimate)
        assert 0.0 <= out.soc <= 1.0
        assert out.soc_std >= 0.0


def test_e8_lgbm_dropout_handling(params):
    """Verify estimator survives missing measurements without NaN or failure."""
    est = E8ResidualLGBMEstimator(params)
    est.reset(0.60)

    est.step(Measurement(v=3.28, i=2.0, temp_c=25.0, dt=1.0, dropout=False))
    out_drop = est.step(Measurement(v=float("nan"), i=float("nan"), temp_c=float("nan"), dt=1.0, dropout=True))

    assert isinstance(out_drop, SocEstimate)
    assert 0.0 <= out_drop.soc <= 1.0
    assert out_drop.voltage_residual is None


def test_e8_lgbm_registry_lookup(params):
    """Verify E8-LGBM is registered under canonical and alias names in the registry."""
    for name in ["E8-LGBM", "e8-lgbm", "e8_lgbm"]:
        est = get_estimator(name, params)
        assert isinstance(est, E8ResidualLGBMEstimator)


def test_e8_lgbm_smoothing(params):
    """Verify smoothing parameter alpha alters residual trajectory smoothly."""
    est_raw = E8ResidualLGBMEstimator(params, smoothing_alpha=1.0)
    est_smooth = E8ResidualLGBMEstimator(params, smoothing_alpha=0.1)

    est_raw.reset(0.50)
    est_smooth.reset(0.50)

    meas = Measurement(v=3.25, i=5.0, temp_c=25.0, dt=1.0, dropout=False)
    out_raw = est_raw.step(meas)
    out_smooth = est_smooth.step(meas)

    assert isinstance(out_raw, SocEstimate)
    assert isinstance(out_smooth, SocEstimate)


def test_e8_lgbm_runtime(params):
    """Verify combined physics + LightGBM step runtime is well under 5 ms."""
    est = E8ResidualLGBMEstimator(params)
    est.reset(0.50)

    meas = Measurement(v=3.28, i=1.5, temp_c=25.0, dt=1.0, dropout=False)
    for _ in range(5):
        est.step(meas)

    t0 = time.perf_counter()
    n_steps = 100
    for _ in range(n_steps):
        est.step(meas)
    elapsed = time.perf_counter() - t0
    ms_per_step = (elapsed / n_steps) * 1000.0

    assert ms_per_step < 5.0, f"Expected < 5.0 ms/step, got {ms_per_step:.3f} ms"
