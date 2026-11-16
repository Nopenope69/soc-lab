"""Unit and integration tests for SOH Phase 6.2: Production Prototype Qualification.

Tests cover:
1. Capacity (SOH_C) and Resistance (SOH_R) independent qualification status separation.
2. Standardized HPPC pulse detection, 2-RC identifiability, and voltage reconstruction.
3. Empirical power-law bidirectional batch holdout and negative control responsiveness.
4. Embedded edge pipeline (empirical, pulse ECM, dual tracker) and 5,000-cycle stability.
5. Concurrent execution of SOH edge tracker with BmsSocEstimatorRef reference SOC estimator.
6. Execution of compiled ANSI C edge verification binary.
"""

import math
from pathlib import Path
import subprocess
import sys
import numpy as np
import pytest

pytest.importorskip("sklearn")

from soh.common.contracts import (
    CycleRecord,
    EstimationStatus,
    FeatureQualityRecord,
    QualificationStatus,
    SOHState,
    SohEstimate,
)
from soh.data.base_loader import SohBatteryData, SohDataset
from soh.data.pulse_hppc_cohort import StandardizedHppcCohortGenerator
from soh.data.real_cell_adapters import RealCellDataLoader
from soh.embedded.pipeline import EmbeddedSohEdgePipeline, profile_edge_inference
from soh.features.pulse_ecm import Ecm2RcFitter, PulseSegmenter
from soh.fusion.tracker import DualSohFusionTracker, FusionConfig
from soh.validation.harness import ConstantMeanBaseline, EmpiricalEstimatorWrapper

# Add deliverable path for reference SOC estimator
DELIVERABLE_DIR = Path(__file__).resolve().parents[2] / "deliverable"
if str(DELIVERABLE_DIR) not in sys.path:
    sys.path.insert(0, str(DELIVERABLE_DIR))

from bms_soc_ref import BmsSocEstimatorRef


# =====================================================================
# 1. Capacity and Resistance Qualification Status Separation Tests
# =====================================================================

def test_qualification_status_enum():
    """Verify independent QualificationStatus enum values."""
    assert QualificationStatus.QUALIFIED == "QUALIFIED"
    assert QualificationStatus.UNVALIDATED == "UNVALIDATED"
    assert QualificationStatus.EXPERIMENTAL == "EXPERIMENTAL"
    assert QualificationStatus.REJECTED == "REJECTED"


def test_independent_soh_c_and_soh_r_tracker_separation():
    """Verify that an estimator with qualified SOH_C but unvalidated SOH_R does not qualify SOH_R."""
    tracker = DualSohFusionTracker()
    tracker.reset(initial_soh_c=1.0, initial_soh_r=1.0)

    assert not tracker.is_c_qualified
    assert not tracker.is_r_qualified

    # Construct cycle and estimate where C is qualified, but R is unvalidated
    cycle = CycleRecord(
        cycle_index=1,
        time_s=np.array([0.0, 10.0]),
        voltage_v=np.array([3.3, 3.3]),
        current_a=np.array([0.0, 0.0]),
        temp_c=np.array([25.0, 25.0]),
        ah_throughput=1.0,
    )

    est_c_only = SohEstimate(
        status=EstimationStatus.VALID,
        soh_c=0.98,
        soh_r=1.0,  # Unvalidated placeholder
        variance_c=1.0e-5,
        variance_r=1.0e-2,
        qualification_status_c=QualificationStatus.QUALIFIED,
        qualification_status_r=QualificationStatus.UNVALIDATED,
    )

    state, log = tracker.update_cycle(cycle=cycle, est_ica=est_c_only)

    # SOH_C must become qualified, while SOH_R MUST REMAIN UNVALIDATED
    assert state.is_c_qualified
    assert state.qualification_status_c == QualificationStatus.QUALIFIED
    assert not state.is_r_qualified
    assert state.qualification_status_r == QualificationStatus.UNVALIDATED


