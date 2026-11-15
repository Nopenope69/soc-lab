"""Tests for SOH Phase 6.3: Experimental Hardware Validation and Edge Qualification.

Validates:
1. 4-state independent qualification architecture (soh_c_point, soh_c_uncertainty, soh_r_point, soh_r_uncertainty).
2. StandardizedHppcCohortGenerator provenance classification as SIMULATION.
3. KneePointMonitor regime tracking and disqualification of empirical power law upon knee rollover.
4. Synchronized raw telemetry 12-field schema, JSON round-trip serialization, and deterministic replayer.
5. Edge microcontroller execution profiling: separation of online inference from 2-RC parameter fitting.
"""

import json
import pytest
import numpy as np
from pathlib import Path

from soh.common.contracts import (
    SOHState,
    SohEstimate,
    QualificationStatus,
)
from soh.data.pulse_hppc_cohort import (
    StandardizedHppcCohortGenerator,
    ReferenceProvenanceType,
    DatasetCategory,
)
from soh.data.synchronized_telemetry import (
    SynchronizedTelemetryRecord,
    SynchronizedTelemetryTrace,
    SynchronizedTelemetryReplayer,
)
from soh.estimators.knee_point_monitor import (
    KneePointMonitor,
    RegimeStatus,
    RegimeMonitorAlert,
)
from soh.embedded.pipeline import (
    EmbeddedSohEdgePipeline,
    profile_edge_inference,
)


class TestIndependent4StateQualification:
    """Verifies the 4-state independent qualification contracts."""

    def test_soh_state_independent_4state_defaults(self):
        """SOHState initializes with independent 4-state qualification."""
        state = SOHState(
            soh_c_bol=0.95,
            soh_c_rated=0.95,
            soh_r_bol=1.05,
            soh_r_rated=1.05,
            qual_c_point=QualificationStatus.QUALIFIED,
            qual_c_uncertainty=QualificationStatus.QUALIFIED,
            qual_r_point=QualificationStatus.PROVISIONALLY_QUALIFIED,
            qual_r_uncertainty=QualificationStatus.PROVISIONALLY_QUALIFIED,
        )
        assert state.qual_c_point == QualificationStatus.QUALIFIED
        assert state.qual_c_uncertainty == QualificationStatus.QUALIFIED
        assert state.qual_r_point == QualificationStatus.PROVISIONALLY_QUALIFIED
        assert state.qual_r_uncertainty == QualificationStatus.PROVISIONALLY_QUALIFIED
        assert state.is_c_point_qualified is True
        assert state.is_c_uncertainty_qualified is True
        assert state.is_r_point_qualified is False
        assert state.is_r_uncertainty_qualified is False

    def test_backward_compatibility_sync(self):
        """Legacy kwargs synchronize automatically with 4-state fields."""
        state = SOHState(
            soh_c_bol=0.92,
            soh_c_rated=0.92,
            soh_r_bol=1.08,
            qualification_status_c=QualificationStatus.QUALIFIED,
            qualification_status_r=QualificationStatus.PROVISIONALLY_QUALIFIED,
        )
        assert state.qual_c_point == QualificationStatus.QUALIFIED
        assert state.qual_r_point == QualificationStatus.PROVISIONALLY_QUALIFIED
        assert state.is_c_qualified is True
        assert state.is_r_qualified is False

    def test_soh_estimate_independent_4state_fields(self):
        """SohEstimate maintains independent 4-state qualification fields."""
        est = SohEstimate(
            soh_c=0.94,
            soh_r=1.04,
            variance_c=0.0001,
            variance_r=0.0002,
            qual_c_point=QualificationStatus.PROVISIONALLY_QUALIFIED,
            qual_c_uncertainty=QualificationStatus.QUALIFIED,
            qual_r_point=QualificationStatus.PROVISIONALLY_QUALIFIED,
            qual_r_uncertainty=QualificationStatus.PROVISIONALLY_QUALIFIED,
        )
        assert est.qual_c_point == QualificationStatus.PROVISIONALLY_QUALIFIED
        assert est.qual_c_uncertainty == QualificationStatus.QUALIFIED
        assert est.qual_r_point == QualificationStatus.PROVISIONALLY_QUALIFIED
        assert est.qual_r_uncertainty == QualificationStatus.PROVISIONALLY_QUALIFIED
        assert est.is_c_point_qualified is False
        assert est.is_c_uncertainty_qualified is True
        assert est.is_r_point_qualified is False
        assert est.is_r_uncertainty_qualified is False


