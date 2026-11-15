"""Unit tests for multi-estimator fusion layer (Phase 4).

Covers:
1. Positive-semidefinite enforcement & matrix numerical stability.
2. Scalar and Vector Covariance Intersection.
3. Chi-squared innovation gating and outlier rejection.
4. DualSohFusionTracker under simultaneous, asynchronous, and dropped updates.
5. Numerical stability over extended cycling.
"""

import numpy as np
import pytest

from soh.common.contracts import (
    CycleRecord,
    EstimationStatus,
    FeatureQualityRecord,
    SohEstimate,
)
from soh.fusion.covariance import (
    covariance_intersection_scalar,
    covariance_intersection_vector,
    enforce_positive_semidefinite,
)
from soh.fusion.gating import InnovationGater
from soh.fusion.tracker import DualSohFusionTracker, FusionConfig


def test_positive_semidefinite_enforcement():
    # Matrix with negative eigenvalue and asymmetry
    bad_mat = np.array([[1.0, 2.5], [1.5, -0.5]])
    psd_mat = enforce_positive_semidefinite(bad_mat, min_eigenval=1e-6)

    # Must be symmetric
    assert np.allclose(psd_mat, psd_mat.T)
    # Eigenvalues must be >= 1e-6
    eigvals = np.linalg.eigvalsh(psd_mat)
    assert np.all(eigvals >= 1e-6)


def test_covariance_intersection_scalar():
    val1, var1 = 0.95, 1e-4
    val2, var2 = 0.90, 4e-4

    # 1. Balanced objective
    fused_val, fused_var, omega = covariance_intersection_scalar(
        val1, var1, val2, var2, objective="balanced"
    )
    assert 0.0 <= omega <= 1.0
    assert min(val1, val2) <= fused_val <= max(val1, val2)
    assert min(var1, var2) <= fused_var <= max(var1, var2)

    # 2. Min-trace objective (selects smaller variance)
    fused_val_mt, fused_var_mt, omega_mt = covariance_intersection_scalar(
        val1, var1, val2, var2, objective="min_trace"
    )
    assert omega_mt == 1.0
    assert fused_var_mt == var1
    assert fused_val_mt == val1

    # 3. Explicit omega
    fused_val_eq, fused_var_eq, omega_eq = covariance_intersection_scalar(
        val1, var1, val2, var2, omega=0.5
    )
    assert omega_eq == 0.5
    expected_var = 1.0 / (0.5 / var1 + 0.5 / var2)
    assert np.isclose(fused_var_eq, expected_var)


def test_covariance_intersection_closed_form_references():
    """Validate scalar and vector CI against exact analytical literature references."""
    # 1. Scalar CI with equal variances (Julier & Uhlmann 1997)
    val1, val2 = 10.0, 20.0
    var = 2.0
    f_val, f_var, omega = covariance_intersection_scalar(val1, var, val2, var, objective="balanced")
    assert omega == pytest.approx(0.5)
    assert f_var == pytest.approx(var)
    assert f_val == pytest.approx(15.0)

    # 2. Vector CI benchmark (Niehsen 2002 standard test case)
    x1 = np.array([1.0, 2.0])
    p1 = np.array([[2.0, 0.5], [0.5, 1.0]])
    x2 = np.array([1.5, 1.8])
    p2 = np.array([[1.0, -0.5], [-0.5, 2.0]])

    det_p1 = np.linalg.det(p1)  # 2.0*1.0 - 0.25 = 1.75
    det_p2 = np.linalg.det(p2)  # 2.0 - 0.25 = 1.75
    assert det_p1 == pytest.approx(1.75)

    f_x, f_p, w_opt = covariance_intersection_vector(x1, p1, x2, p2, objective="det")
    # Due to symmetry, optimal weight is exactly 0.5
    assert w_opt == pytest.approx(0.5, abs=1e-2)
    # Fused determinant should be strictly bounded
    assert np.linalg.det(f_p) <= max(det_p1, det_p2)
    assert np.all(np.linalg.eigvalsh(f_p) > 0)


def test_cross_covariance_propagation_under_scalar_ica():
    """Verify that scalar SOH_C observation correctly updates SOH_R via cross-covariance."""
    config = FusionConfig(
        initial_var_c=1e-4,
        initial_var_r=1e-4,
        initial_cov_cr=0.5e-4,  # Positive correlation: capacity fade accompanied by resistance growth
    )
    tracker = DualSohFusionTracker(config=config)
    tracker.reset(initial_soh_c=1.0, initial_soh_r=1.0)
    assert tracker.P[0, 1] == pytest.approx(0.5e-4)

    # Arrival of scalar ICA observation indicating capacity degradation (soh_c = 0.90)
    c1 = _create_mock_cycle(1, 4.0)
    est_ica = SohEstimate(
        soh_c=0.90,
        variance_c=1e-4,
        status=EstimationStatus.VALID,
        quality=FeatureQualityRecord(is_eligible=True),
    )

    state, log = tracker.update_cycle(c1, est_ica=est_ica, est_pulse=None)
    # SOH_C is pulled down
    assert state.soh_c_bol < 1.0
    # SOH_R must also be pulled down via cross-covariance (K_R = P_RC / S > 0)
    assert state.soh_r_bol < 1.0
    # Cross-covariance must be preserved in posterior P
    assert tracker.P[0, 1] > 0


