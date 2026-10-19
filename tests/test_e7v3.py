"""Unit tests for E7v3 Confidence-Aware Composite Estimator.

Tests:
1. Initialisation and state bounds
2. reset(soc0, soc_std) confidence scaling
3. Temperature-scheduled Q(T) and M(T) lookups
4. Propagation against cell model using Q(T)
5. RLS updates on discrete current steps |dI| >= 1 A
6. Observability gating and plateau step capping
7. Covariance symmetry and positive-definiteness
8. Dropout handling
9. Estimator isolation check
10. Per-step runtime (< 5 ms)
"""

import inspect
import math
import time
from typing import get_type_hints
import numpy as np
import pytest

from soc.assumptions.loader import load_assumptions
from soc.estimators.base import ParamSet, SocEstimate
from soc.estimators.e7v3 import E7V3CompositeFilter
from soc.models.plant import Measurement


@pytest.fixture
def params() -> ParamSet:
    assumptions, _, _ = load_assumptions(profile="calce_a123_v4")
    return ParamSet.from_assumptions(assumptions, matched=True)


def test_e7v3_initialisation_and_confidence_reset(params):
    """Verify E7v3 initializes states, covariance, and scales initial P_soc on soc_std."""
    est = E7V3CompositeFilter(params)

    # 1. Default reset (soc_std=None)
    est.reset(0.85)
    assert est.x[0] == pytest.approx(0.85)
    assert est.x[1] == 0.0
    assert est.x[2] == 0.0
    assert est.x[3] == 0.0
    assert est.theta == 1.0
    assert est.p[0, 0] == pytest.approx(params.initial_soc_std ** 2)

    # 2. Tight confidence reset (e.g. S-A / S-C known start: soc_std = 0.005)
    est.reset(0.80, soc_std=0.005)
    assert est.x[0] == pytest.approx(0.80)
    assert est.p[0, 0] == pytest.approx(0.005 ** 2)

    # 3. High uncertainty reset (e.g. S-B unknown start: soc_std = 0.10)
    est.reset(0.60, soc_std=0.10)
    assert est.x[0] == pytest.approx(0.60)
    assert est.p[0, 0] == pytest.approx(0.10 ** 2)


def test_e7v3_temperature_scheduled_q_and_m(params):
    """Verify Q(T) and M(T) lookup tables interpolate and clamp properly."""
    est = E7V3CompositeFilter(params)

    # Exact calibration points for A1-007
    assert est.get_capacity_ah(20.0) == pytest.approx(1.065214687790664, rel=1e-5)
    assert est.get_capacity_ah(25.0) == pytest.approx(1.0635616695823449, rel=1e-5)
    assert est.get_capacity_ah(30.0) == pytest.approx(1.0730061548855323, rel=1e-5)
    assert est.get_capacity_ah(40.0) == pytest.approx(1.0801900610401025, rel=1e-5)
    assert est.get_capacity_ah(50.0) == pytest.approx(1.0809567995408316, rel=1e-5)

    assert est.get_m_hyst(20.0) == pytest.approx(0.02701, rel=1e-4)
    assert est.get_m_hyst(25.0) == pytest.approx(0.01719, rel=1e-4)
    assert est.get_m_hyst(30.0) == pytest.approx(0.02436, rel=1e-4)
    assert est.get_m_hyst(40.0) == pytest.approx(0.02155, rel=1e-4)
    assert est.get_m_hyst(50.0) == pytest.approx(0.01988, rel=1e-4)

    # Clamping outside [20, 50]
    assert est.get_capacity_ah(10.0) == pytest.approx(est.get_capacity_ah(20.0))
    assert est.get_capacity_ah(60.0) == pytest.approx(est.get_capacity_ah(50.0))
    assert est.get_m_hyst(10.0) == pytest.approx(est.get_m_hyst(20.0))
    assert est.get_m_hyst(60.0) == pytest.approx(est.get_m_hyst(50.0))

    # Interpolation mid-range (35 C)
    q_35 = est.get_capacity_ah(35.0)
    assert est.get_capacity_ah(30.0) < q_35 < est.get_capacity_ah(40.0)