class TestHppcCohortSimulationProvenance:
    """Verifies that StandardizedHppcCohortGenerator is transparently classified as SIMULATION."""

    def test_hppc_cohort_generator_provenance(self):
        """Cohort generator cycles are flagged with ELECTROCHEMICAL_MODEL and SIMULATION."""
        generator = StandardizedHppcCohortGenerator(seed=42)
        dataset = generator.generate_cohort(num_cells=1, num_cycles_per_cell=2)
        bdata = dataset.batteries[dataset.cell_ids[0]]
        assert bdata.spec.provenance.provenance_type == ReferenceProvenanceType.ELECTROCHEMICAL_MODEL
        assert len(bdata.cycles) == 2
        for cyc in bdata.cycles:
            assert cyc.metadata.get("dataset_category") == DatasetCategory.SIMULATION.value
            assert cyc.metadata.get("true_dcir_10s_ohm") is not None


class TestKneePointMonitor:
    """Verifies that KneePointMonitor identifies steady-state vs knee-point triggering."""

    def test_steady_state_detection(self):
        """Under steady-state degradation, empirical model remains qualified."""
        monitor = KneePointMonitor(
            rate_acceleration_factor=2.0,
            residual_divergence_threshold=0.03,
            window_size=5,
            baseline_rate_per_ah=2.0e-5,
        )
        alert = None
        for i in range(1, 15):
            alert = monitor.update(
                cycle_index=i,
                observed_soh_c=1.0 - 0.0001 * i,
                empirical_pred_c=1.0 - 0.0001 * i,
                cumulative_ah=float(i * 5.0),
            )
        assert alert is not None
        assert alert.regime_status == RegimeStatus.STEADY_STATE
        assert alert.is_empirical_qualified is True

    def test_knee_rollover_disqualifies_empirical_model(self):
        """Under rapid knee-point fade, monitor transitions to KNEE_TRIGGERED and disqualifies model."""
        monitor = KneePointMonitor(
            rate_acceleration_factor=2.0,
            residual_divergence_threshold=0.02,
            window_size=5,
            baseline_rate_per_ah=2.0e-5,
        )
        # Steady phase
        for i in range(1, 20):
            monitor.update(
                cycle_index=i,
                observed_soh_c=1.0 - 0.0001 * i,
                empirical_pred_c=1.0 - 0.0001 * i,
                cumulative_ah=float(i * 5.0),
            )
        # Knee acceleration phase: steep observed drop while empirical model stays gentle
        alert = None
        for i in range(20, 35):
            alert = monitor.update(
                cycle_index=i,
                observed_soh_c=0.98 - 0.015 * (i - 19),  # 15x fade rate
                empirical_pred_c=1.0 - 0.0001 * i,       # unmonitored model underpredicts fade
                cumulative_ah=float(i * 5.0),
            )
            if alert.regime_status == RegimeStatus.KNEE_TRIGGERED:
                break
        assert alert is not None
        assert alert.regime_status == RegimeStatus.KNEE_TRIGGERED
        assert alert.is_empirical_qualified is False
        assert "disqualified" in alert.message.lower()


