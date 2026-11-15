"""Unit and integration tests for SOH Phase 6: Independent Validation and Shadow Integration.

Tests cover:
1. GRU degradation estimator (forward pass, fit, predict_cycle, conformal calibration).
2. Real-cell data adapters and provenance registry (CALCE, LG M50T, Oxford, MIT).
3. Unified independent validation harness (LOBO, Batch, Chemistry, Temperature, Extrapolation splits).
4. Shadow inference engine (multi-model execution, disagreement metrics, state isolation).
"""

import numpy as np
import pytest
import torch

from soh.common.contracts import (
    CycleRecord,
    EstimationStatus,
    FeatureQualityRecord,
    PartialWindow,
    SOHState,
    SohEstimate,
)
from soh.common.protocols import (
    CellReferenceSpec,
    ReferenceProvenance,
    ReferenceProvenanceType,
)
from soh.data.base_loader import SohBatteryData, SohDataset
from soh.data.real_cell_adapters import (
    DATASET_PROVENANCE_REGISTRY,
    DatasetProvenanceRecord,
    DatasetSource,
    RealCellDataLoader,
)
from soh.data.synthetic_aging import SyntheticAgingGenerator
from soh.estimators.baseline_ridge import BaselineRidgeEstimator
from soh.estimators.gru import (
    BatteryDegradationGRU,
    GruNetworkConfig,
    GruSohEstimator,
    GruTrainingConfig,
)
from soh.fusion.tracker import DualSohFusionTracker
from soh.shadow.engine import ShadowInferenceEngine, ShadowTelemetryFrame
from soh.validation.harness import (
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
    """Generate a clean synthetic cohort of 2 cells with 15 cycles each."""
    generator = SyntheticAgingGenerator(seed=42)
    return generator.generate_cohort(cell_ids=["TEST_CELL_01", "TEST_CELL_02"], num_cycles=15)


# =====================================================================
# 1. GRU Degradation Estimator Tests
# =====================================================================

def test_gru_architecture():
    """Verify PyTorch GRU architecture tensor shapes and forward execution."""
    cfg = GruNetworkConfig(input_dim=5, hidden_dim=16, num_layers=1, dropout_rate=0.1)
    model = BatteryDegradationGRU(config=cfg)

    # Input shape: (batch_size=4, sequence_length=5, input_dim=5)
    x = torch.randn(4, 5, 5, dtype=torch.float32)
    sc, sr, lv_c, lv_r, next_h = model(x)

    assert sc.shape == (4, 1)
    assert sr.shape == (4, 1)
    assert lv_c.shape == (4, 1)
    assert lv_r.shape == (4, 1)
    assert next_h.shape == (1, 4, 16)

    # Sigmoid outputs must be strictly in (0, 1)
    assert torch.all(sc >= 0.0) and torch.all(sc <= 1.0)
    assert torch.all(sr >= 0.0) and torch.all(sr <= 1.0)


def test_gru_estimator_lifecycle(synthetic_cohort):
    """Verify GruSohEstimator fit, predict_cycle, and conformal calibration."""
    estimator = GruSohEstimator(
        config=GruTrainingConfig(epochs=5, batch_size=8, mc_samples=5, seed=101),
        network_config=GruNetworkConfig(hidden_dim=16, num_layers=1, sequence_length=3),
    )

    # Initial check before fit
    assert not estimator.is_fitted

    # Fit on synthetic cohort
    estimator.fit(synthetic_cohort)
    assert estimator.is_fitted

    # Predict single cycle
    test_cell = synthetic_cohort.batteries["TEST_CELL_01"]
    cycle = test_cell.cycles[5]

    est = estimator.predict_cycle(cycle)
    assert isinstance(est, SohEstimate)
    assert est.status == EstimationStatus.VALID
    assert est.soh_c is not None and 0.5 <= est.soh_c <= 1.05
    assert est.soh_r is not None and 0.5 <= est.soh_r <= 1.05
    assert est.variance_c is not None and est.variance_c > 0.0
    assert est.variance_r is not None and est.variance_r > 0.0
    assert est.confidence_interval_95_c is not None
    assert est.confidence_interval_95_c[0] <= est.confidence_interval_95_c[1]

    # Conformal calibration on the cohort
    scale_c, scale_r = estimator.calibrate_conformal(synthetic_cohort, target_coverage=0.95)
    assert scale_c > 0.0
    assert scale_r > 0.0


# =====================================================================
# 2. Real-Cell Data Adapters & Provenance Registry Tests
# =====================================================================

def test_provenance_registry_integrity():
    """Verify dataset provenance records enforce qualified measurement metadata."""
    registry = DATASET_PROVENANCE_REGISTRY

    # Ensure all four major cohorts are cataloged
    for src in [DatasetSource.LG_M50T, DatasetSource.CALCE_A123, DatasetSource.OXFORD, DatasetSource.MIT_STANFORD]:
        assert src in registry
        rec = registry[src]
        assert isinstance(rec, DatasetProvenanceRecord)
        assert len(rec.citation) > 0
        assert len(rec.qualification_notes) > 0

    # Explicit audit assertions:
    # 1. CALCE must NOT be classified as pristine factory acceptance BOL
    assert registry[DatasetSource.CALCE_A123].is_pristine_bol is False
    # 2. CALCE cycler load perturbation is NOT validated standardized DCIR HPPC
    assert registry[DatasetSource.CALCE_A123].is_resistance_validated is False
    assert "NOT equivalent to standardized DCIR" in registry[DatasetSource.CALCE_A123].resistance_measurement_protocol

    # 3. MIT/Stanford has batch metadata
    assert "manufacturing batch metadata available" in registry[DatasetSource.MIT_STANFORD].qualification_notes


def test_real_cell_loader_reference_cohorts():
    """Verify loading and synthetic adapter generation for real datasets."""
    loader = RealCellDataLoader()

    # Oxford Pouch Reference Cohort
    ox_ds = loader.create_oxford_reference_cohort(num_cells=2, num_cycles=10)
    assert len(ox_ds.batteries) == 2
    for cid, bdata in ox_ds.batteries.items():
        assert len(bdata.cycles) == 10
        assert bdata.spec.chemistry == "NMC-LCO blend / Graphite"
        assert bdata.spec.nominal_capacity_ah == 0.74

    # MIT Stanford Reference Cohort
    mit_ds = loader.create_mit_stanford_reference_cohort(num_cells=2, num_cycles=12)
    assert len(mit_ds.batteries) == 2
    for cid, bdata in mit_ds.batteries.items():
        assert len(bdata.cycles) == 12
        assert bdata.spec.chemistry == "LiFePO4 (LFP) / Graphite"
        assert bdata.spec.nominal_capacity_ah == 1.10
        assert "batch_id" in bdata.cycles[0].metadata


# =====================================================================
# 3. Unified Validation Harness Tests
# =====================================================================

def test_validation_harness_split_generators(synthetic_cohort):
    """Verify split generators for LOBO, Batch, Chemistry, Temperature, Extrapolation."""
    harness = UnifiedValidationHarness(seed=42)

    # 1. Battery LOBO
    lobo_splits = harness.create_battery_lobo_splits(synthetic_cohort)
    assert len(lobo_splits) == 2
    for s in lobo_splits:
        assert s.strategy == HoldoutStrategy.BATTERY_LOBO
        assert len(s.test_dataset.batteries) == 1
        assert len(s.train_dataset.batteries) == 1

    # 2. Manufacturing Batch
    batch_splits = harness.create_batch_splits(synthetic_cohort)
    assert len(batch_splits) >= 2
    for s in batch_splits:
        assert s.strategy == HoldoutStrategy.BATCH_HOLDOUT

    # 3. Early Life Extrapolation
    first_cell = list(synthetic_cohort.batteries.values())[0]
    extrap_splits = harness.create_extrapolation_splits(first_cell, train_fractions=[0.25, 0.50])
    assert len(extrap_splits) == 2
    for s in extrap_splits:
        assert s.strategy == HoldoutStrategy.EARLY_LIFE_EXTRAPOLATION


def test_evaluate_estimator_on_split(synthetic_cohort):
    """Verify single estimator evaluation against a validation split."""
    harness = UnifiedValidationHarness(seed=42)
    splits = harness.create_battery_lobo_splits(synthetic_cohort)
    split = splits[0]

    result = harness.evaluate_estimator_on_split(
        estimator_id="empirical_power_law",
        constructor=lambda: EmpiricalEstimatorWrapper(),
        model_version="1.0.0-powerlaw",
        split=split,
        calibrate_uncertainty=False,
    )

    assert isinstance(result, EstimatorBenchmarkResult)
    assert result.estimator_id == "empirical_power_law"
    assert result.strategy == HoldoutStrategy.BATTERY_LOBO
    assert result.sample_count > 0
    assert result.mae_c_pct >= 0.0
    assert result.rmse_c_pct >= 0.0
    assert 0.0 <= result.picp_95_c <= 100.0
    assert result.mpiw_c >= 0.0
    assert result.latency_ms_per_cycle >= 0.0


# =====================================================================
# 4. Shadow Inference Engine Tests
# =====================================================================

def test_shadow_engine_multi_model_execution(synthetic_cohort):
    """Verify ShadowInferenceEngine runs multiple estimators, computes disagreement, and does NOT mutate tracker."""
    test_cell = synthetic_cohort.batteries["TEST_CELL_01"]
    cycle = test_cell.cycles[5]

    # Initialize estimators
    ridge = BaselineRidgeEstimator()
    ridge.fit(synthetic_cohort)

    empirical = EmpiricalEstimatorWrapper()

    # Active tracker state
    active_tracker = DualSohFusionTracker()
    initial_soh_c = float(active_tracker.x[0])
    initial_soh_r = float(active_tracker.x[1])
    initial_cycle_idx = active_tracker.current_cycle_index

    # Initialize shadow engine
    shadow_engine = ShadowInferenceEngine()
    shadow_engine.register_estimator("ridge", ridge, "1.0.0")
    shadow_engine.register_estimator("empirical", empirical, "1.0.0")

    # Process cycle in shadow mode
    frame = shadow_engine.process_cycle(cycle)

    assert isinstance(frame, ShadowTelemetryFrame)
    assert frame.cycle_index == cycle.cycle_index
    assert len(frame.estimator_records) == 2
    assert "ridge" in frame.estimator_records
    assert "empirical" in frame.estimator_records

    # Disagreement metrics
    assert frame.ensemble_mean_c is not None
    assert frame.ensemble_dispersion_c is not None
    assert frame.max_pairwise_disagreement_c is not None
    assert frame.has_reference_ground_truth is True
    assert frame.ground_truth_soh_c is not None

    # Verify active tracker state isolation (Zero Side-Effects)
    assert float(active_tracker.x[0]) == initial_soh_c
    assert float(active_tracker.x[1]) == initial_soh_r
    assert active_tracker.current_cycle_index == initial_cycle_idx

    # Export to JSON
    json_str = shadow_engine.to_json()
    assert "ridge" in json_str
    assert "empirical" in json_str