def test_tracker_qualifies_soh_r_only_when_pulse_is_qualified():
    """Verify that SOH_R becomes qualified only when receiving an explicitly qualified measurement."""
    tracker = DualSohFusionTracker()
    tracker.reset(initial_soh_c=1.0, initial_soh_r=1.0, initial_cov=np.diag([4.0e-4, 4.0e-4]))

    cycle = CycleRecord(
        cycle_index=1,
        time_s=np.array([0.0, 10.0]),
        voltage_v=np.array([3.3, 3.3]),
        current_a=np.array([0.0, 0.0]),
        temp_c=np.array([25.0, 25.0]),
        ah_throughput=1.0,
    )

    est_pulse = SohEstimate(
        status=EstimationStatus.VALID,
        soh_c=0.99,
        soh_r=0.98,
        variance_c=1.0e-5,
        variance_r=2.0e-5,
        qualification_status_c=QualificationStatus.QUALIFIED,
        qualification_status_r=QualificationStatus.QUALIFIED,
    )

    state, _ = tracker.update_cycle(cycle=cycle, est_pulse=est_pulse)

    # Both must now be qualified
    assert state.is_c_qualified
    assert state.is_r_qualified
    assert state.qualification_status_r == QualificationStatus.QUALIFIED


# =====================================================================
# 2. Standardized HPPC Pulse Detection and 2-RC Identifiability Tests
# =====================================================================

def test_standardized_hppc_pulse_generation_and_identifiability():
    """Verify HPPC cohort generator, pulse segmentation, and 2-RC parameter identification."""
    hppc_gen = StandardizedHppcCohortGenerator(seed=42)
    cohort = hppc_gen.generate_cohort(num_cells=1, num_cycles_per_cell=3)
    battery = list(cohort.batteries.values())[0]

    segmenter = PulseSegmenter()
    fitter = Ecm2RcFitter()

    detected = 0
    identifiable = 0
    rmses = []

    for cyc in battery.cycles:
        pulses = segmenter.detect_pulses(cyc.time_s, cyc.voltage_v, cyc.current_a, cyc.temp_c, cyc.cycle_index)
        assert len(pulses) >= 1
        p = pulses[0]
        detected += 1
        assert p.pulse_duration_s >= 8.0
        assert p.relax_duration_s >= 35.0

        params, fq = fitter.fit_pulse(p)
        assert params is not None
        assert fq.is_eligible
        identifiable += 1
        rmses.append(params.fit_rmse_mv)

        # Voltage reconstruction residual must be < 2.0 mV
        assert params.fit_rmse_mv < 2.0
        # Jacobian conditioning must be well-conditioned (< 5000)
        assert params.jacobian_condition_number < 5000.0

    assert detected == 3
    assert identifiable == 3
    assert np.mean(rmses) < 1.0


# =====================================================================
# 3. Empirical Power-Law Bidirectional Batch Holdout Tests
# =====================================================================

def test_empirical_bidirectional_batch_holdout_and_negative_control():
    """Verify bidirectional batch holdout, disjoint IDs, and negative control responsiveness."""
    loader = RealCellDataLoader()
    mit_ds = loader.create_mit_stanford_synthetic_cohort(num_cells=4, num_cycles=40)

    b12_cids = [cid for cid, b in mit_ds.batteries.items() if "2017-05-12" in str(b.cycles[0].metadata.get("batch_id"))]
    b30_cids = [cid for cid, b in mit_ds.batteries.items() if "2017-06-30" in str(b.cycles[0].metadata.get("batch_id"))]

    assert len(b12_cids) >= 1 and len(b30_cids) >= 1
    assert set(b12_cids).isdisjoint(set(b30_cids))

    ds_12, ds_30 = mit_ds.split_by_battery(b12_cids, b30_cids)

    # Direction A
    emp_a = EmpiricalEstimatorWrapper()
    emp_a.fit(ds_12)
    errs_a = [abs(c.soh_c_bol_true - emp_a.predict_cycle(c).soh_c) for b in ds_30.batteries.values() for c in b.cycles]
    rmse_a = float(np.sqrt(np.mean(np.array(errs_a) ** 2)) * 100.0)

    # Direction B
    emp_b = EmpiricalEstimatorWrapper()
    emp_b.fit(ds_30)
    errs_b = [abs(c.soh_c_bol_true - emp_b.predict_cycle(c).soh_c) for b in ds_12.batteries.values() for c in b.cycles]
    rmse_b = float(np.sqrt(np.mean(np.array(errs_b) ** 2)) * 100.0)

    # Shuffled Negative Control on Direction A
    emp_shuf = EmpiricalEstimatorWrapper()
    emp_shuf.fit(ds_12, shuffle_targets=True)
    errs_shuf = [abs(c.soh_c_bol_true - emp_shuf.predict_cycle(c).soh_c) for b in ds_30.batteries.values() for c in b.cycles]
    rmse_shuf = float(np.sqrt(np.mean(np.array(errs_shuf) ** 2)) * 100.0)

    # Both batch holdouts must achieve sub-1.5% RMSE on this cohort
    assert rmse_a < 1.5
    assert rmse_b < 1.5
    # Shuffled control must degrade substantially (> 2x higher error)
    assert rmse_shuf > rmse_a * 2.0


