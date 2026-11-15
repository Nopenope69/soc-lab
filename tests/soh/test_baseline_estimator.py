"""Unit tests for the baseline Ridge estimator."""

import numpy as np
import pytest

from soh.common.contracts import EstimationStatus, PartialWindow
from soh.data.synthetic_aging import SyntheticAgingGenerator
from soh.estimators.baseline_ridge import BaselineRidgeEstimator


def test_baseline_ridge_fit_and_predict():
    """Verify BaselineRidgeEstimator fits on synthetic cohort and produces valid estimates."""
    generator = SyntheticAgingGenerator(seed=101)
    train_cohort = generator.generate_cohort(cell_ids=["B1", "B2"], num_cycles=25)

    estimator = BaselineRidgeEstimator(alpha_c=1.0, alpha_r=1.0)
    assert not estimator.is_fitted

    estimator.fit(train_cohort)
    assert estimator.is_fitted

    # Test prediction on a valid window from an unseen cell
    test_cell = generator.generate_battery("B_TEST", num_cycles=10)
    c0 = test_cell.cycles[0]
    windows = estimator.extractor.extract_windows_from_cycle(c0)
    assert len(windows) > 0

    valid_win = [w for w, el in windows if el][0]
    est = estimator.predict_window(valid_win)

    assert est.status == EstimationStatus.VALID
    assert est.soh_c is not None and 0.5 < est.soh_c < 1.2
    assert est.soh_r is not None and 0.5 < est.soh_r < 1.5
    assert est.variance_c is not None and est.variance_c > 0.0
    assert est.confidence_interval_95_c is not None
    lower, upper = est.confidence_interval_95_c
    assert lower < est.soh_c < upper


def test_baseline_ridge_ineligible_window_rejection():
    """Verify ineligible window returns INSUFFICIENT_INFORMATION without prediction."""
    estimator = BaselineRidgeEstimator()
    # Mock fitted parameters
    estimator.is_fitted = True

    # Too short window
    short_win = PartialWindow(
        window_id="short",
        cycle_index=1,
        time_s=np.array([0.0, 5.0]),
        voltage_v=np.array([3.2, 3.205]),
        current_a=np.array([-1.0, -1.0]),
        temp_c=np.array([25.0, 25.0]),
        delta_v=0.005,
        delta_soc=0.001,
        duration_s=5.0,
        ah_charged=0.001,
        is_charging=True,
        is_discharging=False,
        dropout_fraction=0.0,
    )

    est = estimator.predict_window(short_win)
    assert est.status == EstimationStatus.INSUFFICIENT_INFORMATION
    assert est.soh_c is None
    assert not est.quality.is_eligible
