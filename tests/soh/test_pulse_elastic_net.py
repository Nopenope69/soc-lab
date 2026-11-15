"""Unit tests for the PulseElasticNetEstimator."""

from pathlib import Path
import numpy as np
import pytest

from soh.common.contracts import EstimationStatus
from soh.data.synthetic_aging import SyntheticAgingGenerator
from soh.estimators.pulse_elastic_net import PulseElasticNetEstimator
from soh.features.pulse_ecm import PulseRecord


def test_pulse_elastic_net_fit_and_predict(tmp_path: Path):
    """Verify PulseElasticNetEstimator fits on synthetic cohort and predicts with uncertainty."""
    generator = SyntheticAgingGenerator(seed=303)
    cohort = generator.generate_cohort(cell_ids=["B1", "B2"], num_cycles=20)

    estimator = PulseElasticNetEstimator(alpha_c=0.05, l1_ratio_c=0.5)
    assert not estimator.is_fitted

    estimator.fit(cohort)
    assert estimator.is_fitted

    # Test prediction with a synthesized pulse
    t_pulse = np.linspace(0, 10, 100)
    v_pulse = 3.30 - 2.0 * 0.020 - 2.0 * 0.010 * (1.0 - np.exp(-t_pulse / 4.0))
    t_relax = np.linspace(0, 20, 100)
    v_relax = 3.30 - 2.0 * 0.010 * (1.0 - np.exp(-10.0 / 4.0)) * np.exp(-t_relax / 4.0)

    pulse = PulseRecord(
        pulse_id="p_test",
        cycle_index=5,
        t_pulse_s=t_pulse,
        v_pulse_v=v_pulse,
        i_pulse_a=np.full_like(t_pulse, 2.0),
        t_relax_s=t_relax,
        v_relax_v=v_relax,
        i_relax_a=np.zeros_like(t_relax),
        temp_c=25.0,
        i_amplitude_a=2.0,
        pulse_duration_s=10.0,
        relax_duration_s=20.0,
    )

    est = estimator.predict_pulse(pulse)
    assert est.status == EstimationStatus.VALID
    assert est.soh_c is not None and 0.5 < est.soh_c < 1.2
    assert est.soh_r is not None and 0.5 < est.soh_r < 1.5
    assert est.confidence_interval_95_c is not None
    lb, ub = est.confidence_interval_95_c
    assert lb < est.soh_c < ub

    # Verify C header export
    header_file = tmp_path / "soh_pulse_elasticnet.h"
    estimator.export_c_header(header_file)
    assert header_file.exists()
    content = header_file.read_text(encoding="utf-8")
    assert "SOH_C_COEFS" in content
    assert "soh_predict_pulse" in content