# =====================================================================
# 4. Embedded Edge Pipeline & 5,000 Step Numerical Stability
# =====================================================================

def test_embedded_edge_pipeline_and_numerical_stability():
    """Verify edge pipeline lifecycle, independent qualification, and 5000-cycle stability."""
    pipeline = EmbeddedSohEdgePipeline()

    assert pipeline.state.soh_c_bol == 1.0
    assert not pipeline.state.is_c_qualified
    assert not pipeline.state.is_r_qualified

    # Empirical Step
    st = pipeline.step(delta_ah=0.5, dt_s=10.0, temp_c=25.0, total_ah=5.0)
    assert st.is_c_qualified
    assert not st.is_r_qualified

    # Pulse Step
    mock_pulse = np.array([0.015, 0.005, 1000.0, 0.006, 4000.0, 0.026, 5.0, 25.0, -2.0, 25.0, 3.3], dtype=np.float32)
    st_pulse = pipeline.step(delta_ah=0.1, dt_s=10.0, pulse_features=mock_pulse)
    assert st_pulse.is_c_qualified
    assert st_pulse.is_r_qualified

    # 5,000 Step Continuous Numerical Stability Test
    for i in range(5000):
        if i % 25 == 0:
            st = pipeline.step(delta_ah=0.05, dt_s=1.0, pulse_features=mock_pulse)
        else:
            st = pipeline.step(delta_ah=0.05, dt_s=1.0, total_ah=float(i * 0.05))

        assert not math.isnan(st.soh_c_bol)
        assert not math.isnan(st.soh_r_bol)
        assert not math.isnan(st.covariance[0, 0])
        assert not math.isnan(st.covariance[1, 1])
        assert st.covariance[0, 0] >= pipeline.min_eigenval
        assert st.covariance[1, 1] >= pipeline.min_eigenval
        assert 0.20 <= st.soh_c_bol <= 1.20


# =====================================================================
# 5. SOC Estimator Concurrency Benchmark
# =====================================================================

def test_soc_estimator_concurrency_execution():
    """Verify concurrent execution of BmsSocEstimatorRef and EmbeddedSohEdgePipeline."""
    soc_estimator = BmsSocEstimatorRef()
    soc_estimator.reset(soc0=0.85)

    soh_pipeline = EmbeddedSohEdgePipeline()

    for k in range(200):
        v = 3.33 + 0.002 * math.cos(k * 0.05)
        i = -1.5
        dt = 0.1
        temp = 25.0

        # Concurrent step in single loop iteration
        soc_est = soc_estimator.step(v=v, i=i, dt=dt, temp_c=temp)
        soh_st = soh_pipeline.step(delta_ah=abs(i * dt / 3600.0), dt_s=dt, temp_c=temp, total_ah=float(k * 0.01))

        assert 0.0 <= soc_est.soc <= 1.0
        assert 0.20 <= soh_st.soh_c_bol <= 1.20


# =====================================================================
# 6. Standalone Compiled C Edge Verification Executable Test
# =====================================================================

def test_compiled_c_edge_executable():
    """Verify that the compiled ANSI C standalone edge verification executable runs and exits with 0."""
    binary_path = DELIVERABLE_DIR / "edge_pkg" / "test_soh_edge"

    # Re-compile if missing
    if not binary_path.exists():
        c_srcs = [
            str(DELIVERABLE_DIR / "edge_pkg" / "soh_pulse_elasticnet.c"),
            str(DELIVERABLE_DIR / "edge_pkg" / "soh_empirical_powerlaw.c"),
            str(DELIVERABLE_DIR / "edge_pkg" / "soh_dual_state_tracker.c"),
            str(DELIVERABLE_DIR / "edge_pkg" / "soh_edge_pipeline.c"),
            str(DELIVERABLE_DIR / "edge_pkg" / "test_soh_edge.c"),
        ]
        cmd = ["clang", "-Wall", "-Wextra", "-Werror", "-pedantic", "-std=c99"] + c_srcs + ["-o", str(binary_path), "-lm"]
        compile_res = subprocess.run(cmd, capture_output=True, text=True)
        assert compile_res.returncode == 0, f"Compilation failed: {compile_res.stderr}"

    run_res = subprocess.run([str(binary_path)], capture_output=True, text=True)
    assert run_res.returncode == 0, f"C test execution failed: {run_res.stderr}"
    assert "ALL SOH EDGE C TESTS PASSED" in run_res.stdout