def test_covariance_intersection_vector():
    x1 = np.array([0.95, 0.92])
    p1 = np.diag([1e-4, 2e-4])
    x2 = np.array([0.94, 0.93])
    p2 = np.diag([2e-4, 1e-4])

    fused_x, fused_p, omega = covariance_intersection_vector(x1, p1, x2, p2, objective="det")
    assert 0.0 <= omega <= 1.0
    assert fused_x.shape == (2,)
    assert fused_p.shape == (2, 2)

    # Must be symmetric and positive definite
    assert np.allclose(fused_p, fused_p.T)
    eigvals = np.linalg.eigvalsh(fused_p)
    assert np.all(eigvals > 0)


def test_innovation_gater_acceptance_and_rejection():
    gater = InnovationGater(significance_level=0.01)

    x_prior = np.array([0.95, 0.95])
    P_prior = np.diag([1e-4, 1e-4])
    H = np.eye(2)
    R = np.diag([1e-4, 1e-4])

    # 1. Normal observation close to prior
    z_good = np.array([0.948, 0.952])
    res_good = gater.evaluate(z_good, H, x_prior, P_prior, R)
    assert res_good.is_accepted
    assert res_good.mahalanobis_dist_sq < res_good.threshold

    # 2. Extreme sensor glitch / outlier
    z_bad = np.array([0.50, 0.95])  # Massive drop on SOH_C
    res_bad = gater.evaluate(z_bad, H, x_prior, P_prior, R)
    assert not res_bad.is_accepted
    assert res_bad.mahalanobis_dist_sq > res_bad.threshold
    assert "Innovation outlier" in (res_bad.rejection_reason or "")


def _create_mock_cycle(cycle_index: int, ah_throughput: float) -> CycleRecord:
    t = np.linspace(0.0, 100.0, 50)
    return CycleRecord(
        cycle_index=cycle_index,
        time_s=t,
        voltage_v=np.full(50, 3.3),
        current_a=np.full(50, -1.0),
        temp_c=np.full(50, 25.0),
        ah_throughput=ah_throughput,
    )


def test_dual_fusion_tracker_simultaneous_ica_and_pulse():
    config = FusionConfig(ci_objective="balanced")
    tracker = DualSohFusionTracker(config=config)
    tracker.reset(initial_soh_c=1.0, initial_soh_r=1.0)

    cycle = _create_mock_cycle(cycle_index=1, ah_throughput=4.6)
    est_ica = SohEstimate(
        soh_c=0.98,
        variance_c=2e-4,
        status=EstimationStatus.VALID,
        quality=FeatureQualityRecord(is_eligible=True),
    )
    est_pulse = SohEstimate(
        soh_c=0.97,
        soh_r=0.96,
        variance_c=3e-4,
        variance_r=2e-4,
        status=EstimationStatus.VALID,
        quality=FeatureQualityRecord(is_eligible=True),
    )

    state, log = tracker.update_cycle(cycle, est_ica=est_ica, est_pulse=est_pulse)

    # Check that fusion occurred
    assert log.ci_weight_omega is not None
    assert 0.0 < log.ci_weight_omega < 1.0
    assert "ICA_CI" in log.updated_sources
    assert "PULSE_CI_R" in log.updated_sources

    # Posterior should be updated (pulled toward measurement from 1.0 by Kalman gain)
    assert 0.97 <= state.soh_c_bol < 1.0
    assert 0.96 <= state.soh_r_bol < 1.0
    # Uncertainty should decrease
    assert state.covariance[0, 0] < config.initial_var_c


def test_dual_fusion_tracker_asynchronous_updates():
    tracker = DualSohFusionTracker()
    tracker.reset(initial_soh_c=1.0, initial_soh_r=1.0)

    # Cycle 1: Only ICA available
    c1 = _create_mock_cycle(1, 4.0)
    est_ica = SohEstimate(
        soh_c=0.985,
        variance_c=1e-4,
        status=EstimationStatus.VALID,
        quality=FeatureQualityRecord(is_eligible=True),
    )
    s1, log1 = tracker.update_cycle(c1, est_ica=est_ica, est_pulse=None)
    assert log1.updated_sources == ["ICA"]
    assert np.isclose(s1.soh_c_bol, 0.985, atol=0.01)

    # Cycle 2: Only Pulse available (Resistance update only)
    c2 = _create_mock_cycle(2, 8.0)
    est_pulse_r = SohEstimate(
        soh_r=0.975,
        variance_r=1.5e-4,
        status=EstimationStatus.VALID,
        quality=FeatureQualityRecord(is_eligible=True),
    )
    s2, log2 = tracker.update_cycle(c2, est_ica=None, est_pulse=est_pulse_r)
    assert log2.updated_sources == ["PULSE_R"]
    # State pulled toward measurement from prior 1.0
    assert 0.98 <= s2.soh_r_bol < 1.0
    assert s2.covariance[1, 1] < tracker.config.initial_var_r


