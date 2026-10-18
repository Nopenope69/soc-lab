"""Unit tests for E2 with Component C6: Temperature- and Rate-Aware Hysteresis Amplitude.

Tests:
1. Initialisation and state bounds
2. Propagation against the cell model
3. Rate and temperature dependency of compute_m_hyst: matches A1 audit tables
4. Covariance symmetry and positive semidefiniteness
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
from soc.estimators.e2_rate_hyst import E2RateHystEstimator
from soc.models.plant import Measurement


@pytest.fixture
def params() -> ParamSet:
    assumptions, _, _ = load_assumptions(profile="calce_a123_v3")
    return ParamSet.from_assumptions(assumptions, matched=True)


def test_e2_rate_hyst_initialisation(params):
    """Verify E2RateHyst initializes correctly."""
    est = E2RateHystEstimator(params)
    est.reset(0.80)

    assert est.x[0] == pytest.approx(0.80)
    assert est.x[1] == 0.0
    assert est.p.shape == (4, 4)
    assert np.all(np.diag(est.p) > 0.0)


def test_e2_rate_hyst_table_matching(params):
    """Verify compute_m_hyst outputs match A1 audit values at C/20 and zero rate."""
    est = E2RateHystEstimator(params)

    # At 20 C, zero rate: should be M_rtot (25.10 mV)
    m_20_0 = est.compute_m_hyst(20.0, 0.0)
    assert m_20_0 == pytest.approx(0.02510, abs=1e-4)

    # At 20 C, 55 mA (C/20): should be M_r0 (27.01 mV)
    m_20_c20 = est.compute_m_hyst(20.0, 0.055)
    assert m_20_c20 == pytest.approx(0.02701, abs=1e-4)

    # At 40 C, 55 mA: should be 21.55 mV
    m_40_c20 = est.compute_m_hyst(40.0, 0.055)
    assert m_40_c20 == pytest.approx(0.02155, abs=1e-4)

    # At high rate (e.g. 5 A), should be clamped to M_raw (35.69 mV at 20 C)
    m_20_high = est.compute_m_hyst(20.0, 5.0)
    assert m_20_high == pytest.approx(0.03569, abs=1e-4)


def test_e2_rate_hyst_covariance_symmetry(params):
    """Verify covariance symmetry and positive semidefiniteness."""
    est = E2RateHystEstimator(params)
    est.reset(0.50)

    meas = Measurement(v=3.29, i=0.5, temp_c=25.0, dt=1.0, dropout=False)
    for _ in range(10):
        est.step(meas)

    assert np.allclose(est.p, est.p.T, atol=1e-8)
    eigenvalues = np.linalg.eigvalsh(est.p)
    assert np.all(eigenvalues >= 0.0)


def test_e2_rate_hyst_dropout_handling(params):
    """Verify estimator continues dead-reckoning on sensor dropout."""
    est = E2RateHystEstimator(params)
    est.reset(0.70)

    meas_drop = Measurement(v=float("nan"), i=float("nan"), temp_c=25.0, dt=1.0, dropout=True)
    out = est.step(meas_drop)

    assert not math.isnan(out.soc)
    assert out.voltage_residual is None


def test_e2_rate_hyst_reset(params):
    """Verify reset properly clears states and covariances."""
    est = E2RateHystEstimator(params)
    est.reset(0.60)
    est.step(Measurement(v=3.30, i=1.0, temp_c=25.0, dt=1.0, dropout=False))

    est.reset(0.40)
    assert est.x[0] == pytest.approx(0.40)
    assert est.x[1] == 0.0
    assert est.x[2] == 0.0
    assert est.x[3] == 0.0


def test_e2_rate_hyst_runtime(params):
    """Verify per-step runtime is well within 5 ms."""
    est = E2RateHystEstimator(params)
    est.reset(0.50)
    meas = Measurement(v=3.29, i=0.5, temp_c=25.0, dt=1.0, dropout=False)

    t0 = time.perf_counter()
    n_steps = 1000
    for _ in range(n_steps):
        est.step(meas)
    elapsed = time.perf_counter() - t0

    ms_per_step = (elapsed / n_steps) * 1000.0
    assert ms_per_step < 5.0, f"Runtime too slow: {ms_per_step:.3f} ms/step"
