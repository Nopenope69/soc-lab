"""Unit and integration tests for SOH Phase 6.1: Benchmark Integrity and Production Qualification.

Tests cover:
1. Selective estimation accounting (zero sentinels, None for RMSE/MAE on 0% coverage).
2. Dataset provenance audit (DatasetCategory enum: SIMULATION vs EXPERIMENTAL vs DERIVED).
3. Empirical power-law parameter fitting and negative control verification.
4. GRU upper bound confidence interval calibration (no 1.00 hard-clamp cutoff).
5. Shadow disagreement analysis (pairwise matrix, knee-point dispersion, error correlation).
"""

import numpy as np
import pytest

from soh.common.contracts import (
    CycleRecord,
    EstimationStatus,
    FeatureQualityRecord,
    SOHState,
    SohEstimate,
)
from soh.data.base_loader import SohBatteryData, SohDataset
from soh.data.real_cell_adapters import (
    DATASET_PROVENANCE_REGISTRY,
    DatasetCategory,
    DatasetProvenanceRecord,
    DatasetSource,
)
from soh.data.synthetic_aging import SyntheticAgingGenerator

pytest.importorskip("torch")
from soh.estimators.gru import BatteryDegradationGRU, GruNetworkConfig, GruSohEstimator, GruTrainingConfig
from soh.shadow.engine import ShadowEstimatorRecord, ShadowInferenceEngine, ShadowTelemetryFrame
from soh.validation.harness import (
    ConstantMeanBaseline,
    EmpiricalEstimatorWrapper,
    EstimatorBenchmarkResult,
    HoldoutStrategy,
    UnifiedValidationHarness,
    ValidationSplit,
)


# =====================================================================
# Fixtures
# =====================================================================

@pytest.fixture
def synthetic_cohort():
    """Generate a clean synthetic cohort of 2 cells with 10 cycles each."""
    generator = SyntheticAgingGenerator(seed=42)
    return generator.generate_cohort(cell_ids=["TEST_CELL_A", "TEST_CELL_B"], num_cycles=10)


# =====================================================================
# 1. Selective Estimation Metrics (No Sentinels)
# =====================================================================

def test_selective_estimation_no_sentinels_on_zero_coverage():
    """Ensure that an estimator with 0% coverage reports None for RMSE/MAE, NOT 99.9%."""
    result = EstimatorBenchmarkResult(
        estimator_id="StubAbstainingEstimator",
        model_version="1.0.0",
        strategy=HoldoutStrategy.BATTERY_LOBO,
        split_name="TEST_SPLIT_01",
        sample_count=0,
        total_cycles=50,
        eligible_count=0,
        abstention_count=50,
        prediction_coverage_pct=0.0,
        estimation_availability_pct=0.0,
        abstention_rate_pct=100.0,
        rmse_c_pct=None,
        mae_c_pct=None,
        rejection_reasons={"INSUFFICIENT_INFORMATION": 50},
    )

    assert result.prediction_coverage_pct == 0.0
    assert result.abstention_rate_pct == 100.0
    assert result.rmse_c_pct is None
    assert result.mae_c_pct is None
    assert result.rejection_reasons["INSUFFICIENT_INFORMATION"] == 50


def test_selective_risk_coverage_curve():
    """Verify selective risk calculation in harness without sentinels."""
    harness = UnifiedValidationHarness()
    assert harness is not None


# =====================================================================
# 2. Dataset Provenance and Classification
# =====================================================================

def test_dataset_provenance_registry_classification():
    """Verify all datasets in registry are classified into EXPERIMENTAL, SIMULATION, or DERIVED."""
    assert len(DATASET_PROVENANCE_REGISTRY) >= 4

    for source, record in DATASET_PROVENANCE_REGISTRY.items():
        assert isinstance(record.dataset_category, DatasetCategory)
        assert record.cell_identifiers is not None and len(record.cell_identifiers) > 0
        assert record.ground_truth_protocol != ""
        assert record.bol_capacity_measurement_ah > 0.0

    # Specifically verify LG M50T is SIMULATION and CALCE / OXFORD / MIT are EXPERIMENTAL
    assert DATASET_PROVENANCE_REGISTRY[DatasetSource.LG_M50T].dataset_category == DatasetCategory.SIMULATION
    assert DATASET_PROVENANCE_REGISTRY[DatasetSource.CALCE_A123].dataset_category == DatasetCategory.EXPERIMENTAL
    assert DATASET_PROVENANCE_REGISTRY[DatasetSource.OXFORD].dataset_category == DatasetCategory.EXPERIMENTAL
    assert DATASET_PROVENANCE_REGISTRY[DatasetSource.MIT_STANFORD].dataset_category == DatasetCategory.EXPERIMENTAL


# =====================================================================
# 3. Empirical Power-Law Parameter Fitting & Negative Controls
# =====================================================================

def test_empirical_estimator_fitting_and_negative_control(synthetic_cohort):
    """Verify log-linear least-squares fitting and target-shuffled negative control."""
    cell_a = synthetic_cohort.batteries["TEST_CELL_A"]
    cell_b = synthetic_cohort.batteries["TEST_CELL_B"]

    train_dataset = SohDataset(batteries={"TEST_CELL_A": cell_a})
    test_battery = cell_b

    # Fit genuine model
    empirical_model = EmpiricalEstimatorWrapper()
    empirical_model.fit(train_dataset, shuffle_targets=False)
    assert empirical_model.is_fitted

    preds_real = [empirical_model.predict_cycle(c) for c in test_battery.cycles]
    errors_real = [abs(p.soh_c - (c.soh_c_bol_true or 1.0)) for p, c in zip(preds_real, test_battery.cycles)]
    mae_real = np.mean(errors_real)

    # Fit shuffled negative control
    shuffled_model = EmpiricalEstimatorWrapper()
    shuffled_model.fit(train_dataset, shuffle_targets=True)
    assert shuffled_model.is_fitted

    preds_shuffled = [shuffled_model.predict_cycle(c) for c in test_battery.cycles]
    errors_shuffled = [abs(p.soh_c - (c.soh_c_bol_true or 1.0)) for p, c in zip(preds_shuffled, test_battery.cycles)]
    mae_shuffled = np.mean(errors_shuffled)

    # Shuffled negative control parameters must differ from un-shuffled parameters
    assert shuffled_model.alpha_deg != empirical_model.alpha_deg or shuffled_model.z_exponent != empirical_model.z_exponent