def test_e7v3_rls_updates_on_current_steps(params):
    """Verify theta updates when |dI| >= 1 A and stays static when |dI| < 1 A."""
    est = E7V3CompositeFilter(params)
    est.reset(0.80)

    # Small step: dI = 0.3 A -> no RLS update
    est.step(Measurement(v=3.28, i=0.5, temp_c=25.0, dt=1.0, dropout=False))
    th0 = est.theta
    est.step(Measurement(v=3.27, i=0.8, temp_c=25.0, dt=1.0, dropout=False))
    assert est.theta == th0

    # Large step: dI = 2.7 A >= 1.0 A -> RLS updates
    est.step(Measurement(v=2.95, i=3.5, temp_c=25.0, dt=1.0, dropout=False))
    assert est.theta != th0
    assert 0.5 <= est.theta <= 2.0


def test_e7v3_observability_and_plateau_capping(params):
    """Verify observability gating attenuates gain on flat slope and plateau step is capped."""
    est = E7V3CompositeFilter(params)
    est.reset(0.50)  # Flat plateau

    out = est.step(Measurement(v=2.5, i=0.0, temp_c=25.0, dt=1.0, dropout=False))
    delta_applied = abs(est.last_applied_delta_soc)

    assert delta_applied <= 0.01
    assert out.soc < 0.50


def test_e7v3_covariance_properties(params):
    """Verify P matrix remains symmetric and positive-definite after updates."""
    est = E7V3CompositeFilter(params)
    est.reset(0.70, soc_std=0.02)

    for i in range(10):
        meas = Measurement(v=3.25 + 0.01 * (i % 3), i=1.5 * (i % 2), temp_c=25.0, dt=1.0, dropout=False)
        est.step(meas)
        assert np.allclose(est.p, est.p.T, atol=1e-10)
        eigvals = np.linalg.eigvalsh(est.p)
        assert np.all(eigvals > 0.0)


def test_e7v3_dropout_handling(params):
    """Verify estimator handles dropout smoothly."""
    est = E7V3CompositeFilter(params)
    est.reset(0.60)

    est.step(Measurement(v=3.28, i=2.0, temp_c=25.0, dt=1.0, dropout=False))
    th_before = est.theta

    out_drop = est.step(Measurement(v=float("nan"), i=float("nan"), temp_c=float("nan"), dt=1.0, dropout=True))
    assert est.theta == th_before
    assert out_drop.voltage_residual is None
    assert 0.0 <= out_drop.soc <= 1.0


def test_e7v3_estimator_isolation(params):
    """Verify E7v3 adheres strictly to isolation rules."""
    hints = get_type_hints(E7V3CompositeFilter.step)
    params_keys = list(inspect.signature(E7V3CompositeFilter.step).parameters.keys())
    assert params_keys == ["self", "measurement"]
    assert hints.get("measurement") is Measurement
    assert hints.get("return") is SocEstimate

    init_params = list(inspect.signature(E7V3CompositeFilter.__init__).parameters.keys())
    assert init_params == ["self", "params"]


def test_e7v3_per_step_runtime(params):
    """Verify per-step execution time is well under the 5 ms limit."""
    est = E7V3CompositeFilter(params)
    est.reset(0.50)

    meas = Measurement(v=3.28, i=1.5, temp_c=25.0, dt=1.0, dropout=False)
    for _ in range(20):
        est.step(meas)

    n_steps = 1000
    t0 = time.perf_counter()
    for _ in range(n_steps):
        est.step(meas)
    t1 = time.perf_counter()

    avg_ms = (t1 - t0) * 1000.0 / n_steps
    assert avg_ms < 5.0, f"Average step time {avg_ms:.2f} ms exceeds 5 ms limit"
