"""Unit tests for the ICA-GPR-EKF estimator."""

import numpy as np
import pytest

pytest.importorskip("sklearn")
from soh.common.contracts import EstimationStatus, FeatureQualityRecord, SOHState, SohEstimate
from soh.data.synthetic_aging import SyntheticAgingGenerator
from soh.estimators.ica_gpr_ekf import IcaGprEkfEstimator


def test_ica_gpr_ekf_fit_and_predict():
    """Verify IcaGprEkfEstimator fits on synthetic cohort and produces valid estimates."""
    generator = SyntheticAgingGenerator(seed=606)
    cohort = generator.generate_cohort(cell_ids=["B1", "B2"], num_cycles=25)

    estimator = IcaGprEkfEstimator()
    assert not estimator.is_fitted

    estimator.fit(cohort)
    assert estimator.is_fitted

    # Predict on unseen cell cycle
    test_cell = generator.generate_battery("B_TEST", num_cycles=10)
    c0 = test_cell.cycles[0]

    est = estimator.predict_cycle(c0)
    assert est.status == EstimationStatus.VALID
    assert est.soh_c is not None and 0.5 < est.soh_c < 1.2
    assert est.variance_c is not None and est.variance_c > 0.0
    assert est.confidence_interval_95_c is not None
    lb, ub = est.confidence_interval_95_c
    assert lb < est.soh_c < ub


def test_ica_gpr_ekf_intermittent_and_gating():
    """Verify EKF handles intermittent observations and outlier innovation gating."""
    estimator = IcaGprEkfEstimator(innovation_gate_threshold=6.635)
    estimator.is_fitted = True

    init_state = SOHState(
        soh_c_bol=0.95,
        soh_c_rated=0.95,
        soh_r_bol=1.0,
        covariance=np.diag([1e-4, 1e-4]),
    )

    # 1. Intermittent update (measurement is missing / invalid)
    missing_est = SohEstimate(
        status=EstimationStatus.INSUFFICIENT_INFORMATION,
        quality=FeatureQualityRecord(is_eligible=False, failure_reasons=["Missing ICA"]),
    )
    # Ah throughput delta = 100 Ah
    step1_state = estimator.update_state(init_state, missing_est, dt_s=100.0, ah_delta=100.0)
    # State should degrade based on throughput transition model, covariance should grow
    assert step1_state.soh_c_bol < init_state.soh_c_bol
    assert step1_state.covariance[0, 0] > init_state.covariance[0, 0]

    # 2. Extreme outlier observation (e.g. SOH_C = 0.20 when true state is ~0.95)
    outlier_est = SohEstimate(
        soh_c=0.20,
        variance_c=1e-4,
        status=EstimationStatus.VALID,
    )
    step2_state = estimator.update_state(step1_state, outlier_est, dt_s=10.0, ah_delta=0.0)
    # Should reject update as outlier, keeping prior state
    assert step2_state.soh_c_bol == pytest.approx(step1_state.soh_c_bol, abs=1e-4)

    # 3. Valid normal observation (SOH_C = 0.94)
    valid_est = SohEstimate(
        soh_c=0.94,
        variance_c=1e-4,
        status=EstimationStatus.VALID,
    )
    step3_state = estimator.update_state(step2_state, valid_est, dt_s=10.0, ah_delta=0.0)
    # Should perform Kalman measurement update, reducing variance
    assert step3_state.soh_c_bol == pytest.approx(0.94, abs=0.02)
    assert step3_state.covariance[0, 0] < step2_state.covariance[0, 0]
