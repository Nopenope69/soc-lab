"""Hardening and robustness tests for deliverable/bms_soc_ref.py.

Verifications:
1. Signal validation & range bounds (T in {-30, 85}, V in {0, 5}, I = inf).
2. dt validation (dt <= 0, dt > 60, NaN/Inf dt).
3. NaN temperature handling and recovery.
4. Per-signal dropouts (V missing vs I missing).
5. Current staleness timeout (> 10s).
6. Finite-state guard and STATE_RESET recovery.
7. Bit-identical repeatability on valid synthetic sequences.
"""

import math
import pytest

from deliverable.bms_soc_ref import BmsSocEstimatorRef, SocEstimateRef
from deliverable.calibration import default_calce_calibration


def test_hardening_dt_invalid():
    """Verify non-finite or non-positive dt triggers DT_INVALID and preserves finite state."""
    est = BmsSocEstimatorRef()
    est.reset(0.80, soc_std=0.01)

    # dt <= 0
    res = est.step(v=3.28, i=1.0, temp_c=25.0, dt=-1.0)
    assert "DT_INVALID" in res.status_flags
    assert math.isfinite(res.soc)
    assert math.isfinite(res.soc_std)

    # dt > 60.0
    res = est.step(v=3.28, i=1.0, temp_c=25.0, dt=120.0)
    assert "DT_INVALID" in res.status_flags
    assert math.isfinite(res.soc)

    # NaN dt
    res = est.step(v=3.28, i=1.0, temp_c=25.0, dt=math.nan)
    assert "DT_INVALID" in res.status_flags
    assert math.isfinite(res.soc)


def test_hardening_temperature_invalid_and_out_of_envelope():
    """Verify NaN temperature holds last valid temp; out of envelope temps flag properly."""
    est = BmsSocEstimatorRef()
    est.reset(0.80, soc_std=0.01)

    # Step with normal temp
    res = est.step(v=3.28, i=1.0, temp_c=25.0, dt=1.0)
    assert res.status_flags == ["OK"]

    # Step with NaN temperature
    res_nan = est.step(v=3.28, i=1.0, temp_c=math.nan, dt=1.0)
    assert "TEMP_INVALID" in res_nan.status_flags
    assert math.isfinite(res_nan.soc)

    # Step with extreme sub-zero (-30 C)
    res_cold = est.step(v=3.28, i=1.0, temp_c=-30.0, dt=1.0)
    assert "OUT_OF_ENVELOPE" in res_cold.status_flags
    assert math.isfinite(res_cold.soc)

    # Step with extreme heat (85 C)
    res_hot = est.step(v=3.28, i=1.0, temp_c=85.0, dt=1.0)
    assert "OUT_OF_ENVELOPE" in res_hot.status_flags
    assert math.isfinite(res_hot.soc)

    # Recovery on next normal sample
    res_rec = est.step(v=3.28, i=1.0, temp_c=25.0, dt=1.0)
    assert res_rec.status_flags == ["OK"]


def test_hardening_voltage_out_of_range():
    """Verify extreme voltage signals (0 V, 5 V) flag V_OUT_OF_RANGE and don't destabilize state."""
    est = BmsSocEstimatorRef()
    est.reset(0.80, soc_std=0.01)

    # 0 V (e.g. short circuit / sensor disconnect)
    res_low = est.step(v=0.0, i=1.0, temp_c=25.0, dt=1.0)
    assert "V_OUT_OF_RANGE" in res_low.status_flags
    assert math.isfinite(res_low.soc)
    assert 0.0 <= res_low.soc <= 1.0

    # 5 V (over-voltage spike)
    res_high = est.step(v=5.0, i=1.0, temp_c=25.0, dt=1.0)
    assert "V_OUT_OF_RANGE" in res_high.status_flags
    assert math.isfinite(res_high.soc)
    assert 0.0 <= res_high.soc <= 1.0


def test_hardening_current_inf_and_dropouts():
    """Verify infinite current is treated as dropout, and stale current triggers timeout."""
    est = BmsSocEstimatorRef()
    est.reset(0.80, soc_std=0.01)

    # Normal step to set last_valid_i
    est.step(v=3.28, i=2.0, temp_c=25.0, dt=1.0)

    # i = Inf
    res_inf = est.step(v=3.28, i=math.inf, temp_c=25.0, dt=1.0)
    assert "DROPOUT" in res_inf.status_flags
    assert "STALE_CURRENT" in res_inf.status_flags
    assert math.isfinite(res_inf.soc)

    # Current missing for 12 seconds (> 10s timeout)
    for _ in range(12):
        res = est.step(v=3.28, i=math.nan, temp_c=25.0, dt=1.0)
        assert "STALE_CURRENT" in res.status_flags

    # State should remain completely finite
    assert math.isfinite(est.x[0])
    assert math.isfinite(est.p[0][0])


def test_hardening_voltage_dropout_pure_time_update():
    """Verify voltage dropout continues Coulomb counting time propagation with real current."""
    est = BmsSocEstimatorRef()
    est.reset(0.80, soc_std=0.01)

    soc_start = est.x[0]
    # 5 steps of 10 A discharge with voltage missing
    for _ in range(5):
        res = est.step(v=math.nan, i=10.0, temp_c=25.0, dt=1.0)
        assert "DROPOUT" in res.status_flags

    soc_end = est.x[0]
    # Pure discharge must have lowered SOC
    assert soc_end < soc_start


def test_finite_state_guard_and_state_reset():
    """Verify finite-state guard catches corrupted state/covariance and rolls back."""
    est = BmsSocEstimatorRef()
    est.reset(0.80, soc_std=0.01)
    res_good = est.step(v=3.28, i=1.0, temp_c=25.0, dt=1.0)
    assert res_good.status_flags == ["OK"]

    # Deliberately corrupt state vector with NaN
    est.x[1] = math.nan
    res_corrupt = est.step(v=3.28, i=1.0, temp_c=25.0, dt=1.0)
    assert "STATE_RESET" in res_corrupt.status_flags
    assert math.isfinite(est.x[0])
    assert math.isfinite(est.x[1])


def test_repeatability_on_synthetic_sequence():
    """Verify bit-identical output across two independent runs on identical synthetic sequence."""
    est1 = BmsSocEstimatorRef()
    est2 = BmsSocEstimatorRef()

    est1.reset(0.75, soc_std=0.005)
    est2.reset(0.75, soc_std=0.005)

    for k in range(100):
        v = 3.25 + 0.05 * math.sin(k * 0.1)
        i = 1.5 * math.cos(k * 0.05)
        t = 25.0 + 2.0 * math.sin(k * 0.01)
        dt = 0.5 + 0.1 * math.cos(k)

        out1 = est1.step(v=v, i=i, temp_c=t, dt=dt)
        out2 = est2.step(v=v, i=i, temp_c=t, dt=dt)

        assert out1.soc == out2.soc
        assert out1.soc_std == out2.soc_std
        assert out1.theta == out2.theta
        assert out1.status_flags == out2.status_flags