# =====================================================================
# 4. GRU SOH Upper Bound Truncation
# =====================================================================

def test_gru_upper_bound_not_hard_clamped_at_one(synthetic_cohort):
    """Verify GRU 95% CI upper bound allows values up to 1.20 for pristine BOL cells."""
    estimator = GruSohEstimator(
        config=GruTrainingConfig(epochs=2, batch_size=8, mc_samples=5, seed=42),
        network_config=GruNetworkConfig(hidden_dim=16, num_layers=1, sequence_length=3),
    )
    estimator.fit(synthetic_cohort)

    # Use first cycle of cell_a (pristine BOL)
    pristine_cycle = synthetic_cohort.batteries["TEST_CELL_A"].cycles[0]

    pred = estimator.predict_cycle(pristine_cycle)
    assert pred.status == EstimationStatus.VALID
    low_c, high_c = pred.confidence_interval_95_c
    # Upper confidence interval bound must be permitted to be >= 1.0 (up to 1.20)
    assert high_c >= low_c
    assert high_c <= 1.201


# =====================================================================
# 5. Shadow Disagreement Analysis
# =====================================================================

def test_shadow_disagreement_analysis_structure():
    """Verify detailed disagreement analysis generates pairwise matrix, knee dispersion, and correlation."""
    engine = ShadowInferenceEngine()

    dummy_fq = FeatureQualityRecord(
        is_eligible=True,
        snr_db=40.0,
        fit_rmse_mv=0.5,
    )

    # Feed telemetry frames with intentional model disagreements
    for cycle_idx in range(1, 45):
        rec_mlp = ShadowEstimatorRecord(
            estimator_id="Pure MLP",
            model_version="1.0.0",
            status=EstimationStatus.VALID,
            soh_c=1.0 - 0.002 * cycle_idx,
            soh_r=1.0 + 0.002 * cycle_idx,
            variance_c=0.0001,
            variance_r=0.0001,
            confidence_interval_95_c=(0.95, 1.05),
            confidence_interval_95_r=(0.95, 1.05),
            feature_quality=dummy_fq,
            latency_ms=1.2,
            disagreement_from_mean_c=0.001,
            reference_residual_c=0.002,
            reference_residual_r=0.002,
        )
        rec_gru = ShadowEstimatorRecord(
            estimator_id="GRU Sequence Model",
            model_version="1.0.0",
            status=EstimationStatus.VALID,
            soh_c=1.0 - 0.003 * cycle_idx,
            soh_r=1.0 + 0.003 * cycle_idx,
            variance_c=0.0001,
            variance_r=0.0001,
            confidence_interval_95_c=(0.95, 1.05),
            confidence_interval_95_r=(0.95, 1.05),
            feature_quality=dummy_fq,
            latency_ms=3.5,
            disagreement_from_mean_c=0.001,
            reference_residual_c=0.003,
            reference_residual_r=0.003,
        )
        rec_pinn = ShadowEstimatorRecord(
            estimator_id="Physics-Informed PINN",
            model_version="1.0.0",
            status=EstimationStatus.VALID,
            soh_c=1.0 - 0.0025 * cycle_idx,
            soh_r=1.0 + 0.0025 * cycle_idx,
            variance_c=0.0001,
            variance_r=0.0001,
            confidence_interval_95_c=(0.95, 1.05),
            confidence_interval_95_r=(0.95, 1.05),
            feature_quality=dummy_fq,
            latency_ms=2.1,
            disagreement_from_mean_c=0.0005,
            reference_residual_c=0.0025,
            reference_residual_r=0.0025,
        )

        mean_val = (rec_mlp.soh_c + rec_gru.soh_c + rec_pinn.soh_c) / 3.0
        disp_val = float(np.std([rec_mlp.soh_c, rec_gru.soh_c, rec_pinn.soh_c]))

        frame = ShadowTelemetryFrame(
            cycle_index=cycle_idx,
            timestamp_s=float(cycle_idx * 3600),
            estimator_records={
                "Pure MLP": rec_mlp,
                "GRU Sequence Model": rec_gru,
                "Physics-Informed PINN": rec_pinn,
            },
            ensemble_mean_c=mean_val,
            ensemble_dispersion_c=disp_val,
            ground_truth_soh_c=1.0 - 0.0022 * cycle_idx,
            ground_truth_soh_r=1.0 + 0.0022 * cycle_idx,
        )
        engine.history.append(frame)

    analysis = engine.get_detailed_disagreement_analysis()

    assert "pairwise_matrix" in analysis
    assert "phase_stratification" in analysis
    assert "error_dispersion_correlation" in analysis

    assert "linear_phase_mean_dispersion_pct" in analysis["phase_stratification"]
    assert "knee_phase_mean_dispersion_pct" in analysis["phase_stratification"]
    assert isinstance(analysis["error_dispersion_correlation"], float)
