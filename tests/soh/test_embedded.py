"""Unit tests for embedded C export and resource profiling."""

from pathlib import Path
import pytest

pytest.importorskip("sklearn")
from soh.embedded import EmbeddedProfiler, export_estimator_to_c
from soh.estimators.pulse_elastic_net import PulseElasticNetEstimator
from soh.data.synthetic_aging import SyntheticAgingGenerator


def test_embedded_profiler():
    """Verify resource profiler computes expected Flash, RAM, and FLOP counts."""
    profile = EmbeddedProfiler.profile_elastic_net(num_features=11, benchmark_iterations=500)

    # Flash: (4*11 + 2)*4 + 140 = 184 + 140 = 324 bytes
    assert profile.rom_flash_bytes == 324
    # RAM: input buffer (44) + output ptrs (8) + accumulators (8) + frame (16) = 76 bytes
    assert profile.ram_stack_peak_bytes == 76
    # FLOPs: 6 * 11 + 2 = 68 FLOPs
    assert profile.floating_point_ops == 68
    assert profile.mean_latency_us > 0.0


def test_export_estimator_to_c(tmp_path: Path):
    """Verify export_estimator_to_c protocol and file generation."""
    generator = SyntheticAgingGenerator(seed=404)
    cohort = generator.generate_cohort(cell_ids=["B1", "B2"], num_cycles=10)

    estimator = PulseElasticNetEstimator()
    estimator.fit(cohort)

    dest = tmp_path / "ecm_pulse_model.h"
    out = export_estimator_to_c(estimator, dest)
    assert out.exists()
    assert out.stat().st_size > 500  # valid header file size