def test_dual_fusion_tracker_intermittent_dropouts_propagation():
    tracker = DualSohFusionTracker()
    tracker.reset(initial_soh_c=1.0, initial_soh_r=1.0)

    init_var_c = tracker.P[0, 0]

    # Run 5 cycles where all estimators drop out
    for k in range(1, 6):
        ck = _create_mock_cycle(k, float(k * 4.0))
        dropped_est = SohEstimate(
            status=EstimationStatus.INSUFFICIENT_INFORMATION,
            quality=FeatureQualityRecord(is_eligible=False, failure_reasons=["Sensor timeout"]),
        )
        sk, logk = tracker.update_cycle(ck, est_ica=dropped_est, est_pulse=dropped_est)
        assert len(logk.updated_sources) == 0

    # SOH_C must have degraded due to throughput
    assert sk.soh_c_bol < 1.0
    # Uncertainty must have grown due to process noise
    assert sk.covariance[0, 0] > init_var_c


def test_dual_fusion_tracker_outlier_rejection():
    tracker = DualSohFusionTracker()
    tracker.reset(initial_soh_c=0.98, initial_soh_r=0.98)

    c1 = _create_mock_cycle(1, 4.0)
    # Huge anomalous drop in SOH_C
    bad_ica = SohEstimate(
        soh_c=0.40,
        variance_c=1e-5,
        status=EstimationStatus.VALID,
        quality=FeatureQualityRecord(is_eligible=True),
    )

    s1, log1 = tracker.update_cycle(c1, est_ica=bad_ica)
    # Should be rejected
    assert log1.gating_result is not None
    assert not log1.gating_result.is_accepted
    assert len(log1.updated_sources) == 0
    # State must NOT be corrupted to 0.40
    assert s1.soh_c_bol > 0.95


def test_dual_fusion_tracker_staleness_and_out_of_order():
    tracker = DualSohFusionTracker()
    tracker.reset(initial_soh_c=1.0, initial_soh_r=1.0)

    # Process cycle 5
    c5 = _create_mock_cycle(5, 20.0)
    tracker.update_cycle(c5)

    # Stale cycle 2 arrives out-of-order
    c2 = _create_mock_cycle(2, 8.0)
    est_ica = SohEstimate(
        soh_c=0.99,
        variance_c=1e-4,
        status=EstimationStatus.VALID,
        quality=FeatureQualityRecord(is_eligible=True),
    )
    s_stale, log_stale = tracker.update_cycle(c2, est_ica=est_ica)
    assert any("Out-of-order" in r for r in log_stale.rejection_reasons)
    assert tracker.current_cycle_index == 5


def test_numerical_stability_over_200_steps():
    tracker = DualSohFusionTracker()
    tracker.reset(initial_soh_c=1.0, initial_soh_r=1.0)
    rng = np.random.default_rng(1234)

    for k in range(1, 201):
        ah = float(k * 4.6)
        c = _create_mock_cycle(k, ah)

        # Alternating random noise and availability
        has_ica = rng.random() > 0.3
        has_pulse = rng.random() > 0.3

        ica_est = None
        pulse_est = None

        true_c = max(0.60, 1.0 - 1.5e-5 * ah)
        true_r = max(0.60, 1.0 - 2.0e-5 * ah)

        if has_ica:
            ica_est = SohEstimate(
                soh_c=true_c + float(rng.normal(0, 0.005)),
                variance_c=float(rng.uniform(1e-4, 5e-4)),
                status=EstimationStatus.VALID,
                quality=FeatureQualityRecord(is_eligible=True),
            )

        if has_pulse:
            pulse_est = SohEstimate(
                soh_c=true_c + float(rng.normal(0, 0.006)),
                soh_r=true_r + float(rng.normal(0, 0.006)),
                variance_c=float(rng.uniform(1e-4, 5e-4)),
                variance_r=float(rng.uniform(1e-4, 5e-4)),
                status=EstimationStatus.VALID,
                quality=FeatureQualityRecord(is_eligible=True),
            )

        state, log = tracker.update_cycle(c, est_ica=ica_est, est_pulse=pulse_est)

        # Check positive-definiteness on every single step
        eigvals = np.linalg.eigvalsh(state.covariance)
        assert np.all(eigvals >= 1e-8)
        assert not np.isnan(state.soh_c_bol)
        assert not np.isnan(state.soh_r_bol)
        assert 0.05 <= state.soh_c_bol <= 1.20
        assert 0.05 <= state.soh_r_bol <= 1.20
