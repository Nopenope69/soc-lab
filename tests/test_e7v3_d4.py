"""Unit tests for Component D4 (Adaptive Covariance Fading) Filter.

Tests:
1. Normal operation with small residuals: D4 timer remains 0
2. Transient high residual (< N seconds): no covariance inflation
3. Persistent high residual (>= N seconds): covariance inflates up to P_max
4. Residual recovery resets timer and stops inflation
5. reset() clears D4 timer and state
6. Per-step runtime < 5 ms
"""

import math
import time
import numpy as np
import pytest

from soc.assumptions.loader import load_assumptions
from soc.estimators.base import ParamSet
from soc.estimators.e7v3_d4 import E7V3D4Filter
from soc.models.plant import Measurement


@pytest.fixture
def params() -> ParamSet:
    assumptions, _, _ = load_assumptions(profile="calce_a123_v4")
    return ParamSet.from_assumptions(assumptions, matched=True)


def test_d4_normal_operation_no_inflation(params):
    """Verify D4 stays inactive when residuals are within normal bounds."""
    est = E7V3D4Filter(params)
    est.reset(0.50, soc_std=0.01)

    # Feed normal measurements matching OCV (~3.28 V at 50% SOC)
    for _ in range(70):
        meas = Measurement(v=3.28, i=0.0, temp_c=25.0, dt=1.0, dropout=False)
        est.step(meas)

    assert est.d4_timer_s == 0.0
    assert not est.d4_fading_active
    assert est.p[0, 0] < 0.001  # Normal process noise variance, no inflation to p_max (0.01)


def test_d4_persistent_residual_triggers_inflation(params):
    """Verify persistent high residual (>= duration_s) inflates P[0,0] up to p_max."""
    from dataclasses import replace
    # Fast test tunings: duration = 5s, k = 2.0, lambda_f = 1.2
    d4_params = replace(params, d4_k=2.0, d4_duration_s=5.0, d4_lambda_f=1.2, d4_p_max=0.01)
    est = E7V3D4Filter(d4_params)
    est.reset(0.50, soc_std=0.005)  # initial p_soc = 2.5e-5

    # Step 1-4: high residual (v = 2.5 V vs OCV ~ 3.28 V) for 4 seconds (< 5s)
    for _ in range(4):
        est.step(Measurement(v=2.5, i=0.0, temp_c=25.0, dt=1.0, dropout=False))
        assert not est.d4_fading_active

    # Step 5+: duration reached (>= 5s), fading activates and inflates P[0,0]
    p_before_inflate = est.p[0, 0]
    for _ in range(10):
        est.step(Measurement(v=2.5, i=0.0, temp_c=25.0, dt=1.0, dropout=False))

    assert est.d4_fading_active
    assert est.p[0, 0] > p_before_inflate
    assert est.p[0, 0] <= d4_params.d4_p_max


def test_d4_residual_recovery_resets_timer(params):
    """Verify that when residual drops below threshold, timer resets to 0."""
    from dataclasses import replace
    d4_params = replace(params, d4_k=2.0, d4_duration_s=5.0)
    est = E7V3D4Filter(d4_params)
    est.reset(0.50, soc_std=0.005)

    # 3 seconds of high residual
    for _ in range(3):
        est.step(Measurement(v=2.5, i=0.0, temp_c=25.0, dt=1.0, dropout=False))
    assert est.d4_timer_s == 3.0

    # Measurement matching the filter's predicted voltage: residual is near 0
    temp_c = 25.0
    r0 = est.r0_table.lookup(est.x[0], temp_c) * est.theta
    r1 = est.r1_table.lookup(est.x[0], temp_c) * est.theta
    r2 = est.r2_table.lookup(est.x[0], temp_c)
    ocv = est.ocv_table.lookup(est.x[0], temp_c)
    m_h = est.get_m_hyst(temp_c)
    v_pred = ocv + m_h * est.x[-1] - r1 * est.x[1] - r2 * est.x[2]

    est.step(Measurement(v=v_pred, i=0.0, temp_c=25.0, dt=1.0, dropout=False))
    assert est.d4_timer_s == 0.0
    assert not est.d4_fading_active


def test_d4_reset_clears_timer(params):
    """Verify reset clears D4 timer and state."""
    est = E7V3D4Filter(params)
    est.reset(0.50)
    for _ in range(10):
        est.step(Measurement(v=2.5, i=0.0, temp_c=25.0, dt=1.0, dropout=False))
    assert est.d4_timer_s > 0.0

    est.reset(0.80)
    assert est.d4_timer_s == 0.0
    assert not est.d4_fading_active


def test_d4_per_step_runtime(params):
    """Verify per-step runtime remains well below 5 ms."""
    est = E7V3D4Filter(params)
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