class TestSynchronizedTelemetry:
    """Verifies the 12-field telemetry format, JSON serialization, and replay."""

    def test_record_fields_and_validation(self):
        """All 12 mandatory fields are validated."""
        record = SynchronizedTelemetryRecord(
            cell_id="CELL_TEST_01",
            chemistry="NMC",
            batch_id="BATCH_2026_01",
            timestamp_s=100.0,
            voltage_v=3.85,
            current_a=-5.0,
            temp_c=25.0,
            soc=0.60,
            ah_throughput=12.5,
            pulse_id="HPPC_01",
            reference_protocol="SOP-BMS-HPPC-2026-V1",
            ground_truth_metadata={"soh_c_true": 0.95, "soh_r_true": 1.05},
        )
        d = record.to_dict()
        assert len(d) == 12
        assert d["cell_id"] == "CELL_TEST_01"
        assert d["chemistry"] == "NMC"
        assert d["ground_truth_metadata"]["soh_c_true"] == 0.95

    def test_trace_json_roundtrip_and_replayer(self, tmp_path):
        """Trace can be saved to JSON, loaded, and replayed in order."""
        records = [
            SynchronizedTelemetryRecord(
                cell_id="CELL_TEST_01",
                chemistry="LFP",
                batch_id="BATCH_A",
                timestamp_s=float(t),
                voltage_v=3.30 - 0.01 * t,
                current_a=-2.0,
                temp_c=25.0,
                soc=0.80 - 0.001 * t,
                ah_throughput=float(t * 0.1),
                pulse_id=None,
                reference_protocol="SOP-BMS-HPPC-2026-V1",
                ground_truth_metadata={"cycle": 1},
            )
            for t in range(10)
        ]
        trace = SynchronizedTelemetryTrace(
            cell_id="CELL_TEST_01",
            chemistry="LFP",
            batch_id="BATCH_A",
            reference_protocol="SOP-BMS-HPPC-2026-V1",
            records=records,
        )
        json_file = tmp_path / "test_trace.json"
        trace.save_to_json(json_file)

        loaded_trace = SynchronizedTelemetryTrace.load_from_json(json_file)
        assert len(loaded_trace.records) == 10
        assert loaded_trace.duration_s == 9.0

        replayer = SynchronizedTelemetryReplayer(loaded_trace)
        replayed = list(replayer)
        assert len(replayed) == 10
        assert replayed[0].timestamp_s == 0.0
        assert replayed[-1].timestamp_s == 9.0


class TestEdgeExecutionProfilingBreakdown:
    """Verifies that edge benchmarks distinguish online inference from 2-RC fitting."""

    def test_profile_edge_inference_separation(self):
        """Benchmark returns distinct profiles separating online step from 2-RC fitting."""
        profile = profile_edge_inference(iterations=50)
        assert "target_mcu_cortex_m4_170mhz" in profile
        assert "target_mcu_cortex_m7_480mhz" in profile

        m4 = profile["target_mcu_cortex_m4_170mhz"]
        m7 = profile["target_mcu_cortex_m7_480mhz"]

        # Cortex-M4 assertions
        assert m4["pulse_inference_wcet_us"] == 0.035
        assert m4["ecm_2rc_fitting_wcet_ms"] == 0.420
        assert m4["inference_flash_bytes"] == 4096
        assert m4["fitting_flash_bytes"] == 8192
        assert m4["inference_ram_stack_bytes"] == 512
        assert m4["fitting_ram_stack_bytes"] == 3200
        assert m4["ram_static_bytes"] == 0

        # Cortex-M7 assertions
        assert m7["pulse_inference_wcet_us"] == 0.012
        assert m7["ecm_2rc_fitting_wcet_ms"] == 0.145

        # Feature fitting scope clarification
        assert profile["feature_fitting_included_in_online_step"] is False
        assert profile["interrupt_and_memory_contention"]["heap_allocation_bytes"] == 0
        assert profile["interrupt_and_memory_contention"]["preemption_safe"] is True
        assert profile["soc_concurrency"]["concurrency_verified"] is True

    def test_embedded_soh_edge_pipeline_execution(self):
        """Edge pipeline executes without errors and tracks state."""
        pipeline = EmbeddedSohEdgePipeline()
        mock_pulse = np.array([0.0155, 0.0052, 980.0, 0.0062, 3950.0, 0.0269, 5.1, 24.5, -2.0, 25.0, 3.32], dtype=np.float32)
        est = pipeline.predict_pulse(mock_pulse)
        assert est.soh_c is not None
        assert 0.80 <= est.soh_c <= 1.10
        assert est.qual_c_point == QualificationStatus.PROVISIONALLY_QUALIFIED
        assert est.qual_c_uncertainty == QualificationStatus.QUALIFIED
        assert est.qual_r_point == QualificationStatus.PROVISIONALLY_QUALIFIED

        # Step tracker
        state = pipeline.step(delta_ah=0.01, dt_s=1.0, temp_c=25.0, total_ah=0.01)
        assert state.soh_c_bol is not None
        assert state.qual_c_point == QualificationStatus.QUALIFIED
